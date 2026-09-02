"""PostgreSQL / Storage repository for pipeline state persistence."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from backend.storage.db import StorageBackend, get_db_storage


class PipelineRepository:
    """Repository handling SQL queries for pipeline state and state history."""

    def __init__(self, storage: Optional[StorageBackend] = None):
        self.storage = storage or get_db_storage()

    def get_pipeline_state(self, pipeline_id: str = "icestream") -> Optional[Dict[str, Any]]:
        return self.storage.get_pipeline_state(pipeline_id)

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
        return self.storage.upsert_pipeline_state(
            pipeline_id=pipeline_id,
            state=state,
            previous_state=previous_state,
            reason=reason,
            updated_at=updated_at,
            active_incident_id=active_incident_id,
            recovery_attempt=recovery_attempt,
            last_error=last_error,
        )

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
        self.storage.record_state_history(
            pipeline_id=pipeline_id,
            from_state=from_state,
            to_state=to_state,
            reason=reason,
            timestamp=timestamp,
            incident_id=incident_id,
            recovery_attempt=recovery_attempt,
        )

    def get_state_history(self, pipeline_id: str = "icestream", limit: int = 50) -> List[Dict[str, Any]]:
        return self.storage.get_state_history(pipeline_id=pipeline_id, limit=limit)
