"""Data Quality API Router."""

from fastapi import APIRouter

from backend.models.quality import QualityResponse
from backend.services.quality_service import QualityService

router = APIRouter(prefix="/quality", tags=["Quality"])


def get_quality_service() -> QualityService:
    from backend.app import get_error_rate_engine
    return QualityService(error_rate_engine=get_error_rate_engine())


@router.get(
    "",
    response_model=QualityResponse,
    summary="Get Data Quality Overview",
    description="Returns current 1m & 5m error rates, total/valid/failed event counts, failed rules, and severity breakdown from QualityEngine.",
)
def get_quality() -> QualityResponse:
    service = get_quality_service()
    return service.get_quality_status()
