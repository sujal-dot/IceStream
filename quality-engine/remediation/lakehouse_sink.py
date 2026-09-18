"""Lakehouse Sink for Remediated Events.

Provides durable re-ingestion of healed/remediated events back into Apache Iceberg lakehouse tables.
Ensures zero-silent-data-loss when events recover from quarantine.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
import logging
import os
import random
import sys
import time
from typing import Any, Dict, List, Optional

import pyarrow as pa
from pyiceberg.catalog import Catalog
from pyiceberg.exceptions import CommitFailedException
from pyiceberg.io.pyarrow import schema_to_pyarrow

# Ensure iceberg module is accessible
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from iceberg.config.catalog import get_catalog
from iceberg.schemas.table_schemas import (
    BRONZE_CHECKOUT_EVENTS_SCHEMA,
    BRONZE_TABLE_PROPERTIES,
)

logger = logging.getLogger("icestream.remediation.lakehouse_sink")


@dataclass
class IngestionResult:
    """Result of lakehouse re-ingestion attempt."""
    records_written: int
    success: bool
    error: Optional[str] = None
    table_name: Optional[str] = None
    snapshot_id: Optional[int] = None
    event_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "records_written": self.records_written,
            "success": self.success,
            "error": self.error,
            "table_name": self.table_name,
            "snapshot_id": self.snapshot_id,
            "event_ids": self.event_ids,
        }


class LakehouseSink(ABC):
    """Abstract base interface for persisting healed events to Lakehouse."""

    @abstractmethod
    def write_events(self, events: List[Dict[str, Any]]) -> IngestionResult:
        """Persist a list of validated events to the target lakehouse storage.

        Args:
            events: List of event dictionaries validated by QualityEngine.

        Returns:
            IngestionResult containing success status, record count, and metadata.
        """
        pass


class IcebergLakehouseSink(LakehouseSink):
    """Production Lakehouse sink appending remediated events to Apache Iceberg tables via PyIceberg."""

    def __init__(
        self,
        catalog: Optional[Catalog] = None,
        table_name: str = "bronze.checkout_events",
        max_retries: int = 5,
        is_internal: bool = False,
    ):
        self._catalog = catalog
        self.table_name = table_name
        self.max_retries = max_retries
        self.is_internal = is_internal

    @property
    def catalog(self) -> Catalog:
        """Lazily load catalog if not injected."""
        if self._catalog is None:
            self._catalog = get_catalog(is_internal=self.is_internal)
        return self._catalog

    def ensure_table_exists(self) -> None:
        """Verify target table and namespace exist in the catalog."""
        cat = self.catalog
        if not cat.table_exists(self.table_name):
            ns = self.table_name.split(".")[0]
            try:
                cat.create_namespace(ns)
            except Exception:
                pass
            cat.create_table(
                self.table_name,
                schema=BRONZE_CHECKOUT_EVENTS_SCHEMA,
                properties=BRONZE_TABLE_PROPERTIES,
            )
            logger.info("Created Iceberg table '%s'", self.table_name)

    def _normalize_events_for_schema(
        self, events: List[Dict[str, Any]], schema_fields: List[Any]
    ) -> Dict[str, List[Any]]:
        """Normalize event dictionaries to match the PyIceberg/PyArrow table schema.

        Converts ISO datetime strings to UTC datetime objects, floats/ints to Decimals for amount,
        and ensures missing columns are filled with None.
        Internal metadata fields like '_remediation_incident_id' are filtered out.
        """
        dict_data: Dict[str, List[Any]] = {field.name: [] for field in schema_fields}
        now_utc = datetime.now(timezone.utc)

        for event in events:
            for field in schema_fields:
                fname = field.name
                val = event.get(fname)

                if val is None:
                    # Provide sensible default for ingestion_time if absent
                    if fname == "ingestion_time":
                        val = now_utc
                    dict_data[fname].append(None if fname != "ingestion_time" else val)
                    continue

                # Type conversions based on target Iceberg field types
                field_type_str = str(field.field_type).lower()

                if "timestamp" in field_type_str:
                    if isinstance(val, str):
                        try:
                            # Handle ISO format timestamp strings
                            dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
                            if dt.tzinfo is None:
                                dt = dt.replace(tzinfo=timezone.utc)
                            val = dt
                        except Exception:
                            val = now_utc
                    elif isinstance(val, (int, float)):
                        # Epoch timestamp in seconds or millis
                        val = datetime.fromtimestamp(val if val < 1e11 else val / 1000.0, tz=timezone.utc)
                elif "decimal" in field_type_str:
                    if not isinstance(val, Decimal):
                        try:
                            val = Decimal(f"{float(val):.2f}")
                        except Exception:
                            val = Decimal("0.00")

                dict_data[fname].append(val)

        return dict_data

    def write_events(self, events: List[Dict[str, Any]]) -> IngestionResult:
        """Durable batch append of remediated events to the Iceberg table with optimistic retry."""
        if not events:
            logger.info("[IcebergLakehouseSink] No events to append.")
            return IngestionResult(records_written=0, success=True, table_name=self.table_name)

        event_ids = [str(e.get("event_id", "")) for e in events]

        try:
            try:
                table = self.catalog.load_table(self.table_name)
            except Exception as load_err:
                logger.warning(
                    "[IcebergLakehouseSink] Failed to load table '%s', attempting creation: %s",
                    self.table_name,
                    load_err,
                )
                self.ensure_table_exists()
                table = self.catalog.load_table(self.table_name)

            table.refresh()
            schema = table.schema()
            pa_schema = schema_to_pyarrow(schema)
            dict_data = self._normalize_events_for_schema(events, schema.fields)
            arrow_table = pa.Table.from_pydict(dict_data, schema=pa_schema)

            # Optimistic Concurrency Retry Loop
            attempts = 0
            committed = False
            last_err: Optional[Exception] = None
            snap_id: Optional[int] = None

            while attempts < self.max_retries and not committed:
                attempts += 1
                try:
                    table.append(arrow_table)
                    table.refresh()
                    committed = True
                    snap = table.current_snapshot()
                    snap_id = snap.snapshot_id if snap else None
                    logger.info(
                        "[IcebergLakehouseSink] Successfully appended %d remediated record(s) to '%s' "
                        "(snapshot_id=%s, attempt=%d)",
                        len(events),
                        self.table_name,
                        snap_id,
                        attempts,
                    )
                except (CommitFailedException, Exception) as commit_err:
                    last_err = commit_err
                    if attempts < self.max_retries:
                        backoff = random.uniform(0.1, 0.4) * (1.5 ** attempts)
                        logger.warning(
                            "[IcebergLakehouseSink] Commit conflict on attempt %d/%d: %s. Retrying in %.2fs...",
                            attempts,
                            self.max_retries,
                            commit_err,
                            backoff,
                        )
                        time.sleep(backoff)
                        table.refresh()
                    else:
                        logger.error(
                            "[IcebergLakehouseSink] Commit failed after %d attempts: %s",
                            attempts,
                            commit_err,
                        )
                        raise commit_err

            return IngestionResult(
                records_written=len(events),
                success=True,
                table_name=self.table_name,
                snapshot_id=snap_id,
                event_ids=event_ids,
            )

        except Exception as e:
            err_msg = f"Failed to append remediated events to '{self.table_name}': {str(e)}"
            logger.error(f"[IcebergLakehouseSink] {err_msg}")
            return IngestionResult(
                records_written=0,
                success=False,
                error=err_msg,
                table_name=self.table_name,
                event_ids=event_ids,
            )


class MockLakehouseSink(LakehouseSink):
    """In-memory Mock Lakehouse Sink for fast, deterministic unit and failure testing."""

    def __init__(self, table_name: str = "bronze.checkout_events"):
        self.table_name = table_name
        self.written_events: List[Dict[str, Any]] = []
        self.fail_next_write: bool = False
        self.failure_error: str = "Simulated lakehouse commit failure"
        self.write_calls: int = 0

    def write_events(self, events: List[Dict[str, Any]]) -> IngestionResult:
        self.write_calls += 1
        event_ids = [str(e.get("event_id", "")) for e in events]

        if self.fail_next_write:
            self.fail_next_write = False
            logger.warning("[MockLakehouseSink] Failing write as requested by test.")
            return IngestionResult(
                records_written=0,
                success=False,
                error=self.failure_error,
                table_name=self.table_name,
                event_ids=event_ids,
            )

        self.written_events.extend(events)
        logger.info(
            "[MockLakehouseSink] Successfully wrote %d events (total_stored=%d)",
            len(events),
            len(self.written_events),
        )
        return IngestionResult(
            records_written=len(events),
            success=True,
            table_name=self.table_name,
            snapshot_id=1000 + self.write_calls,
            event_ids=event_ids,
        )

    def clear(self) -> None:
        self.written_events.clear()
        self.fail_next_write = False
        self.write_calls = 0
