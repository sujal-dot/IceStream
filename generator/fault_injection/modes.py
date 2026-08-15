"""Fault injection mode definitions and constants for IceStream."""

from enum import Enum
from typing import List


class FaultMode(str, Enum):
    """Supported fault modes in IceStream event generator."""

    NULL = "NULL"
    DUPLICATE = "DUPLICATE"
    NEGATIVE = "NEGATIVE"
    INVALID_ENUM = "INVALID_ENUM"
    SCHEMA_DRIFT = "SCHEMA_DRIFT"
    TYPE_CHANGE = "TYPE_CHANGE"
    TIMESTAMP_DRIFT = "TIMESTAMP_DRIFT"


ALL_FAULT_MODES: List[str] = [mode.value for mode in FaultMode]

# Permitted enumeration values for valid checkout events
VALID_PAYMENT_METHODS = [
    "UPI",
    "CREDIT_CARD",
    "DEBIT_CARD",
    "NET_BANKING",
    "WALLET",
    "COD",
]

VALID_PAYMENT_STATUSES = [
    "SUCCESS",
    "FAILED",
    "PENDING",
]

# Supported Schema Drift scenarios
class SchemaDriftType(str, Enum):
    ADD_FIELD = "ADD_FIELD"
    REMOVE_FIELD = "REMOVE_FIELD"
    RENAME_FIELD = "RENAME_FIELD"


ALL_SCHEMA_DRIFT_TYPES: List[str] = [s.value for s in SchemaDriftType]

# Supported Timestamp Drift variants
class TimestampDriftVariant(str, Enum):
    FUTURE_TIMESTAMP = "FUTURE_TIMESTAMP"
    STALE_TIMESTAMP = "STALE_TIMESTAMP"
    CLOCK_SKEW = "CLOCK_SKEW"


ALL_TIMESTAMP_DRIFT_VARIANTS: List[str] = [v.value for v in TimestampDriftVariant]
