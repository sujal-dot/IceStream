"""Incident service layer."""

import logging
from typing import Any, Dict, Optional
from fastapi import HTTPException, status

from backend.database.repositories.incident_repository import IncidentRepository
from backend.models.incidents import IncidentDetailResponse, IncidentItem, IncidentListResponse

logger = logging.getLogger("icestream.services.incident")


class IncidentService:
    """Service orchestrating incident queries from database storage."""

    def __init__(self, repository: Optional[IncidentRepository] = None):
        self.repository = repository or IncidentRepository()

    def get_incidents(
        self, status_filter: Optional[str] = None, limit: int = 50, offset: int = 0
    ) -> IncidentListResponse:
        """Fetch paginated incidents from repository."""
        limit = max(1, min(limit, 100))
        offset = max(0, offset)

        data = self.repository.list_incidents(status=status_filter, limit=limit, offset=offset)
        items = []
        for raw in data.get("items", []):
            items.append(
                IncidentItem(
                    incident_id=raw["incident_id"],
                    pipeline_id=raw.get("pipeline_id", "icestream"),
                    created_at=str(raw["created_at"]),
                    trigger=raw["trigger"],
                    error_rate=float(raw.get("error_rate", 0.0)),
                    circuit_state=raw.get("circuit_state", "OPEN"),
                    failed_event_count=int(raw.get("failed_event_count", 0)),
                    quarantine_count=int(raw.get("quarantine_count", 0)),
                    status=raw["status"],
                    recovery_attempt=int(raw.get("recovery_attempt", 0)),
                    last_error=raw.get("last_error"),
                    resolved_at=str(raw["resolved_at"]) if raw.get("resolved_at") else None,
                )
            )
        return IncidentListResponse(items=items, total=data.get("total", len(items)))

    def get_incident_detail(
        self, incident_id: str, current_circuit_state: str, current_pipeline_state: str
    ) -> IncidentDetailResponse:
        """Fetch detailed incident record including remediation attempt history."""
        inc = self.repository.get_incident(incident_id)
        if not inc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Incident '{incident_id}' not found",
            )

        attempts = self.repository.get_remediation_attempts(incident_id)
        item = IncidentItem(
            incident_id=inc["incident_id"],
            pipeline_id=inc.get("pipeline_id", "icestream"),
            created_at=str(inc["created_at"]),
            trigger=inc["trigger"],
            error_rate=float(inc.get("error_rate", 0.0)),
            circuit_state=inc.get("circuit_state", "OPEN"),
            failed_event_count=int(inc.get("failed_event_count", 0)),
            quarantine_count=int(inc.get("quarantine_count", 0)),
            status=inc["status"],
            recovery_attempt=int(inc.get("recovery_attempt", 0)),
            last_error=inc.get("last_error"),
            resolved_at=str(inc["resolved_at"]) if inc.get("resolved_at") else None,
        )

        return IncidentDetailResponse(
            incident=item,
            circuit_state=inc.get("circuit_state", current_circuit_state),
            remediation_stage=current_pipeline_state,
            recovery_attempts=len(attempts),
            attempts_history=attempts,
            resolved_at=str(inc["resolved_at"]) if inc.get("resolved_at") else None,
        )
