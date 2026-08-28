"""Unit tests for Great Expectations Adapter, Expectation Registry, and Result Mapper."""

import pytest
import pandas as pd

from schemas.event import QualityEvent
from rules.base import Severity, RuleStatus
from metrics.collector import InMemoryMetricsCollector
from ge_adapter.expectations import GEExpectationRegistry, ExpectationConfig
from ge_adapter.runner import GERunner
from ge_adapter.result_mapper import GEResultMapper
from ge_adapter.adapter import GEAdapter


def build_valid_record(index: int) -> dict:
    """Helper to build a clean valid event dictionary."""
    return {
        "event_id": f"evt_{index:04d}",
        "customer_id": f"cust_{index}",
        "session_id": f"sess_{index}",
        "order_id": f"ord_{index}",
        "product_id": "prod_123",
        "amount": 150.50 + index,
        "currency": "USD",
        "payment_method": "CREDIT_CARD",
        "payment_status": "SUCCESS",
        "device": "MOBILE",
        "country": "US",
        "source_version": "1.0.0",
        "event_time": "2026-08-28T10:00:00Z",
        "ingestion_time": "2026-08-28T10:00:01Z",
    }


def test_valid_batch_100_events():
    """Step 29: Test GE validation against a 100-event valid batch."""
    records = [build_valid_record(i) for i in range(100)]
    adapter = GEAdapter()
    results, summary = adapter.validate_with_summary(records, batch_id="batch_valid_100")

    assert summary.batch_id == "batch_valid_100"
    assert summary.success is True
    assert summary.total_expectations == 5
    assert summary.passed_expectations == 5
    assert summary.failed_expectations == 0
    assert summary.critical_failures == 0

    for r in results:
        assert r.passed is True
        assert r.status == RuleStatus.PASS
        assert r.metadata["source"] == "great_expectations"


def test_invalid_batch_expectations_failures():
    """Step 30: Test deterministic invalid batch containing specific failures."""
    records = [build_valid_record(i) for i in range(10)]

    # Inject specific failures
    records[0]["amount"] = None  # null amount
    records[1]["amount"] = -10.0  # negative amount
    records[2]["currency"] = "XYZ"  # invalid currency
    records[3]["payment_status"] = "UNKNOWN"  # invalid payment status

    adapter = GEAdapter()
    results, summary = adapter.validate_with_summary(records, batch_id="batch_invalid")

    assert summary.success is False
    assert summary.failed_expectations > 0

    failed_rules = {r.rule_name: r for r in results if not r.passed}
    assert "amount_not_null" in failed_rules
    assert failed_rules["amount_not_null"].severity == Severity.CRITICAL
    assert failed_rules["amount_not_null"].field == "amount"

    assert "amount_positive" in failed_rules
    assert failed_rules["amount_positive"].severity == Severity.HIGH

    assert "currency_valid" in failed_rules
    assert failed_rules["currency_valid"].severity == Severity.HIGH
    assert failed_rules["currency_valid"].field == "currency"

    assert "payment_status_valid" in failed_rules
    assert failed_rules["payment_status_valid"].severity == Severity.HIGH
    assert failed_rules["payment_status_valid"].field == "payment_status"


def test_result_normalization_structure():
    """Step 32: Verify raw GE results normalize into IceStream ValidationResult format."""
    records = [build_valid_record(1)]
    records[0]["currency"] = "INVALID_CURRENCY"

    adapter = GEAdapter()
    results = adapter.validate(records, batch_id="batch_norm")

    currency_res = next(r for r in results if r.rule_name == "currency_valid")
    assert isinstance(currency_res.rule_name, str)
    assert currency_res.passed is False
    assert currency_res.status == RuleStatus.FAIL
    assert currency_res.severity == Severity.HIGH
    assert "currency" in currency_res.field
    assert currency_res.metadata["source"] == "great_expectations"
    assert currency_res.event_id == "batch_norm"


