"""Incidents API Router."""

from typing import Optional
from fastapi import APIRouter, Depends, Query, status

from pydantic import BaseModel, Field

from backend.models.incidents import (
    IncidentActionResponse,
    IncidentDetailResponse,
    IncidentListResponse,
)
from backend.services.incident_service import IncidentService
from backend.security import verify_api_token

router = APIRouter(prefix="/incidents", tags=["Incidents"])


class TriggerIncidentRequest(BaseModel):
    trigger: str = Field(default="NULL_FIELD_SPIKE", description="Incident trigger type")
    error_rate: float = Field(default=0.045, description="Error rate percentage")
    failed_event_count: int = Field(default=45, description="Failed record count")
    quarantine_count: int = Field(default=45, description="Quarantine count")


def get_incident_service() -> IncidentService:
    return IncidentService()


@router.post(
    "/trigger",
    summary="Trigger Test Incident",
    description="Simulate or generate a new incident record in backend storage.",
)
def trigger_incident(
    payload: Optional[TriggerIncidentRequest] = None,
):
    from backend.app import get_remediation_controller
    controller = get_remediation_controller()
    req = payload or TriggerIncidentRequest()
    inc = controller.get_or_create_incident(
        trigger=req.trigger,
        error_rate=req.error_rate,
        failed_event_count=req.failed_event_count,
        quarantine_count=req.quarantine_count,
    )
    return {"status": "SUCCESS", "incident": inc}


@router.get(
    "",
    response_model=IncidentListResponse,
    summary="List Pipeline Incidents",
    description="Retrieve paginated list of persisted pipeline incidents from PostgreSQL storage with optional status/severity filters.",
)
def list_incidents(
    status: Optional[str] = Query(None, description="Filter incidents by status e.g. OPEN, ACKNOWLEDGED, RESOLVED"),
    severity: Optional[str] = Query(None, description="Filter incidents by severity e.g. CRITICAL, WARNING, HEALTHY"),
    limit: int = Query(50, ge=1, le=100, description="Number of items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
) -> IncidentListResponse:
    service = get_incident_service()
    return service.get_incidents(
        status_filter=status, severity_filter=severity, limit=limit, offset=offset
    )


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


@router.post(
    "/{incident_id}/acknowledge",
    response_model=IncidentActionResponse,
    summary="Acknowledge Pipeline Incident",
    description="Transition incident lifecycle status from OPEN to ACKNOWLEDGED.",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_api_token)],
)
def acknowledge_incident(incident_id: str) -> IncidentActionResponse:
    service = get_incident_service()
    return service.acknowledge_incident(incident_id=incident_id)


@router.post(
    "/{incident_id}/resolve",
    response_model=IncidentActionResponse,
    summary="Resolve Pipeline Incident",
    description="Transition incident lifecycle status to RESOLVED and send resolution notification.",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_api_token)],
)
def resolve_incident(incident_id: str) -> IncidentActionResponse:
    service = get_incident_service()
    return service.resolve_incident(incident_id=incident_id)
