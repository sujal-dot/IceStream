"""Source Adapter for Self-Healing Remediation Pipeline.

Provides abstract SourceAdapter interface and LocalSourceAdapter implementation for deterministic source re-fetching.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("icestream.remediation.source_adapter")


class SourceAdapter(ABC):
    """Abstract interface for re-fetching source data during recovery."""

    @abstractmethod
    def fetch_for_recovery(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fetch corrected/re-fetched source payloads given recovery context."""
        pass

    @abstractmethod
    def get_source_reference(self) -> str:
        """Return identifiable source reference or origin URI for audit logging."""
        pass


def make_valid_checkout_event(
    event_id: str = "evt_recovery_001",
    customer_id: str = "cust_recovery_001",
    amount: float = 1499.00,
    currency: str = "INR",
) -> Dict[str, Any]:
    """Helper to create a fully schema-compliant checkout event."""
    ts = datetime.now(timezone.utc).isoformat()
    return {
        "event_id": event_id,
        "event_type": "checkout",
        "event_time": ts,
        "customer_id": customer_id,
        "session_id": f"sess_{customer_id}",
        "order_id": f"ord_{event_id}",
        "product_id": "prod_100",
        "quantity": 1,
        "unit_price": amount,
        "amount": amount,
        "currency": currency,
        "payment_method": "credit_card",
        "payment_status": "SUCCESS",
        "device": "desktop",
        "country": "IN",
        "source": "icestream_web",
        "source_version": "v1.0",
        "ingestion_time": ts,
        "schema_version": "v1.0",
    }


class LocalSourceAdapter(SourceAdapter):
    """Local portfolio/demo SourceAdapter providing deterministic corrected source data.

    Supports re-fetching corrected versions of corrupted/quarantined events.
    """

    def __init__(self, source_reference: str = "replay_fixture:recovery_case_001"):
        self.source_reference = source_reference
        self._fixtures: Dict[str, Dict[str, Any]] = {}
        self._default_corrected_events: List[Dict[str, Any]] = []

    def register_fixture(self, event_id: str, corrected_event: Dict[str, Any]):
        """Register explicit corrected fixture for event_id."""
        self._fixtures[event_id] = corrected_event

    def set_default_recovery_events(self, events: List[Dict[str, Any]]):
        """Set fallback list of corrected events returned if no specific event fixture matches."""
        self._default_corrected_events = events

    def get_source_reference(self) -> str:
        return self.source_reference

    def fetch_for_recovery(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Re-fetch corrected events matching quarantine or incident context."""
        event_ids = context.get("event_ids", [])
        incident_id = context.get("incident_id", "inc_default")
        failed_events = context.get("failed_events", [])

        recovered_events: List[Dict[str, Any]] = []

        # 1. Match registered fixtures by event_id
        for evt_id in event_ids:
            if evt_id in self._fixtures:
                recovered_events.append(self._fixtures[evt_id].copy())

        # 2. Automatically generate corrected event from failed event if fixture not explicitly registered
        if not recovered_events and failed_events:
            for bad_evt in failed_events:
                evt_id = str(bad_evt.get("event_id", f"evt_repaired_{incident_id[:8]}"))
                cust_id = str(bad_evt.get("customer_id") or "cust_repaired_001")
                amt = bad_evt.get("amount")
                if amt is None or not isinstance(amt, (int, float)) or amt <= 0:
                    amt = 1499.00
                curr = bad_evt.get("currency")
                if not curr or curr not in ("INR", "USD", "EUR"):
                    curr = "INR"

                corrected = make_valid_checkout_event(
                    event_id=evt_id, customer_id=cust_id, amount=amt, currency=curr
                )
                recovered_events.append(corrected)

        # 3. Fallback to default registered events if provided
        if not recovered_events and self._default_corrected_events:
            recovered_events = [e.copy() for e in self._default_corrected_events]

        # 4. Ultimate fallback demo scenario event if no input events exist
        if not recovered_events:
            evt_id = context.get("event_id", f"evt_recovery_{incident_id[:8]}")
            recovered_events = [make_valid_checkout_event(event_id=evt_id)]

        logger.info(
            f"[LocalSourceAdapter] Re-fetched {len(recovered_events)} corrected events "
            f"from reference '{self.source_reference}' for incident '{incident_id}'"
        )
        return recovered_events
