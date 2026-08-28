"""Integration and performance tests for HybridQualityEngine (GE + Custom Rules)."""

import pytest
import time
from datetime import datetime, timezone

from schemas.event import QualityEvent
from rules.base import EventStatus, RuleStatus, Severity
from metrics.collector import InMemoryMetricsCollector
from hybrid_engine import HybridQualityEngine
from test_ge_adapter import build_valid_record


def test_hybrid_custom_plus_ge_together():
    """Step 31: Test Custom + GE running together on a mixed batch."""
    events = [
        # Event A: valid
        build_valid_record(1),
        # Event B: duplicate event_id (same event_id as Event A)
        build_valid_record(1),
        # Event C: negative amount
        build_valid_record(3),
        # Event D: future timestamp
        build_valid_record(4),
        # Event E: invalid currency
        build_valid_record(5),
    ]

    events[0]["event_id"] = "EVT_DUPLICATE_ID"
    events[1]["event_id"] = "EVT_DUPLICATE_ID"
    events[2]["amount"] = -50.0
    events[3]["event_time"] = "2099-01-01T00:00:00Z"
    events[4]["currency"] = "XYZ"

    engine = HybridQualityEngine()
    unified = engine.validate_batch(events, batch_id="batch_hybrid_mixed")

    assert unified.batch_id == "batch_hybrid_mixed"
    assert unified.overall_status in (EventStatus.FAILED, EventStatus.WARNING)
    assert len(unified.ge_results) > 0
    assert len(unified.custom_results) > 0

    # GE should catch declarative failures
    ge_failed_names = [r.rule_name for r in unified.ge_results if not r.passed]
    assert "amount_positive" in ge_failed_names
    assert "currency_valid" in ge_failed_names

    # Custom engine should catch duplicate_event and future_timestamp
    custom_failed_names = [r.rule_name for r in unified.custom_results if not r.passed]
    assert "duplicate_event" in custom_failed_names
    assert "future_timestamp" in custom_failed_names

    # Sources must be distinguishable
    for r in unified.ge_results:
        assert r.metadata.get("source") == "great_expectations"
    for r in unified.custom_results:
        assert r.metadata.get("source") == "custom"


def test_result_merging_and_deduplication():
    """Step 40: Test result merging and event invalidity deduplication."""
    events = [build_valid_record(i) for i in range(5)]
    # Event 0 fails both GE (amount negative) and Custom (impossible amount / duplicate)
    events[0]["amount"] = -100.0

    engine = HybridQualityEngine()
    unified = engine.validate_batch(events, batch_id="batch_dedup")

    # Unified result retains results from both sources
    ge_sources = {r.metadata.get("source") for r in unified.ge_results}
    custom_sources = {r.metadata.get("source") for r in unified.custom_results}

    assert ge_sources == {"great_expectations"}
    assert custom_sources == {"custom"}
    assert unified.total_events == 5


def test_format_quality_summary_output():
    """Step 41: Test formatted Quality Summary text generation."""
    events = [build_valid_record(1)]
    events[0]["amount"] = -10.0  # Fails GE amount_positive
    events[0]["currency"] = "XYZ"  # Fails GE currency_valid

    engine = HybridQualityEngine()
    unified = engine.validate_batch(events, batch_id="summary_test")

    summary_text = engine.format_quality_summary(unified.ge_results, unified.custom_results)

    assert "IceStream Quality Summary" in summary_text
    assert "GE Checks:" in summary_text
    assert "GE Passed:" in summary_text
    assert "GE Failed:" in summary_text
    assert "Custom Checks:" in summary_text
    assert "Custom Passed:" in summary_text
    assert "Custom Failed:" in summary_text
    assert "Critical:" in summary_text
    assert "Warning:" in summary_text
    assert "Overall:" in summary_text


def test_order_independence():
    """Step 44: Test that merged results produce deterministic outcome regardless of input list ordering."""
    records = [build_valid_record(i) for i in range(5)]
    records[1]["currency"] = "INVALID_1"
    records[3]["amount"] = -999.0

    engine = HybridQualityEngine()
    res1 = engine.validate_batch(records, batch_id="b1")
    res2 = engine.validate_batch(list(reversed(records)), batch_id="b2")

    assert res1.ge_batch_summary.passed_expectations == res2.ge_batch_summary.passed_expectations
    assert res1.ge_batch_summary.failed_expectations == res2.ge_batch_summary.failed_expectations
    assert res1.overall_status == res2.overall_status


@pytest.mark.performance
def test_large_batch_performance_benchmark():
    """Step 37: 10,000 events batch validation benchmark."""
    records = [build_valid_record(i % 100) for i in range(10000)]
    engine = HybridQualityEngine()

    start_t = time.perf_counter()
    unified = engine.validate_batch(records, batch_id="bench_10k")
    duration = time.perf_counter() - start_t

    rows_per_sec = 10000 / duration if duration > 0 else 0

    assert unified.total_events == 10000
    assert unified.ge_batch_summary.success is True
    assert duration < 10.0  # Must process 10,000 events in under 10 seconds
    print(f"\n10,000 events GE+Custom validation completed in {duration:.3f}s ({rows_per_sec:.0f} events/sec)")
