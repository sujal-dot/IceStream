"""
Lakehouse Small-File Compaction Engine for Apache Iceberg Tables.

Provides atomic consolidation of fragmented streaming Parquet data files into
optimized target-sized files (e.g. 128 MB) with zero data loss and optimistic
concurrency retry handling.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import random
import time
from typing import Any, Dict, List, Optional

import pyarrow as pa
from pyiceberg.catalog import Catalog
from pyiceberg.exceptions import CommitFailedException, NoSuchTableError
from pyiceberg.table import Table

from iceberg.config.catalog import get_catalog

logger = logging.getLogger("icestream.iceberg.compactor")


@dataclass
class CompactionResult:
    """Result metrics for a table compaction operation."""
    table_name: str
    needed: bool
    files_before: int
    files_after: int
    bytes_before: int
    bytes_after: int
    records_compacted: int
    duration_ms: float
    success: bool
    error: Optional[str] = None
    snapshot_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "table_name": self.table_name,
            "needed": self.needed,
            "files_before": self.files_before,
            "files_after": self.files_after,
            "bytes_before": self.bytes_before,
            "bytes_after": self.bytes_after,
            "records_compacted": self.records_compacted,
            "duration_ms": round(self.duration_ms, 2),
            "success": self.success,
            "error": self.error,
            "snapshot_id": self.snapshot_id,
        }


class TableCompactor:
    """Compacts fragmented small Parquet data files in Iceberg tables."""

    def __init__(
        self,
        catalog: Optional[Catalog] = None,
        is_internal: bool = False,
        max_retries: int = 3,
        retry_delay_seconds: float = 1.0,
    ):
        self._catalog = catalog
        self.is_internal = is_internal
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds

    @property
    def catalog(self) -> Catalog:
        """Lazily load catalog if not injected."""
        if self._catalog is None:
            self._catalog = get_catalog(is_internal=self.is_internal)
        return self._catalog

    def get_table(self, table_name: str) -> Table:
        """Load and return an Iceberg table instance."""
        return self.catalog.load_table(table_name)

    def is_compaction_needed(
        self,
        table_name: str,
        min_file_count: int = 2,
        target_file_size_bytes: int = 128 * 1024 * 1024,
    ) -> bool:
        """Evaluate if the table has small file fragmentation requiring compaction."""
        tbl = self.get_table(table_name)
        tasks = list(tbl.scan().plan_files())
        if len(tasks) < min_file_count:
            return False
        # If any data file is smaller than target file size and multiple files exist
        has_small_files = any(t.file.file_size_in_bytes < target_file_size_bytes for t in tasks)
        return has_small_files

    def compact_table(
        self,
        table_name: str,
        target_file_size_bytes: int = 128 * 1024 * 1024,
        min_file_count: int = 2,
        max_retries: Optional[int] = None,
    ) -> CompactionResult:
        """Consolidate small Parquet data files into optimized files.

        Reads all records in the active snapshot, atomically replaces fragmented files
        via PyIceberg table overwrite, and verifies complete record preservation.

        Args:
            table_name: Fully qualified Iceberg table identifier (e.g. 'bronze.checkout_events').
            target_file_size_bytes: Target file size in bytes (default 128 MB).
            min_file_count: Minimum file count to trigger compaction (default 2).
            max_retries: Concurrency conflict retry limit (defaults to class config).

        Returns:
            CompactionResult containing file counts, sizes, record counts, and duration.
        """
        start_time = time.perf_counter()
        retries = max_retries if max_retries is not None else self.max_retries

        try:
            tbl = self.get_table(table_name)
        except NoSuchTableError as e:
            elapsed = (time.perf_counter() - start_time) * 1000
            return CompactionResult(
                table_name=table_name,
                needed=False,
                files_before=0,
                files_after=0,
                bytes_before=0,
                bytes_after=0,
                records_compacted=0,
                duration_ms=elapsed,
                success=False,
                error=f"Table '{table_name}' does not exist: {e}",
            )

        tasks_before = list(tbl.scan().plan_files())
        files_before = len(tasks_before)
        bytes_before = sum(t.file.file_size_in_bytes for t in tasks_before)

        # Check if compaction is needed
        if files_before < min_file_count:
            elapsed = (time.perf_counter() - start_time) * 1000
            logger.info(
                f"Compaction not needed for {table_name}: {files_before} files "
                f"(min threshold: {min_file_count})"
            )
            return CompactionResult(
                table_name=table_name,
                needed=False,
                files_before=files_before,
                files_after=files_before,
                bytes_before=bytes_before,
                bytes_after=bytes_before,
                records_compacted=0,
                duration_ms=elapsed,
                success=True,
                snapshot_id=tbl.current_snapshot().snapshot_id if tbl.current_snapshot() else None,
            )

        last_error = None
        for attempt in range(1, retries + 1):
            try:
                tbl.refresh()
                # Read all active records
                arrow_data = tbl.scan().to_arrow()
                records_before = arrow_data.num_rows

                if records_before == 0:
                    elapsed = (time.perf_counter() - start_time) * 1000
                    return CompactionResult(
                        table_name=table_name,
                        needed=False,
                        files_before=files_before,
                        files_after=0,
                        bytes_before=bytes_before,
                        bytes_after=0,
                        records_compacted=0,
                        duration_ms=elapsed,
                        success=True,
                        snapshot_id=tbl.current_snapshot().snapshot_id if tbl.current_snapshot() else None,
                    )

                logger.info(
                    f"[Attempt {attempt}/{retries}] Compacting {table_name}: "
                    f"{files_before} files, {records_before} records, {bytes_before} bytes"
                )

                # Atomically overwrite table with consolidated PyArrow data
                tbl.overwrite(arrow_data)
                tbl.refresh()

                # Post-compaction record integrity check
                records_after = tbl.scan().to_arrow().num_rows
                if records_after != records_before:
                    raise ValueError(
                        f"Compaction record count mismatch: before={records_before}, after={records_after}"
                    )

                tasks_after = list(tbl.scan().plan_files())
                files_after = len(tasks_after)
                bytes_after = sum(t.file.file_size_in_bytes for t in tasks_after)
                snapshot_id = tbl.current_snapshot().snapshot_id if tbl.current_snapshot() else None
                elapsed = (time.perf_counter() - start_time) * 1000

                logger.info(
                    f"Compaction completed successfully for {table_name}: "
                    f"{files_before} -> {files_after} files ({records_before} records, "
                    f"{bytes_before} -> {bytes_after} bytes in {elapsed:.2f}ms)"
                )

                return CompactionResult(
                    table_name=table_name,
                    needed=True,
                    files_before=files_before,
                    files_after=files_after,
                    bytes_before=bytes_before,
                    bytes_after=bytes_after,
                    records_compacted=records_before,
                    duration_ms=elapsed,
                    success=True,
                    snapshot_id=snapshot_id,
                )

            except CommitFailedException as e:
                last_error = e
                logger.warning(
                    f"[Attempt {attempt}/{retries}] Optimistic concurrency conflict while compacting "
                    f"{table_name}: {e}"
                )
                if attempt < retries:
                    # Exponential backoff with jitter
                    sleep_time = (self.retry_delay_seconds * (2 ** (attempt - 1))) + random.uniform(0.1, 0.5)
                    time.sleep(sleep_time)
            except Exception as e:
                last_error = e
                logger.error(f"Unexpected error compacting {table_name}: {e}")
                break

        elapsed = (time.perf_counter() - start_time) * 1000
        return CompactionResult(
            table_name=table_name,
            needed=True,
            files_before=files_before,
            files_after=files_before,
            bytes_before=bytes_before,
            bytes_after=bytes_before,
            records_compacted=0,
            duration_ms=elapsed,
            success=False,
            error=str(last_error),
        )
