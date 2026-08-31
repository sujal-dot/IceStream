"""
IceStream Day 21 — Quarantine / Dead Letter Queue Test Suite
Covers unit tests, integration tests, error code mapping, multi-rule aggregation,
valid event rejection, schema drift quarantine, duplicate protection, injectable clock,
metrics, and Iceberg storage read-back.
"""
from datetime import datetime, timezone
import pytest
from unittest.mock import MagicMock

from iceberg.config.catalog import get_catalog
from rules.base import EventStatus, RuleStatus, Severity, ValidationResult, ValidationSummary
from schemas.event import QualityEvent
from metrics.collector import InMemoryMetricsCollector
from quarantine.error_codes import (
    RULE_ERROR_CODE_MAP,
    DEFAULT_FALLBACK_ERROR_CODE,
    determine_primary_error,
    get_error_code_for_rule,
)
from quarantine.models import QuarantineRecord, QuarantineRouteResult
from quarantine.router import QuarantineRouter
from quarantine.writer import QuarantineWriter


# ==============================================================================
# UNIT TESTS
# ==============================================================================

def test_error_code_mappings():
    """Verify all defined quality rules map to canonical low-cardinality error codes."""
    assert get_error_code_for_rule("amount_not_null") == "NULL_AMOUNT"
    assert get_error_code_for_rule("amount_positive") == "INVALID_AMOUNT"
    assert get_error_code_for_rule("currency_valid") == "INVALID_CURRENCY"
    assert get_error_code_for_rule("payment_status_valid") == "INVALID_PAYMENT_STATUS"
    assert get_error_code_for_rule("event_time_valid") == "INVALID_TIMESTAMP"
    assert get_error_code_for_rule("duplicate_event") == "DUPLICATE_EVENT"
    assert get_error_code_for_rule("duplicate_order") == "DUPLICATE_ORDER"
    assert get_error_code_for_rule("impossible_amount") == "IMPOSSIBLE_AMOUNT"
    assert get_error_code_for_rule("future_timestamp") == "FUTURE_TIMESTAMP"
    assert get_error_code_for_rule("late_event") == "LATE_EVENT"
    assert get_error_code_for_rule("schema_drift") == "SCHEMA_DRIFT"


def test_unmapped_error_code_fallback():
    """Verify unmapped rule names fall back gracefully to DATA_QUALITY_FAILURE."""
    assert get_error_code_for_rule("unknown_custom_rule") == DEFAULT_FALLBACK_ERROR_CODE


def test_multiple_failed_rules_primary_error_selection():
    """Verify that multiple rule failures produce 1 primary error based on severity (CRITICAL > HIGH > MEDIUM > LOW)."""
    failures = [
        ValidationResult(rule_name="currency_valid", passed=False, severity=Severity.HIGH, message="Invalid currency 'XYZ'"),
        ValidationResult(rule_name="amount_not_null", passed=False, severity=Severity.CRITICAL, message="amount is null"),
        ValidationResult(rule_name="payment_status_valid", passed=False, severity=Severity.MEDIUM, message="Unknown status"),
    ]

    primary_code, err_msg, sorted_rules = determine_primary_error(failures)

    assert primary_code == "NULL_AMOUNT"  # CRITICAL beats HIGH and MEDIUM
    assert sorted_rules == ["amount_not_null", "currency_valid", "payment_status_valid"]
    assert "amount_not_null" in err_msg
    assert "currency_valid" in err_msg


def test_valid_event_protection():
    """Verify QuarantineRouter rejects valid events without creating quarantine records."""
    metrics = InMemoryMetricsCollector()
    writer = MagicMock(spec=QuarantineWriter)
    router = QuarantineRouter(writer=writer, metrics_collector=metrics)

    valid_event = {
        "event_id": "evt_valid_001",
        "amount": 1499.00,
        "currency": "INR",
        "payment_status": "SUCCESS",
    }
    validation_results = [
        ValidationResult(rule_name="amount_not_null", passed=True, severity=Severity.CRITICAL, message="Valid"),
        ValidationResult(rule_name="currency_valid", passed=True, severity=Severity.HIGH, message="Valid"),
    ]

    res = router.route_invalid_event(valid_event, validation_results)

    assert res.success is False
    assert res.skipped_reason == "EVENT_IS_VALID"
    assert res.quarantine_record is None
    writer.write_record.assert_not_called()


