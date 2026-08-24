"""Tests for MetricsCollector and InMemoryMetricsCollector."""

from metrics.collector import InMemoryMetricsCollector
from rules.base import EventStatus, Severity, ValidationResult


def test_metrics_initial_state():
    """Verify metrics initialize to clean zero state."""
    collector = InMemoryMetricsCollector()
    metrics = collector.get_metrics()
    assert metrics["total_events"] == 0
    assert metrics["valid_events"] == 0
    assert metrics["invalid_events"] == 0
    assert metrics["error_rate"] == 0.0
    assert metrics["critical_failures"] == 0
    assert metrics["rule_passes"] == {}
    assert metrics["rule_failures"] == {}


def test_metrics_recording():
    """Verify recording rule passes, failures, and event classifications."""
    collector = InMemoryMetricsCollector()

    # Pass result
    pass_res = ValidationResult(
        rule_name="rule_a",
        passed=True,
        severity=Severity.HIGH,
        message="ok",
    )
    collector.record_rule_result(pass_res)
    collector.increment_event_validation(EventStatus.HEALTHY)

    # Fail result (CRITICAL)
    fail_res = ValidationResult(
        rule_name="rule_b",
        passed=False,
        severity=Severity.CRITICAL,
        message="failed",
    )
    collector.record_rule_result(fail_res)
    collector.increment_event_validation(EventStatus.FAILED)

    collector.record_validation_latency(1.5)
    collector.record_validation_latency(2.5)

    metrics = collector.get_metrics()
    assert metrics["total_events"] == 2
    assert metrics["valid_events"] == 1
    assert metrics["invalid_events"] == 1
    assert metrics["error_rate"] == 0.5
    assert metrics["critical_failures"] == 1
    assert metrics["rule_passes"]["rule_a"] == 1
    assert metrics["rule_failures"]["rule_b"] == 1
    assert metrics["validation_latency_count"] == 2
    assert metrics["validation_latency_avg_ms"] == 2.0


def test_metrics_reset():
    """Verify metrics reset clears all accumulated values."""
    collector = InMemoryMetricsCollector()
    collector.increment_rule_pass("rule_x")
    collector.increment_event_validation(EventStatus.HEALTHY)
    assert collector.get_metrics()["total_events"] == 1

    collector.reset()
    assert collector.get_metrics()["total_events"] == 0
    assert collector.get_metrics()["rule_passes"] == {}
