"""Unit Test Suite for Day 19 Error Rate Engine."""

import os
import sys
import pytest

# Ensure quality-engine is on sys.path
QUALITY_ENGINE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "quality-engine"))
if QUALITY_ENGINE_DIR not in sys.path:
    sys.path.insert(0, QUALITY_ENGINE_DIR)

from metrics.error_rate import ErrorRateConfig, ErrorRateEngine, HealthStatus
from rules.base import EventStatus, ValidationResult, ValidationSummary, Severity
from rules.clock import FixedClock


def test_1_zero_events():
    """Verify zero traffic returns 0 error rate, HEALTHY status, and data_available=False."""
    engine = ErrorRateEngine()
    metrics = engine.calculate(window_seconds=60)

    assert metrics.total_events == 0
    assert metrics.valid_events == 0
    assert metrics.failed_events == 0
    assert metrics.error_rate == 0.0
    assert metrics.error_rate_percent == 0.0
    assert metrics.health_status == HealthStatus.HEALTHY
    assert metrics.data_available is False


def test_2_all_valid_events():
    """Verify 100% valid traffic returns error_rate=0.0 and HEALTHY."""
    engine = ErrorRateEngine()
    for _ in range(100):
        engine.record_event_outcome(is_valid=True)

    metrics = engine.calculate(window_seconds=60)
    assert metrics.total_events == 100
    assert metrics.valid_events == 100
    assert metrics.failed_events == 0
    assert metrics.error_rate == 0.0
    assert metrics.error_rate_percent == 0.0
    assert metrics.health_status == HealthStatus.HEALTHY
    assert metrics.data_available is True


def test_3_all_invalid_events():
    """Verify 100% failed traffic returns error_rate=1.0 and CRITICAL."""
    engine = ErrorRateEngine()
    for _ in range(100):
        engine.record_event_outcome(is_valid=False)

    metrics = engine.calculate(window_seconds=60)
    assert metrics.total_events == 100
    assert metrics.valid_events == 0
    assert metrics.failed_events == 100
    assert metrics.error_rate == 1.0
    assert metrics.error_rate_percent == 100.0
    assert metrics.health_status == HealthStatus.CRITICAL
    assert metrics.data_available is True


def test_4_healthy_threshold():
    """Test 1000 events with 5 failures (0.5% error rate) -> HEALTHY."""
    engine = ErrorRateEngine()
    for _ in range(995):
        engine.record_event_outcome(is_valid=True)
    for _ in range(5):
        engine.record_event_outcome(is_valid=False)

    metrics = engine.calculate(window_seconds=60)
    assert metrics.total_events == 1000
    assert metrics.valid_events == 995
    assert metrics.failed_events == 5
    assert metrics.error_rate == 0.005
    assert metrics.error_rate_percent == 0.5
    assert metrics.health_status == HealthStatus.HEALTHY


def test_5_warning_lower_boundary():
    """Test 1000 events with 10 failures (exact 1.0% error rate) -> WARNING."""
    engine = ErrorRateEngine()
    for _ in range(990):
        engine.record_event_outcome(is_valid=True)
    for _ in range(10):
        engine.record_event_outcome(is_valid=False)

    metrics = engine.calculate(window_seconds=60)
    assert metrics.total_events == 1000
    assert metrics.failed_events == 10
    assert metrics.error_rate == 0.01
    assert metrics.error_rate_percent == 1.0
    assert metrics.health_status == HealthStatus.WARNING


def test_6_warning_upper_boundary():
    """Test 1000 events with 20 failures (exact 2.0% error rate) -> WARNING."""
    engine = ErrorRateEngine()
    for _ in range(980):
        engine.record_event_outcome(is_valid=True)
    for _ in range(20):
        engine.record_event_outcome(is_valid=False)

    metrics = engine.calculate(window_seconds=60)
    assert metrics.total_events == 1000
    assert metrics.failed_events == 20
    assert metrics.error_rate == 0.02
    assert metrics.error_rate_percent == 2.0
    assert metrics.health_status == HealthStatus.WARNING


def test_7_critical_threshold():
    """Test 1000 events with 21 failures (2.1% error rate) -> CRITICAL."""
    engine = ErrorRateEngine()
    for _ in range(979):
        engine.record_event_outcome(is_valid=True)
    for _ in range(21):
        engine.record_event_outcome(is_valid=False)

    metrics = engine.calculate(window_seconds=60)
    assert metrics.total_events == 1000
    assert metrics.failed_events == 21
    assert metrics.error_rate == 0.021
    assert metrics.error_rate_percent == 2.1
    assert metrics.health_status == HealthStatus.CRITICAL


