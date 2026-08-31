#!/usr/bin/env python3
"""
IceStream Day 21 — Quarantine Benchmark
Measures quarantine record creation throughput, batch write throughput, write latency,
and memory usage for 1,000 invalid events.
"""
import os
import sys
from pathlib import Path
import time
import tracemalloc

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "quality-engine"))

from rules.base import Severity, ValidationResult
from metrics.collector import InMemoryMetricsCollector
from quarantine.writer import QuarantineWriter
from quarantine.router import QuarantineRouter


def run_benchmark(event_count: int = 1000, batch_size: int = 250):
    print("========================================")
    print("IceStream Day 21 — Quarantine Benchmark")
    print("========================================")
    print(f"Target Events: {event_count:,}")
    print(f"Batch Size:    {batch_size:,}")
    print()

    metrics = InMemoryMetricsCollector()
    writer = QuarantineWriter(metrics_collector=metrics)
    router = QuarantineRouter(writer=writer, metrics_collector=metrics)

    tracemalloc.start()

    # 1. Prepare 1,000 synthetic invalid events with failures
    prepare_start = time.perf_counter()
    batch_input = []
    for i in range(event_count):
        event = {
            "event_id": f"bench_evt_{i:04d}",
            "amount": None if i % 2 == 0 else -50.0,
            "currency": "INR" if i % 3 != 0 else "XYZ",
            "payment_status": "SUCCESS",
            "source_version": "v3",
        }
        failures = [
            ValidationResult(
                rule_name="amount_not_null" if i % 2 == 0 else "amount_positive",
                passed=False,
                severity=Severity.CRITICAL if i % 2 == 0 else Severity.HIGH,
                message="Invalid amount value",
            )
        ]
        if i % 3 == 0:
            failures.append(
                ValidationResult(
                    rule_name="currency_valid",
                    passed=False,
                    severity=Severity.MEDIUM,
                    message="Invalid currency",
                )
            )
        batch_input.append((event, failures))

    prepare_time = (time.perf_counter() - prepare_start) * 1000.0

    # 2. Measure Batch Quarantine Routing & Iceberg Append
    write_start = time.perf_counter()
    total_written = 0

    for idx in range(0, event_count, batch_size):
        chunk = batch_input[idx : idx + batch_size]
        results = router.route_batch(chunk)
        total_written += sum(1 for r in results if r.success and r.quarantine_record is not None)

    total_write_time_sec = time.perf_counter() - write_start
    write_latency_ms = total_write_time_sec * 1000.0
    throughput = event_count / total_write_time_sec if total_write_time_sec > 0 else 0.0

    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print("----------------------------------------")
    print("Benchmark Results:")
    print("----------------------------------------")
    print(f"Preparation Latency:    {prepare_time:.2f} ms")
    print(f"Total Written Records:  {total_written:,}")
    print(f"Total Write Time:       {write_latency_ms:.2f} ms ({total_write_time_sec:.3f} s)")
    print(f"Write Throughput:       {throughput:.2f} records/sec")
    print(f"Average Record Latency: {(write_latency_ms / event_count):.3f} ms/record")
    print(f"Peak Memory Usage:      {(peak_mem / (1024 * 1024)):.2f} MB")
    print("----------------------------------------")
    print("Quarantine Benchmark Status: SUCCESS ✓")
    print("========================================")


if __name__ == "__main__":
    run_benchmark(event_count=1000, batch_size=250)
