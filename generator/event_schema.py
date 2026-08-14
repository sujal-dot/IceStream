"""Event schema definition and data models for checkout events."""

from dataclasses import asdict, dataclass
from typing import Any, Dict


@dataclass
class CheckoutEvent:
    event_id: str
    event_time: str
    event_type: str
    customer_id: str
    session_id: str
    order_id: str
    product_id: str
    quantity: int
    unit_price: float
    amount: float
    currency: str
    payment_method: str
    payment_status: str
    device: str
    country: str
    source: str
    source_version: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert dataclass instance to a dictionary payload."""
        return asdict(self)


REQUIRED_FIELDS = [
    "event_id",
    "event_time",
    "event_type",
    "customer_id",
    "session_id",
    "order_id",
    "product_id",
    "quantity",
    "unit_price",
    "amount",
    "currency",
    "payment_method",
    "payment_status",
    "device",
    "country",
    "source",
    "source_version",
]
