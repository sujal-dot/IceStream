"""Pipeline Status and Control API Router."""

from typing import Optional
from fastapi import APIRouter, Body

from backend.models.pipeline import (
    PipelineControlRequest,
    PipelineControlResponse,
    PipelineStatusResponse,
    RecoverRequest,
    RecoveryResponse,
)
from backend.services.pipeline_service import PipelineService

router = APIRouter(prefix="/pipeline", tags=["Pipeline"])


def get_pipeline_service() -> PipelineService:
    from backend.app import (
        get_circuit_breaker,
        get_remediation_controller,
        get_state_manager,
    )
    return PipelineService(
        state_manager=get_state_manager(),
        circuit_breaker=get_circuit_breaker(),
        remediation_controller=get_remediation_controller(),
    )


@router.get(
    "/status",
    response_model=PipelineStatusResponse,
    summary="Authoritative Pipeline Status",
    description="Returns the authoritative current IceStream pipeline state from PipelineStateManager.",
)
def get_pipeline_status() -> PipelineStatusResponse:
    service = get_pipeline_service()
    return service.get_status()


@router.post(
    "/pause",
    response_model=PipelineControlResponse,
    summary="Pause Pipeline Operations",
    description="Manually pause pipeline processing using authoritative state transitions.",
)
def pause_pipeline(
    payload: Optional[PipelineControlRequest] = Body(default=None),
) -> PipelineControlResponse:
    service = get_pipeline_service()
    reason = payload.reason if payload else None
    return service.pause(reason=reason)


@router.post(
    "/resume",
    response_model=PipelineControlResponse,
    summary="Resume Pipeline Operations",
    description="Manually resume pipeline processing. Blocked with 409 Conflict if circuit breaker is OPEN.",
)
def resume_pipeline(
    payload: Optional[PipelineControlRequest] = Body(default=None),
) -> PipelineControlResponse:
    service = get_pipeline_service()
    reason = payload.reason if payload else None
    return service.resume(reason=reason)


@router.post(
    "/recover",
    response_model=RecoveryResponse,
    summary="Trigger Automated Recovery",
    description="Starts the existing remediation workflow when recovery is eligible.",
)
def recover_pipeline(
    payload: Optional[RecoverRequest] = Body(default=None),
) -> RecoveryResponse:
    service = get_pipeline_service()
    inc_id = payload.incident_id if payload else None
    ctx = payload.context if payload else None
    return service.recover(incident_id=inc_id, context=ctx)
