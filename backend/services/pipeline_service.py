"""Pipeline service layer controlling authoritative pipeline state and remediation execution."""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional
from fastapi import HTTPException, status

from backend.models.pipeline import (
    FlinkTelemetryResponse,
    PipelineControlResponse,
    PipelineStatusResponse,
    RecoveryResponse,
)

logger = logging.getLogger("icestream.services.pipeline")


class PipelineService:
    """Service layer for pipeline state control operations."""

    def __init__(
        self,
        state_manager=None,
        circuit_breaker=None,
        remediation_controller=None,
        flink_controller=None,
    ):
        self.state_manager = state_manager
        self.circuit_breaker = circuit_breaker
        self.remediation_controller = remediation_controller
        self.flink_controller = flink_controller or (
            getattr(remediation_controller, "flink_controller", None)
            if remediation_controller
            else None
        )

    def get_status(self) -> PipelineStatusResponse:
        """Return authoritative backend pipeline state enriched with Flink streaming telemetry."""
        if not self.state_manager:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="PipelineStateManager is unavailable",
            )

        st = self.state_manager.get_state()
        state_str = str(st.get("state", "RUNNING"))

        flink_job_id = None
        flink_job_state = None
        latest_chk_path = None
        chk_completed = None

        if self.flink_controller:
            try:
                active_id = self.flink_controller.get_active_job_id()
                if active_id:
                    flink_job_id = active_id
                    flink_job_state = self.flink_controller.get_job_status(active_id)
                    chk_metrics = self.flink_controller.get_checkpoint_metrics(active_id)
                    if chk_metrics and chk_metrics.get("available"):
                        latest_chk = chk_metrics.get("latest_checkpoint")
                        if latest_chk:
                            latest_chk_path = latest_chk.get("external_path")
                        chk_completed = chk_metrics.get("counts", {}).get("completed")
            except Exception as e:
                logger.debug("Failed to retrieve Flink status for get_status: %s", e)

        return PipelineStatusResponse(
            pipeline_id=str(st.get("pipeline_id", "icestream")),
            state=state_str,
            previous_state=st.get("previous_state"),
            reason=st.get("reason"),
            incident_id=st.get("active_incident_id"),
            recovery_attempt=int(st.get("recovery_attempt", 0)),
            stage=state_str,
            last_error=st.get("last_error"),
            updated_at=str(st.get("updated_at")),
            flink_job_id=flink_job_id,
            flink_job_state=flink_job_state,
            latest_checkpoint_path=latest_chk_path,
            checkpoints_completed=chk_completed,
        )

    def get_flink_telemetry(self) -> FlinkTelemetryResponse:
        """Return real-time Flink cluster, job, and checkpoint telemetry."""
        if not self.flink_controller:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="FlinkController is unavailable",
            )
        summary = self.flink_controller.get_telemetry_summary()
        return FlinkTelemetryResponse(
            cluster=summary.get("cluster", {}),
            active_job=summary.get("active_job", {}),
            retrieved_at=datetime.now(timezone.utc).isoformat(),
        )

    def pause(self, reason: Optional[str] = None) -> PipelineControlResponse:
        """Pause pipeline operations explicitly (idempotent)."""
        if not self.state_manager:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="PipelineStateManager is unavailable",
            )

        st = self.state_manager.get_state()
        current_state = str(st.get("state", "RUNNING"))

        if current_state == "PAUSED":
            return PipelineControlResponse(
                pipeline_id=str(st.get("pipeline_id", "icestream")),
                state="PAUSED",
                previous_state=st.get("previous_state"),
                message="Pipeline is already paused.",
                updated_at=datetime.now(timezone.utc).isoformat(),
            )

        if self.remediation_controller and hasattr(self.remediation_controller, "flink_controller") and self.remediation_controller.flink_controller:
            self.remediation_controller.flink_controller.pause_job()

        new_st = self.state_manager.transition_to(
            to_state="PAUSED",
            reason=reason or "Manual pause initiated via API",
        )

        return PipelineControlResponse(
            pipeline_id=str(new_st.get("pipeline_id", "icestream")),
            state="PAUSED",
            previous_state=current_state,
            message="Pipeline paused successfully.",
            updated_at=datetime.now(timezone.utc).isoformat(),
        )

    def resume(self, reason: Optional[str] = None) -> PipelineControlResponse:
        """Resume pipeline operations with safety check against OPEN circuit breaker."""
        if not self.state_manager:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="PipelineStateManager is unavailable",
            )

        # Safety Check: Do NOT allow manual resume to bypass an OPEN Circuit Breaker
        if self.circuit_breaker:
            cb_state = str(self.circuit_breaker.state.name)
            if cb_state == "OPEN":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error": "PIPELINE_PROTECTED",
                        "message": "Pipeline cannot resume while circuit breaker is OPEN.",
                    },
                )

        st = self.state_manager.get_state()
        current_state = str(st.get("state", "RUNNING"))

        if current_state == "RUNNING":
            return PipelineControlResponse(
                pipeline_id=str(st.get("pipeline_id", "icestream")),
                state="RUNNING",
                previous_state=st.get("previous_state"),
                message="Pipeline is already running.",
                updated_at=datetime.now(timezone.utc).isoformat(),
            )

        if self.remediation_controller and hasattr(self.remediation_controller, "flink_controller") and self.remediation_controller.flink_controller:
            self.remediation_controller.flink_controller.resume_job()

        new_st = self.state_manager.transition_to(
            to_state="RUNNING",
            reason=reason or "Manual resume initiated via API",
        )

        return PipelineControlResponse(
            pipeline_id=str(new_st.get("pipeline_id", "icestream")),
            state="RUNNING",
            previous_state=current_state,
            message="Pipeline resumed successfully.",
            updated_at=datetime.now(timezone.utc).isoformat(),
        )

    def recover(self, incident_id: Optional[str] = None, context: Optional[dict] = None) -> RecoveryResponse:
        """Trigger self-healing remediation workflow."""
        if not self.remediation_controller:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="RemediationController is unavailable",
            )

        st = self.state_manager.get_state() if self.state_manager else {}
        curr_state = str(st.get("state", "RUNNING"))

        # Check if already remediating
        inc_id = incident_id or st.get("active_incident_id")
        if curr_state in ("REMEDIATING", "REFETCHING", "REPROCESSING", "VALIDATING"):
            return RecoveryResponse(
                incident_id=inc_id or "inc_active",
                status="ALREADY_RUNNING",
                pipeline_state=curr_state,
                recovery_attempt=int(st.get("recovery_attempt", 1)),
                message="Remediation workflow is already in progress.",
            )

        # Ensure an incident exists or create/get eligible incident
        if not inc_id:
            # Check if recovery is required
            if curr_state == "RUNNING" and (not self.circuit_breaker or self.circuit_breaker.state.name == "CLOSED"):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error": "RECOVERY_NOT_REQUIRED",
                        "message": "Pipeline is healthy and no active incident requires recovery.",
                    },
                )
            inc = self.remediation_controller.get_or_create_incident(trigger="API_RECOVERY")
            inc_id = inc["incident_id"]

        # Execute remediation using existing domain controller
        result = self.remediation_controller.execute_remediation(
            incident_id=inc_id, context=context
        )

        resulting_state = self.state_manager.get_state().get("state", "RUNNING") if self.state_manager else result.stage

        return RecoveryResponse(
            incident_id=inc_id,
            status="STARTED" if result.success else "FAILED",
            pipeline_state=resulting_state,
            recovery_attempt=result.attempt,
            message=result.error or "Remediation executed successfully.",
        )