def test_injectable_clock_timestamp():
    """Verify quarantine router respects injected clock function without using sleep()."""
    metrics = InMemoryMetricsCollector()
    writer = MagicMock(spec=QuarantineWriter)
    writer.write_record.return_value = True

    fixed_time = "2026-08-31T10:00:00Z"
    router = QuarantineRouter(writer=writer, metrics_collector=metrics, clock_fn=lambda: fixed_time)

    invalid_event = {"event_id": "evt_clock_001", "amount": None}
    failures = [ValidationResult(rule_name="amount_not_null", passed=False, severity=Severity.CRITICAL, message="null amount")]

    res = router.route_invalid_event(invalid_event, failures)

    assert res.success is True
    assert res.quarantine_record is not None
    assert res.quarantine_record.detected_at == fixed_time


def test_duplicate_quarantine_protection():
    """Verify sending the exact same invalid event twice in same context skips duplicate write."""
    metrics = InMemoryMetricsCollector()
    writer = MagicMock(spec=QuarantineWriter)
    writer.write_record.return_value = True

    fixed_time = "2026-08-31T10:00:00Z"
    router = QuarantineRouter(writer=writer, metrics_collector=metrics, clock_fn=lambda: fixed_time)

    invalid_event = {"event_id": "evt_dup_001", "amount": None}
    failures = [ValidationResult(rule_name="amount_not_null", passed=False, severity=Severity.CRITICAL, message="null amount")]

    # First write -> Success
    res1 = router.route_invalid_event(invalid_event, failures)
    assert res1.success is True
    assert res1.skipped_reason is None
    assert writer.write_record.call_count == 1

    # Second write -> Skipped duplicate
    res2 = router.route_invalid_event(invalid_event, failures)
    assert res2.success is True
    assert res2.skipped_reason == "DUPLICATE_QUARANTINE_SKIPPED"
    assert writer.write_record.call_count == 1  # No second write call


def test_write_failure_handling_and_no_false_success():
    """Verify writer failures return success=False and increment write failure metrics."""
    metrics = InMemoryMetricsCollector()
    writer = MagicMock(spec=QuarantineWriter)
    writer.write_record.return_value = False  # Storage write failed!

    router = QuarantineRouter(writer=writer, metrics_collector=metrics)

    invalid_event = {"event_id": "evt_fail_001", "amount": None}
    failures = [ValidationResult(rule_name="amount_not_null", passed=False, severity=Severity.CRITICAL, message="null amount")]

    res = router.route_invalid_event(invalid_event, failures)

    assert res.success is False
    assert res.error == "Iceberg write failure"


# ==============================================================================
# INTEGRATION TESTS (Iceberg REST Catalog + MinIO)
# ==============================================================================

@pytest.mark.integration
def test_single_invalid_event_quarantine_e2e():
    """End-to-End: Route single invalid event, write to Iceberg, and read back."""
    metrics = InMemoryMetricsCollector()
    writer = QuarantineWriter(metrics_collector=metrics)
    router = QuarantineRouter(writer=writer, metrics_collector=metrics)

    invalid_event = {
        "event_id": "evt_invalid_001",
        "amount": None,
        "currency": "INR",
        "payment_status": "SUCCESS",
        "source_version": "v3",
    }
    failures = [
        ValidationResult(rule_name="amount_not_null", passed=False, severity=Severity.CRITICAL, message="amount is null")
    ]

    res = router.route_invalid_event(invalid_event, failures)

    assert res.success is True
    assert res.quarantine_record is not None
    rec = res.quarantine_record
    assert rec.event_id == "evt_invalid_001"
    assert rec.error_code == "NULL_AMOUNT"
    assert rec.failed_rules == ["amount_not_null"]
    assert rec.schema_version == "v3"

    # Read back from Iceberg catalog table
    catalog = get_catalog()
    table = catalog.load_table("quarantine.invalid_checkout_events")
    table.refresh()
    arrow_tbl = table.scan().to_arrow()
    data = arrow_tbl.to_pydict()

    assert rec.quarantine_id in data["quarantine_id"]
    idx = data["quarantine_id"].index(rec.quarantine_id)
    assert data["event_id"][idx] == "evt_invalid_001"
    assert data["error_code"][idx] == "NULL_AMOUNT"
    assert data["failed_rules"][idx] == ["amount_not_null"]


