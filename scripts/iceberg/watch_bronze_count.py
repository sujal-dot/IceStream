#!/usr/bin/env python3
"""
IceStream Bronze Table Count Monitoring Script
Continuously polls the record count of icestream.bronze.checkout_events,
computes real-time streaming ingestion rates, and verifies continuous growth.
"""

import sys
import time
import argparse
from datetime import datetime
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from iceberg.config.catalog import get_catalog


def watch_bronze_count(interval: int = 5, duration: int = 30):
    print("========================================")
    print("IceStream Bronze Count Monitor")
    print("========================================")
    print(f"{'Time':<20} {'Count':<15} {'Status':<15} {'Rate (ev/s)':<15}")
    print("-" * 65)

    catalog = get_catalog()
    table = catalog.load_table("bronze.checkout_events")

    start_time = time.time()
    last_count = None
    last_time = None
    initial_count = None
    counts = []

    while time.time() - start_time <= duration:
        now = datetime.now()
        current_time_str = now.strftime("%H:%M:%S")
        cur_time = time.time()

        try:
            # Refresh table metadata and scan count
            table.refresh()
            count = len(table.scan().to_arrow())
        except Exception as e:
            print(f"{current_time_str:<20} {'ERROR':<15} {str(e):<30}")
            time.sleep(interval)
            continue

        if initial_count is None:
            initial_count = count

        status = "INITIAL"
        rate_str = "N/A"

        if last_count is not None:
            delta_count = count - last_count
            delta_t = cur_time - last_time
            if delta_t > 0:
                rate = delta_count / delta_t
                rate_str = f"{rate:.1f}"

            if count > last_count:
                status = "INCREASING"
            elif count == last_count:
                status = "STABLE"
            else:
                status = "DECREASING"

        counts.append(count)
        print(f"{current_time_str:<20} {count:<15} {status:<15} {rate_str:<15}")

        last_count = count
        last_time = cur_time
        time.sleep(interval)

    print("-" * 65)
    final_count = counts[-1] if counts else 0
    total_delta = final_count - (initial_count or 0)
    total_time = duration

    print(f"\nInitial Count: {initial_count}")
    print(f"Final Count:   {final_count}")
    print(f"Total Growth:  {total_delta} events")

    is_growing = final_count > (initial_count or 0) or (len(counts) > 1 and max(counts) > min(counts))
    growth_status = "INCREASING" if is_growing else "NOT INCREASING"
    print(f"Overall Trend: {growth_status}")

    return is_growing


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Watch Bronze count continuously.")
    parser.add_argument("--interval", type=int, default=5, help="Polling interval in seconds")
    parser.add_argument("--duration", type=int, default=30, help="Total watch duration in seconds")
    args = parser.parse_args()

    watch_bronze_count(interval=args.interval, duration=args.duration)
