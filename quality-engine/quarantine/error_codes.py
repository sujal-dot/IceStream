"""
IceStream Quarantine Error Code Mapping & Policy Engine
Handles deterministic rule-to-error-code translation, severity weighting,
and primary error selection.
"""
import logging
from typing import Dict, List, Optional, Tuple
from rules.base import Severity, ValidationResult

logger = logging.getLogger("quality_engine.quarantine.error_codes")

# Standard Error Code Constants
DEFAULT_FALLBACK_ERROR_CODE = "DATA_QUALITY_FAILURE"

RULE_ERROR_CODE_MAP: Dict[str, str] = {
    "amount_not_null": "NULL_AMOUNT",
    "amount_positive": "INVALID_AMOUNT",
    "currency_valid": "INVALID_CURRENCY",
    "payment_status_valid": "INVALID_PAYMENT_STATUS",
    "event_time_valid": "INVALID_TIMESTAMP",
    "duplicate_event": "DUPLICATE_EVENT",
    "duplicate_order": "DUPLICATE_ORDER",
    "impossible_amount": "IMPOSSIBLE_AMOUNT",
    "future_timestamp": "FUTURE_TIMESTAMP",
    "late_event": "LATE_EVENT",
    "schema_drift": "SCHEMA_DRIFT",
}

SEVERITY_WEIGHTS: Dict[Severity, int] = {
    Severity.CRITICAL: 400,
    Severity.HIGH: 300,
    Severity.WARNING: 200,
    Severity.MEDIUM: 200,
    Severity.LOW: 100,
    Severity.INFO: 100,
}


def get_error_code_for_rule(rule_name: str) -> str:
    """Map a single failed rule name to its canonical error_code.
    
    If the rule is unmapped, logs a warning and returns DATA_QUALITY_FAILURE.
    """
    if rule_name in RULE_ERROR_CODE_MAP:
        return RULE_ERROR_CODE_MAP[rule_name]
    logger.warning("Unmapped quality rule '%s' encountered; falling back to '%s'", rule_name, DEFAULT_FALLBACK_ERROR_CODE)
    return DEFAULT_FALLBACK_ERROR_CODE


def get_severity_weight(severity: Optional[Severity]) -> int:
    """Return numeric weight for severity level comparison."""
    if severity is None:
        return 0
    return SEVERITY_WEIGHTS.get(severity, 0)


def sort_failed_results(failed_results: List[ValidationResult]) -> List[ValidationResult]:
    """Sort failed validation results deterministically by severity weight descending,
    then rule_name alphabetically.
    """
    return sorted(
        failed_results,
        key=lambda r: (-get_severity_weight(r.severity), r.rule_name)
    )


def determine_primary_error(failed_results: List[ValidationResult]) -> Tuple[str, str, List[str]]:
    """Determine primary error_code, combined error_message, and sorted failed_rules list.
    
    Args:
        failed_results: List of ValidationResult objects where passed == False.

    Returns:
        Tuple of (primary_error_code, error_message, sorted_failed_rules)
    """
    if not failed_results:
        return ("NONE", "No failures", [])

    sorted_results = sort_failed_results(failed_results)
    sorted_rule_names = [r.rule_name for r in sorted_results]

    primary_result = sorted_results[0]
    primary_error_code = get_error_code_for_rule(primary_result.rule_name)

    if len(sorted_results) == 1:
        error_msg = primary_result.message
    else:
        messages = [f"{r.rule_name}: {r.message}" for r in sorted_results]
        error_msg = " | ".join(messages)

    return (primary_error_code, error_msg, sorted_rule_names)
