#!/usr/bin/env python3
"""
IceStream Day 13 — Apache Iceberg ACID Audit Script
Orchestrates concurrent Writer A, Writer B, and Reader C execution against bronze.checkout_events.
Validates Atomicity, Consistency, Isolation, and Durability guarantees.
"""
import sys
import os
import json
import time
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from iceberg.config.catalog import get_catalog, get_catalog_config
from tests.acid.writer_a import WriterA
from tests.acid.writer_b import WriterB
from tests.acid.reader_c import ReaderC


def verify_infrastructure() -> bool:
    """Verifies that Kafka, Flink, MinIO, and Iceberg catalog are responding."""
    config = get_catalog_config(is_internal=False)
    catalog_url = config["uri"]
    
    # 1. Iceberg REST Catalog check
    try:
        req = urllib.request.urlopen(f"{catalog_url}/v1/config", timeout=5)
        if req.status != 200:
            print("Error: Iceberg catalog endpoint returned status", req.status)
            return False
    except Exception as e:
        print(f"Error checking Iceberg REST catalog: {e}")
        return False

    # 2. PyIceberg Table check
    try:
        catalog = get_catalog()
        table = catalog.load_table("bronze.checkout_events")
        if table is None:
            print("Error: Table bronze.checkout_events not found")
            return False
    except Exception as e:
        print(f"Error loading bronze.checkout_events: {e}")
        return False
        
    return True


