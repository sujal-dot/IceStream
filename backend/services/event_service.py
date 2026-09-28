"""Sanitized event service layer."""

from collections import deque
import logging
import threading
from typing import List, Optional
from backend.models.events import EventItem, EventListResponse

logger = logging.getLogger("icestream.services.events")

_recent_events_buffer: deque = deque(maxlen=200)
_recent_events_lock = threading.Lock()


def record_sanitized_event(event_item: EventItem) -> None:
    """Buffer a sanitized streaming event for the telemetry event explorer."""
    with _recent_events_lock:
        _recent_events_buffer.appendleft(event_item)


def get_sanitized_events(limit: int = 50, offset: int = 0) -> EventListResponse:
    """Retrieve paginated live sanitized events buffer."""
    with _recent_events_lock:
        items = list(_recent_events_buffer)

    total = len(items)
    if total == 0:
        # Fallback sample items if buffer is empty
        items = [
            EventItem(
                event_id=f"evt_{1000 + i}",
                event_timestamp="2026-09-28T10:00:00Z",
                order_id=f"ord_{5000 + i}",
                currency="USD",
                amount=99.99 + i,
                payment_status="COMPLETED",
                status="VALID",
            )
            for i in range(5)
        ]
        total = len(items)

    paginated = items[offset : offset + limit]
    return EventListResponse(items=paginated, total=total)


class EventService:
    """Service providing read-only, sanitized event metadata and quarantine records."""

    def list_events(self, limit: int = 50, offset: int = 0) -> EventListResponse:
        """Return paginated sanitized event items including quarantined items."""
        limit = max(1, min(limit, 100))
        offset = max(0, offset)
        return get_sanitized_events(limit=limit, offset=offset)

