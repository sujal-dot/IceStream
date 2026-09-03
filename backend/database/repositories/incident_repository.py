"""PostgreSQL / Storage repository for incident persistence."""

from typing import Any, Dict, List, Optional
from backend.storage.db import StorageBackend, get_db_storage


class IncidentRepository:
    """Repository handling SQL queries for incidents and remediation attempts."""

    def __init__(self, storage: Optional[StorageBackend] = None):
        self.storage = storage or get_db_storage()

    def list_incidents(
        self,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        return self.storage.list_incidents(status=status, severity=severity, limit=limit, offset=offset)

    def get_incident(self, incident_id: str) -> Optional[Dict[str, Any]]:
        return self.storage.get_incident(incident_id)

    def get_remediation_attempts(self, incident_id: str) -> List[Dict[str, Any]]:
        return self.storage.get_remediation_attempts(incident_id)

    def create_incident(self, incident: Dict[str, Any]) -> Dict[str, Any]:
        return self.storage.create_incident(incident)

    def update_incident(self, incident_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return self.storage.update_incident(incident_id, updates)

    def find_active_incident(self, pipeline_name: str = "checkout-stream") -> Optional[Dict[str, Any]]:
        return self.storage.find_active_incident(pipeline_name)

    def generate_incident_id(self, date_str: Optional[str] = None) -> str:
        return self.storage.generate_incident_id(date_str)

