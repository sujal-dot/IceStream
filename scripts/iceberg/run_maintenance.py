#!/usr/bin/env python3
"""
IceStream Lakehouse Maintenance CLI & Scheduled Maintenance Runner.

Executes automated small-file compaction, snapshot expiration, and orphan file
cleanup for Apache Iceberg tables backed by MinIO/S3 object storage.
Can be executed on-demand or as an automated cron/orchestrator task.
"""
import argparse
import os
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.storage.db import get_db_storage
from iceberg.maintenance.manager import LakehouseMaintenanceService


def parse_args():
    parser = argparse.ArgumentParser(
        description="IceStream Lakehouse Maintenance Engine CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--table",
        type=str,
        default="bronze.checkout_events",
        help="Target table identifier or 'all'",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run maintenance for all registered lakehouse tables",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Audit table health and fragmentation without modifying data",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Execute small-file compaction",
    )
    parser.add_argument(
        "--expire-snapshots",
        action="store_true",
        help="Expire historical snapshots beyond retention limit",
    )
    parser.add_argument(
        "--retain-last",
        type=int,
        default=5,
        help="Number of snapshots to unconditionally retain",
    )
    parser.add_argument(
        "--cleanup-orphans",
        action="store_true",
        help="Scan and delete unreferenced S3 files",
    )
    parser.add_argument(
        "--orphan-safety-seconds",
        type=int,
        default=3600,
        help="Age buffer in seconds to protect in-flight writes during orphan cleanup",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate actions without deleting files or committing changes",
    )
    parser.add_argument(
        "--target-file-size-mb",
        type=int,
        default=128,
        help="Target compacted file size in MB",
    )
    parser.add_argument(
        "--min-file-count",
        type=int,
        default=2,
        help="Minimum file count threshold to trigger compaction",
    )
    return parser.parse_args()


def print_health_report(report):
    print("=" * 60)
    print(f"Table: {report.table_name}")
    print("=" * 60)
    if not report.exists:
        print("Status: Table does NOT exist in catalog.")
        return

    print(f"  Fragmentation Status:   {report.fragmentation_status}")
    print(f"  Active Data Files:      {report.total_files}")
    print(f"  Small Files (<10 MB):   {report.small_files_count}")
    print(f"  Total Records:          {report.total_records}")
    print(f"  Total Size (Bytes):     {report.total_bytes:,} ({report.total_bytes / (1024*1024):.2f} MB)")
    print(f"  Avg File Size:          {report.avg_file_size_bytes:,} bytes")
    print(f"  Snapshot History Count: {report.snapshot_count}")
    print(f"  Current Snapshot ID:    {report.current_snapshot_id}")
    print(f"  Partition Count:        {report.partition_count}")
    print(f"  Last Updated At:        {report.last_updated_at}")
    print()


def print_maintenance_result(res):
    print("-" * 60)
    print(f"Maintenance Result: {res.table_name} [Status: {res.status}]")
    print(f"Duration: {res.duration_ms:.2f} ms")
    print("-" * 60)

    if res.compaction:
        c = res.compaction
        print("  [Compaction]")
        print(f"    Needed:             {c.needed}")
        print(f"    Files:              {c.files_before} -> {c.files_after}")
        print(f"    Bytes:              {c.bytes_before:,} -> {c.bytes_after:,}")
        print(f"    Records Compacted:  {c.records_compacted:,}")
        print(f"    Duration:           {c.duration_ms:.2f} ms")
        if c.error:
            print(f"    Error:              {c.error}")

    if res.snapshot_expiration:
        s = res.snapshot_expiration
        print("  [Snapshot Expiration]")
        print(f"    Snapshots:          {s.snapshots_before} -> {s.snapshots_remaining} (Expired: {s.snapshots_expired})")
        print(f"    Expired IDs:        {s.expired_ids}")
        print(f"    Duration:           {s.duration_ms:.2f} ms")
        if s.error:
            print(f"    Error:              {s.error}")

    if res.orphan_cleanup:
        o = res.orphan_cleanup
        print("  [Orphan Cleanup]")
        print(f"    Orphans Found:      {o.orphan_files_found}")
        print(f"    Orphans Deleted:    {o.orphan_files_deleted} (Dry Run: {o.dry_run})")
        print(f"    Bytes Reclaimed:    {o.bytes_reclaimed:,}")
        print(f"    Duration:           {o.duration_ms:.2f} ms")
        if o.error:
            print(f"    Error:              {o.error}")

    if res.error:
        print(f"  General Error: {res.error}")
    print()


def main():
    args = parse_args()
    storage = get_db_storage()
    service = LakehouseMaintenanceService(storage=storage)

    # Determine tables to process
    if args.all or args.table.lower() == "all":
        target_tables = service.KNOWN_TABLES
    else:
        target_tables = [args.table]

    # Health / Status Audit Only
    if args.status:
        print("\n🔍 Running Lakehouse Health & Fragmentation Audit...\n")
        for tbl in target_tables:
            report = service.get_table_health(tbl)
            print_health_report(report)
        return

    # If no action flag specified, default to compact + expire-snapshots
    do_compact = args.compact
    do_expire = args.expire_snapshots
    do_orphans = args.cleanup_orphans
    if not (do_compact or do_expire or do_orphans):
        # Default full maintenance
        do_compact = True
        do_expire = True
        do_orphans = False

    target_bytes = args.target_file_size_mb * 1024 * 1024

    print(f"\n🚀 Starting Lakehouse Table Maintenance...")
    print(f"Tables: {', '.join(target_tables)}")
    print(f"Actions: Compact={do_compact}, ExpireSnapshots={do_expire}, CleanupOrphans={do_orphans} (DryRun={args.dry_run})\n")

    has_failures = False
    for tbl in target_tables:
        result = service.run_table_maintenance(
            table_name=tbl,
            compact=do_compact,
            expire_snapshots=do_expire,
            cleanup_orphans=do_orphans,
            retain_last_snapshots=args.retain_last,
            orphan_safety_seconds=args.orphan_safety_seconds,
            dry_run=args.dry_run,
            target_file_size_bytes=target_bytes,
            min_file_count=args.min_file_count,
        )
        print_maintenance_result(result)
        if result.status == "FAILED":
            has_failures = True

    if has_failures:
        print("⚠️ Maintenance finished with errors.")
        sys.exit(1)
    else:
        print("✅ Lakehouse Maintenance completed successfully.")


if __name__ == "__main__":
    main()