def test_ge_adapter_failure_error_handling():
    """Step 33: Test that execution errors raise controlled engine-level exceptions."""
    registry = GEExpectationRegistry()

    # Register an invalid expectation configuration targeting a nonexistent method
    bad_cfg = ExpectationConfig(
        name="bad_rule",
        expectation="nonexistent_ge_expectation_method",
        column="amount",
        severity=Severity.HIGH,
    )
    # Bypass initial validation to test runtime runner isolation
    registry._expectations["bad_rule"] = bad_cfg

    adapter = GEAdapter(registry=registry)
    results = adapter.validate([build_valid_record(1)])

    bad_res = next(r for r in results if r.rule_name == "bad_rule")
    assert bad_res.passed is False
    assert bad_res.severity == Severity.CRITICAL
    assert "execution error" in bad_res.message.lower() or "has no method" in bad_res.message.lower()


def test_disabled_expectation():
    """Step 34: Test that disabled expectation is not executed."""
    registry = GEExpectationRegistry()
    cfg1 = ExpectationConfig(
        name="amount_not_null",
        expectation="expect_column_values_to_not_be_null",
        column="amount",
        enabled=True,
    )
    cfg2 = ExpectationConfig(
        name="currency_valid",
        expectation="expect_column_values_to_be_in_set",
        column="currency",
        value_set=["USD", "EUR"],
        enabled=False,
    )
    registry.register(cfg1)
    registry.register(cfg2)

    adapter = GEAdapter(registry=registry)
    results = adapter.validate([build_valid_record(1)])

    rule_names = [r.rule_name for r in results]
    assert "amount_not_null" in rule_names
    assert "currency_valid" not in rule_names


def test_empty_batch_handling():
    """Step 35: Test GE execution on 0 records empty batch."""
    adapter = GEAdapter()
    results, summary = adapter.validate_with_summary([], batch_id="empty_batch")

    assert summary.batch_id == "empty_batch"
    assert summary.success is True
    assert len(results) == 5
    for r in results:
        assert r.passed is True
        assert "empty batch" in r.message.lower()


def test_missing_column_batch_handling():
    """Step 36: Test batch missing required column 'amount'."""
    df_missing = pd.DataFrame([
        {"event_id": "evt_1", "currency": "USD"}
    ])

    adapter = GEAdapter()
    results, summary = adapter.validate_with_summary(df_missing, batch_id="missing_col_batch")

    assert summary.success is False
    failed_names = [r.rule_name for r in results if not r.passed]
    assert "amount_not_null" in failed_names
    assert "amount_positive" in failed_names

    amt_res = next(r for r in results if r.rule_name == "amount_not_null")
    assert amt_res.field == "amount"
    assert "missing" in amt_res.message.lower()


def test_severity_configuration_override():
    """Step 42: Test severity comes from IceStream configuration."""
    registry = GEExpectationRegistry()
    cfg1 = ExpectationConfig(
        name="amount_not_null",
        expectation="expect_column_values_to_not_be_null",
        column="amount",
        severity=Severity.WARNING,  # Override to WARNING
        enabled=True,
    )
    registry.register(cfg1)

    adapter = GEAdapter(registry=registry)
    records = [build_valid_record(1)]
    records[0]["amount"] = None

    results = adapter.validate(records)
    amt_res = next(r for r in results if r.rule_name == "amount_not_null")
    assert amt_res.passed is False
    assert amt_res.severity == Severity.WARNING


def test_metrics_collector_integration():
    """Step 25 & 26: Test GE metrics recorded with low-cardinality source label."""
    collector = InMemoryMetricsCollector()
    adapter = GEAdapter(metrics_collector=collector)

    records = [build_valid_record(1)]
    records[0]["amount"] = None

    adapter.validate_with_summary(records, batch_id="batch_metrics")

    m = collector.get_metrics()
    assert m["ge_validation_runs"] == 1
    assert m["ge_expectations_total"] == 5
    assert m["ge_expectations_passed"] == 4
    assert m["ge_expectations_failed"] == 1
