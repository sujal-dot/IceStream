"""Observability Telemetry Backend Service for IceStream.

Provides REST endpoints for pipeline error rate metrics and service health monitoring.
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

logger = logging.getLogger("icestream.backend")

# Global singleton ErrorRateEngine instance for backend API
_global_error_rate_engine: Optional[ErrorRateEngine] = None


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


def create_app(engine: Optional[ErrorRateEngine] = None) -> FastAPI:
    """Construct and configure the FastAPI Observability Backend application."""
    if engine is not None:
        set_error_rate_engine(engine)

    app = FastAPI(
        title="IceStream Observability Telemetry API",
        description="Real-Time Lakehouse Observability & Error Rate Telemetry Backend",
        version="0.19.0",
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
        "/metrics",
        summary="Pipeline Metrics & Error Rates",
        description="Retrieve real-time rolling window error rates (1m and 5m) and pipeline health classification.",
    )
    def get_metrics() -> Dict[str, Any]:
        """Retrieve real-time rolling window metrics snapshot without mutating state."""
        try:
            target_engine = get_error_rate_engine()
            snapshot = target_engine.get_metrics_snapshot()
            return snapshot
        except Exception as e:
            logger.exception("Failed to calculate pipeline metrics: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Internal metrics calculation failure: {str(e)}",
            ) from e

    return app


app = create_app()
