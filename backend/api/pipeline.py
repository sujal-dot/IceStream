"""Pipeline Status and Control API Router."""

from typing import Optional
from fastapi import APIRouter, Body, Depends

from backend.models.pipeline import (
    FlinkTelemetryResponse,
    PipelineControlRequest,
    PipelineControlResponse,
    PipelineStatusResponse,
    RecoverRequest,
    RecoveryResponse,
)
from backend.services.pipeline_service import PipelineService
from backend.security import verify_api_token

router = APIRouter(prefix="/pipeline", tags=["Pipeline"])


def get_pipeline_service() -> PipelineService:
    from backend.app import (
        get_circuit_breaker,
        get_flink_controller,
        get_remediation_controller,
        get_state_manager,
    )
    return PipelineService(
        state_manager=get_state_manager(),
        circuit_breaker=get_circuit_breaker(),
        remediation_controller=get_remediation_controller(),
        flink_controller=get_flink_controller(),
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
    dependencies=[Depends(verify_api_token)],
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
    dependencies=[Depends(verify_api_token)],
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
    dependencies=[Depends(verify_api_token)],
)
def recover_pipeline(
    payload: Optional[RecoverRequest] = Body(default=None),
) -> RecoveryResponse:
    service = get_pipeline_service()
    inc_id = payload.incident_id if payload else None
    ctx = payload.context if payload else None
    return service.recover(incident_id=inc_id, context=ctx)


@router.get(
    "/flink",
    response_model=FlinkTelemetryResponse,
    summary="Get Flink Cluster & Checkpoint Telemetry",
    description="Returns real-time Flink cluster capacity, running jobs, checkpoint history, and exception metrics.",
)
def get_flink_telemetry() -> FlinkTelemetryResponse:
    service = get_pipeline_service()
    return service.get_flink_telemetry()

