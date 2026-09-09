"""
IceStream Quarantine Writer
Handles durable persistence of quarantine records to Apache Iceberg via PyArrow & REST Catalog.
Includes bounded in-memory batching (50 records or 5s flush interval), thread safety,
failure preservation, and shutdown flush guarantees.
"""
import json
import logging
import os
import threading
import time
from typing import List, Optional, Tuple
import pyarrow as pa

from pyiceberg.catalog import Catalog
from iceberg.config.catalog import get_catalog
from iceberg.schemas.table_schemas import QUARANTINE_INVALID_CHECKOUT_EVENTS_SCHEMA
from metrics.collector import InMemoryMetricsCollector, MetricsCollector
from quarantine.models import QuarantineRecord

logger = logging.getLogger("quality_engine.quarantine.writer")

QUARANTINE_TABLE_NAME = "quarantine.invalid_checkout_events"

PYARROW_QUARANTINE_SCHEMA = pa.schema([
    ("quarantine_id", pa.string()),
    ("event_id", pa.string()),
    ("event", pa.string()),
    ("error_code", pa.string()),
    ("error_message", pa.string()),
    ("failed_rules", pa.list_(pa.string())),
    ("detected_at", pa.string()),
    ("pipeline_version", pa.string()),
    ("schema_version", pa.string()),
])


