"""
IceStream Flink Job Controller
Orchestrates real-time control operations (discovery, pause/cancel, resume/restart)
against the Apache Flink JobManager REST API.
"""
import json
import logging
import os
import subprocess
import time
import urllib.request
import urllib.parse
from typing import Any, Dict, List, Optional

logger = logging.getLogger("icestream.remediation.flink_controller")


def _load_env_if_needed() -> None:
    """Load configuration from .env file if key environment variables are missing."""
    if not os.getenv("MINIO_ROOT_PASSWORD") or not os.getenv("FLINK_REST_URI"):
        candidates = [
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env")),
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env")),
            os.path.abspath(".env"),
        ]
        for path in candidates:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith("#") and "=" in line:
                                k, v = line.split("=", 1)
                                k = k.strip()
                                v = v.strip().strip("'\"")
                                if k not in os.environ:
                                    os.environ[k] = v
                    break
                except Exception:
                    pass


class FlinkController:
    """Controller interfacing with Apache Flink JobManager REST API and container runtime."""

    def __init__(
        self,
        flink_url: Optional[str] = None,
        jobmanager_container: str = "icestream-flink-jobmanager",
        savepoints_dir: Optional[str] = None,
    ) -> None:
        _load_env_if_needed()
        env_url = os.getenv("FLINK_REST_URI") or os.getenv("FLINK_URL")
        if not env_url:
            host = os.getenv("FLINK_JOBMANAGER_HOST", "localhost")
            port = os.getenv("FLINK_PORT", "8081")
            env_url = f"http://{host}:{port}"
        self.flink_url = flink_url or env_url
        self.jobmanager_container = jobmanager_container
        self.savepoints_dir = savepoints_dir or os.getenv(
            "FLINK_SAVEPOINTS_DIR", "s3://checkpoints/flink-savepoints/"
        )
        self._last_savepoint_path: Optional[str] = None

    def _rest_request(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
        timeout: float = 5.0,
    ) -> Optional[Dict[str, Any]]:
        """Perform HTTP request against Flink REST API with JSON serialization and error handling."""
        try:
            clean_path = path if path.startswith("/") else f"/{path}"
            url = f"{self.flink_url.rstrip('/')}{clean_path}"
            data = json.dumps(payload).encode("utf-8") if payload is not None else None
            req = urllib.request.Request(
                url,
                data=data,
                method=method,
                headers={"Accept": "application/json", "Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status in (200, 201, 202):
                    body = resp.read().decode("utf-8")
                    return json.loads(body) if body else {}
        except Exception as e:
            logger.debug("Flink REST %s %s failed: %s", method, path, e)
        return None

    def get_cluster_overview(self) -> Dict[str, Any]:
        """Query Flink JobManager for high-level cluster capacity, slots, and status."""
        overview = self._rest_request("GET", "/overview") or {}
        config = self._rest_request("GET", "/config") or {}
        return {
            "taskmanagers": overview.get("taskmanagers", 0),
            "slots_total": overview.get("slots-total", 0),
            "slots_available": overview.get("slots-available", 0),
            "jobs_running": overview.get("jobs-running", 0),
            "jobs_finished": overview.get("jobs-finished", 0),
            "jobs_cancelled": overview.get("jobs-cancelled", 0),
            "jobs_failed": overview.get("jobs-failed", 0),
            "flink_version": overview.get("flink-version") or config.get("flink-version", "unknown"),
        }

    def get_active_job_id(self) -> Optional[str]:
        """Discover running IceStream Flink job ID from JobManager REST API."""
        try:
            data = self._rest_request("GET", "/jobs/overview")
            if data:
                jobs = data.get("jobs", [])
                active_jobs = [
                    j for j in jobs
                    if j.get("state") in ("RUNNING", "INITIALIZING", "CREATED", "RESTARTING")
                    and ("checkout_events" in j.get("name", "") or "icestream" in j.get("name", "") or "insert-into" in j.get("name", ""))
                ]
                if active_jobs:
                    return str(active_jobs[0]["jid"])
        except Exception as e:
            logger.warning("Failed to query Flink active jobs: %s", e)
        return None

    def get_job_status(self, job_id: str) -> Optional[str]:
        """Query state of a specific Flink job ID."""
        try:
            data = self._rest_request("GET", f"/jobs/{job_id}")
            if data:
                return str(data.get("state"))
        except Exception as e:
            logger.warning("Failed to query state for Flink job '%s': %s", job_id, e)
        return None

    def get_checkpoint_metrics(self, job_id: Optional[str] = None) -> Dict[str, Any]:
        """Query checkpoint statistics and history for a given or active Flink job."""
        target_id = job_id or self.get_active_job_id()
        if not target_id:
            return {
                "available": False,
                "message": "No active Flink job",
                "job_id": None,
                "counts": {"total": 0, "completed": 0, "failed": 0, "in_progress": 0, "restored": 0},
                "latest_checkpoint": None,
                "latest_savepoint": None,
                "summary": {"avg_duration_ms": 0, "avg_state_size_bytes": 0},
            }

        data = self._rest_request("GET", f"/jobs/{target_id}/checkpoints")
        if not data:
            return {
                "available": False,
                "message": f"Unable to fetch checkpoints for job {target_id}",
                "job_id": target_id,
                "counts": {"total": 0, "completed": 0, "failed": 0, "in_progress": 0, "restored": 0},
                "latest_checkpoint": None,
                "latest_savepoint": None,
                "summary": {"avg_duration_ms": 0, "avg_state_size_bytes": 0},
            }

        counts = data.get("counts", {})
        latest = data.get("latest", {})
        summary = data.get("summary", {})

        latest_completed = latest.get("completed")
        latest_chk_info = None
        if latest_completed:
            latest_chk_info = {
                "id": latest_completed.get("id"),
                "status": latest_completed.get("status"),
                "external_path": latest_completed.get("external_path"),
                "state_size_bytes": latest_completed.get("state_size", 0),
                "duration_ms": latest_completed.get("end_to_end_duration", 0),
                "trigger_timestamp": latest_completed.get("trigger_timestamp"),
            }

        latest_savepoint = latest.get("savepoint")
        latest_sp_info = None
        if latest_savepoint:
            latest_sp_info = {
                "id": latest_savepoint.get("id"),
                "status": latest_savepoint.get("status"),
                "external_path": latest_savepoint.get("external_path"),
                "state_size_bytes": latest_savepoint.get("state_size", 0),
                "trigger_timestamp": latest_savepoint.get("trigger_timestamp"),
            }

        latest_failed = latest.get("failed")
        latest_failed_info = None
        if latest_failed:
            latest_failed_info = {
                "id": latest_failed.get("id"),
                "status": latest_failed.get("status"),
                "failure_message": latest_failed.get("failure_message"),
                "failure_timestamp": latest_failed.get("failure_timestamp"),
            }

        avg_dur = summary.get("end_to_end_duration", {}).get("avg", 0)
        avg_sz = summary.get("state_size", {}).get("avg", 0)

        return {
            "available": True,
            "job_id": target_id,
            "counts": {
                "total": counts.get("total", 0),
                "completed": counts.get("completed", 0),
                "failed": counts.get("failed", 0),
                "in_progress": counts.get("in_progress", 0),
                "restored": counts.get("restored", 0),
            },
            "latest_checkpoint": latest_chk_info,
            "latest_savepoint": latest_sp_info,
            "latest_failed": latest_failed_info,
            "summary": {
                "avg_duration_ms": 0 if str(avg_dur) == "NaN" else avg_dur,
                "avg_state_size_bytes": 0 if str(avg_sz) == "NaN" else avg_sz,
            },
        }

    def get_job_exceptions(self, job_id: Optional[str] = None) -> Dict[str, Any]:
        """Query execution exceptions and root cause for a given or active Flink job."""
        target_id = job_id or self.get_active_job_id()
        if not target_id:
            return {"job_id": None, "has_exceptions": False, "root_exception": None}

        data = self._rest_request("GET", f"/jobs/{target_id}/exceptions")
        if not data:
            return {"job_id": target_id, "has_exceptions": False, "root_exception": None}

        root_exc = data.get("root-exception")
        all_exceptions = data.get("all-exceptions", [])
        return {
            "job_id": target_id,
            "has_exceptions": bool(root_exc or all_exceptions),
            "root_exception": root_exc[:500] if root_exc else None,
            "timestamp": data.get("timestamp"),
            "truncated": data.get("truncated", False),
        }

    def trigger_savepoint(self, job_id: Optional[str] = None, cancel: bool = False) -> Dict[str, Any]:
        """Trigger an asynchronous savepoint via Flink REST API and poll until completed."""
        target_id = job_id or self.get_active_job_id()
        if not target_id:
            return {"status": "FAILED", "error": "No active Flink job"}

        endpoint = f"/jobs/{target_id}/stop" if cancel else f"/jobs/{target_id}/savepoints"
        payload = {"drain": False, "targetDirectory": self.savepoints_dir}
        res = self._rest_request("POST", endpoint, payload=payload, timeout=10)
        if not res or "request-id" not in res:
            return {"status": "FAILED", "error": f"Failed to trigger savepoint on {endpoint}"}

        trigger_id = res["request-id"]
        for _ in range(20):
            time.sleep(1.0)
            status_data = self._rest_request("GET", f"/jobs/{target_id}/savepoints/{trigger_id}")
            if status_data:
                status_id = status_data.get("status", {}).get("id")
                if status_id == "COMPLETED":
                    loc = status_data.get("operation", {}).get("location")
                    self._last_savepoint_path = loc
                    return {"status": "SUCCESS", "savepoint_path": loc, "trigger_id": trigger_id}
                elif status_id in ("FAILED", "FAILURE"):
                    cause = status_data.get("operation", {}).get("failure-cause")
                    return {"status": "FAILED", "error": f"Savepoint failed: {cause}", "trigger_id": trigger_id}

        return {"status": "TIMEOUT", "error": "Savepoint trigger timed out", "trigger_id": trigger_id}

    def get_telemetry_summary(self) -> Dict[str, Any]:
        """Aggregate Flink cluster health, active job status, and checkpoint telemetry."""
        active_id = self.get_active_job_id()
        cluster = self.get_cluster_overview()
        job_status = self.get_job_status(active_id) if active_id else None
        checkpoints = self.get_checkpoint_metrics(active_id) if active_id else {}
        exceptions = self.get_job_exceptions(active_id) if active_id else {}

        return {
            "cluster": cluster,
            "active_job": {
                "job_id": active_id,
                "status": job_status,
                "checkpoints": checkpoints,
                "exceptions": exceptions,
            },
        }

    def pause_job(self) -> Dict[str, Any]:
        """Cancel/pause running Flink job with savepoint (idempotent).
        
        Returns:
            Dict describing status: SUCCESS, SKIPPED, or FAILED, including savepoint_path if created.
        """
        job_id = self.get_active_job_id()
        if not job_id:
            logger.info("[FlinkController] No active Flink job running. Pause operation skipped (idempotent).")
            return {
                "status": "SKIPPED",
                "message": "No active Flink job running",
                "job_id": None,
                "savepoint_path": None,
            }

        logger.info("[FlinkController] Attempting to pause Flink job '%s' with savepoint...", job_id)
        cancel_success = False
        savepoint_path = None

        # 1. Attempt graceful stop with savepoint (POST /jobs/:jobid/stop)
        try:
            stop_url = f"{self.flink_url}/jobs/{job_id}/stop"
            payload = json.dumps({"drain": False, "targetDirectory": self.savepoints_dir}).encode("utf-8")
            req = urllib.request.Request(
                stop_url,
                data=payload,
                method="POST",
                headers={"Accept": "application/json", "Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status in (200, 202):
                    stop_data = json.loads(resp.read().decode("utf-8"))
                    trigger_id = stop_data.get("request-id")
                    if trigger_id:
                        for _ in range(15):
                            time.sleep(1.0)
                            try:
                                sp_poll_url = f"{self.flink_url}/jobs/{job_id}/savepoints/{trigger_id}"
                                poll_req = urllib.request.Request(sp_poll_url, headers={"Accept": "application/json"})
                                with urllib.request.urlopen(poll_req, timeout=5) as poll_resp:
                                    if poll_resp.status == 200:
                                        p_data = json.loads(poll_resp.read().decode("utf-8"))
                                        status_id = p_data.get("status", {}).get("id")
                                        if status_id == "COMPLETED":
                                            savepoint_path = p_data.get("operation", {}).get("location")
                                            cancel_success = True
                                            logger.info("[FlinkController] Graceful stop with savepoint succeeded: %s", savepoint_path)
                                            break
                                        elif status_id in ("FAILED", "FAILURE"):
                                            logger.warning("[FlinkController] Savepoint trigger failed: %s", p_data.get("operation", {}).get("failure-cause"))
                                            break
                            except Exception as poll_err:
                                logger.debug("[FlinkController] Polling savepoint status: %s", poll_err)
        except Exception as stop_err:
            logger.warning("[FlinkController] REST stop with savepoint failed for job '%s': %s. Falling back to cancel...", job_id, stop_err)

        # 2. Fallback to REST cancellation if savepoint stop did not succeed
        if not cancel_success:
            try:
                cancel_url = f"{self.flink_url}/jobs/{job_id}?mode=cancel"
                req = urllib.request.Request(cancel_url, method="PATCH", headers={"Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    if resp.status in (200, 202):
                        cancel_success = True
                        logger.info("[FlinkController] REST cancel request issued for job '%s'", job_id)
            except Exception as rest_err:
                logger.warning("[FlinkController] REST cancel failed for job '%s': %s. Trying CLI fallback...", job_id, rest_err)

        # 3. CLI fallback if REST cancel fails
        if not cancel_success:
            try:
                cmd = ["docker", "exec", self.jobmanager_container, "/opt/flink/bin/flink", "cancel", job_id]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if res.returncode == 0 or "Cancelled job" in res.stdout:
                    cancel_success = True
                    logger.info("[FlinkController] CLI cancel succeeded for job '%s'", job_id)
                else:
                    logger.error("[FlinkController] CLI cancel error output: %s", res.stderr)
            except Exception as cli_err:
                logger.error("[FlinkController] CLI cancel failed: %s", cli_err)

        if not cancel_success:
            return {
                "status": "FAILED",
                "error": f"Failed to cancel Flink job '{job_id}' via REST API or CLI",
                "job_id": job_id,
                "savepoint_path": None,
            }

        self._last_savepoint_path = savepoint_path

        # 4. Confirm job state changed to CANCELED/FINISHED/SUSPENDED
        for _ in range(10):
            time.sleep(1.0)
            st = self.get_job_status(job_id)
            if st in ("CANCELED", "SUSPENDED", "FINISHED", "FAILED") or (self.get_active_job_id() != job_id):
                logger.info("[FlinkController] Confirmed Flink job '%s' is in state '%s'", job_id, st)
                return {
                    "status": "SUCCESS",
                    "job_id": job_id,
                    "final_state": st or "CANCELED",
                    "savepoint_path": savepoint_path,
                }

        return {
            "status": "FAILED",
            "error": f"Flink job '{job_id}' cancellation request sent, but job state did not transition within timeout",
            "job_id": job_id,
            "savepoint_path": savepoint_path,
        }

    def resume_job(self, savepoint_path: Optional[str] = None) -> Dict[str, Any]:
        """Submit and start Flink streaming Bronze pipeline job with optional savepoint restoration (idempotent).
        
        Returns:
            Dict describing status: SUCCESS, SKIPPED, or FAILED.
        """
        active_id = self.get_active_job_id()
        if active_id:
            logger.info("[FlinkController] Flink job '%s' is already running. Resume operation skipped (idempotent).", active_id)
            return {
                "status": "SKIPPED",
                "message": f"Flink job '{active_id}' is already running",
                "job_id": active_id,
            }

        target_savepoint = savepoint_path or self._last_savepoint_path
        if target_savepoint:
            logger.info("[FlinkController] Submitting Flink Bronze streaming pipeline job resuming from savepoint: %s", target_savepoint)
        else:
            logger.info("[FlinkController] Submitting Flink Bronze streaming pipeline job (group-offsets mode)...")
        
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        sql_path = os.path.join(project_root, "flink", "jobs", "kafka_to_iceberg.sql")

        if not os.path.exists(sql_path):
            return {
                "status": "FAILED",
                "error": f"SQL file not found at '{sql_path}'",
                "job_id": None,
            }

        user = os.getenv("MINIO_ROOT_USER") or os.getenv("MINIO_ACCESS_KEY") or "icestream_minio"
        pwd = os.getenv("MINIO_ROOT_PASSWORD") or os.getenv("MINIO_SECRET_KEY") or "change-me-minio-secret"

        try:
            with open(sql_path, "r", encoding="utf-8") as f:
                sql_content = f.read()
            sql_rendered = sql_content.replace("${MINIO_ROOT_USER}", user).replace("${MINIO_ROOT_PASSWORD}", pwd)

            # If resuming from a savepoint, inject the savepoint configuration
            if target_savepoint:
                savepoint_directive = (
                    f"SET 'execution.savepoint.path' = '{target_savepoint}';\n"
                    f"SET 'execution.savepoint.ignore-unclaimed-state' = 'false';\n"
                )
                if "SET 'table.exec.sink.not-null-enforcer'" in sql_rendered:
                    sql_rendered = sql_rendered.replace(
                        "SET 'table.exec.sink.not-null-enforcer' = 'DROP';",
                        f"SET 'table.exec.sink.not-null-enforcer' = 'DROP';\n{savepoint_directive}"
                    )
                else:
                    sql_rendered = savepoint_directive + sql_rendered

            cmd = ["docker", "exec", "-i", self.jobmanager_container, "/opt/flink/bin/sql-client.sh"]
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            proc.communicate(input=sql_rendered, timeout=20)
        except Exception as sub_err:
            logger.error("[FlinkController] Job submission error: %s", sub_err)
            return {
                "status": "FAILED",
                "error": f"Job submission failed: {sub_err}",
                "job_id": None,
            }

        # Confirm new job is running
        for _ in range(15):
            time.sleep(1.0)
            new_job_id = self.get_active_job_id()
            if new_job_id:
                logger.info("[FlinkController] Confirmed new Flink job '%s' is RUNNING", new_job_id)
                self._last_savepoint_path = None
                return {
                    "status": "SUCCESS",
                    "job_id": new_job_id,
                    "final_state": "RUNNING",
                    "resumed_from_savepoint": target_savepoint,
                }

        return {
            "status": "FAILED",
            "error": "Flink job submitted, but active job was not detected within timeout",
            "job_id": None,
        }
