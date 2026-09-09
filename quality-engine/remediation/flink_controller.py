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


class FlinkController:
    """Controller interfacing with Apache Flink JobManager REST API and container runtime."""

    def __init__(
        self,
        flink_url: Optional[str] = None,
        jobmanager_container: str = "icestream-flink-jobmanager",
    ) -> None:
        env_url = os.getenv("FLINK_REST_URI") or os.getenv("FLINK_URL")
        if not env_url:
            host = os.getenv("FLINK_JOBMANAGER_HOST", "localhost")
            port = os.getenv("FLINK_PORT", "8081")
            env_url = f"http://{host}:{port}"
        self.flink_url = flink_url or env_url
        self.jobmanager_container = jobmanager_container

    def get_active_job_id(self) -> Optional[str]:
        """Discover running IceStream Flink job ID from JobManager REST API."""
        try:
            url = f"{self.flink_url}/jobs/overview"
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    jobs = data.get("jobs", [])
                    active_jobs = [
                        j for j in jobs
                        if j.get("state") in ("RUNNING", "INITIALIZING", "CREATED")
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
            url = f"{self.flink_url}/jobs/{job_id}"
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    return str(data.get("state"))
        except Exception as e:
            logger.warning("Failed to query state for Flink job '%s': %s", job_id, e)
        return None

    def pause_job(self) -> Dict[str, Any]:
        """Cancel/pause running Flink job (idempotent).
        
        Returns:
            Dict describing status: SUCCESS, SKIPPED, or FAILED.
        """
        job_id = self.get_active_job_id()
        if not job_id:
            logger.info("[FlinkController] No active Flink job running. Pause operation skipped (idempotent).")
            return {
                "status": "SKIPPED",
                "message": "No active Flink job running",
                "job_id": None,
            }

        logger.info("[FlinkController] Attempting to cancel Flink job '%s'...", job_id)
        cancel_success = False

        # 1. Attempt HTTP REST cancellation
        try:
            cancel_url = f"{self.flink_url}/jobs/{job_id}?mode=cancel"
            req = urllib.request.Request(cancel_url, method="PATCH", headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status in (200, 202):
                    cancel_success = True
                    logger.info("[FlinkController] REST cancel request issued for job '%s'", job_id)
        except Exception as rest_err:
            logger.warning("[FlinkController] REST cancel failed for job '%s': %s. Trying CLI fallback...", job_id, rest_err)

        # 2. CLI fallback if REST fails
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
            }

        # 3. Confirm job state changed to CANCELED/FINISHED
        for _ in range(10):
            time.sleep(1.0)
            st = self.get_job_status(job_id)
            if st in ("CANCELED", "SUSPENDED", "FINISHED", "FAILED") or (self.get_active_job_id() != job_id):
                logger.info("[FlinkController] Confirmed Flink job '%s' is in state '%s'", job_id, st)
                return {
                    "status": "SUCCESS",
                    "job_id": job_id,
                    "final_state": st or "CANCELED",
                }

        return {
            "status": "FAILED",
            "error": f"Flink job '{job_id}' cancellation request sent, but job state did not transition within timeout",
            "job_id": job_id,
        }

    def resume_job(self) -> Dict[str, Any]:
        """Submit and start Flink streaming Bronze pipeline job (idempotent).
        
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

        logger.info("[FlinkController] Submitting Flink Bronze streaming pipeline job...")
        
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        sql_path = os.path.join(project_root, "flink", "jobs", "kafka_to_iceberg.sql")

        if not os.path.exists(sql_path):
            return {
                "status": "FAILED",
                "error": f"SQL file not found at '{sql_path}'",
                "job_id": None,
            }

        user = os.getenv("MINIO_ROOT_USER") or os.getenv("MINIO_ACCESS_KEY") or "icestream_minio"
        pwd = os.getenv("MINIO_ROOT_PASSWORD") or os.getenv("MINIO_SECRET_KEY") or "icestream_minio_secret"

        try:
            with open(sql_path, "r", encoding="utf-8") as f:
                sql_content = f.read()
            sql_rendered = sql_content.replace("${MINIO_ROOT_USER}", user).replace("${MINIO_ROOT_PASSWORD}", pwd)

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
                return {
                    "status": "SUCCESS",
                    "job_id": new_job_id,
                    "final_state": "RUNNING",
                }

        return {
            "status": "FAILED",
            "error": "Flink job submitted, but active job was not detected within timeout",
            "job_id": None,
        }
