"""Database storage layer for IceStream pipeline state, incidents, and remediation audit trail.

Provides persistent storage in PostgreSQL with in-memory SQLite fallback for unit testing.
"""

from datetime import datetime, timezone
import logging
import os
import sqlite3
from typing import Any, Dict, List, Optional

logger = logging.getLogger("icestream.storage.db")


class StorageBackend:
    """Interface for DB operations supporting PostgreSQL or SQLite fallback."""

    def __init__(self, db_uri: Optional[str] = None, use_sqlite: bool = False):
        self.use_sqlite = use_sqlite
        self.db_uri = db_uri or os.getenv(
            "DATABASE_URL",
            "postgresql://icestream_user:icestream_password@localhost:5432/icestream_db",
        )
        self._sqlite_conn: Optional[sqlite3.Connection] = None

        if self.use_sqlite or "sqlite" in self.db_uri:
            self.use_sqlite = True
            # SQLite connection setup (check_same_thread=False for multithreaded test access)
            self._sqlite_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._sqlite_conn.row_factory = sqlite3.Row
            logger.info("StorageBackend initialized with SQLite in-memory database")
        else:
            logger.info(f"StorageBackend initialized with PostgreSQL at {self.db_uri.split('@')[-1]}")

        self._init_tables()

    def _get_connection(self):
        if self.use_sqlite:
            return self._sqlite_conn
        else:
            import psycopg2
            import psycopg2.extras
            host = os.getenv("POSTGRES_HOST", "localhost")
            port = int(os.getenv("POSTGRES_PORT", "5432"))
            dbname = os.getenv("POSTGRES_DB", "icestream_db")
            user = os.getenv("POSTGRES_USER", "icestream_user")
            password = os.getenv("POSTGRES_PASSWORD", "icestream_password")
            return psycopg2.connect(
                host=host,
                port=port,
                dbname=dbname,
                user=user,
                password=password,
                cursor_factory=psycopg2.extras.DictCursor,
            )

    def _init_tables(self):
        """Create tables if they do not exist."""
        sql_commands = [
            """
            CREATE TABLE IF NOT EXISTS pipeline_state (
                pipeline_id VARCHAR(64) PRIMARY KEY,
                state VARCHAR(64) NOT NULL,
                previous_state VARCHAR(64),
                reason TEXT,
                updated_at TIMESTAMP NOT NULL,
                active_incident_id VARCHAR(64),
                recovery_attempt INT DEFAULT 0,
                last_error TEXT
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS pipeline_state_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT if_sqlite,
                pipeline_id VARCHAR(64) NOT NULL,
                from_state VARCHAR(64) NOT NULL,
                to_state VARCHAR(64) NOT NULL,
                reason TEXT,
                timestamp TIMESTAMP NOT NULL,
                incident_id VARCHAR(64),
                recovery_attempt INT DEFAULT 0
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS pipeline_incidents (
                incident_id VARCHAR(64) PRIMARY KEY,
                pipeline_id VARCHAR(64) NOT NULL DEFAULT 'icestream',
                pipeline_name VARCHAR(64) NOT NULL DEFAULT 'checkout-stream',
                created_at TIMESTAMP NOT NULL,
                detected_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                trigger VARCHAR(64) NOT NULL DEFAULT 'CRITICAL_ERROR_RATE',
                trigger_type VARCHAR(64) NOT NULL DEFAULT 'CRITICAL_ERROR_RATE',
                error_rate REAL NOT NULL DEFAULT 0.0,
                threshold REAL NOT NULL DEFAULT 0.02,
                circuit_state VARCHAR(64) NOT NULL DEFAULT 'OPEN',
                failed_event_count INT NOT NULL DEFAULT 0,
                failed_records INT NOT NULL DEFAULT 0,
                total_records INT NOT NULL DEFAULT 0,
                quarantine_count INT NOT NULL DEFAULT 0,
                status VARCHAR(64) NOT NULL DEFAULT 'OPEN',
                severity VARCHAR(32) NOT NULL DEFAULT 'CRITICAL',
                message TEXT,
                action_taken TEXT,
                slack_sent BOOLEAN DEFAULT FALSE,
                slack_sent_at TIMESTAMP,
                slack_error TEXT,
                recovery_attempt INT NOT NULL DEFAULT 0,
                last_error TEXT,
                resolved_at TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS remediation_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT if_sqlite,
                incident_id VARCHAR(64) NOT NULL,
                attempt_number INT NOT NULL,
                started_at TIMESTAMP NOT NULL,
                completed_at TIMESTAMP,
                stage VARCHAR(64) NOT NULL,
                status VARCHAR(64) NOT NULL,
                error TEXT,
                source_reference VARCHAR(256),
                recovered_event_count INT DEFAULT 0
            );
            """,
        ]

        # Columns to ensure exist for backwards compatibility with existing DB tables
        extra_cols = [
            ("pipeline_name", "VARCHAR(64) DEFAULT 'checkout-stream'"),
            ("detected_at", "TIMESTAMP"),
            ("updated_at", "TIMESTAMP"),
            ("trigger_type", "VARCHAR(64) DEFAULT 'CRITICAL_ERROR_RATE'"),
            ("threshold", "REAL DEFAULT 0.02"),
            ("failed_records", "INT DEFAULT 0"),
            ("total_records", "INT DEFAULT 0"),
            ("severity", "VARCHAR(32) DEFAULT 'CRITICAL'"),
            ("message", "TEXT"),
            ("action_taken", "TEXT"),
            ("slack_sent", "BOOLEAN DEFAULT FALSE"),
            ("slack_sent_at", "TIMESTAMP"),
            ("slack_error", "TEXT"),
        ]

        if self.use_sqlite:
            conn = self._get_connection()
            cursor = conn.cursor()
            for cmd in sql_commands:
                cmd_clean = cmd.replace("AUTOINCREMENT if_sqlite", "AUTOINCREMENT")
                cursor.execute(cmd_clean)
            for col_name, col_def in extra_cols:
                try:
                    cursor.execute(f"ALTER TABLE pipeline_incidents ADD COLUMN {col_name} {col_def};")
                except Exception:
                    pass
            conn.commit()
        else:
            try:
                conn = self._get_connection()
                with conn.cursor() as cursor:
                    for cmd in sql_commands:
                        cmd_clean = cmd.replace("AUTOINCREMENT if_sqlite", "")
                        cmd_clean = cmd_clean.replace("INTEGER PRIMARY KEY", "SERIAL PRIMARY KEY")
                        cursor.execute(cmd_clean)
                    for col_name, col_def in extra_cols:
                        try:
                            cursor.execute(f"ALTER TABLE pipeline_incidents ADD COLUMN IF NOT EXISTS {col_name} {col_def};")
                        except Exception:
                            pass
                conn.commit()
                conn.close()
            except Exception as e:
                logger.warning(f"Could not initialize PostgreSQL tables: {e}. Falling back to SQLite.")
                self.use_sqlite = True
                self._sqlite_conn = sqlite3.connect(":memory:", check_same_thread=False)
                self._sqlite_conn.row_factory = sqlite3.Row
                self._init_tables()

    # --- Pipeline State Methods ---

    def upsert_pipeline_state(
        self,
        pipeline_id: str,
        state: str,
        previous_state: Optional[str] = None,
        reason: Optional[str] = None,
        updated_at: Optional[datetime] = None,
        active_incident_id: Optional[str] = None,
        recovery_attempt: int = 0,
        last_error: Optional[str] = None,
    ) -> Dict[str, Any]:
        ts = updated_at or datetime.now(timezone.utc)
        if self.use_sqlite:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO pipeline_state (
                    pipeline_id, state, previous_state, reason, updated_at, active_incident_id, recovery_attempt, last_error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(pipeline_id) DO UPDATE SET
                    state=excluded.state,
                    previous_state=excluded.previous_state,
                    reason=excluded.reason,
                    updated_at=excluded.updated_at,
                    active_incident_id=excluded.active_incident_id,
                    recovery_attempt=excluded.recovery_attempt,
                    last_error=excluded.last_error;
                """,
                (
                    pipeline_id,
                    state,
                    previous_state,
                    reason,
                    ts.isoformat(),
                    active_incident_id,
                    recovery_attempt,
                    last_error,
                ),
            )
            conn.commit()
        else:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO pipeline_state (
                        pipeline_id, state, previous_state, reason, updated_at, active_incident_id, recovery_attempt, last_error
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT(pipeline_id) DO UPDATE SET
                        state=EXCLUDED.state,
                        previous_state=EXCLUDED.previous_state,
                        reason=EXCLUDED.reason,
                        updated_at=EXCLUDED.updated_at,
                        active_incident_id=EXCLUDED.active_incident_id,
                        recovery_attempt=EXCLUDED.recovery_attempt,
                        last_error=EXCLUDED.last_error;
                    """,
                    (
                        pipeline_id,
                        state,
                        previous_state,
                        reason,
                        ts,
                        active_incident_id,
                        recovery_attempt,
                        last_error,
                    ),
                )
            conn.commit()
            conn.close()

        return {
            "pipeline_id": pipeline_id,
            "state": state,
            "previous_state": previous_state,
            "reason": reason,
            "updated_at": ts.isoformat() if isinstance(ts, datetime) else str(ts),
            "active_incident_id": active_incident_id,
            "recovery_attempt": recovery_attempt,
            "last_error": last_error,
        }

    def get_pipeline_state(self, pipeline_id: str = "icestream") -> Optional[Dict[str, Any]]:
        if self.use_sqlite:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM pipeline_state WHERE pipeline_id = ?", (pipeline_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return dict(row)
        else:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM pipeline_state WHERE pipeline_id = %s", (pipeline_id,)
                )
                row = cursor.fetchone()
            conn.close()
            if not row:
                return None
            return dict(row)

    def record_state_history(
        self,
        pipeline_id: str,
        from_state: str,
        to_state: str,
        reason: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        incident_id: Optional[str] = None,
        recovery_attempt: int = 0,
    ) -> None:
        ts = timestamp or datetime.now(timezone.utc)
        if self.use_sqlite:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO pipeline_state_history (
                    pipeline_id, from_state, to_state, reason, timestamp, incident_id, recovery_attempt
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pipeline_id,
                    from_state,
                    to_state,
                    reason,
                    ts.isoformat(),
                    incident_id,
                    recovery_attempt,
                ),
            )
            conn.commit()
        else:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO pipeline_state_history (
                        pipeline_id, from_state, to_state, reason, timestamp, incident_id, recovery_attempt
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        pipeline_id,
                        from_state,
                        to_state,
                        reason,
                        ts,
                        incident_id,
                        recovery_attempt,
                    ),
                )
            conn.commit()
            conn.close()

    def get_state_history(self, pipeline_id: str = "icestream", limit: int = 50) -> List[Dict[str, Any]]:
        if self.use_sqlite:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM pipeline_state_history WHERE pipeline_id = ? ORDER BY timestamp DESC LIMIT ?",
                (pipeline_id, limit),
            )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
        else:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM pipeline_state_history WHERE pipeline_id = %s ORDER BY timestamp DESC LIMIT %s",
                    (pipeline_id, limit),
                )
                rows = cursor.fetchall()
            conn.close()
            return [dict(r) for r in rows]

    # --- Pipeline Incident Methods ---

    # --- Pipeline Incident Methods ---

    def _normalize_incident_dict(self, d: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize DB dictionary output so both legacy and Day 24 field aliases exist."""
        if not d:
            return d
        res = dict(d)
        p_name = res.get("pipeline_name") or res.get("pipeline_id") or "checkout-stream"
        res["pipeline_name"] = p_name
        res["pipeline_id"] = res.get("pipeline_id") or p_name

        trig = res.get("trigger_type") or res.get("trigger") or "CRITICAL_ERROR_RATE"
        res["trigger_type"] = trig
        res["trigger"] = res.get("trigger") or trig

        failed = res.get("failed_records") if res.get("failed_records") is not None else res.get("failed_event_count", 0)
        res["failed_records"] = failed
        res["failed_event_count"] = res.get("failed_event_count") if res.get("failed_event_count") is not None else failed

        res["threshold"] = float(res.get("threshold") or 0.02)
        res["total_records"] = int(res.get("total_records") or 0)
        res["severity"] = res.get("severity") or ("CRITICAL" if float(res.get("error_rate", 0.0)) > 0.02 else ("WARNING" if float(res.get("error_rate", 0.0)) >= 0.01 else "HEALTHY"))
        res["action_taken"] = res.get("action_taken") or "Downstream pipeline paused."

        c_at = res.get("created_at")
        res["detected_at"] = str(res.get("detected_at") or c_at or "")
        res["created_at"] = str(c_at or "")
        res["updated_at"] = str(res.get("updated_at") or c_at or "")
        res["resolved_at"] = str(res["resolved_at"]) if res.get("resolved_at") else None
        res["slack_sent"] = bool(res.get("slack_sent"))
        res["slack_sent_at"] = str(res["slack_sent_at"]) if res.get("slack_sent_at") else None
        res["slack_error"] = res.get("slack_error")
        return res

    def generate_incident_id(self, date_str: Optional[str] = None) -> str:
        """Generate deterministic sequential incident ID e.g. INC-2026-0903-0001."""
        now = datetime.now(timezone.utc)
        if not date_str:
            date_str = now.strftime("%Y-%m%d")
        prefix = f"INC-{date_str}-"
        pattern = f"{prefix}%"

        if self.use_sqlite:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT incident_id FROM pipeline_incidents WHERE incident_id LIKE ? ORDER BY incident_id DESC LIMIT 1",
                (pattern,),
            )
            row = cursor.fetchone()
        else:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT incident_id FROM pipeline_incidents WHERE incident_id LIKE %s ORDER BY incident_id DESC LIMIT 1",
                    (pattern,),
                )
                row = cursor.fetchone()
            conn.close()

        seq = 1
        if row and row[0]:
            try:
                parts = str(row[0]).split("-")
                seq = int(parts[-1]) + 1
            except Exception:
                seq = 1
        return f"{prefix}{seq:04d}"

    def find_active_incident(self, pipeline_name: str = "checkout-stream") -> Optional[Dict[str, Any]]:
        """Find active OPEN or ACKNOWLEDGED incident for pipeline deduplication."""
        query_sql_sqlite = "SELECT * FROM pipeline_incidents WHERE (pipeline_name = ? OR pipeline_id = ?) AND status IN ('OPEN', 'ACKNOWLEDGED') ORDER BY created_at DESC LIMIT 1"
        query_sql_pg = "SELECT * FROM pipeline_incidents WHERE (pipeline_name = %s OR pipeline_id = %s) AND status IN ('OPEN', 'ACKNOWLEDGED') ORDER BY created_at DESC LIMIT 1"

        if self.use_sqlite:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(query_sql_sqlite, (pipeline_name, pipeline_name))
            row = cursor.fetchone()
            if not row:
                return None
            return self._normalize_incident_dict(dict(row))
        else:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute(query_sql_pg, (pipeline_name, pipeline_name))
                row = cursor.fetchone()
            conn.close()
            if not row:
                return None
            return self._normalize_incident_dict(dict(row))

    def create_incident(self, incident: Dict[str, Any]) -> Dict[str, Any]:
        """Persist or update incident record in database."""
        now = datetime.now(timezone.utc)
        ts = incident.get("created_at") or now
        created_str = ts.isoformat() if isinstance(ts, datetime) else str(ts)
        det_ts = incident.get("detected_at") or ts
        detected_str = det_ts.isoformat() if isinstance(det_ts, datetime) else str(det_ts)
        upd_ts = incident.get("updated_at") or now
        updated_str = upd_ts.isoformat() if isinstance(upd_ts, datetime) else str(upd_ts)

        resolved_str = None
        if incident.get("resolved_at"):
            r = incident["resolved_at"]
            resolved_str = r.isoformat() if isinstance(r, datetime) else str(r)

        slack_sent_str = None
        if incident.get("slack_sent_at"):
            s_at = incident["slack_sent_at"]
            slack_sent_str = s_at.isoformat() if isinstance(s_at, datetime) else str(s_at)

        p_name = incident.get("pipeline_name") or incident.get("pipeline_id") or "checkout-stream"
        p_id = incident.get("pipeline_id") or p_name
        trig = incident.get("trigger_type") or incident.get("trigger") or "CRITICAL_ERROR_RATE"
        err_rate = float(incident.get("error_rate", 0.0))
        thresh = float(incident.get("threshold", 0.02))

        failed_c = int(incident.get("failed_records") if incident.get("failed_records") is not None else incident.get("failed_event_count", 0))
        total_c = int(incident.get("total_records") or 0)
        sev = incident.get("severity") or ("CRITICAL" if err_rate > 0.02 else ("WARNING" if err_rate >= 0.01 else "HEALTHY"))
        act = incident.get("action_taken") or "Downstream pipeline paused."

        if self.use_sqlite:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO pipeline_incidents (
                    incident_id, pipeline_id, pipeline_name, created_at, detected_at, updated_at,
                    trigger, trigger_type, error_rate, threshold, circuit_state,
                    failed_event_count, failed_records, total_records, quarantine_count,
                    status, severity, message, action_taken, slack_sent, slack_sent_at, slack_error,
                    recovery_attempt, last_error, resolved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(incident_id) DO UPDATE SET
                    status=excluded.status,
                    severity=excluded.severity,
                    error_rate=excluded.error_rate,
                    threshold=excluded.threshold,
                    failed_event_count=excluded.failed_event_count,
                    failed_records=excluded.failed_records,
                    total_records=excluded.total_records,
                    circuit_state=excluded.circuit_state,
                    quarantine_count=excluded.quarantine_count,
                    action_taken=excluded.action_taken,
                    slack_sent=excluded.slack_sent,
                    slack_sent_at=excluded.slack_sent_at,
                    slack_error=excluded.slack_error,
                    recovery_attempt=excluded.recovery_attempt,
                    last_error=excluded.last_error,
                    updated_at=excluded.updated_at,
                    resolved_at=excluded.resolved_at;
                """,
                (
                    incident["incident_id"],
                    p_id,
                    p_name,
                    created_str,
                    detected_str,
                    updated_str,
                    trig,
                    trig,
                    err_rate,
                    thresh,
                    incident.get("circuit_state", "OPEN"),
                    failed_c,
                    failed_c,
                    total_c,
                    int(incident.get("quarantine_count", 0)),
                    incident.get("status", "OPEN"),
                    sev,
                    incident.get("message"),
                    act,
                    1 if incident.get("slack_sent") else 0,
                    slack_sent_str,
                    incident.get("slack_error"),
                    int(incident.get("recovery_attempt", 0)),
                    incident.get("last_error"),
                    resolved_str,
                ),
            )
            conn.commit()
        else:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO pipeline_incidents (
                        incident_id, pipeline_id, pipeline_name, created_at, detected_at, updated_at,
                        trigger, trigger_type, error_rate, threshold, circuit_state,
                        failed_event_count, failed_records, total_records, quarantine_count,
                        status, severity, message, action_taken, slack_sent, slack_sent_at, slack_error,
                        recovery_attempt, last_error, resolved_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT(incident_id) DO UPDATE SET
                        status=EXCLUDED.status,
                        severity=EXCLUDED.severity,
                        error_rate=EXCLUDED.error_rate,
                        threshold=EXCLUDED.threshold,
                        failed_event_count=EXCLUDED.failed_event_count,
                        failed_records=EXCLUDED.failed_records,
                        total_records=EXCLUDED.total_records,
                        circuit_state=EXCLUDED.circuit_state,
                        quarantine_count=EXCLUDED.quarantine_count,
                        action_taken=EXCLUDED.action_taken,
                        slack_sent=EXCLUDED.slack_sent,
                        slack_sent_at=EXCLUDED.slack_sent_at,
                        slack_error=EXCLUDED.slack_error,
                        recovery_attempt=EXCLUDED.recovery_attempt,
                        last_error=EXCLUDED.last_error,
                        updated_at=EXCLUDED.updated_at,
                        resolved_at=EXCLUDED.resolved_at;
                    """,
                    (
                        incident["incident_id"],
                        p_id,
                        p_name,
                        created_str,
                        detected_str,
                        updated_str,
                        trig,
                        trig,
                        err_rate,
                        thresh,
                        incident.get("circuit_state", "OPEN"),
                        failed_c,
                        failed_c,
                        total_c,
                        int(incident.get("quarantine_count", 0)),
                        incident.get("status", "OPEN"),
                        sev,
                        incident.get("message"),
                        act,
                        bool(incident.get("slack_sent")),
                        slack_sent_str,
                        incident.get("slack_error"),
                        int(incident.get("recovery_attempt", 0)),
                        incident.get("last_error"),
                        resolved_str,
                    ),
                )
            conn.commit()
            conn.close()

        return self.get_incident(incident["incident_id"]) or incident

    def update_incident(self, incident_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update specific fields of an incident safely in DB."""
        inc = self.get_incident(incident_id)
        if not inc:
            return None
        merged = dict(inc)
        merged.update(updates)
        merged["updated_at"] = datetime.now(timezone.utc)
        return self.create_incident(merged)

    def get_incident(self, incident_id: str) -> Optional[Dict[str, Any]]:
        if self.use_sqlite:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM pipeline_incidents WHERE incident_id = ?", (incident_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self._normalize_incident_dict(dict(row))
        else:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM pipeline_incidents WHERE incident_id = %s", (incident_id,)
                )
                row = cursor.fetchone()
            conn.close()
            if not row:
                return None
            return self._normalize_incident_dict(dict(row))

    def list_incidents(
        self,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Fetch paginated incidents from database with optional status or severity filter."""
        limit = max(1, min(limit, 100))
        offset = max(0, offset)

        where_clauses = []
        params: List[Any] = []
        if status:
            where_clauses.append("status = ?")
            params.append(status)
        if severity:
            where_clauses.append("severity = ?")
            params.append(severity)

        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        if self.use_sqlite:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM pipeline_incidents{where_sql}", tuple(params))
            total = cursor.fetchone()[0]

            cursor.execute(
                f"SELECT * FROM pipeline_incidents{where_sql} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                tuple(params + [limit, offset]),
            )
            rows = cursor.fetchall()
            return {"items": [self._normalize_incident_dict(dict(r)) for r in rows], "total": total}
        else:
            pg_where_sql = where_sql.replace("?", "%s")
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute(f"SELECT COUNT(*) FROM pipeline_incidents{pg_where_sql}", tuple(params))
                total = cursor.fetchone()[0]
                cursor.execute(
                    f"SELECT * FROM pipeline_incidents{pg_where_sql} ORDER BY created_at DESC LIMIT %s OFFSET %s",
                    tuple(params + [limit, offset]),
                )
                rows = cursor.fetchall()
            conn.close()
            return {"items": [self._normalize_incident_dict(dict(r)) for r in rows], "total": total}

    # --- Remediation Attempt Methods ---

    def record_remediation_attempt(
        self,
        incident_id: str,
        attempt_number: int,
        stage: str,
        status: str,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        error: Optional[str] = None,
        source_reference: Optional[str] = None,
        recovered_event_count: int = 0,
    ) -> None:
        start_ts = started_at or datetime.now(timezone.utc)
        comp_str = None
        if completed_at:
            comp_str = completed_at.isoformat() if isinstance(completed_at, datetime) else str(completed_at)

        if self.use_sqlite:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO remediation_attempts (
                    incident_id, attempt_number, started_at, completed_at, stage, status, error, source_reference, recovered_event_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    incident_id,
                    attempt_number,
                    start_ts.isoformat(),
                    comp_str,
                    stage,
                    status,
                    error,
                    source_reference,
                    recovered_event_count,
                ),
            )
            conn.commit()
        else:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO remediation_attempts (
                        incident_id, attempt_number, started_at, completed_at, stage, status, error, source_reference, recovered_event_count
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        incident_id,
                        attempt_number,
                        start_ts,
                        completed_at if isinstance(completed_at, datetime) else comp_str,
                        stage,
                        status,
                        error,
                        source_reference,
                        recovered_event_count,
                    ),
                )
            conn.commit()
            conn.close()

    def get_remediation_attempts(self, incident_id: str) -> List[Dict[str, Any]]:
        if self.use_sqlite:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM remediation_attempts WHERE incident_id = ? ORDER BY attempt_number ASC",
                (incident_id,),
            )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
        else:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM remediation_attempts WHERE incident_id = %s ORDER BY attempt_number ASC",
                    (incident_id,),
                )
                rows = cursor.fetchall()
            conn.close()
            return [dict(r) for r in rows]


# Global singleton instance for app / services
_global_db_storage: Optional[StorageBackend] = None


def get_db_storage(use_sqlite: bool = False) -> StorageBackend:
    global _global_db_storage
    if _global_db_storage is None:
        _global_db_storage = StorageBackend(use_sqlite=use_sqlite)
    return _global_db_storage


def set_db_storage(storage: Optional[StorageBackend]) -> None:
    global _global_db_storage
    _global_db_storage = storage
