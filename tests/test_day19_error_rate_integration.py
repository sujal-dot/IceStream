"""Integration Test Suite for Day 19 End-to-End Error Rate Telemetry.

Verifies complete execution path:
QualityEvent -> QualityEngine -> ValidationSummary -> ErrorRateEngine -> WindowMetrics -> Health Classification -> GET /metrics
"""

import os
import sys
import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
QUALITY_ENGINE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "quality-engine"))
for d in [BACKEND_DIR, QUALITY_ENGINE_DIR]:
    if d not in sys.path:
        sys.path.insert(0, d)

from backend.app import create_app
from metrics.error_rate import ErrorRateEngine, HealthStatus
from rules.engine import QualityEngine
from rules.registry import default_registry
from rules.not_null import NotNullRule
from rules.positive import AmountPositiveRule
from rules.base import Severity
from schemas.event import QualityEvent


from rules.clock import FixedClock


from rules.registry import RuleRegistry


def test_full_pipeline_error_rate_integration():
    """Execute end-to-end flow from QualityEvent processing to GET /metrics endpoint."""
    clock = FixedClock("2026-08-29T10:00:00Z")
    error_engine = ErrorRateEngine(clock=clock)
    
    registry = RuleRegistry()
    registry.register(NotNullRule(field="event_id", name="event_id_not_null", severity_override=Severity.CRITICAL))
    registry.register(AmountPositiveRule(field="amount", name="amount_positive", severity_override=Severity.HIGH))
    quality_engine = QualityEngine(registry=registry)

    app = create_app(engine=error_engine)
    client = TestClient(app)

    # 1. Verify initial zero state from GET /metrics
    resp0 = client.get("/metrics").json()
    assert resp0["windows"]["1m"]["total_events"] == 0
    assert resp0["windows"]["1m"]["data_available"] is False

    # 2. Process Batch 1: 99 valid events, 1 invalid event (AmountPositiveRule fail)
    for i in range(99):
        evt = QualityEvent(
            event_id=f"evt_valid_{i}",
            customer_id=f"cust_{i}",
            amount=150.0 + i,
            event_time="2026-08-29T10:00:00Z",
        )
        _, summary = quality_engine.validate_with_summary(evt)
        error_engine.record_event(summary)

    evt_fail = QualityEvent(
        event_id="evt_fail_1",
        customer_id="cust_fail",
        amount=-50.0,  # Negative amount! Triggers amount_positive FAIL
        event_time="2026-08-29T10:00:00Z",
    )
    _, summary_fail = quality_engine.validate_with_summary(evt_fail)
    error_engine.record_event(summary_fail)

    # 3. Query GET /metrics -> total=100, failed=1, error_rate=0.01 (1.0%) -> WARNING
    resp1 = client.get("/metrics").json()
    win1 = resp1["windows"]["1m"]
    assert win1["total_events"] == 100
    assert win1["valid_events"] == 99
    assert win1["failed_events"] == 1
    assert win1["error_rate"] == 0.01
    assert win1["error_rate_percent"] == 1.0
    assert win1["health"] == "WARNING"
    assert win1["data_available"] is True

    # 4. Add Batch 2: 200 events, 10 failed events
    for i in range(190):
        evt = QualityEvent(
            event_id=f"evt_b2_valid_{i}",
            customer_id=f"cust_b2_{i}",
            amount=200.0,
            event_time="2026-08-29T10:00:10Z",
        )
        _, summary = quality_engine.validate_with_summary(evt)
        error_engine.record_event(summary)

    for i in range(10):
        evt_fail_multi = QualityEvent(
            event_id=None,  # event_id_not_null FAIL
            customer_id=f"cust_b2_fail_{i}",
            amount=-100.0,  # amount_positive FAIL (2 rules failed on 1 event!)
            event_time="2026-08-29T10:00:10Z",
        )
        _, summary_multi = quality_engine.validate_with_summary(evt_fail_multi)
        # Verify 2 rules failed for this single event
        assert summary_multi.failed_rules >= 2
        error_engine.record_event(summary_multi)

    # 5. Query GET /metrics -> total=300, valid=289, failed=11, error_rate=11/300 = 0.03667 (3.67%) -> CRITICAL
    resp2 = client.get("/metrics").json()
    win2 = resp2["windows"]["1m"]
    assert win2["total_events"] == 300
    assert win2["valid_events"] == 289
    assert win2["failed_events"] == 11
    assert abs(win2["error_rate"] - (11.0 / 300.0)) < 1e-5
    assert win2["health"] == "CRITICAL"

    # 6. Verify 5m window contains the exact same total events (since all events were within 5m)
    win5m = resp2["windows"]["5m"]
    assert win5m["total_events"] == 300
    assert win5m["failed_events"] == 11
    assert win5m["health"] == "CRITICAL"
