"""Incidents API Router."""

from typing import Optional
from fastapi import APIRouter, Query

from backend.models.incidents import IncidentDetailResponse, IncidentListResponse
from backend.services.incident_service import IncidentService

router = APIRouter(prefix="/incidents", tags=["Incidents"])


def get_incident_service() -> IncidentService:
    from backend.app import get_db_storage
    return IncidentService()


@router.get(
    "",
    response_model=IncidentListResponse,
    summary="List Pipeline Incidents",
    description="Retrieve paginated list of persisted pipeline incidents from PostgreSQL storage.",
)
def list_incidents(
    status: Optional[str] = Query(None, description="Filter incidents by status e.g. OPEN, RECOVERED, RECOVERY_FAILED"),
    limit: int = Query(50, ge=1, le=100, description="Number of items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
) -> IncidentListResponse:
    service = get_incident_service()
    return service.get_incidents(status_filter=status, limit=limit, offset=offset)


@router.get(
    "/{incident_id}",
    response_model=IncidentDetailResponse,
    summary="Get Incident Details",
    description="Retrieve full details, circuit status, remediation stage, and attempts history for an incident.",
)
def get_incident_details(incident_id: str) -> IncidentDetailResponse:
    from backend.app import get_circuit_breaker, get_state_manager
    service = get_incident_service()
    cb = get_circuit_breaker()
    sm = get_state_manager()
    return service.get_incident_detail(
        incident_id=incident_id,
        current_circuit_state=cb.state.name,
        current_pipeline_state=sm.current_state.value,
    )
