"""Tests for ValidationResult, ValidationSummary, and summary computation."""

from rules.base import (
    EventStatus,
    RuleStatus,
    Severity,
    ValidationResult,
    ValidationSummary,
    compute_validation_summary,
)


def test_validation_result_serialization():
    """Verify ValidationResult dictionary representation and properties."""
    result = ValidationResult(
        rule_name="test_rule",
        passed=False,
        severity=Severity.HIGH,
        message="Failure reason",
        field="customer_id",
        event_id="evt_555",
        metadata={"extra_info": 42},
    )
    assert result.status == RuleStatus.FAIL
    d = result.to_dict()
    assert d["rule_name"] == "test_rule"
    assert d["passed"] is False
    assert d["status"] == "FAIL"
    assert d["severity"] == "HIGH"
    assert d["message"] == "Failure reason"
    assert d["field"] == "customer_id"
    assert d["event_id"] == "evt_555"
    assert d["metadata"]["extra_info"] == 42


def test_compute_validation_summary_healthy():
    """Verify summary is HEALTHY when all rules pass."""
    res1 = ValidationResult(
        rule_name="rule1",
        passed=True,
        severity=Severity.CRITICAL,
        message="ok",
    )
    res2 = ValidationResult(
        rule_name="rule2",
        passed=True,
        severity=Severity.LOW,
        message="ok",
    )

    summary = compute_validation_summary([res1, res2], event_id="evt_01")
    assert summary.event_id == "evt_01"
    assert summary.total_rules == 2
    assert summary.passed_rules == 2
    assert summary.failed_rules == 0
    assert summary.critical_failures == 0
    assert summary.overall_status == EventStatus.HEALTHY


def test_compute_validation_summary_warning():
    """Verify summary is WARNING when only non-critical (LOW/MEDIUM) rules fail."""
    res1 = ValidationResult(
        rule_name="rule1",
        passed=True,
        severity=Severity.CRITICAL,
        message="ok",
    )
    res2 = ValidationResult(
        rule_name="rule2",
        passed=False,
        severity=Severity.MEDIUM,
        message="minor warning",
    )

    summary = compute_validation_summary([res1, res2], event_id="evt_02")
    assert summary.overall_status == EventStatus.WARNING
    assert summary.failed_rules == 1
    assert summary.critical_failures == 0


def test_compute_validation_summary_failed():
    """Verify summary is FAILED when HIGH or CRITICAL rules fail."""
    res1 = ValidationResult(
        rule_name="rule1",
        passed=False,
        severity=Severity.CRITICAL,
        message="critical violation",
    )
    res2 = ValidationResult(
        rule_name="rule2",
        passed=True,
        severity=Severity.LOW,
        message="ok",
    )

    summary = compute_validation_summary([res1, res2], event_id="evt_03")
    assert summary.overall_status == EventStatus.FAILED
    assert summary.failed_rules == 1
    assert summary.critical_failures == 1

    d = summary.to_dict()
    assert d["overall_status"] == "FAILED"
    assert len(d["results"]) == 2
