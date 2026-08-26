"""Unit tests for duplicate event and duplicate order detection rules."""

import pytest
from detectors.duplicate import DuplicateEventRule, DuplicateOrderRule
from rules.base import RuleStatus, Severity
from rules.clock import FixedClock
from rules.engine import QualityEngine
from rules.registry import RuleRegistry
from schemas.event import QualityEvent


def test_duplicate_event_first_and_second_occurrence():
    clock = FixedClock("2026-08-26T10:00:00Z")
    rule = DuplicateEventRule(window_seconds=300, clock=clock)

    event1 = QualityEvent(event_id="evt_001", order_id="ORD001")
    event2 = QualityEvent(event_id="evt_001", order_id="ORD002")

    res1 = rule.validate(event1)
    assert res1.passed is True
    assert res1.status == RuleStatus.PASS

    res2 = rule.validate(event2)
    assert res2.passed is False
    assert res2.status == RuleStatus.FAIL
    assert res2.severity == Severity.CRITICAL
    assert res2.message == "duplicate event_id detected"
    assert res2.field == "event_id"
    assert res2.event_id == "evt_001"


def test_duplicate_event_state_expiration():
    clock = FixedClock("2026-08-26T10:00:00Z")
    rule = DuplicateEventRule(window_seconds=300, clock=clock)

    event = QualityEvent(event_id="evt_001")

    # First occurrence -> PASS
    assert rule.validate(event).passed is True

    # Immediate second occurrence -> FAIL
    assert rule.validate(event).passed is False

    # Advance clock past 300-second window (301 seconds)
    clock.advance(301)

    # Third occurrence after window expiration -> PASS
    res3 = rule.validate(event)
    assert res3.passed is True
    assert res3.message == "event_id is unique in active window"


def test_duplicate_event_null_handling():
    clock = FixedClock("2026-08-26T10:00:00Z")
    rule = DuplicateEventRule(window_seconds=300, clock=clock)

    event_null = QualityEvent(event_id=None)
    event_empty = QualityEvent(event_id="")
    event_none_str = QualityEvent(event_id="None")

    assert rule.validate(event_null).passed is True
    assert rule.validate(event_empty).passed is True
    assert rule.validate(event_none_str).passed is True


def test_duplicate_order_detection_independent_of_event_id():
    clock = FixedClock("2026-08-26T10:00:00Z")
    rule = DuplicateOrderRule(window_seconds=300, clock=clock)

    event1 = QualityEvent(event_id="evt_001", order_id="ORD001")
    event2 = QualityEvent(event_id="evt_002", order_id="ORD001")

    res1 = rule.validate(event1)
    assert res1.passed is True

    res2 = rule.validate(event2)
    assert res2.passed is False
    assert res2.severity == Severity.HIGH
    assert res2.message == "duplicate order_id detected"
    assert res2.field == "order_id"


def test_duplicate_order_state_expiration():
    clock = FixedClock("2026-08-26T10:00:00Z")
    rule = DuplicateOrderRule(window_seconds=300, clock=clock)

    event = QualityEvent(event_id="evt_100", order_id="ORD500")

    assert rule.validate(event).passed is True
    assert rule.validate(event).passed is False

    clock.advance(305)
    assert rule.validate(event).passed is True


def test_state_isolation_between_engines():
    registry1 = RuleRegistry()
    registry1.register(DuplicateEventRule(window_seconds=300))

    registry2 = RuleRegistry()
    registry2.register(DuplicateEventRule(window_seconds=300))

    engine1 = QualityEngine(registry=registry1)
    engine2 = QualityEngine(registry=registry2)

    event = QualityEvent(event_id="evt_isolated_100")

    res1 = engine1.validate(event)[0]
    assert res1.passed is True

    # Same event validated in engine2 should PASS because state is not shared
    res2 = engine2.validate(event)[0]
    assert res2.passed is True

    # Second validation in engine1 should FAIL
    res1_second = engine1.validate(event)[0]
    assert res1_second.passed is False
