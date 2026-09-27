"""Sanitized event service layer."""

import logging
from typing import List, Optional
from backend.models.events import EventItem, EventListResponse

logger = logging.getLogger("icestream.services.events")


class EventService:
    """Service providing read-only, sanitized event metadata and quarantine records."""

    def list_events(self, limit: int = 50, offset: int = 0) -> EventListResponse:
        """Return paginated sanitized event items including quarantined items."""
        limit = max(1, min(limit, 100))
        offset = max(0, offset)

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
            for i in range(8)
        ] + [
            EventItem(
                event_id=f"q_evt_{8000 + i}",
                event_timestamp="2026-09-02T10:05:00Z",
                order_id=f"ord_bad_{9000 + i}",
                currency="USD",
                amount=-15.50 if i % 2 == 0 else None,
                payment_status="QUARANTINED",
                status="QUARANTINED",
                failure_reason="Rule violation: NOT_NULL / Positive amount constraint failed on mandatory payload attributes.",
                schema_version="v2.1.0",
                payload_json=f'{{\n  "event_id": "q_evt_{8000 + i}",\n  "order_id": "ord_bad_{9000 + i}",\n  "amount": {-15.50 if i % 2 == 0 else "null"},\n  "currency": "USD",\n  "error": "INVALID_AMOUNT_OR_NULL"\n}}',
            )
            for i in range(5)
        ]

        paginated = sample_items[offset : offset + limit]
        return EventListResponse(items=paginated, total=len(sample_items))
