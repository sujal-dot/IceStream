"""
IceStream Quarantine Writer
Handles durable persistence of quarantine records to Apache Iceberg via PyArrow & REST Catalog.
"""
import logging
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
    ) -> None:
        self._catalog = catalog
        self._metrics = metrics_collector or InMemoryMetricsCollector()

    @property
    def catalog(self) -> Catalog:
        """Lazily load catalog if not injected."""
        if self._catalog is None:
            self._catalog = get_catalog()
        return self._catalog

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

    def write_record(self, record: QuarantineRecord) -> bool:
        """Persist a single quarantine record to Iceberg."""
        written_count, success = self.write_batch([record])
        return success and (written_count == 1)

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
            self._metrics.increment_counter("quarantine_write_success_total", amount=len(records))
            logger.info("Successfully appended %d record(s) to '%s'", len(records), QUARANTINE_TABLE_NAME)
            return (len(records), True)
        except Exception as e:
            logger.error("Failed to append records to Iceberg quarantine table '%s': %s", QUARANTINE_TABLE_NAME, e)
            self._metrics.increment_counter("quarantine_write_failure_total", amount=len(records))
            return (0, False)
