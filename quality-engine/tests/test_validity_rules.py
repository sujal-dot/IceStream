"""Unit tests for Day 15 Null + Validity Detection Rules."""

import pytest
from rules.base import Severity, RuleStatus
from rules.not_null import NotNullRule
from rules.positive import AmountPositiveRule
from rules.allowed_values import AllowedValuesRule, CurrencyValidRule, PaymentStatusValidRule
from rules.timestamp import TimestampValidRule
from schemas.event import QualityEvent


# -----------------------------------------------------------------------------
# 1. NOT NULL RULE TESTS
# -----------------------------------------------------------------------------

def test_event_id_not_null_pass():
    rule = NotNullRule(field="event_id")
    event = QualityEvent(event_id="evt_123")
    res = rule.validate(event)
    assert res.passed is True
    assert res.status == RuleStatus.PASS
    assert res.field == "event_id"


def test_event_id_not_null_fail():
    rule = NotNullRule(field="event_id")
    for bad_val in [None, "", "   ", "none", "NONE"]:
        event = QualityEvent(event_id=bad_val)
        res = rule.validate(event)
        assert res.passed is False
        assert res.status == RuleStatus.FAIL
        assert res.field == "event_id"


def test_amount_not_null_pass():
    rule = NotNullRule(field="amount")
    event = QualityEvent(amount=1499.00)
    res = rule.validate(event)
    assert res.passed is True
    assert res.field == "amount"


def test_amount_not_null_fail():
    rule = NotNullRule(field="amount")
    event = QualityEvent(amount=None)
    res = rule.validate(event)
    assert res.passed is False
    assert res.field == "amount"


def test_not_null_rule_tolerates_zero_and_false():
    """Verify 0, 0.0, and False are NOT treated as null."""
    rule_amount = NotNullRule(field="amount")
    rule_bool = NotNullRule(field="is_flag")

    event_zero = QualityEvent(amount=0)
    res = rule_amount.validate(event_zero)
    assert res.passed is True

    event_flag = QualityEvent(raw_payload={"is_flag": False})
    res_flag = rule_bool.validate(event_flag)
    assert res_flag.passed is True


# -----------------------------------------------------------------------------
# 2. AMOUNT POSITIVE RULE TESTS
# -----------------------------------------------------------------------------

def test_amount_positive_pass():
    rule = AmountPositiveRule(field="amount")
    for valid_amt in [1499.00, 0.01, 100, "250.50"]:
        event = QualityEvent(amount=valid_amt)
        res = rule.validate(event)
        assert res.passed is True
        assert res.status == RuleStatus.PASS


def test_amount_zero_fail():
    rule = AmountPositiveRule(field="amount")
    event = QualityEvent(amount=0)
    res = rule.validate(event)
    assert res.passed is False
    assert "greater than 0" in res.message


def test_amount_negative_fail():
    rule = AmountPositiveRule(field="amount")
    event = QualityEvent(amount=-100)
    res = rule.validate(event)
    assert res.passed is False
    assert "greater than 0" in res.message


def test_amount_null_fail():
    rule = AmountPositiveRule(field="amount")
    event = QualityEvent(amount=None)
    res = rule.validate(event)
    assert res.passed is False
    assert res.metadata.get("is_null") is True


def test_amount_invalid_type_fail():
    rule = AmountPositiveRule(field="amount")
    for bad_type in ["abc", True, object()]:
        event = QualityEvent(amount=bad_type)
        res = rule.validate(event)
        assert res.passed is False
        assert "invalid" in res.message or "unsupported" in res.message


# -----------------------------------------------------------------------------
# 3. CURRENCY VALIDITY TESTS
# -----------------------------------------------------------------------------

def test_currency_inr_pass():
    rule = CurrencyValidRule()
    event = QualityEvent(currency="INR")
    res = rule.validate(event)
    assert res.passed is True


def test_currency_usd_pass():
    rule = CurrencyValidRule()
    event = QualityEvent(currency="USD")
    res = rule.validate(event)
    assert res.passed is True


def test_currency_eur_pass():
    rule = CurrencyValidRule()
    event = QualityEvent(currency="EUR")
    res = rule.validate(event)
    assert res.passed is True


def test_currency_invalid_fail():
    rule = CurrencyValidRule()
    for invalid in ["GBP", "XYZ", "inr", "usd"]:
        event = QualityEvent(currency=invalid)
        res = rule.validate(event)
        assert res.passed is False


def test_currency_null_fail():
    rule = CurrencyValidRule()
    for empty in [None, "", "  "]:
        event = QualityEvent(currency=empty)
        res = rule.validate(event)
        assert res.passed is False
        assert res.metadata.get("is_null") is True


# -----------------------------------------------------------------------------
# 4. PAYMENT STATUS VALIDITY TESTS
# -----------------------------------------------------------------------------

def test_payment_status_valid_pass():
    rule = PaymentStatusValidRule()
    for status in ["SUCCESS", "FAILED", "PENDING", "CANCELLED"]:
        event = QualityEvent(payment_status=status)
        res = rule.validate(event)
        assert res.passed is True


def test_payment_status_invalid_fail():
    rule = PaymentStatusValidRule()
    for invalid in ["UNKNOWN", "PROCESSING", "success"]:
        event = QualityEvent(payment_status=invalid)
        res = rule.validate(event)
        assert res.passed is False


def test_payment_status_null_fail():
    rule = PaymentStatusValidRule()
    for empty in [None, ""]:
        event = QualityEvent(payment_status=empty)
        res = rule.validate(event)
        assert res.passed is False
        assert res.metadata.get("is_null") is True


# -----------------------------------------------------------------------------
# 5. TIMESTAMP VALIDITY TESTS
# -----------------------------------------------------------------------------

def test_event_timestamp_valid():
    rule = TimestampValidRule(field="event_time")
    for ts in [
        "2026-08-25T10:30:22.431Z",
        "2026-08-25T10:30:22Z",
        "2026-08-25T10:30:22+05:30",
    ]:
        event = QualityEvent(event_time=ts)
        res = rule.validate(event)
        assert res.passed is True


def test_event_timestamp_invalid():
    rule = TimestampValidRule(field="event_time")
    for invalid in ["not-a-timestamp", "2026-13-45T99:99:99Z", 123456789, object()]:
        event = QualityEvent(event_time=invalid)
        res = rule.validate(event)
        assert res.passed is False


def test_event_timestamp_null():
    rule = TimestampValidRule(field="event_time")
    event = QualityEvent(event_time=None)
    res = rule.validate(event)
    assert res.passed is False
    assert res.metadata.get("is_null") is True


def test_ingestion_timestamp_valid():
    rule = TimestampValidRule(field="ingestion_time")
    event = QualityEvent(ingestion_time="2026-08-25T10:30:23.000Z")
    res = rule.validate(event)
    assert res.passed is True


def test_ingestion_timestamp_invalid():
    rule = TimestampValidRule(field="ingestion_time")
    event = QualityEvent(ingestion_time="invalid_iso_string")
    res = rule.validate(event)
    assert res.passed is False


def test_ingestion_timestamp_null():
    rule = TimestampValidRule(field="ingestion_time")
    event = QualityEvent(ingestion_time=None)
    res = rule.validate(event)
    assert res.passed is False
