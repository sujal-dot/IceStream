"""Metrics API Router."""

from fastapi import APIRouter

from backend.models.metrics import MetricsResponse
from backend.services.metrics_service import MetricsService

router = APIRouter(prefix="/metrics", tags=["Metrics"])


def get_metrics_service() -> MetricsService:
    from backend.app import get_circuit_breaker, get_error_rate_engine, get_state_manager
    return MetricsService(
        error_rate_engine=get_error_rate_engine(),
        circuit_breaker=get_circuit_breaker(),
        state_manager=get_state_manager(),
    )


@router.get(
    "",
    response_model=MetricsResponse,
    summary="Pipeline Metrics & Telemetry",
    description="Returns real-time data-quality, circuit-breaker, quarantine, and remediation metrics.",
)
def get_metrics() -> MetricsResponse:
    service = get_metrics_service()
    return service.get_metrics()
