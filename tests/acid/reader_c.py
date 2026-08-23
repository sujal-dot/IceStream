"""
IceStream Day 13 — Reader C Client for Iceberg ACID Audit
Continuously queries bronze.checkout_events while concurrent writers run, capturing snapshot isolation metrics.
"""
import sys
import time
import threading
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from iceberg.config.catalog import get_catalog


class ReaderC:
    """
    Reader C background worker polling table state during concurrent writes.
    """
    def __init__(self, poll_interval_sec: float = 0.5, is_internal: bool = False):
        self.poll_interval_sec = poll_interval_sec
        self.is_internal = is_internal
        self.observations: List[Dict[str, Any]] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self.successful_queries = 0
        self.failed_queries = 0
        self._table = None

    def _get_table(self):
        if self._table is None:
            catalog = get_catalog(is_internal=self.is_internal)
            self._table = catalog.load_table("bronze.checkout_events")
        return self._table

    def query_table(self) -> Dict[str, Any]:
        """
        Executes a single scan of bronze.checkout_events to inspect snapshot and row counts.
        """
        now = datetime.now(timezone.utc)
        obs: Dict[str, Any] = {
            "timestamp": now.isoformat(),
            "total_rows": 0,
            "acid_a_count": 0,
            "acid_b_count": 0,
            "snapshot_id": None,
            "status": "FAILED",
            "error": None,
        }
        
        try:
            table = self._get_table()
            table.refresh()
            
            snap = table.current_snapshot()
            obs["snapshot_id"] = snap.snapshot_id if snap else None
            
            if snap and snap.summary and "total-records" in snap.summary:
                obs["total_rows"] = int(snap.summary["total-records"])
            else:
                arrow_tbl = table.scan(selected_fields=("event_id",)).to_arrow()
                obs["total_rows"] = len(arrow_tbl)
            
            obs["status"] = "SUCCESS"
            self.successful_queries += 1
            
        except Exception as e:
            # If cached handle failed, clear it for next poll
            self._table = None
            obs["error"] = str(e)
            self.failed_queries += 1
            
        return obs

    def _poll_loop(self):
        while self._running:
            obs = self.query_table()
            self.observations.append(obs)
            time.sleep(self.poll_interval_sec)

    def start(self):
        """
        Starts Reader C in a background thread.
        """
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """
        Stops Reader C background thread and waits for termination.
        """
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)

    def get_observations(self) -> List[Dict[str, Any]]:
        return self.observations


if __name__ == "__main__":
    reader = ReaderC(poll_interval_sec=0.5)
    print("Testing single query...")
    obs = reader.query_table()
    print("Observation:", obs)
