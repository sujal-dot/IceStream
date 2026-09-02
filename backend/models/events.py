"""Sanitized event API models."""

from typing import List, Optional
from pydantic import BaseModel, Field


class EventItem(BaseModel):
    """Sanitized metadata event item."""

    event_id: str
    event_timestamp: str
    order_id: Optional[str] = None
    currency: Optional[str] = None
    amount: Optional[float] = None
    payment_status: Optional[str] = None
    status: str = "VALID"


class EventListResponse(BaseModel):
    """Paginated list of sanitized event items."""

    items: List[EventItem]
    total: int
