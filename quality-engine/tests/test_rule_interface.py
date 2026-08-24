"""Tests for QualityRule interface and Event model."""

import pytest
from datetime import datetime, timezone

from schemas.event import QualityEvent
from rules.base import (
    EventIdNotNullRule,
    EventStatus,
    QualityRule,
    RuleStatus,
    Severity,
    ValidationResult,
)


class DummyAmountPositiveRule(QualityRule):
    """Test rule ensuring amount is positive."""

    @property
    def name(self) -> str:
        return "dummy_amount_positive"

    @property
    def default_severity(self) -> Severity:
        return Severity.HIGH

    def validate(self, event: QualityEvent) -> ValidationResult:
        amt = event.amount
        if amt is None or amt <= 0:
            return ValidationResult(
                rule_name=self.name,
                passed=False,
                severity=self.severity,
                message=f"amount must be > 0, got {amt}",
                field="amount",
                event_id=event.event_id,
            )
        return ValidationResult(
            rule_name=self.name,
            passed=True,
            severity=self.severity,
            message="amount is positive",
            field="amount",
            event_id=event.event_id,
        )


def test_event_model_instantiation():
    """Verify QualityEvent can instantiate with all standard fields."""
    event = QualityEvent(
        event_id="evt_001",
        customer_id="cust_101",
        amount=150.0,
        currency="INR",
    )
    assert event.event_id == "evt_001"
    assert event.customer_id == "cust_101"
    assert event.amount == 150.0
    assert event.currency == "INR"
    assert event.order_id is None


def test_event_model_from_dict_and_to_dict():
    """Verify conversion from/to dictionary."""
    data = {
        "event_id": "evt_002",
        "customer_id": "cust_102",
        "amount": "250.50",
        "quantity": "3",
        "custom_field": "extra_val",
    }
    event = QualityEvent.from_dict(data)
    assert event.event_id == "evt_002"
    assert event.customer_id == "cust_102"
    assert event.amount == 250.50
    assert event.quantity == 3
    assert event.get_field("custom_field") == "extra_val"

    out_dict = event.to_dict()
    assert out_dict["event_id"] == "evt_002"
    assert out_dict["custom_field"] == "extra_val"


def test_event_model_tolerates_missing_and_corrupt_fields():
    """Event model should not crash when fields are null or invalid."""
    raw = {
        "event_id": None,
        "amount": "not_a_float",
        "quantity": None,
    }
    event = QualityEvent.from_dict(raw)
    assert event.event_id is None
    assert event.quantity is None


def test_severity_and_status_enums():
    """Verify standard controlled enum members."""
    assert Severity.INFO.value == "INFO"
    assert Severity.LOW.value == "LOW"
    assert Severity.MEDIUM.value == "MEDIUM"
    assert Severity.HIGH.value == "HIGH"
    assert Severity.CRITICAL.value == "CRITICAL"

    assert RuleStatus.PASS.value == "PASS"
    assert RuleStatus.FAIL.value == "FAIL"

    assert EventStatus.HEALTHY.value == "HEALTHY"
    assert EventStatus.WARNING.value == "WARNING"
    assert EventStatus.FAILED.value == "FAILED"


def test_quality_rule_abstract_instantiation():
    """QualityRule cannot be instantiated without implementing abstract methods."""
    with pytest.raises(TypeError):
        QualityRule()  # type: ignore


def test_custom_rule_implementation():
    """Verify custom rule implements validate(event) contract cleanly."""
    rule = DummyAmountPositiveRule()
    assert rule.name == "dummy_amount_positive"
    assert rule.severity == Severity.HIGH
    assert rule.enabled is True

    # Valid event
    evt_valid = QualityEvent(event_id="evt_10", amount=99.9)
    res_valid = rule.validate(evt_valid)
    assert isinstance(res_valid, ValidationResult)
    assert res_valid.passed is True
    assert res_valid.severity == Severity.HIGH

    # Invalid event
    evt_invalid = QualityEvent(event_id="evt_10", amount=-10.0)
    res_invalid = rule.validate(evt_invalid)
    assert res_invalid.passed is False
    assert res_invalid.severity == Severity.HIGH
    assert "amount must be > 0" in res_invalid.message


def test_event_id_not_null_rule_pass():
    """Verify demonstration rule passes for non-null event_id."""
    rule = EventIdNotNullRule()
    evt = QualityEvent(event_id="evt_test_valid_001")
    result = rule.validate(evt)
    assert result.passed is True
    assert result.rule_name == "event_id_not_null"
    assert result.severity == Severity.CRITICAL
    assert result.event_id == "evt_test_valid_001"


def test_event_id_not_null_rule_fail():
    """Verify demonstration rule fails for null, empty, or 'None' event_id."""
    rule = EventIdNotNullRule()

    for bad_id in [None, "", "   ", "None", "none"]:
        evt = QualityEvent(event_id=bad_id)
        result = rule.validate(evt)
        assert result.passed is False, f"Expected fail for event_id={bad_id}"
        assert result.severity == Severity.CRITICAL
        assert "null" in result.message.lower() or "empty" in result.message.lower()