def test_8_multiple_rule_failures_single_failed_event():
    """Test Event A (3 failed rules), Event B (2 failed rules), Event C (0 failed rules) -> failed_events=2, error_rate=2/3."""
    engine = ErrorRateEngine()

    summary_a = ValidationSummary(
        event_id="evt_a",
        total_rules=3,
        passed_rules=0,
        failed_rules=3,
        critical_failures=3,
        overall_status=EventStatus.FAILED,
        results=[
            ValidationResult(rule_name="r1", passed=False, severity=Severity.CRITICAL, message="fail 1"),
            ValidationResult(rule_name="r2", passed=False, severity=Severity.CRITICAL, message="fail 2"),
            ValidationResult(rule_name="r3", passed=False, severity=Severity.CRITICAL, message="fail 3"),
        ],
    )

    summary_b = ValidationSummary(
        event_id="evt_b",
        total_rules=2,
        passed_rules=0,
        failed_rules=2,
        critical_failures=2,
        overall_status=EventStatus.FAILED,
        results=[
            ValidationResult(rule_name="r1", passed=False, severity=Severity.HIGH, message="fail 1"),
            ValidationResult(rule_name="r2", passed=False, severity=Severity.HIGH, message="fail 2"),
        ],
    )

    summary_c = ValidationSummary(
        event_id="evt_c",
        total_rules=3,
        passed_rules=3,
        failed_rules=0,
        critical_failures=0,
        overall_status=EventStatus.HEALTHY,
        results=[
            ValidationResult(rule_name="r1", passed=True, severity=Severity.INFO, message="pass"),
        ],
    )

    engine.record_event(summary_a)
    engine.record_event(summary_b)
    engine.record_event(summary_c)

    metrics = engine.calculate(window_seconds=60)
    assert metrics.total_events == 3
    assert metrics.valid_events == 1
    assert metrics.failed_events == 2
    assert abs(metrics.error_rate - (2.0 / 3.0)) < 1e-6


def test_9_1_minute_window():
    """Test 1-minute window aggregation."""
    clock = FixedClock("2026-08-29T10:00:00Z")
    engine = ErrorRateEngine(clock=clock)

    for _ in range(9):
        engine.record_event_outcome(is_valid=True, timestamp="2026-08-29T10:00:10Z")
    engine.record_event_outcome(is_valid=False, timestamp="2026-08-29T10:00:20Z")

    m1 = engine.calculate(window_seconds=60, ref_time="2026-08-29T10:00:30Z")
    assert m1.window_seconds == 60
    assert m1.total_events == 10
    assert m1.failed_events == 1
    assert m1.error_rate == 0.10


def test_10_5_minute_window_weighted():
    """Verify 5-minute window calculates weighted error rate directly from events, not average of 1m error rates."""
    clock = FixedClock("2026-08-29T10:00:00Z")
    engine = ErrorRateEngine(clock=clock)

    # Minute 1: 10 events, 1 failed (10% error rate)
    for _ in range(9):
        engine.record_event_outcome(is_valid=True, timestamp="2026-08-29T10:00:10Z")
    engine.record_event_outcome(is_valid=False, timestamp="2026-08-29T10:00:20Z")

    # Minute 2: 100 events, 1 failed (1% error rate)
    for _ in range(99):
        engine.record_event_outcome(is_valid=True, timestamp="2026-08-29T10:01:10Z")
    engine.record_event_outcome(is_valid=False, timestamp="2026-08-29T10:01:20Z")

    # If averaged: (10% + 1%) / 2 = 5.5% -> WRONG
    # Correct weighted: 2 / 110 = 1.818%
    m5 = engine.calculate(window_seconds=300, ref_time="2026-08-29T10:02:00Z")
    assert m5.total_events == 110
    assert m5.failed_events == 2
    assert abs(m5.error_rate - (2.0 / 110.0)) < 1e-6
    assert m5.health_status == HealthStatus.WARNING


def test_11_window_expiration():
    """Test window eviction as time advances."""
    clock = FixedClock("2026-08-29T10:00:00Z")
    engine = ErrorRateEngine(clock=clock)

    # Event at 10:00:00
    engine.record_event_outcome(is_valid=False, timestamp="2026-08-29T10:00:00Z")

    # At 10:00:30 -> event active
    m1 = engine.calculate(window_seconds=60, ref_time="2026-08-29T10:00:30Z")
    assert m1.total_events == 1
    assert m1.failed_events == 1

    # At 10:01:05 -> event expired
    m2 = engine.calculate(window_seconds=60, ref_time="2026-08-29T10:01:05Z")
    assert m2.total_events == 0
    assert m2.failed_events == 0
    assert m2.data_available is False


def test_12_precision_unrounded_classification():
    """Verify raw float 0.0201 is CRITICAL and not rounded to 0.02 (WARNING) before classification."""
    engine = ErrorRateEngine()
    health = engine.classify(0.0201)
    assert health == HealthStatus.CRITICAL

    health_warn = engine.classify(0.0200)
    assert health_warn == HealthStatus.WARNING


def test_13_invalid_configuration():
    """Verify invalid threshold configs fail fast during configuration loading."""
    # Negative threshold
    with pytest.raises(ValueError):
        ErrorRateConfig(healthy_max=-0.01, warning_max=0.02)

    # Threshold > 1.0
    with pytest.raises(ValueError):
        ErrorRateConfig(healthy_max=0.01, warning_max=1.5)

    # healthy_max >= warning_max
    with pytest.raises(ValueError):
        ErrorRateConfig(healthy_max=0.05, warning_max=0.02)

    # Non-numeric
    with pytest.raises(ValueError):
        ErrorRateConfig(healthy_max="0.01", warning_max=0.02)  # type: ignore

    # Boolean
    with pytest.raises(ValueError):
        ErrorRateConfig(healthy_max=True, warning_max=0.02)  # type: ignore


def test_14_metric_invariants():
    """Verify metric invariants hold across calculations."""
    engine = ErrorRateEngine()
    for _ in range(50):
        engine.record_event_outcome(is_valid=True)
    for _ in range(10):
        engine.record_event_outcome(is_valid=False)

    metrics = engine.calculate(window_seconds=60)
    assert metrics.total_events >= 0
    assert metrics.valid_events >= 0
    assert metrics.failed_events >= 0
    assert metrics.valid_events + metrics.failed_events == metrics.total_events
    assert metrics.failed_events <= metrics.total_events
    assert 0.0 <= metrics.error_rate <= 1.0
