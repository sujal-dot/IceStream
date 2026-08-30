"""Observability Telemetry Backend Service for IceStream.

Provides REST endpoints for pipeline error rate metrics, circuit breaker state, and service health monitoring.
"""

from datetime import datetime, timezone
import logging
import os
import sys
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse

# Ensure quality-engine directory is on sys.path for metrics imports
QUALITY_ENGINE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "quality-engine"))
if QUALITY_ENGINE_DIR not in sys.path:
    sys.path.insert(0, QUALITY_ENGINE_DIR)

from metrics.error_rate import ErrorRateConfig, ErrorRateEngine, HealthStatus
from circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitState

logger = logging.getLogger("icestream.backend")

# Global singleton ErrorRateEngine & CircuitBreaker instances for backend API
_global_error_rate_engine: Optional[ErrorRateEngine] = None
_global_circuit_breaker: Optional[CircuitBreaker] = None


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


def create_app(
    engine: Optional[ErrorRateEngine] = None,
    breaker: Optional[CircuitBreaker] = None,
) -> FastAPI:
    """Construct and configure the FastAPI Observability Backend application."""
    if engine is not None:
        set_error_rate_engine(engine)
    if breaker is not None:
        set_circuit_breaker(breaker)

    app = FastAPI(
        title="IceStream Observability Telemetry API",
        description="Real-Time Lakehouse Observability & Error Rate Telemetry Backend",
        version="0.20.0",
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
        "/metrics",
        summary="Pipeline Metrics & Error Rates",
        description="Retrieve real-time rolling window error rates (1m and 5m), pipeline health, and circuit breaker state.",
    )
    def get_metrics() -> Dict[str, Any]:
        """Retrieve real-time rolling window metrics snapshot without mutating state."""
        try:
            target_engine = get_error_rate_engine()
            target_breaker = get_circuit_breaker()

            snapshot = target_engine.get_metrics_snapshot()

            # Attach circuit breaker status to snapshot for backward-compatible telemetry
            cb_status = target_breaker.get_status().to_dict()
            snapshot["circuit_breaker"] = {
                "state": cb_status["state"],
                "enabled": cb_status["enabled"],
                "can_process": cb_status["can_process"],
                "can_probe": cb_status["can_probe"],
                "error_rate": cb_status["error_rate"],
                "threshold": cb_status["threshold"],
            }
            return snapshot
        except Exception as e:
            logger.exception("Failed to calculate pipeline metrics: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Internal metrics calculation failure: {str(e)}",
            ) from e

    return app


app = create_app()
