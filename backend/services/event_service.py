"""Sanitized event service layer."""

import logging
from typing import List, Optional
from backend.models.events import EventItem, EventListResponse

logger = logging.getLogger("icestream.services.events")


class EventService:
    """Service providing read-only, sanitized event metadata."""

    def list_events(self, limit: int = 50, offset: int = 0) -> EventListResponse:
        """Return paginated sanitized event items."""
        limit = max(1, min(limit, 100))
        offset = max(0, offset)

        # Sample sanitized metadata list
        sample_items = [
            EventItem(
                event_id=f"evt_{1000 + i}",
                event_timestamp="2026-09-02T10:00:00Z",
                order_id=f"ord_{5000 + i}",
                currency="USD",
                amount=99.99 + i,
                payment_status="COMPLETED",
                status="VALID",
            )
            for i in range(10)
        ]

        paginated = sample_items[offset : offset + limit]
        return EventListResponse(items=paginated, total=len(sample_items))
