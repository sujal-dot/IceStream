"""PostgreSQL / Storage repository for incident persistence."""

from typing import Any, Dict, List, Optional
from backend.storage.db import StorageBackend, get_db_storage


class IncidentRepository:
    """Repository handling SQL queries for incidents and remediation attempts."""

    def __init__(self, storage: Optional[StorageBackend] = None):
        self.storage = storage or get_db_storage()

    def list_incidents(
        self, status: Optional[str] = None, limit: int = 50, offset: int = 0
    ) -> Dict[str, Any]:
        return self.storage.list_incidents(status=status, limit=limit, offset=offset)

    def get_incident(self, incident_id: str) -> Optional[Dict[str, Any]]:
        return self.storage.get_incident(incident_id)

    def get_remediation_attempts(self, incident_id: str) -> List[Dict[str, Any]]:
        return self.storage.get_remediation_attempts(incident_id)

    def create_incident(self, incident: Dict[str, Any]) -> Dict[str, Any]:
        return self.storage.create_incident(incident)
