"""Observability Telemetry Backend Service for IceStream.

Provides REST endpoints for pipeline error rate metrics, circuit breaker state,
authoritative pipeline state, self-healing remediation, and service health monitoring.
"""

from datetime import datetime, timezone
import logging
import os
import sys
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse

# Ensure quality-engine directory is on sys.path for metrics & remediation imports
QUALITY_ENGINE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "quality-engine"))
if QUALITY_ENGINE_DIR not in sys.path:
    sys.path.insert(0, QUALITY_ENGINE_DIR)

from metrics.error_rate import ErrorRateConfig, ErrorRateEngine, HealthStatus
from circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitState
from remediation.state_manager import PipelineStateManager, PipelineState
from remediation.controller import RemediationController

logger = logging.getLogger("icestream.backend")

# Global singleton instances
_global_error_rate_engine: Optional[ErrorRateEngine] = None
_global_circuit_breaker: Optional[CircuitBreaker] = None
_global_state_manager: Optional[PipelineStateManager] = None
_global_remediation_controller: Optional[RemediationController] = None


def get_error_rate_engine() -> ErrorRateEngine:
    """Retrieve or initialize the global shared ErrorRateEngine instance."""
    global _global_error_rate_engine
    if _global_error_rate_engine is None:
        _global_error_rate_engine = ErrorRateEngine()
    return _global_error_rate_engine


def set_error_rate_engine(engine: Optional[ErrorRateEngine]) -> None:
    """Override or reset the global shared ErrorRateEngine instance (for testing)."""
    global _global_error_rate_engine
    _global_error_rate_engine = engine


def get_circuit_breaker() -> CircuitBreaker:
    """Retrieve or initialize the global shared CircuitBreaker instance."""
    global _global_circuit_breaker
    if _global_circuit_breaker is None:
        _global_circuit_breaker = CircuitBreaker()
    return _global_circuit_breaker


def set_circuit_breaker(breaker: Optional[CircuitBreaker]) -> None:
    """Override or reset the global shared CircuitBreaker instance (for testing)."""
    global _global_circuit_breaker
    _global_circuit_breaker = breaker


def get_state_manager() -> PipelineStateManager:
    """Retrieve or initialize global PipelineStateManager."""
    global _global_state_manager
    if _global_state_manager is None:
        _global_state_manager = PipelineStateManager(pipeline_id="icestream")
    return _global_state_manager


def set_state_manager(manager: Optional[PipelineStateManager]) -> None:
    """Override global PipelineStateManager (for testing)."""
    global _global_state_manager
    _global_state_manager = manager


def get_remediation_controller() -> RemediationController:
    """Retrieve or initialize global RemediationController."""
    global _global_remediation_controller
    if _global_remediation_controller is None:
        state_mgr = get_state_manager()
        breaker = get_circuit_breaker()
        _global_remediation_controller = RemediationController(
            pipeline_id="icestream",
            state_manager=state_mgr,
            circuit_breaker=breaker,
        )
    return _global_remediation_controller


def set_remediation_controller(controller: Optional[RemediationController]) -> None:
    """Override global RemediationController (for testing)."""
    global _global_remediation_controller
    _global_remediation_controller = controller


