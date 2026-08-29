"""Lightweight Performance Benchmark for Day 19 ErrorRateEngine.

Measures event recording throughput and metric calculation latency over 10,000 events.
"""

import os
import sys
import time

QUALITY_ENGINE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "quality-engine"))
if QUALITY_ENGINE_DIR not in sys.path:
    sys.path.insert(0, QUALITY_ENGINE_DIR)

from metrics.error_rate import ErrorRateEngine


def run_benchmark(num_events: int = 10000) -> None:
    """Run performance benchmark recording num_events into ErrorRateEngine."""
    print("=" * 60)
    print(f"IceStream Day 19 Performance Benchmark — {num_events:,} Events")
    print("=" * 60)

    engine = ErrorRateEngine()

    start_time = time.perf_counter()
    for i in range(num_events):
        is_valid = (i % 20 != 0)  # 5% failure rate
        engine.record_event_outcome(is_valid=is_valid)

    elapsed_recording = time.perf_counter() - start_time
    events_per_sec = num_events / elapsed_recording if elapsed_recording > 0 else 0.0

    calc_start = time.perf_counter()
    metrics = engine.calculate(window_seconds=60)
    calc_latency_ms = (time.perf_counter() - calc_start) * 1000.0

    snap_start = time.perf_counter()
    snapshot = engine.get_metrics_snapshot()
    snap_latency_ms = (time.perf_counter() - snap_start) * 1000.0

    print(f"Recorded Events     : {num_events:,}")
    print(f"Total Recording Time: {elapsed_recording * 1000.0:.2f} ms")
    print(f"Throughput          : {events_per_sec:,.0f} events/sec")
    print(f"Calc Latency (1m)   : {calc_latency_ms:.4f} ms")
    print(f"Snapshot Latency    : {snap_latency_ms:.4f} ms")
    print("-" * 60)
    print(f"Calculated Metrics  : Total={metrics.total_events}, Valid={metrics.valid_events}, Failed={metrics.failed_events}")
    print(f"Error Rate          : {metrics.error_rate_percent:.2f}% ({metrics.health_status.value})")
    print("=" * 60)

    assert metrics.total_events == num_events
    assert events_per_sec > 1000.0, f"Throughput should exceed 1,000 events/sec (got {events_per_sec:.0f})"
    assert calc_latency_ms < 50.0, f"Calculation latency should be under 50ms (got {calc_latency_ms:.2f}ms)"
    print("BENCHMARK PASSED SUCCESSFULLY.")


if __name__ == "__main__":
    run_benchmark(10000)