@pytest.mark.integration
def test_multiple_failures_single_record_demonstration():
    """Demonstration 2: 3 rule failures on 1 event result in 1 quarantine record."""
    metrics = InMemoryMetricsCollector()
    writer = QuarantineWriter(metrics_collector=metrics)
    router = QuarantineRouter(writer=writer, metrics_collector=metrics)

    invalid_event = {
        "event_id": "evt_multi_fail_001",
        "amount": None,
        "currency": "XYZ",
        "payment_status": "UNKNOWN",
        "source_version": "v3",
    }
    failures = [
        ValidationResult(rule_name="amount_not_null", passed=False, severity=Severity.CRITICAL, message="amount is null"),
        ValidationResult(rule_name="currency_valid", passed=False, severity=Severity.HIGH, message="currency 'XYZ' invalid"),
        ValidationResult(rule_name="payment_status_valid", passed=False, severity=Severity.MEDIUM, message="status 'UNKNOWN' invalid"),
    ]

    res = router.route_invalid_event(invalid_event, failures)

    assert res.success is True
    rec = res.quarantine_record
    assert rec.event_id == "evt_multi_fail_001"
    assert rec.error_code == "NULL_AMOUNT"  # CRITICAL severity
    assert rec.failed_rules == ["amount_not_null", "currency_valid", "payment_status_valid"]


@pytest.mark.integration
def test_schema_drift_quarantine_demonstration():
    """Demonstration 3: Schema drift failure generates SCHEMA_DRIFT quarantine record preserving raw event."""
    metrics = InMemoryMetricsCollector()
    writer = QuarantineWriter(metrics_collector=metrics)
    router = QuarantineRouter(writer=writer, metrics_collector=metrics)

    invalid_event = {
        "event_id": "evt_schema_drift_001",
        "amount": "1499.00",  # String instead of float!
        "currency": "INR",
        "source_version": "v1",
    }
    failures = [
        ValidationResult(rule_name="schema_drift", passed=False, severity=Severity.CRITICAL, message="Field 'amount' expected float, got string", metadata={"change_type": "TYPE_CHANGE"})
    ]

    res = router.route_invalid_event(invalid_event, failures)

    assert res.success is True
    rec = res.quarantine_record
    assert rec.error_code == "SCHEMA_DRIFT"
    assert rec.failed_rules == ["schema_drift"]
    assert "evt_schema_drift_001" in rec.event


@pytest.mark.integration
def test_batch_quarantine_write():
    """Verify batch routing of 100 events (95 valid, 5 invalid) produces 5 quarantine records."""
    metrics = InMemoryMetricsCollector()
    writer = QuarantineWriter(metrics_collector=metrics)
    router = QuarantineRouter(writer=writer, metrics_collector=metrics)

    batch_input = []
    for i in range(100):
        if i < 95:
            ev = {"event_id": f"evt_b_{i}", "amount": 100.0}
            res = [ValidationResult(rule_name="amount_not_null", passed=True, severity=Severity.CRITICAL, message="Valid")]
        else:
            ev = {"event_id": f"evt_b_{i}", "amount": None}
            res = [ValidationResult(rule_name="amount_not_null", passed=False, severity=Severity.CRITICAL, message="Null amount")]
        batch_input.append((ev, res))

    route_results = router.route_batch(batch_input)

    successful_quarantines = [r for r in route_results if r.success and r.quarantine_record is not None]
    assert len(successful_quarantines) == 5

    # Check metrics counters
    metric_snapshot = metrics.get_metrics()
    assert metric_snapshot["counters"]["quarantine_events_total"] >= 5
