"""Fault mutation strategies for IceStream Fault Injection Engine."""

import datetime
import random
from collections import deque
from typing import Any, Dict, List, Optional, Tuple

from generator.fault_injection.modes import (
    ALL_SCHEMA_DRIFT_TYPES,
    ALL_TIMESTAMP_DRIFT_VARIANTS,
    FaultMode,
    SchemaDriftType,
    TimestampDriftVariant,
)


class BaseFaultStrategy:
    """Base interface for a fault mutation strategy."""

    def mutate(
        self, event_dict: Dict[str, Any], rnd: random.Random
    ) -> Dict[str, Any]:
        raise NotImplementedError


class NullFaultStrategy(BaseFaultStrategy):
    """Injects NULL values into required fields."""

    NULLABLE_TARGET_FIELDS = [
        "customer_id",
        "session_id",
        "order_id",
        "product_id",
        "amount",
        "currency",
        "payment_method",
        "payment_status",
    ]

    def mutate(
        self, event_dict: Dict[str, Any], rnd: random.Random
    ) -> Dict[str, Any]:
        event_copy = dict(event_dict)
        target_field = rnd.choice(self.NULLABLE_TARGET_FIELDS)
        event_copy[target_field] = None
        return event_copy


class DuplicateFaultStrategy(BaseFaultStrategy):
    """Re-uses exact past event identity to simulate stream duplicate delivery."""

    def __init__(self, max_history: int = 1000):
        self._history: deque = deque(maxlen=max_history)

    def record_event(self, event_dict: Dict[str, Any]):
        """Buffer past valid event payload copies."""
        self._history.append(dict(event_dict))

    def mutate(
        self, event_dict: Dict[str, Any], rnd: random.Random
    ) -> Dict[str, Any]:
        if self._history:
            # Pick a previously seen event to duplicate exact payload and identity
            dup_event = dict(rnd.choice(list(self._history)))
            return dup_event
        else:
            # Fallback if history is empty
            event_copy = dict(event_dict)
            event_copy["event_id"] = "evt_duplicate_00001"
            return event_copy


class NegativeFaultStrategy(BaseFaultStrategy):
    """Injects logically impossible negative numeric values."""

    def mutate(
        self, event_dict: Dict[str, Any], rnd: random.Random
    ) -> Dict[str, Any]:
        event_copy = dict(event_dict)
        target_field = rnd.choice(["amount", "unit_price", "quantity"])

        if target_field == "amount":
            curr = event_copy.get("amount", 1499.00)
            event_copy["amount"] = -abs(curr) if curr != 0 else -1499.00
        elif target_field == "unit_price":
            curr = event_copy.get("unit_price", 749.50)
            event_copy["unit_price"] = -abs(curr) if curr != 0 else -749.50
        elif target_field == "quantity":
            curr = event_copy.get("quantity", 2)
            event_copy["quantity"] = -abs(curr) if curr != 0 else -2

        return event_copy


class InvalidEnumFaultStrategy(BaseFaultStrategy):
    """Injects values outside permitted enumerations."""

    INVALID_PAYMENT_METHODS = ["CRYPTO_UNKNOWN", "BITCOIN_PAY", "BARTER"]
    INVALID_PAYMENT_STATUSES = ["UNKNOWN_STATUS_X", "PROCESSING_EXPIRED", "UNKNOWN"]

    def mutate(
        self, event_dict: Dict[str, Any], rnd: random.Random
    ) -> Dict[str, Any]:
        event_copy = dict(event_dict)
        target = rnd.choice(["payment_method", "payment_status"])

        if target == "payment_method":
            event_copy["payment_method"] = rnd.choice(self.INVALID_PAYMENT_METHODS)
        else:
            event_copy["payment_status"] = rnd.choice(self.INVALID_PAYMENT_STATUSES)

        return event_copy


class SchemaDriftFaultStrategy(BaseFaultStrategy):
    """Simulates unexpected producer schema changes."""

    def __init__(self, allowed_drift_types: Optional[List[str]] = None):
        self.allowed_drift_types = (
            allowed_drift_types if allowed_drift_types else list(ALL_SCHEMA_DRIFT_TYPES)
        )

    def mutate(
        self, event_dict: Dict[str, Any], rnd: random.Random
    ) -> Dict[str, Any]:
        event_copy = dict(event_dict)
        drift_type = rnd.choice(self.allowed_drift_types)

        if drift_type == SchemaDriftType.ADD_FIELD or drift_type == "ADD_FIELD":
            event_copy["customer_segment"] = rnd.choice(["premium", "gold", "vip"])
            event_copy["source_version"] = "v2"

        elif drift_type == SchemaDriftType.REMOVE_FIELD or drift_type == "REMOVE_FIELD":
            candidates = [f for f in ["payment_status", "device", "country"] if f in event_copy]
            field_to_remove = rnd.choice(candidates) if candidates else "payment_status"
            del event_copy[field_to_remove]
            event_copy["source_version"] = "v2"

        elif drift_type == SchemaDriftType.RENAME_FIELD or drift_type == "RENAME_FIELD":
            if "customer_id" in event_copy:
                event_copy["client_id"] = event_copy.pop("customer_id")
            elif "order_id" in event_copy:
                event_copy["purchase_order_id"] = event_copy.pop("order_id")
            event_copy["source_version"] = "v2"

        return event_copy


class TypeChangeFaultStrategy(BaseFaultStrategy):
    """Changes data type of a field."""

    def mutate(
        self, event_dict: Dict[str, Any], rnd: random.Random
    ) -> Dict[str, Any]:
        event_copy = dict(event_dict)
        target = rnd.choice(["quantity", "amount", "customer_id"])

        if target == "quantity":
            # Convert int to str
            event_copy["quantity"] = str(event_copy.get("quantity", 2))
        elif target == "amount":
            # Convert float to str
            event_copy["amount"] = str(event_copy.get("amount", 1499.00))
        elif target == "customer_id":
            # Convert str customer ID to integer e.g. "CUS000123" -> 123
            cid = str(event_copy.get("customer_id", "CUS000123"))
            numeric_part = "".join(filter(str.isdigit, cid))
            event_copy["customer_id"] = int(numeric_part) if numeric_part else 123

        return event_copy


class TimestampDriftFaultStrategy(BaseFaultStrategy):
    """Simulates incorrect or skewed timestamps."""

    def mutate(
        self, event_dict: Dict[str, Any], rnd: random.Random
    ) -> Dict[str, Any]:
        event_copy = dict(event_dict)
        variant = rnd.choice(ALL_TIMESTAMP_DRIFT_VARIANTS)
        now_utc = datetime.datetime.now(datetime.timezone.utc)

        if variant == TimestampDriftVariant.FUTURE_TIMESTAMP:
            target_dt = now_utc + datetime.timedelta(hours=2)
        elif variant == TimestampDriftVariant.STALE_TIMESTAMP:
            target_dt = now_utc - datetime.timedelta(days=30)
        else:  # CLOCK_SKEW
            target_dt = now_utc + datetime.timedelta(minutes=15)

        millis = target_dt.microsecond // 1000
        event_copy["event_time"] = f"{target_dt.strftime('%Y-%m-%dT%H:%M:%S')}.{millis:03d}Z"
        return event_copy
