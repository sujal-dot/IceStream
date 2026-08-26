"""Performance and memory safety benchmark for Quality Engine (10,000 events)."""

import time
import pytest
from rules.engine import QualityEngine
from rules.registry import create_default_registry
from schemas.event import QualityEvent


@pytest.mark.performance
def test_quality_engine_10k_events_performance():
    """Benchmark in-memory Quality Engine processing 10,000 events."""
    registry = create_default_registry()
    engine = QualityEngine(registry=registry)

    total_events = 10000
    start_time = time.perf_counter()

    for i in range(total_events):
        event = QualityEvent(
            event_id=f"evt_perf_{i}",
            order_id=f"ORD_{i}",
            customer_id=f"cust_{i % 100}",
            session_id=f"sess_{i % 500}",
            product_id="PROD_100",
            quantity=1,
            unit_price=29.99,
            amount=29.99,
            currency="USD",
            payment_method="CREDIT_CARD",
            payment_status="SUCCESS",
            device="mobile",
            country="US",
            source_version="v1.0.0",
            event_time="2026-08-26T10:00:00Z",
            ingestion_time="2026-08-26T10:00:05Z",
        )
        engine.validate(event)

    elapsed_sec = time.perf_counter() - start_time
    events_per_sec = total_events / elapsed_sec if elapsed_sec > 0 else 0.0

    metrics = engine.metrics.get_metrics()
    assert metrics["total_events"] == total_events
    assert metrics["valid_events"] == total_events
    assert metrics["invalid_events"] == 0
    assert events_per_sec > 500.0, f"Expected > 500 events/sec, got {events_per_sec:.2f}"

    print(
        f"\n--- Quality Engine Performance Benchmark ---\n"
        f"Processed {total_events:,} events in {elapsed_sec:.3f}s\n"
        f"Throughput: {events_per_sec:,.2f} events/sec\n"
        f"Average Latency per event: {(elapsed_sec / total_events) * 1000:.3f} ms"
    )
