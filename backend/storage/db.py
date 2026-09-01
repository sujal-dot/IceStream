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
                pipeline_id VARCHAR(64) NOT NULL,
                created_at TIMESTAMP NOT NULL,
                trigger VARCHAR(64) NOT NULL,
                error_rate REAL NOT NULL,
                circuit_state VARCHAR(64) NOT NULL,
                failed_event_count INT NOT NULL DEFAULT 0,
                quarantine_count INT NOT NULL DEFAULT 0,
                status VARCHAR(64) NOT NULL,
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

        if self.use_sqlite:
            conn = self._get_connection()
            cursor = conn.cursor()
            for cmd in sql_commands:
                cmd_clean = cmd.replace("AUTOINCREMENT if_sqlite", "AUTOINCREMENT")
                cursor.execute(cmd_clean)
            conn.commit()
        else:
            try:
                conn = self._get_connection()
                with conn.cursor() as cursor:
                    for cmd in sql_commands:
                        cmd_clean = cmd.replace("AUTOINCREMENT if_sqlite", "")
                        cmd_clean = cmd_clean.replace("INTEGER PRIMARY KEY", "SERIAL PRIMARY KEY")
                        cursor.execute(cmd_clean)
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

    def create_incident(self, incident: Dict[str, Any]) -> Dict[str, Any]:
        ts = incident.get("created_at") or datetime.now(timezone.utc)
        created_str = ts.isoformat() if isinstance(ts, datetime) else str(ts)
        resolved_str = None
        if incident.get("resolved_at"):
            r = incident["resolved_at"]
            resolved_str = r.isoformat() if isinstance(r, datetime) else str(r)

        if self.use_sqlite:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO pipeline_incidents (
                    incident_id, pipeline_id, created_at, trigger, error_rate, circuit_state,
                    failed_event_count, quarantine_count, status, recovery_attempt, last_error, resolved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(incident_id) DO UPDATE SET
                    status=excluded.status,
                    error_rate=excluded.error_rate,
                    circuit_state=excluded.circuit_state,
                    failed_event_count=excluded.failed_event_count,
                    quarantine_count=excluded.quarantine_count,
                    recovery_attempt=excluded.recovery_attempt,
                    last_error=excluded.last_error,
                    resolved_at=excluded.resolved_at;
                """,
                (
                    incident["incident_id"],
                    incident.get("pipeline_id", "icestream"),
                    created_str,
                    incident.get("trigger", "CRITICAL_ERROR_RATE"),
                    float(incident.get("error_rate", 0.0)),
                    incident.get("circuit_state", "OPEN"),
                    int(incident.get("failed_event_count", 0)),
                    int(incident.get("quarantine_count", 0)),
                    incident.get("status", "OPEN"),
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
                        incident_id, pipeline_id, created_at, trigger, error_rate, circuit_state,
                        failed_event_count, quarantine_count, status, recovery_attempt, last_error, resolved_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT(incident_id) DO UPDATE SET
                        status=EXCLUDED.status,
                        error_rate=EXCLUDED.error_rate,
                        circuit_state=EXCLUDED.circuit_state,
                        failed_event_count=EXCLUDED.failed_event_count,
                        quarantine_count=EXCLUDED.quarantine_count,
                        recovery_attempt=EXCLUDED.recovery_attempt,
                        last_error=EXCLUDED.last_error,
                        resolved_at=EXCLUDED.resolved_at;
                    """,
                    (
                        incident["incident_id"],
                        incident.get("pipeline_id", "icestream"),
                        ts if isinstance(ts, datetime) else created_str,
                        incident.get("trigger", "CRITICAL_ERROR_RATE"),
                        float(incident.get("error_rate", 0.0)),
                        incident.get("circuit_state", "OPEN"),
                        int(incident.get("failed_event_count", 0)),
                        int(incident.get("quarantine_count", 0)),
                        incident.get("status", "OPEN"),
                        int(incident.get("recovery_attempt", 0)),
                        incident.get("last_error"),
                        incident.get("resolved_at") if isinstance(incident.get("resolved_at"), datetime) else resolved_str,
                    ),
                )
            conn.commit()
            conn.close()

        return self.get_incident(incident["incident_id"]) or incident

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
            return dict(row)
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
            return dict(row)

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
