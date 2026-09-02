"""Sanitized Events API Router."""

from fastapi import APIRouter, Query

from backend.models.events import EventListResponse
from backend.services.event_service import EventService

router = APIRouter(prefix="/events", tags=["Events"])


def get_event_service() -> EventService:
    return EventService()


@router.get(
    "",
    response_model=EventListResponse,
    summary="List Sanitized Events",
    description="Retrieve paginated list of sanitized event metadata. Payment data and secrets are never exposed.",
)
def list_events(
    limit: int = Query(50, ge=1, le=100, description="Number of events to return"),
    offset: int = Query(0, ge=0, description="Number of events to skip"),
) -> EventListResponse:
    service = get_event_service()
    return service.list_events(limit=limit, offset=offset)
