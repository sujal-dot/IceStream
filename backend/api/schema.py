"""Schema Drift API Router."""

from fastapi import APIRouter

from backend.models.schema import SchemaDriftResponse
from backend.services.schema_service import SchemaService

router = APIRouter(prefix="/schema", tags=["Schema"])


def get_schema_service() -> SchemaService:
    return SchemaService()


@router.get(
    "/drift",
    response_model=SchemaDriftResponse,
    summary="Get Schema Drift Status",
    description="Returns actual schema drift information using Day 17 Schema Drift Detector and Schema Registry.",
)
def get_schema_drift() -> SchemaDriftResponse:
    service = get_schema_service()
    return service.get_schema_drift()
