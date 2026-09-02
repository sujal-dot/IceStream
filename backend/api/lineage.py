"""Data Lineage API Router."""

from fastapi import APIRouter

from backend.models.lineage import LineageResponse
from backend.services.lineage_service import LineageService

router = APIRouter(prefix="/lineage", tags=["Lineage"])


def get_lineage_service() -> LineageService:
    from backend.app import get_circuit_breaker, get_error_rate_engine, get_state_manager
    return LineageService(
        state_manager=get_state_manager(),
        error_rate_engine=get_error_rate_engine(),
        circuit_breaker=get_circuit_breaker(),
    )


@router.get(
    "",
    response_model=LineageResponse,
    summary="Get End-to-End Data Lineage",
    description="Returns React Flow compatible node/edge structure representing IceStream architectural and runtime data lineage.",
)
def get_lineage() -> LineageResponse:
    service = get_lineage_service()
    return service.get_lineage()