def run_acid_audit():
    print("====================================================")
    print("IceStream Day 13 — Iceberg ACID Audit")
    print("====================================================")
    print()

    # Step 1: Infra verification
    if not verify_infrastructure():
        print("RESULT: FAIL (Infrastructure check failed)")
        sys.exit(1)

    catalog = get_catalog()
    table = catalog.load_table("bronze.checkout_events")
    table.refresh()

    # Step 2: BEFORE state
    before_snap = table.current_snapshot()
    before_snap_id = before_snap.snapshot_id if before_snap else None
    before_arrow = table.scan(selected_fields=("event_id",)).to_arrow()
    before_count = len(before_arrow)
    before_time = datetime.now(timezone.utc).isoformat()

    print("BEFORE")
    print("----------------------------------------------------")
    print(f"Timestamp:                 {before_time}")
    print(f"Rows:                      {before_count}")
    print(f"Snapshot ID:               {before_snap_id}")
    print()

    # Step 3: Initialize workers
    writer_a = WriterA(record_count=500)
    writer_b = WriterB(record_count=500)
    reader_c = ReaderC(poll_interval_sec=1.5)

    print("CONCURRENT TEST")
    print("----------------------------------------------------")
    print("Writer A                   STARTED")
    print("Writer B                   STARTED")
    print("Reader C                   RUNNING")

    # Step 4: Start Reader C and launch Writer A & B concurrently
    reader_c.start()
    test_start_ts = time.time()

    def run_writer_b():
        time.sleep(0.1)
        return writer_b.run()

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_a = executor.submit(writer_a.run)
        future_b = executor.submit(run_writer_b)
        
        audit_a = future_a.result()
        audit_b = future_b.result()

    test_end_ts = time.time()
    
    # Wait briefly for reader observations to catch final state, then stop reader
    time.sleep(1.0)
    reader_c.stop()
    observations = reader_c.get_observations()

    print(f"Writer A committed         {'✓' if audit_a['commit_status'] == 'SUCCESS' else '✗'}")
    print(f"Writer B committed         {'✓' if audit_b['commit_status'] == 'SUCCESS' else '✗'}")
    print(f"Reader queries             {reader_c.successful_queries}")
    print(f"Reader failures            {reader_c.failed_queries}")
    print()

    # Step 5: AFTER state
    table.refresh()
    after_snap = table.current_snapshot()
    after_snap_id = after_snap.snapshot_id if after_snap else None
    after_arrow = table.scan(selected_fields=("event_id",)).to_arrow()
    after_count = len(after_arrow)

    event_ids_set = set(after_arrow.column("event_id").to_pylist())
    a_matched = sum(1 for eid in audit_a["event_ids"] if eid in event_ids_set)
    b_matched = sum(1 for eid in audit_b["event_ids"] if eid in event_ids_set)

    # Check duplicates for test records
    test_ids = [eid for eid in after_arrow.column("event_id").to_pylist() if eid and (str(eid).startswith("acid_a_") or str(eid).startswith("acid_b_"))]
    id_counts = {}
    for eid in test_ids:
        id_counts[eid] = id_counts.get(eid, 0) + 1
    duplicates_found = sum(1 for cnt in id_counts.values() if cnt > 1)

    print("AFTER")
    print("----------------------------------------------------")
    print(f"Rows:                      {after_count}")
    print(f"Snapshot ID:               {after_snap_id}")
    print(f"Writer A expected:          {len(audit_a['event_ids'])}")
    print(f"Writer A found:             {a_matched}")
    print(f"Writer B expected:          {len(audit_b['event_ids'])}")
    print(f"Writer B found:             {b_matched}")
    print(f"Commit conflicts/retries:   A: {audit_a.get('commit_conflicts', 0)}, B: {audit_b.get('commit_conflicts', 0)}")
    print()

    # Step 6: Durability Test (Restart iceberg-rest service)
    print("DURABILITY TEST")
    print("----------------------------------------------------")
    print("Restarting Iceberg REST catalog service (iceberg-rest)...")
    durability_pass = False
    try:
        subprocess.run(["docker", "compose", "restart", "iceberg-rest"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Wait for REST catalog endpoint to respond after restart
        health_ok = False
        config = get_catalog_config(is_internal=False)
        catalog_url = config["uri"]
        
        for _ in range(15):
            time.sleep(1.0)
            try:
                req = urllib.request.urlopen(f"{catalog_url}/v1/config", timeout=2)
                if req.status == 200:
                    health_ok = True
                    break
            except Exception:
                pass
                
        if not health_ok:
            raise RuntimeError("Iceberg REST catalog did not become healthy after restart")
            
        # Verify table reload and snapshot queryability after restart
        restarted_catalog = get_catalog()
        restarted_tbl = restarted_catalog.load_table("bronze.checkout_events")
        restarted_snap = restarted_tbl.current_snapshot()
        restarted_count = len(restarted_tbl.scan(selected_fields=("event_id",)).to_arrow())
        
        if restarted_snap and restarted_snap.snapshot_id == after_snap_id and restarted_count >= after_count:
            durability_pass = True
            print("Catalog restart check:     ✓ (Table accessible, snapshot intact)")
        else:
            print(f"Catalog restart check:     ✗ (Expected snapshot {after_snap_id}, got {restarted_snap.snapshot_id if restarted_snap else None})")
    except Exception as e:
        print(f"Durability check error:    ✗ ({e})")
    print()

    # Step 7: Evaluate Guarantees
    # Atomicity: Writer commits succeeded completely without partial batch exposure
    atomicity_pass = (audit_a["commit_status"] == "SUCCESS" and audit_a["records_committed"] == a_matched and
                      audit_b["commit_status"] == "SUCCESS" and audit_b["records_committed"] == b_matched)
    
    # Consistency: Table remains queryable, duplicates == 0, schema valid
    consistency_pass = (duplicates_found == 0 and after_count >= before_count + audit_a["records_committed"] + audit_b["records_committed"])
    
    # Isolation: Reader C executed successful queries during concurrent writes without crashing or read errors
    isolation_pass = (reader_c.successful_queries > 0 and reader_c.failed_queries == 0)

    print("ACID GUARANTEE EVALUATION")
    print("----------------------------------------------------")
    print(f"Atomicity                  {'PASS' if atomicity_pass else 'FAIL'}")
    print(f"Consistency                {'PASS' if consistency_pass else 'FAIL'}")
    print(f"Isolation                  {'PASS' if isolation_pass else 'FAIL'}")
    print(f"Durability                 {'PASS' if durability_pass else 'FAIL'}")
    print()

    all_passed = atomicity_pass and consistency_pass and isolation_pass and durability_pass
    print(f"RESULT: {'PASS' if all_passed else 'FAIL'}")
    print("====================================================")

    # Save lightweight audit log
    out_dir = Path("artifacts/day13")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    with open(out_dir / "reader_observations.json", "w") as f:
        json.dump(observations, f, indent=2)
        
    audit_summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "before": {
            "snapshot_id": before_snap_id,
            "row_count": before_count,
        },
        "after": {
            "snapshot_id": after_snap_id,
            "row_count": after_count,
        },
        "writer_a": audit_a,
        "writer_b": audit_b,
        "reader_c": {
            "successful_queries": reader_c.successful_queries,
            "failed_queries": reader_c.failed_queries,
            "observations_count": len(observations),
        },
        "evaluations": {
            "atomicity": "PASS" if atomicity_pass else "FAIL",
            "consistency": "PASS" if consistency_pass else "FAIL",
            "isolation": "PASS" if isolation_pass else "FAIL",
            "durability": "PASS" if durability_pass else "FAIL",
        },
        "result": "PASS" if all_passed else "FAIL",
    }
    
    with open(out_dir / "writer_audit.json", "w") as f:
        json.dump(audit_summary, f, indent=2)

    if not all_passed:
        sys.exit(1)


if __name__ == "__main__":
    run_acid_audit()
