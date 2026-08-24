"""Tests for QualityEngine execution, rule isolation, and extensibility."""

import pytest
from rules.base import (
    EventIdNotNullRule,
    EventStatus,
    QualityRule,
    Severity,
    ValidationResult,
)
from rules.engine import QualityEngine
from rules.registry import RuleRegistry
from schemas.event import QualityEvent


class AlwaysPassTestRule(QualityRule):
    """Test rule that always passes."""

    @property
    def name(self) -> str:
        return "always_pass_test_rule"

    @property
    def default_severity(self) -> Severity:
        return Severity.LOW

    def validate(self, event: QualityEvent) -> ValidationResult:
        return ValidationResult(
            rule_name=self.name,
            passed=True,
            severity=self.severity,
            message="Test rule always passes",
            field="test_field",
            event_id=event.event_id,
        )


class AlwaysFailTestRule(QualityRule):
    """Test rule that always fails."""

    @property
    def name(self) -> str:
        return "always_fail_test_rule"

    @property
    def default_severity(self) -> Severity:
        return Severity.HIGH

    def validate(self, event: QualityEvent) -> ValidationResult:
        return ValidationResult(
            rule_name=self.name,
            passed=False,
            severity=self.severity,
            message="Test rule always fails",
            field="test_field",
            event_id=event.event_id,
        )


class ExplodingExceptionRule(QualityRule):
    """Test rule that deliberately throws an unhandled runtime exception."""

    @property
    def name(self) -> str:
        return "exploding_exception_rule"

    @property
    def default_severity(self) -> Severity:
        return Severity.CRITICAL

    def validate(self, event: QualityEvent) -> ValidationResult:
        raise RuntimeError("Simulated unexpected database or memory crash in rule")


def test_engine_valid_event():
    """Verify engine validates a valid event and reports HEALTHY status."""
    registry = RuleRegistry()
    registry.register(EventIdNotNullRule())
    engine = QualityEngine(registry=registry)

    event = QualityEvent(
        event_id="evt_test_001",
        customer_id="CUS001",
        order_id="ORD001",
        amount=1499.00,
        currency="INR",
        payment_method="UPI",
        payment_status="SUCCESS",
        country="IN",
        source_version="v1",
    )

    results, summary = engine.validate_with_summary(event)
    assert len(results) == 1
    assert results[0].rule_name == "event_id_not_null"
    assert results[0].passed is True
    assert summary.overall_status == EventStatus.HEALTHY


def test_engine_invalid_event():
    """Verify engine validates an invalid event (null event_id) and reports FAILED."""
    registry = RuleRegistry()
    registry.register(EventIdNotNullRule())
    engine = QualityEngine(registry=registry)

    event = QualityEvent(
        event_id=None,
        customer_id="CUS001",
        amount=1499.00,
    )

    results, summary = engine.validate_with_summary(event)
    assert len(results) == 1
    assert results[0].rule_name == "event_id_not_null"
    assert results[0].passed is False
    assert results[0].severity == Severity.CRITICAL
    assert summary.overall_status == EventStatus.FAILED
    assert summary.critical_failures == 1


def test_engine_multiple_rules_execution():
    """Verify engine executes multiple registered rules and aggregates results."""
    registry = RuleRegistry()
    registry.register(EventIdNotNullRule())
    registry.register(AlwaysPassTestRule())
    engine = QualityEngine(registry=registry)

    event = QualityEvent(event_id="evt_test_002")
    results, summary = engine.validate_with_summary(event)

    assert len(results) == 2
    rule_names = {r.rule_name for r in results}
    assert "event_id_not_null" in rule_names
    assert "always_pass_test_rule" in rule_names
    assert summary.passed_rules == 2
    assert summary.failed_rules == 0
    assert summary.overall_status == EventStatus.HEALTHY


def test_engine_rule_isolation():
    """Verify a failure in one rule does not prevent other rules from running."""
    registry = RuleRegistry()
    registry.register(EventIdNotNullRule())     # Will pass on valid event
    registry.register(AlwaysFailTestRule())      # Will fail
    registry.register(AlwaysPassTestRule())      # Will pass
    engine = QualityEngine(registry=registry)

    event = QualityEvent(event_id="evt_test_003")
    results, summary = engine.validate_with_summary(event)

    assert len(results) == 3
    statuses = {r.rule_name: r.passed for r in results}
    assert statuses["event_id_not_null"] is True
    assert statuses["always_fail_test_rule"] is False
    assert statuses["always_pass_test_rule"] is True

    assert summary.passed_rules == 2
    assert summary.failed_rules == 1
    assert summary.overall_status == EventStatus.FAILED


def test_engine_rule_exception_handling():
    """Verify unexpected exception in a rule is caught safely and marked as CRITICAL failure."""
    registry = RuleRegistry()
    registry.register(EventIdNotNullRule())      # Normal rule (PASS)
    registry.register(ExplodingExceptionRule())  # Throws exception
    registry.register(AlwaysPassTestRule())      # Normal rule (PASS)
    engine = QualityEngine(registry=registry)

    event = QualityEvent(event_id="evt_test_004")
    results, summary = engine.validate_with_summary(event)

    assert len(results) == 3
    crash_res = next(r for r in results if r.rule_name == "exploding_exception_rule")
    assert crash_res.passed is False
    assert crash_res.severity == Severity.CRITICAL
    assert "Rule execution failure" in crash_res.message
    assert "RuntimeError" in crash_res.message
    assert "traceback" in crash_res.metadata

    # Other rules must have executed successfully
    pass_res = next(r for r in results if r.rule_name == "always_pass_test_rule")
    assert pass_res.passed is True


def test_engine_plugin_extensibility():
    """Verify a newly created rule can be plugged in without modifying the engine."""
    class CustomNewCheckRule(QualityRule):
        @property
        def name(self) -> str:
            return "custom_new_check"

        @property
        def default_severity(self) -> Severity:
            return Severity.MEDIUM

        def validate(self, event: QualityEvent) -> ValidationResult:
            return ValidationResult(
                rule_name=self.name,
                passed=True,
                severity=self.severity,
                message="Custom plugin validated successfully",
            )

    registry = RuleRegistry()
    registry.register(CustomNewCheckRule())

    # Engine runs the new rule with zero modification to engine source code
    engine = QualityEngine(registry=registry)
    results = engine.validate({"event_id": "evt_plugin_01"})
    assert len(results) == 1
    assert results[0].rule_name == "custom_new_check"
    assert results[0].passed is True