class QuarantineWriter:
    """Durable persistence engine writing quarantine records to Apache Iceberg table."""

    def __init__(
        self,
        catalog: Optional[Catalog] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        batch_size: Optional[int] = None,
        flush_interval_seconds: Optional[float] = None,
    ) -> None:
        self._catalog = catalog
        self._metrics = metrics_collector or InMemoryMetricsCollector()

        env_batch_size = int(os.getenv("QUARANTINE_BATCH_SIZE", "50"))
        env_flush_interval = float(os.getenv("QUARANTINE_FLUSH_INTERVAL_SECONDS", "5.0"))

        self.batch_size = batch_size if batch_size is not None else env_batch_size
        self.flush_interval_seconds = (
            flush_interval_seconds if flush_interval_seconds is not None else env_flush_interval
        )

        self._buffer: List[QuarantineRecord] = []
        self._lock = threading.Lock()
        self._last_flush_time = time.time()
        self._append_count = 0

    @property
    def catalog(self) -> Catalog:
        """Lazily load catalog if not injected."""
        if self._catalog is None:
            self._catalog = get_catalog()
        return self._catalog

    @property
    def buffer_size(self) -> int:
        """Return current buffered record count."""
        with self._lock:
            return len(self._buffer)

    @property
    def append_count(self) -> int:
        """Return count of atomic Iceberg batch append operations executed."""
        with self._lock:
            return self._append_count

    def ensure_table_exists(self) -> None:
        """Verify that 'quarantine' namespace and 'quarantine.invalid_checkout_events' table exist."""
        cat = self.catalog
        if not cat.table_exists(QUARANTINE_TABLE_NAME):
            try:
                cat.create_namespace("quarantine")
            except Exception:
                pass
            cat.create_table(
                QUARANTINE_TABLE_NAME,
                schema=QUARANTINE_INVALID_CHECKOUT_EVENTS_SCHEMA,
                properties={"write.format.default": "parquet", "format-version": "2"},
            )
            logger.info("Created Iceberg table '%s'", QUARANTINE_TABLE_NAME)

    def write_record(self, record: QuarantineRecord, immediate: bool = False) -> bool:
        """Buffer a quarantine record, flushing if batch size, time interval, or immediate flag is triggered."""
        with self._lock:
            self._buffer.append(record)
            should_flush = (
                immediate
                or len(self._buffer) >= self.batch_size
                or (time.time() - self._last_flush_time) >= self.flush_interval_seconds
            )

        if should_flush:
            cnt, success = self.flush()
            return success
        return True

    def flush(self) -> Tuple[int, bool]:
        """Flush buffered quarantine records to Iceberg.
        
        Preserves buffer if write fails (failure safety).
        """
        with self._lock:
            if not self._buffer:
                return (0, True)
            records_to_flush = list(self._buffer)

        count, success = self.write_batch(records_to_flush)

        with self._lock:
            if success:
                # Remove successfully written records from buffer
                self._buffer = self._buffer[len(records_to_flush):]
                self._last_flush_time = time.time()
                self._metrics.increment_counter("quarantine_batches_written")
                self._metrics.increment_counter("quarantine_records_written", amount=count)
                return (count, True)
            else:
                self._metrics.increment_counter("quarantine_write_failures")
                logger.error(
                    "[QuarantineWriter] Flush failed for %d records. Retaining in buffer.",
                    len(records_to_flush),
                )
                return (0, False)

    def write_invalid_event(
        self, event: dict, quality_result: dict, error_code: str = "INVALID_EVENT", immediate: bool = True
    ) -> dict:
        """Convenience method to construct QuarantineRecord and write to Iceberg/quarantine."""
        import uuid
        from datetime import datetime, timezone

        q_id = f"q_{uuid.uuid4().hex[:12]}"
        evt_id = str(event.get("event_id", f"evt_{uuid.uuid4().hex[:8]}"))
        failed_rules = quality_result.get("failed_rules", [])
        if isinstance(failed_rules, list):
            failed_rules_list = [str(r) for r in failed_rules]
        else:
            failed_rules_list = [str(failed_rules)]

        rec = QuarantineRecord(
            quarantine_id=q_id,
            event_id=evt_id,
            event=json.dumps(event) if isinstance(event, dict) else str(event),
            error_code=error_code,
            error_message=f"Validation failed: {failed_rules_list}",
            failed_rules=failed_rules_list,
            detected_at=datetime.now(timezone.utc).isoformat(),
            pipeline_version="0.22.0",
            schema_version=str(event.get("schema_version", "v1.0")),
        )

        success = self.write_record(rec, immediate=immediate)
        return {
            "status": "SUCCESS" if success else "FAILED",
            "quarantine_id": q_id,
            "event_id": evt_id,
            "error_code": error_code,
            "records_written": 1 if success else 0,
        }

    def write_batch(self, records: List[QuarantineRecord]) -> Tuple[int, bool]:
        """Persist a batch of quarantine records to Iceberg in a single atomic append.

        Args:
            records: List of QuarantineRecord objects to write.

        Returns:
            Tuple of (records_written_count, success_flag)
        """
        if not records:
            return (0, True)

        try:
            tbl = self.catalog.load_table(QUARANTINE_TABLE_NAME)
        except Exception as load_err:
            logger.warning("Failed to load table '%s', attempting initialization: %s", QUARANTINE_TABLE_NAME, load_err)
            try:
                self.ensure_table_exists()
                tbl = self.catalog.load_table(QUARANTINE_TABLE_NAME)
            except Exception as init_err:
                logger.error("Failed to initialize or load table '%s': %s", QUARANTINE_TABLE_NAME, init_err)
                self._metrics.increment_counter("quarantine_write_failure_total", amount=len(records))
                return (0, False)

        pydict = {
            "quarantine_id": [r.quarantine_id for r in records],
            "event_id": [r.event_id for r in records],
            "event": [r.event for r in records],
            "error_code": [r.error_code for r in records],
            "error_message": [r.error_message for r in records],
            "failed_rules": [r.failed_rules for r in records],
            "detected_at": [r.detected_at for r in records],
            "pipeline_version": [r.pipeline_version for r in records],
            "schema_version": [r.schema_version for r in records],
        }

        try:
            arrow_table = pa.Table.from_pydict(pydict, schema=PYARROW_QUARANTINE_SCHEMA)
            tbl.append(arrow_table)
            with self._lock:
                self._append_count += 1
            self._metrics.increment_counter("quarantine_write_success_total", amount=len(records))
            logger.info("Successfully appended %d record(s) to '%s' (append #%d)", len(records), QUARANTINE_TABLE_NAME, self._append_count)
            return (len(records), True)
        except Exception as e:
            logger.error("Failed to append records to Iceberg quarantine table '%s': %s", QUARANTINE_TABLE_NAME, e)
            self._metrics.increment_counter("quarantine_write_failure_total", amount=len(records))
            return (0, False)

    def close(self) -> Tuple[int, bool]:
        """Flush remaining buffered records on shutdown."""
        return self.flush()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass
