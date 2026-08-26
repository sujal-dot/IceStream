"""Unit tests for impossible amount, future timestamp, and late event rules."""

import pytest
from detectors.anomaly import FutureTimestampRule, ImpossibleAmountRule, LateEventRule
from rules.base import Severity
from rules.clock import FixedClock
from schemas.event import QualityEvent


def test_impossible_amount_rule_thresholds():
    rule = ImpossibleAmountRule(max_value=500000.0)

    # Acceptable amounts
    assert rule.validate(QualityEvent(amount=100.0)).passed is True
    assert rule.validate(QualityEvent(amount=500000.0)).passed is True

    # Exceeding threshold -> FAIL
    res_fail = rule.validate(QualityEvent(amount=500001.0))
    assert res_fail.passed is False
    assert res_fail.severity == Severity.HIGH
    assert "exceeds maximum business limit" in res_fail.message
    assert res_fail.field == "amount"

    # Negative amount -> PASS for impossible amount (AmountPositiveRule checks negative)
    assert rule.validate(QualityEvent(amount=-100.0)).passed is True

    # Null amount -> PASS for impossible amount (NotNullRule checks null)
    assert rule.validate(QualityEvent(amount=None)).passed is True


def test_future_timestamp_rule_deterministic():
    clock = FixedClock("2026-08-26T10:00:00Z")
    rule = FutureTimestampRule(tolerance_seconds=30.0, clock=clock)

    # 1 minute past -> PASS
    assert rule.validate(QualityEvent(event_time="2026-08-26T09:59:00Z")).passed is True

    # 20 seconds future -> PASS (within 30s tolerance)
    assert rule.validate(QualityEvent(event_time="2026-08-26T10:00:20Z")).passed is True

    # Exactly 30 seconds future -> PASS
    assert rule.validate(QualityEvent(event_time="2026-08-26T10:00:30Z")).passed is True

    # 31 seconds future -> FAIL
    res_fail = rule.validate(QualityEvent(event_time="2026-08-26T10:00:31Z"))
    assert res_fail.passed is False
    assert res_fail.severity == Severity.HIGH
    assert res_fail.message == "event_time is beyond allowed clock skew"
    assert res_fail.field == "event_time"


def test_late_event_rule_deterministic():
    clock = FixedClock("2026-08-26T10:00:00Z")
    rule = LateEventRule(allowed_lateness_seconds=120.0, clock=clock)

    # 60 seconds old -> PASS
    assert rule.validate(QualityEvent(event_time="2026-08-26T09:59:00Z")).passed is True

    # Exactly 120 seconds old -> PASS
    assert rule.validate(QualityEvent(event_time="2026-08-26T09:58:00Z")).passed is True

    # 121 seconds old -> FAIL
    res_fail = rule.validate(QualityEvent(event_time="2026-08-26T09:57:59Z"))
    assert res_fail.passed is False
    assert res_fail.severity == Severity.MEDIUM
    assert res_fail.message == "event arrived later than allowed lateness"
    assert res_fail.field == "event_time"
