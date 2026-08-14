"""Error injector for creating realistic corrupted events for streaming testing."""

import datetime
import random
from collections import deque
from typing import Any, Dict, List, Optional

from generator.config import ALL_ERROR_TYPES
from generator.event_schema import REQUIRED_FIELDS


class ErrorInjector:
    """Injects specific, controlled schema errors into valid checkout events."""

    def __init__(
        self,
        seed: Optional[int] = None,
        error_types: Optional[List[str]] = None,
        max_history: int = 1000,
    ):
        self._rnd = random.Random(seed)
        self.error_types = (
            list(error_types) if error_types else list(ALL_ERROR_TYPES)
        )
        self._recent_event_ids: deque = deque(maxlen=max_history)

    def record_valid_event_id(self, event_id: str):
        """Buffer valid event IDs to allow realistic duplicate injection."""
        if event_id:
            self._recent_event_ids.append(event_id)

    def inject_error(
        self, event_dict: Dict[str, Any], target_error_type: Optional[str] = None
    ) -> tuple[Dict[str, Any], str]:
        """Inject a single error into a copy of event_dict.

        Returns (corrupted_event_dict, injected_error_type_name).
        """
        event_copy = dict(event_dict)

        if not target_error_type:
            target_error_type = self._rnd.choice(self.error_types)

        if target_error_type == "null_amount":
            event_copy["amount"] = None

        elif target_error_type == "null_customer_id":
            event_copy["customer_id"] = None

        elif target_error_type == "negative_amount":
            current_amt = event_copy.get("amount")
            if isinstance(current_amt, (int, float)) and current_amt != 0:
                event_copy["amount"] = -abs(current_amt)
            else:
                event_copy["amount"] = -1499.00

        elif target_error_type == "duplicate_event_id":
            if self._recent_event_ids:
                dup_id = self._rnd.choice(list(self._recent_event_ids))
            else:
                dup_id = "evt_duplicate_00001"
            event_copy["event_id"] = dup_id

        elif target_error_type == "invalid_currency":
            event_copy["currency"] = self._rnd.choice(["XXX", "INVALID", "USD_BAD"])

        elif target_error_type == "missing_required_field":
            # Select a random required field to completely delete from the JSON object
            candidates = [
                f
                for f in REQUIRED_FIELDS
                if f in event_copy and f not in ("event_id", "event_type")
            ]
            field_to_remove = (
                self._rnd.choice(candidates) if candidates else "customer_id"
            )
            del event_copy[field_to_remove]

        elif target_error_type == "wrong_data_type":
            # Pick a type mutation target
            target = self._rnd.choice(["quantity", "amount", "unit_price"])
            if target == "quantity":
                event_copy["quantity"] = "two"
            elif target == "amount":
                event_copy["amount"] = str(event_copy.get("amount", "1499.00"))
            elif target == "unit_price":
                event_copy["unit_price"] = str(event_copy.get("unit_price", "749.50"))

        elif target_error_type == "future_timestamp":
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            future_dt = now_utc + datetime.timedelta(hours=1)
            millis = future_dt.microsecond // 1000
            event_copy["event_time"] = (
                f"{future_dt.strftime('%Y-%m-%dT%H:%M:%S')}.{millis:03d}Z"
            )

        else:
            raise ValueError(f"Unknown error type: {target_error_type}")

        return event_copy, target_error_type
