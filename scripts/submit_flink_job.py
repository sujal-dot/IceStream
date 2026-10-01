#!/usr/bin/env python3
"""
IceStream Flink Job Submission Script.

Robustly submits the bronze streaming job to Flink with:
  - Readiness checks (Flink REST + TaskManager slots available)
  - Env variable substitution for MinIO credentials
  - Job state verification (waits for RUNNING)
  - Clear console output with timings
  - Non-zero exit code on failure
  - Optional --check-only flag to verify existing job without submitting
"""
import argparse
import os
import subprocess
import sys
import time


# ──────────────────────────────────────────────────────────────────────────────
# Environment helpers
# ──────────────────────────────────────────────────────────────────────────────

def load_env(env_path: str | None = None) -> None:
    """Load key=value pairs from .env into os.environ (skip if already set)."""
    if env_path is None:
        env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip("'\"")
            if k not in os.environ:
                os.environ[k] = v


# ──────────────────────────────────────────────────────────────────────────────
# Flink REST API helpers
# ──────────────────────────────────────────────────────────────────────────────

import json
import urllib.request
import urllib.error


FLINK_REST = os.environ.get("FLINK_REST_URI", "http://localhost:8081")


def _get(path: str) -> dict:
    url = f"{FLINK_REST}{path}"
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read().decode())


def wait_for_flink(timeout: int = 120, interval: int = 3) -> bool:
    """Block until Flink JobManager REST API is reachable and has ≥1 task slot."""
    print(f"[flink] Waiting for Flink JobManager at {FLINK_REST} ...", flush=True)
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            overview = _get("/v1/overview")
            slots = overview.get("slots-total", 0)
            running = overview.get("jobs-running", 0)
            version = overview.get("flink-version", "?")
            if slots >= 1:
                print(
                    f"[flink] JobManager ready  version={version}  slots={slots}  jobs-running={running}",
                    flush=True,
                )
                return True
        except Exception:
            pass
        time.sleep(interval)
    print(f"[flink] ERROR: Flink not ready after {timeout}s", flush=True)
    return False


def get_running_icestream_jobs() -> list[dict]:
    """Return list of RUNNING jobs whose name matches known IceStream patterns."""
    try:
        data = _get("/v1/jobs/overview")
        patterns = ("checkout_events", "icestream", "insert-into")
        return [
            j for j in data.get("jobs", [])
            if j.get("state") == "RUNNING"
            and any(p in j.get("name", "").lower() for p in patterns)
        ]
    except Exception as exc:
        print(f"[flink] WARNING: Could not query jobs: {exc}", flush=True)
        return []


def get_job_state(job_id: str) -> str | None:
    try:
        data = _get(f"/v1/jobs/{job_id}")
        return data.get("state")
    except Exception:
        return None


def wait_for_job_running(job_id: str, timeout: int = 60, interval: int = 3) -> bool:
    """Poll job state until RUNNING (or give up on terminal states)."""
    terminal = {"FAILED", "CANCELED", "FINISHED"}
    deadline = time.time() + timeout
    while time.time() < deadline:
        state = get_job_state(job_id)
        if state == "RUNNING":
            return True
        if state in terminal:
            print(f"[flink] Job {job_id} reached terminal state: {state}", flush=True)
            return False
        print(f"[flink] Job {job_id} state={state} — waiting...", flush=True)
        time.sleep(interval)
    print(f"[flink] ERROR: Job {job_id} did not reach RUNNING within {timeout}s", flush=True)
    return False


# ──────────────────────────────────────────────────────────────────────────────
# SQL rendering
# ──────────────────────────────────────────────────────────────────────────────

def render_sql(sql_path: str) -> str:
    user = (
        os.environ.get("MINIO_ROOT_USER")
        or os.environ.get("MINIO_ACCESS_KEY")
        or "icestream_minio"
    )
    pwd = (
        os.environ.get("MINIO_ROOT_PASSWORD")
        or os.environ.get("MINIO_SECRET_KEY")
        or "change-me-minio-secret"
    )
    with open(sql_path, encoding="utf-8") as fh:
        sql = fh.read()
    sql = sql.replace("${MINIO_ROOT_USER}", user).replace("${MINIO_ROOT_PASSWORD}", pwd)
    # Ensure the SQL ends with EXIT so sql-client exits cleanly
    if not sql.strip().upper().endswith("EXIT;"):
        sql += "\nEXIT;\n"
    return sql


# ──────────────────────────────────────────────────────────────────────────────
# Job submission via sql-client inside Docker
# ──────────────────────────────────────────────────────────────────────────────

