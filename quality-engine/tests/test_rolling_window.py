"""Unit tests for rolling-window metrics aggregation, error rates, and window expiration."""

import pytest
from metrics.collector import InMemoryMetricsCollector
from metrics.window import WindowAggregator
from rules.base import EventIdNotNullRule, Severity, ValidationResult
from rules.registry import RuleRegistry
from rules.clock import FixedClock
from rules.engine import QualityEngine
from detectors.anomaly import FutureTimestampRule, ImpossibleAmountRule
from detectors.duplicate import DuplicateEventRule
from schemas.event import QualityEvent


def test_1_minute_window_metrics():
    clock = FixedClock("2026-08-26T10:00:00Z")
    agg = WindowAggregator(window_seconds=60, clock=clock)

    # Add 95 valid events and 5 invalid events
    for i in range(95):
        agg.add_event(is_valid=True, timestamp="2026-08-26T10:00:10Z")

    for i in range(5):
        agg.add_event(is_valid=False, timestamp="2026-08-26T10:00:20Z")

    metrics = agg.get_metrics("2026-08-26T10:00:30Z")
    assert metrics.total_events == 100
    assert metrics.valid_events == 95
    assert metrics.invalid_events == 5
    assert metrics.error_rate == 0.05


def test_5_minute_window_metrics_and_expiration():
    clock = FixedClock("2026-08-26T10:00:00Z")
    agg = WindowAggregator(window_seconds=300, clock=clock)

    # Minute 1: 20 events
    for _ in range(20):
        agg.add_event(is_valid=True, timestamp="2026-08-26T10:00:10Z")
    # Minute 2: 20 events
    for _ in range(20):
        agg.add_event(is_valid=True, timestamp="2026-08-26T10:01:10Z")
    # Minute 3: 20 events
    for _ in range(20):
        agg.add_event(is_valid=True, timestamp="2026-08-26T10:02:10Z")
    # Minute 4: 20 events
    for _ in range(20):
        agg.add_event(is_valid=True, timestamp="2026-08-26T10:03:10Z")
    # Minute 5: 20 events
    for _ in range(20):
        agg.add_event(is_valid=True, timestamp="2026-08-26T10:04:10Z")

    metrics_5m = agg.get_metrics("2026-08-26T10:04:59Z")
    assert metrics_5m.total_events == 100
    assert metrics_5m.valid_events == 100

    # Advance clock to 10:05:30Z (5m 20s after first event) -> Minute 1 (10:00:10Z) events should expire
    metrics_after_expiration = agg.get_metrics("2026-08-26T10:05:30Z")
    assert metrics_after_expiration.total_events == 80


def test_window_expiration_granularity():
    clock = FixedClock("2026-08-26T10:00:00Z")
    agg = WindowAggregator(window_seconds=60, clock=clock)

    agg.add_event(is_valid=True, timestamp="2026-08-26T10:00:00Z")  # Batch A
    agg.add_event(is_valid=True, timestamp="2026-08-26T10:00:30Z")  # Batch B

    # At 10:00:45 -> 2 events active
    m1 = agg.get_metrics("2026-08-26T10:00:45Z")
    assert m1.total_events == 2

    # At 10:01:05 -> Batch A (10:00:00) expired, Batch B (10:00:30) active
    m2 = agg.get_metrics("2026-08-26T10:01:05Z")
    assert m2.total_events == 1

    # At 10:01:40 -> Both expired
    m3 = agg.get_metrics("2026-08-26T10:01:40Z")
    assert m3.total_events == 0


def test_error_rate_calculation_cases():
    clock = FixedClock("2026-08-26T10:00:00Z")
    agg = WindowAggregator(window_seconds=60, clock=clock)

    # Case 1: 0 total events
    m0 = agg.get_metrics()
    assert m0.total_events == 0
    assert m0.error_rate == 0.0

    # Case 2: 100% valid
    for _ in range(10):
        agg.add_event(is_valid=True)
    assert agg.get_metrics().error_rate == 0.0

    # Case 3: 10% invalid (90 valid, 10 invalid)
    agg.reset()
    for _ in range(90):
        agg.add_event(is_valid=True)
    for _ in range(10):
        agg.add_event(is_valid=False)
    assert agg.get_metrics().error_rate == 0.10

    # Case 4: 100% invalid
    agg.reset()
    for _ in range(10):
        agg.add_event(is_valid=False)
    assert agg.get_metrics().error_rate == 1.0


def test_multiple_rule_failures_single_invalid_event():
    clock = FixedClock("2026-08-26T10:00:00Z")
    collector = InMemoryMetricsCollector(windows=[60, 300], clock=clock)
    registry = RuleRegistry()
    registry.register(DuplicateEventRule(window_seconds=300, clock=clock))
    registry.register(ImpossibleAmountRule(max_value=500000.0))
    registry.register(FutureTimestampRule(tolerance_seconds=30.0, clock=clock))

    engine = QualityEngine(registry=registry, metrics_collector=collector)

    # First event -> PASSES all rules
    evt1 = QualityEvent(
        event_id="evt_multi_1",
        amount=100.0,
        event_time="2026-08-26T10:00:00Z",
    )
    results1, summary1 = engine.validate_with_summary(evt1)
    assert summary1.failed_rules == 0
    assert summary1.overall_status.value == "HEALTHY"

    # Second event: triggers duplicate_event AND impossible_amount AND future_timestamp
    evt2 = QualityEvent(
        event_id="evt_multi_1",  # Duplicate!
        amount=9999999.0,        # Impossible amount!
        event_time="2026-08-26T11:00:00Z",  # 1 hour in future!
    )
    results2, summary2 = engine.validate_with_summary(evt2)

    # 3 rules failed
    assert len(results2) == 3
    failed_results = [r for r in results2 if not r.passed]
    assert len(failed_results) == 3

    # BUT collector event metrics MUST record 1 valid event and 1 invalid event!
    metrics = collector.get_metrics()
    assert metrics["total_events"] == 2
    assert metrics["valid_events"] == 1
    assert metrics["invalid_events"] == 1
    assert metrics["error_rate"] == 0.50

    # Rule failure counts tracked separately:
    assert metrics["rule_failures"]["duplicate_event"] == 1
    assert metrics["rule_failures"]["impossible_amount"] == 1
    assert metrics["rule_failures"]["future_timestamp"] == 1