def create_app(
    engine: Optional[ErrorRateEngine] = None,
    breaker: Optional[CircuitBreaker] = None,
    state_manager: Optional[PipelineStateManager] = None,
    controller: Optional[RemediationController] = None,
) -> FastAPI:
    """Construct and configure the FastAPI Observability Backend application."""
    if engine is not None:
        set_error_rate_engine(engine)
    if breaker is not None:
        set_circuit_breaker(breaker)
    if state_manager is not None:
        set_state_manager(state_manager)
    if controller is not None:
        set_remediation_controller(controller)

    app = FastAPI(
        title="IceStream Observability Telemetry API",
        description="Real-Time Lakehouse Observability & Automated Self-Healing Pipeline Backend",
        version="0.22.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    @app.get(
        "/health",
        summary="Service Health Check",
        description="Verify backend HTTP service availability (distinguished from pipeline data health).",
    )
    def health_check() -> Dict[str, str]:
        """Return HTTP backend service health."""
        return {
            "service": "icestream-backend",
            "status": "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @app.get(
        "/circuit-breaker",
        summary="Circuit Breaker Status",
        description="Retrieve current authoritative Circuit Breaker state machine status.",
    )
    def get_circuit_breaker_status() -> Dict[str, Any]:
        """Retrieve current circuit breaker state, thresholds, and transition counters (read-only)."""
        try:
            target_breaker = get_circuit_breaker()
            return target_breaker.get_status().to_dict()
        except Exception as e:
            logger.exception("Failed to retrieve circuit breaker status: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Internal circuit breaker status error: {str(e)}",
            ) from e

    @app.get(
        "/pipeline/status",
        summary="Authoritative Pipeline Status",
        description="Retrieve current backend-owned authoritative pipeline state, active incident, and recovery stage.",
    )
    def get_pipeline_status() -> Dict[str, Any]:
        """Return authoritative backend pipeline state response."""
        try:
            target_manager = get_state_manager()
            st_dict = target_manager.get_state()
            active_inc_id = st_dict.get("active_incident_id")

            stage_name = st_dict.get("state", "RUNNING")
            return {
                "pipeline_id": st_dict.get("pipeline_id", "icestream"),
                "state": st_dict.get("state", "RUNNING"),
                "previous_state": st_dict.get("previous_state"),
                "reason": st_dict.get("reason"),
                "incident_id": active_inc_id,
                "recovery_attempt": st_dict.get("recovery_attempt", 0),
                "stage": stage_name,
                "updated_at": st_dict.get("updated_at"),
                "last_error": st_dict.get("last_error"),
            }
        except Exception as e:
            logger.exception("Failed to retrieve pipeline status: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve pipeline status: {str(e)}",
            ) from e

    @app.get(
        "/incidents/{incident_id}",
        summary="Pipeline Incident Details",
        description="Retrieve incident details, circuit status, remediation stage, and attempts history.",
    )
    def get_incident_details(incident_id: str) -> Dict[str, Any]:
        """Retrieve incident detail record from backend storage."""
        try:
            target_controller = get_remediation_controller()
            inc = target_controller.storage.get_incident(incident_id)
            if not inc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Incident '{incident_id}' not found",
                )
            attempts = target_controller.storage.get_remediation_attempts(incident_id)
            return {
                "incident": inc,
                "circuit_state": inc.get("circuit_state", "OPEN"),
                "remediation_stage": get_state_manager().current_state.value,
                "recovery_attempts": len(attempts),
                "attempts_history": attempts,
                "resolved_at": inc.get("resolved_at"),
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Failed to fetch incident details: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error fetching incident details: {str(e)}",
            ) from e

    @app.post(
        "/pipeline/remediate",
        summary="Trigger Automated Remediation",
        description="Execute self-healing remediation workflow for an incident.",
    )
    def trigger_remediation(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Trigger backend remediation execution."""
        p = payload or {}
        inc_id = p.get("incident_id")
        try:
            target_controller = get_remediation_controller()
            if not inc_id:
                inc = target_controller.get_or_create_incident(
                    trigger="API_TRIGGERED",
                    error_rate=0.05,
                )
                inc_id = inc["incident_id"]

            res = target_controller.execute_remediation(incident_id=inc_id, context=p)
            return res.to_dict()
        except Exception as e:
            logger.exception("Failed to execute remediation: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Remediation failure: {str(e)}",
            ) from e

    @app.get(
        "/metrics",
        summary="Pipeline Metrics & Telemetry",
        description="Retrieve real-time error rates, pipeline health, circuit breaker, and authoritative state metrics.",
    )
    def get_metrics() -> Dict[str, Any]:
        """Retrieve real-time rolling window metrics snapshot without mutating state."""
        try:
            target_engine = get_error_rate_engine()
            target_breaker = get_circuit_breaker()
            target_manager = get_state_manager()

            snapshot = target_engine.get_metrics_snapshot()

            cb_status = target_breaker.get_status().to_dict()
            snapshot["circuit_breaker"] = {
                "state": cb_status["state"],
                "enabled": cb_status["enabled"],
                "can_process": cb_status["can_process"],
                "can_probe": cb_status["can_probe"],
                "error_rate": cb_status["error_rate"],
                "threshold": cb_status["threshold"],
            }
            snapshot["pipeline_state"] = target_manager.get_state()
            return snapshot
        except Exception as e:
            logger.exception("Failed to calculate pipeline metrics: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Internal metrics calculation failure: {str(e)}",
            ) from e

    return app


app = create_app()
