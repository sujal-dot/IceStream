"""
IceStream Day 13 — Writer B Client for Iceberg ACID Audit
Appends controlled records with prefix 'acid_b_' to bronze.checkout_events via PyIceberg.
"""
import sys
import uuid
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any, List, Optional
from pathlib import Path

import pyarrow as pa
from pyiceberg.io.pyarrow import schema_to_pyarrow

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from iceberg.config.catalog import get_catalog


import random


def generate_writer_b_batch(count: int = 500) -> tuple[List[Dict[str, Any]], List[str]]:
    """
    Generates a batch of realistic checkout events for Writer B.
    All event_ids start with 'acid_b_' followed by a UUID.
    """
    events = []
    event_ids = []
    now = datetime.now(timezone.utc)
    
    for i in range(count):
        eid = f"acid_b_{uuid.uuid4().hex[:12]}"
        event_ids.append(eid)
        event = {
            "event_id": eid,
            "event_time": now,
            "customer_id": f"cust_b_{i:04d}",
            "session_id": f"sess_b_{i:04d}",
            "order_id": f"ord_b_{i:04d}",
            "product_id": f"prod_{200 + (i % 20)}",
            "amount": Decimal(f"{(29.99 + (i * 0.75)):.2f}"),
            "currency": "EUR",
            "payment_method": "paypal",
            "payment_status": "completed",
            "device": "desktop" if i % 2 == 0 else "mobile",
            "country": "DE",
            "source_version": "1.0.0",
            "ingestion_time": now,
        }
        events.append(event)
        
    return events, event_ids


class WriterB:
    """
    Writer B worker executing controlled Iceberg append operations with optimistic concurrency retry handling.
    """
    def __init__(self, record_count: int = 500, max_retries: int = 20, is_internal: bool = False):
        self.record_count = record_count
        self.max_retries = max_retries
        self.is_internal = is_internal

    def run(self) -> Dict[str, Any]:
        """
        Connects to Iceberg, appends Writer B records with optimistic retries, and returns detailed audit metrics.
        """
        start_time = datetime.now(timezone.utc)
        start_ts = time.time()
        
        result: Dict[str, Any] = {
            "writer": "Writer B",
            "start_time": start_time.isoformat(),
            "end_time": None,
            "duration_sec": 0.0,
            "records_attempted": self.record_count,
            "records_committed": 0,
            "commit_status": "FAILED",
            "commit_retries": 0,
            "commit_conflicts": 0,
            "snapshot_before": None,
            "snapshot_after": None,
            "event_ids": [],
            "error": None,
        }
        
        try:
            catalog = get_catalog(is_internal=self.is_internal)
            table = catalog.load_table("bronze.checkout_events")
            table.refresh()
            
            snap_before = table.current_snapshot()
            result["snapshot_before"] = snap_before.snapshot_id if snap_before else None
            
            events, event_ids = generate_writer_b_batch(self.record_count)
            result["event_ids"] = event_ids
            
            pa_schema = schema_to_pyarrow(table.schema())
            dict_data = {
                field.name: [e[field.name] for e in events]
                for field in table.schema().fields
            }
            arrow_table = pa.Table.from_pydict(dict_data, schema=pa_schema)
            
            # Commit to Iceberg table with optimistic concurrency retry and exponential backoff
            attempts = 0
            committed = False
            last_err = None
            
            while attempts < self.max_retries and not committed:
                attempts += 1
                try:
                    table = catalog.load_table("bronze.checkout_events")
                    table.append(arrow_table)
                    table.refresh()
                    committed = True
                    snap_after = table.current_snapshot()
                    result["snapshot_after"] = snap_after.snapshot_id if snap_after else None
                except Exception as commit_err:
                    last_err = commit_err
                    if attempts < self.max_retries:
                        result["commit_conflicts"] += 1
                        result["commit_retries"] += 1
                        backoff = random.uniform(0.2, 0.6) * (1.2 ** attempts)
                        time.sleep(backoff)
                    else:
                        result["error"] = str(commit_err)
                        raise commit_err
            
            end_ts = time.time()
            end_time = datetime.now(timezone.utc)
            
            result["end_time"] = end_time.isoformat()
            result["duration_sec"] = round(end_ts - start_ts, 3)
            result["records_committed"] = len(events)
            result["commit_status"] = "SUCCESS"
            
        except Exception as e:
            end_ts = time.time()
            end_time = datetime.now(timezone.utc)
            result["end_time"] = end_time.isoformat()
            result["duration_sec"] = round(end_ts - start_ts, 3)
            result["error"] = str(e)
            result["commit_status"] = "FAILED"
            
        return result


if __name__ == "__main__":
    writer = WriterB(record_count=100)
    audit = writer.run()
    print("Writer B Result:", audit)
