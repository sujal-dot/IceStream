"""Observability Telemetry Backend Service for IceStream.

Provides REST endpoints for pipeline error rate metrics, circuit breaker state,
authoritative pipeline state, self-healing remediation, and service health monitoring.
"""

from datetime import datetime, timezone
import logging
import os
import sys
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Ensure quality-engine directory is on sys.path for metrics & remediation imports
QUALITY_ENGINE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "quality-engine"))
if QUALITY_ENGINE_DIR not in sys.path:
    sys.path.insert(0, QUALITY_ENGINE_DIR)

from metrics.error_rate import ErrorRateConfig, ErrorRateEngine, HealthStatus
from circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitState
from remediation.state_manager import PipelineStateManager, PipelineState
from remediation.controller import RemediationController
from storage.db import StorageBackend, get_db_storage

# Import API Routers
from backend.api import incidents, metrics, pipeline, lineage, quality, schema, events
from backend.database.connection import check_db_health

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
        version="0.23.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_tags=[
            {"name": "Health", "description": "API & Dependency Health Checks"},
            {"name": "Pipeline", "description": "Authoritative Pipeline State & Manual Control Operations"},
            {"name": "Metrics", "description": "Real-Time Telemetry, Error-Rate & Circuit Breaker Metrics"},
            {"name": "Incidents", "description": "Pipeline Incident Records & Remediation History"},
            {"name": "Lineage", "description": "End-to-End Data Lineage Graph (React Flow Compatible)"},
            {"name": "Quality", "description": "Data Quality Engine Summaries & Severity Metrics"},
            {"name": "Schema", "description": "Schema Drift Detector & Version Compatibility"},
            {"name": "Events", "description": "Sanitized Event Metadata Inspection"},
        ],
    )

    # CORS Configuration
    origins_str = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173")
    origins = [o.strip() for o in origins_str.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register Routers
    app.include_router(pipeline.router)
    app.include_router(metrics.router)
    app.include_router(incidents.router)
    app.include_router(lineage.router)
    app.include_router(quality.router)
    app.include_router(schema.router)
    app.include_router(events.router)

    @app.get(
        "/health",
        tags=["Health"],
        summary="Service Health Check",
        description="Verify backend HTTP service availability and non-sensitive dependency status (distinguished from pipeline data health).",
    )
    def health_check() -> Dict[str, Any]:
        """Return HTTP backend service health and dependency status."""
        db_status = check_db_health(get_db_storage())
        return {
            "status": "ok",
            "service": "icestream-backend",
            "version": "0.23.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dependencies": {
                "postgres": db_status,
                "quality_engine": "ok",
                "iceberg_catalog": "ok",
            },
        }

    @app.get(
        "/circuit-breaker",
        tags=["Metrics"],
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

    @app.post(
        "/pipeline/remediate",
        tags=["Pipeline"],
        summary="Trigger Automated Remediation (Legacy Alias)",
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

    return app


app = create_app()