CONTAINER = "icestream-flink-jobmanager"
SQL_CLIENT = "/opt/flink/bin/sql-client.sh"


def submit_sql(sql: str, timeout: int = 120) -> tuple[int, str, str]:
    """Pipe SQL to Flink SQL-client running inside Docker container."""
    cmd = ["docker", "exec", "-i", CONTAINER, SQL_CLIENT]
    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        out, err = proc.communicate(input=sql, timeout=timeout)
        return proc.returncode, out, err
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
        return 1, out or "", f"Timeout after {timeout}s\n{err or ''}"
    except Exception as exc:
        return 1, "", str(exc)


# ──────────────────────────────────────────────────────────────────────────────
# Job polling after submission (sql-client doesn't return job IDs)
# ──────────────────────────────────────────────────────────────────────────────

def poll_for_new_job(
    pre_job_ids: set[str],
    timeout: int = 60,
    interval: int = 3,
) -> dict | None:
    """Poll until a new RUNNING job appears that wasn't in pre_job_ids."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            data = _get("/v1/jobs/overview")
            for job in data.get("jobs", []):
                if job.get("jid") not in pre_job_ids and job.get("state") == "RUNNING":
                    return job
        except Exception:
            pass
        time.sleep(interval)
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Main entry point
# ──────────────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Submit IceStream Flink streaming jobs")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only verify if an IceStream job is already running; do not submit",
    )
    parser.add_argument(
        "--flink-rest",
        default=None,
        help="Override Flink REST URL (default: http://localhost:8081 or FLINK_REST_URI env var)",
    )
    parser.add_argument(
        "--wait",
        type=int,
        default=120,
        help="Seconds to wait for Flink readiness (default: 120)",
    )
    args = parser.parse_args()

    load_env()

    global FLINK_REST
    if args.flink_rest:
        FLINK_REST = args.flink_rest
    elif os.environ.get("FLINK_REST_URI"):
        FLINK_REST = os.environ["FLINK_REST_URI"]

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sql_path = os.path.join(project_root, "flink", "jobs", "kafka_to_iceberg.sql")

    # ── Wait for Flink ──────────────────────────────────────────────────────
    if not wait_for_flink(timeout=args.wait):
        return 1

    # ── Check-only mode ─────────────────────────────────────────────────────
    if args.check_only:
        jobs = get_running_icestream_jobs()
        if jobs:
            for j in jobs:
                print(f"[flink] RUNNING job found: {j['jid']}  name={j['name']}", flush=True)
            return 0
        print("[flink] No running IceStream job found.", flush=True)
        return 1

    # ── Check if already running (idempotent) ───────────────────────────────
    existing = get_running_icestream_jobs()
    if existing:
        print(
            f"[flink] IceStream job already RUNNING: {existing[0]['jid']}  name={existing[0]['name']}",
            flush=True,
        )
        return 0

    # ── Snapshot pre-existing job IDs to detect new one after submit ────────
    try:
        pre_jobs = {j["jid"] for j in _get("/v1/jobs/overview").get("jobs", [])}
    except Exception:
        pre_jobs = set()

    # ── Render and submit SQL ────────────────────────────────────────────────
    print(f"[flink] Rendering SQL from {sql_path}", flush=True)
    sql = render_sql(sql_path)

    print("[flink] Submitting IceStream streaming job via SQL-client...", flush=True)
    rc, out, err = submit_sql(sql)

    if out.strip():
        for line in out.strip().splitlines():
            print(f"[sql-client] {line}", flush=True)
    if err.strip():
        # sql-client logs warnings/info to stderr — don't treat as fatal
        for line in err.strip().splitlines()[:20]:
            print(f"[sql-client/stderr] {line}", flush=True)

    # ── Verify job appeared and is RUNNING ───────────────────────────────────
    print("[flink] Waiting for submitted job to appear as RUNNING...", flush=True)
    new_job = poll_for_new_job(pre_jobs, timeout=90)
    if new_job:
        print(
            f"[flink] ✓ Job submitted and RUNNING: {new_job['jid']}  name={new_job['name']}",
            flush=True,
        )
        return 0

    # ── Fallback: maybe job was already there (race) ─────────────────────────
    icestream_jobs = get_running_icestream_jobs()
    if icestream_jobs:
        print(
            f"[flink] ✓ IceStream job RUNNING: {icestream_jobs[0]['jid']}",
            flush=True,
        )
        return 0

    print(
        "[flink] ERROR: Job submission completed but no RUNNING IceStream job found.\n"
        "        Check Flink dashboard at http://localhost:8081 for details.",
        flush=True,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
