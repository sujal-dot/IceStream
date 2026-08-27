#!/usr/bin/env python3
"""Performance benchmark for IceStream Schema Drift Detector."""

import time
from pathlib import Path
import sys

# Ensure project root is in sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from schema.compatibility import SchemaComparator
from schema.registry import SchemaRegistry


def run_benchmark(iterations: int = 10000):
    print("Initializing Schema Registry and loading baseline schemas...")
    registry = SchemaRegistry()
    v1_schema = registry.get("v1")
    v3_schema = registry.get("v3")

    comparator = SchemaComparator()

    print(f"Running schema comparison benchmark for {iterations:,} iterations...")
    start_time = time.perf_counter()

    for _ in range(iterations):
        diff = comparator.compare(v1_schema, v3_schema)

    total_time = time.perf_counter() - start_time
    comparisons_per_sec = iterations / total_time if total_time > 0 else 0.0
    avg_latency_ms = (total_time / iterations) * 1000.0 if iterations > 0 else 0.0

    print("\n--- Benchmark Results ---")
    print(f"Total Iterations    : {iterations:,}")
    print(f"Total Time          : {total_time:.4f} seconds")
    print(f"Comparisons / sec   : {comparisons_per_sec:,.2f}")
    print(f"Average Latency     : {avg_latency_ms:.6f} ms per comparison")
    print("-------------------------\n")


if __name__ == "__main__":
    run_benchmark(10000)
