"""
IceStream Quarantine Package
Exposes quarantine models, error code engine, writer, and router.
"""
from quarantine.models import QuarantineRecord, QuarantineRouteResult
from quarantine.error_codes import (
    RULE_ERROR_CODE_MAP,
    DEFAULT_FALLBACK_ERROR_CODE,
    get_error_code_for_rule,
    determine_primary_error,
)
from quarantine.writer import QuarantineWriter
from quarantine.router import QuarantineRouter

__all__ = [
    "QuarantineRecord",
    "QuarantineRouteResult",
    "RULE_ERROR_CODE_MAP",
    "DEFAULT_FALLBACK_ERROR_CODE",
    "get_error_code_for_rule",
    "determine_primary_error",
    "QuarantineWriter",
    "QuarantineRouter",
]
