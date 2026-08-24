"""Event model and internal representations for IceStream Quality Engine."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass
class QualityEvent:
    """Internal strongly-typed representation of an IceStream event.
    
    Fields are intentionally Optional to allow corrupted, malformed, or
    schema-violating events to be parsed and evaluated by quality rules
    without crashing at the deserialization stage.
    """

    event_id: Optional[str] = None
    event_time: Optional[str] = None
    customer_id: Optional[str] = None
    session_id: Optional[str] = None
    order_id: Optional[str] = None
    product_id: Optional[str] = None
    quantity: Optional[int] = None
    unit_price: Optional[float] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    payment_method: Optional[str] = None
    payment_status: Optional[str] = None
    device: Optional[str] = None
    country: Optional[str] = None
    source: Optional[str] = None
    source_version: Optional[str] = None
    ingestion_time: Optional[str] = None
    raw_payload: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QualityEvent":
        """Construct a QualityEvent from a raw dictionary payload."""
        if not isinstance(data, dict):
            raise TypeError(f"Expected dict, got {type(data).__name__}")

        known_fields = {
            "event_id",
            "event_time",
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
            "ingestion_time",
        }

        extracted = {}
        for k in known_fields:
            if k in data:
                val = data[k]
                extracted[k] = val

        # Handle numeric conversions safely if present
        if "quantity" in extracted and extracted["quantity"] is not None:
            try:
                extracted["quantity"] = int(extracted["quantity"])
            except (ValueError, TypeError):
                pass

        if "amount" in extracted and extracted["amount"] is not None:
            try:
                extracted["amount"] = float(extracted["amount"])
            except (ValueError, TypeError):
                pass

        if "unit_price" in extracted and extracted["unit_price"] is not None:
            try:
                extracted["unit_price"] = float(extracted["unit_price"])
            except (ValueError, TypeError):
                pass

        return cls(raw_payload=dict(data), **extracted)

    def to_dict(self) -> Dict[str, Any]:
        """Convert QualityEvent to a dictionary."""
        result = {
            "event_id": self.event_id,
            "event_time": self.event_time,
            "customer_id": self.customer_id,
            "session_id": self.session_id,
            "order_id": self.order_id,
            "product_id": self.product_id,
            "quantity": self.quantity,
            "unit_price": self.unit_price,
            "amount": self.amount,
            "currency": self.currency,
            "payment_method": self.payment_method,
            "payment_status": self.payment_status,
            "device": self.device,
            "country": self.country,
            "source": self.source,
            "source_version": self.source_version,
            "ingestion_time": self.ingestion_time,
        }
        # Merge any extra keys from raw_payload
        for k, v in self.raw_payload.items():
            if k not in result:
                result[k] = v
        return result

    def get_field(self, field_name: str, default: Any = None) -> Any:
        """Get field value by name, falling back to raw payload or default."""
        if hasattr(self, field_name):
            val = getattr(self, field_name)
            if val is not None:
                return val
        return self.raw_payload.get(field_name, default)
