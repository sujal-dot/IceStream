"""
Lakehouse Maintenance Service Coordinator for Apache Iceberg.

Orchestrates table health inspections, small-file compactions, snapshot expirations,
and orphan file cleanups across all lakehouse layers (Bronze, Silver, Quarantine, Audit).
Persists audit history to the database storage backend.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import time
from typing import Any, Dict, List, Optional

from pyiceberg.catalog import Catalog
from pyiceberg.exceptions import NoSuchTableError

from iceberg.config.catalog import get_catalog
from iceberg.maintenance.compactor import TableCompactor, CompactionResult
from iceberg.maintenance.snapshot_manager import (
    SnapshotManager,
    SnapshotExpirationResult,
    OrphanCleanupResult,
)
from iceberg.maintenance.partition_manager import PartitionManager, PartitionStats

logger = logging.getLogger("icestream.iceberg.maintenance_service")


@dataclass
class TableHealthReport:
    """Detailed health, size, and fragmentation diagnostics for an Iceberg table."""
    table_name: str
    exists: bool
    total_files: int = 0
    total_records: int = 0
    total_bytes: int = 0
    avg_file_size_bytes: int = 0
    small_files_count: int = 0
    snapshot_count: int = 0
    fragmentation_status: str = "HEALTHY"  # HEALTHY | NEEDS_COMPACTION | CRITICALLY_FRAGMENTED
    partition_count: int = 0
    current_snapshot_id: Optional[int] = None
    last_updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "table_name": self.table_name,
            "exists": self.exists,
            "total_files": self.total_files,
            "total_records": self.total_records,
            "total_bytes": self.total_bytes,
            "avg_file_size_bytes": self.avg_file_size_bytes,
            "small_files_count": self.small_files_count,
            "snapshot_count": self.snapshot_count,
            "fragmentation_status": self.fragmentation_status,
            "partition_count": self.partition_count,
            "current_snapshot_id": self.current_snapshot_id,
            "last_updated_at": self.last_updated_at,
        }


@dataclass
class MaintenanceRunResult:
    """Aggregated execution metrics for a maintenance run."""
    table_name: str
    run_id: Optional[int] = None
    compaction: Optional[CompactionResult] = None
    snapshot_expiration: Optional[SnapshotExpirationResult] = None
    orphan_cleanup: Optional[OrphanCleanupResult] = None
    status: str = "SUCCESS"  # SUCCESS | PARTIAL_SUCCESS | FAILED
    error: Optional[str] = None
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "table_name": self.table_name,
            "status": self.status,
            "compaction": self.compaction.to_dict() if self.compaction else None,
            "snapshot_expiration": self.snapshot_expiration.to_dict() if self.snapshot_expiration else None,
            "orphan_cleanup": self.orphan_cleanup.to_dict() if self.orphan_cleanup else None,
            "error": self.error,
            "duration_ms": round(self.duration_ms, 2),
        }


class LakehouseMaintenanceService:
    """Unified service coordinating health auditing and table maintenance."""

    KNOWN_TABLES = [
        "bronze.checkout_events",
        "silver.valid_checkout_events",
        "quarantine.invalid_checkout_events",
        "audit.data_quality_results",
    ]

    def __init__(
        self,
        catalog: Optional[Catalog] = None,
        storage: Optional[Any] = None,
        is_internal: bool = False,
    ):
        self._catalog = catalog
        self.storage = storage
        self.is_internal = is_internal
        self.compactor = TableCompactor(catalog=catalog, is_internal=is_internal)
        self.snapshot_manager = SnapshotManager(catalog=catalog, is_internal=is_internal)
        self.partition_manager = PartitionManager(catalog=catalog, is_internal=is_internal)

    @property
    def catalog(self) -> Catalog:
        """Lazily load catalog if not injected."""
        if self._catalog is None:
            self._catalog = get_catalog(is_internal=self.is_internal)
        return self._catalog

    def get_table_health(
        self,
        table_name: str,
        small_file_threshold_bytes: int = 10 * 1024 * 1024,  # 10 MB threshold for "small"
    ) -> TableHealthReport:
        """Inspect and report table health and fragmentation state."""
        try:
            tbl = self.catalog.load_table(table_name)
        except NoSuchTableError:
            return TableHealthReport(table_name=table_name, exists=False)
        except Exception as e:
            logger.warning(f"Error loading table {table_name} for health report: {e}")
            return TableHealthReport(table_name=table_name, exists=False)

        tbl.refresh()
        tasks = list(tbl.scan().plan_files())
        total_files = len(tasks)
        total_bytes = sum(t.file.file_size_in_bytes for t in tasks)
        total_records = sum(t.file.record_count or 0 for t in tasks)
        avg_file_size = int(total_bytes / total_files) if total_files > 0 else 0
        small_files = sum(1 for t in tasks if t.file.file_size_in_bytes < small_file_threshold_bytes)

        snapshots = tbl.snapshots()
        snapshot_count = len(snapshots)
        current_snapshot = tbl.current_snapshot()
        current_id = current_snapshot.snapshot_id if current_snapshot else None
        last_updated = (
            datetime.fromtimestamp(current_snapshot.timestamp_ms / 1000, tz=timezone.utc).isoformat()
            if current_snapshot else None
        )

        # Evaluate fragmentation status
        if total_files > 50 and small_files > 30:
            frag_status = "CRITICALLY_FRAGMENTED"
        elif total_files >= 2 and small_files > 0:
            frag_status = "NEEDS_COMPACTION"
        else:
            frag_status = "HEALTHY"

        is_part = not tbl.spec().is_unpartitioned()
        part_count = len(set(str(t.file.partition) for t in tasks)) if is_part else 0

        return TableHealthReport(
            table_name=table_name,
            exists=True,
            total_files=total_files,
            total_records=total_records,
            total_bytes=total_bytes,
            avg_file_size_bytes=avg_file_size,
            small_files_count=small_files,
            snapshot_count=snapshot_count,
            fragmentation_status=frag_status,
            partition_count=part_count,
            current_snapshot_id=current_id,
            last_updated_at=last_updated,
        )

    def get_all_tables_health(self) -> List[TableHealthReport]:
        """Audit health across all registered lakehouse tables."""
        reports: List[TableHealthReport] = []
        for tbl_name in self.KNOWN_TABLES:
            try:
                reports.append(self.get_table_health(tbl_name))
            except Exception as e:
                logger.error(f"Failed getting health for {tbl_name}: {e}")
                reports.append(TableHealthReport(table_name=tbl_name, exists=False))
        return reports

    def run_table_maintenance(
        self,
        table_name: str,
        compact: bool = True,
        expire_snapshots: bool = True,
        cleanup_orphans: bool = False,
        retain_last_snapshots: int = 5,
        orphan_safety_seconds: int = 3600,
        dry_run: bool = False,
        target_file_size_bytes: int = 128 * 1024 * 1024,
        min_file_count: int = 2,
    ) -> MaintenanceRunResult:
        """Run requested maintenance operations on an individual table.

        Args:
            table_name: Fully qualified table identifier.
            compact: Whether to run small-file compaction.
            expire_snapshots: Whether to expire old historical snapshots.
            cleanup_orphans: Whether to detect and remove unreferenced S3 files.
            retain_last_snapshots: Snapshots to retain when expiring.
            orphan_safety_seconds: Age buffer for orphan file deletion.
            dry_run: Simulate destructive actions without modifying storage.
            target_file_size_bytes: Target file size for compaction.
            min_file_count: Minimum file count to trigger compaction.

        Returns:
            MaintenanceRunResult with granular operation metrics.
        """
        start_time = time.perf_counter()
        started_at = datetime.now(timezone.utc)
        comp_res = None
        exp_res = None
        orphan_res = None
        has_failure = False
        error_msg = None

        # 1. Compaction
        if compact:
            try:
                comp_res = self.compactor.compact_table(
                    table_name=table_name,
                    target_file_size_bytes=target_file_size_bytes,
                    min_file_count=min_file_count,
                )
                if not comp_res.success:
                    has_failure = True
                    error_msg = f"Compaction failed: {comp_res.error}"
            except Exception as e:
                has_failure = True
                error_msg = f"Compaction exception: {e}"
                logger.error(f"Error running compaction on {table_name}: {e}")

        # 2. Snapshot Expiration
        if expire_snapshots and not (has_failure and comp_res and not comp_res.success):
            try:
                exp_res = self.snapshot_manager.expire_snapshots(
                    table_name=table_name,
                    retain_last=retain_last_snapshots,
                )
                if not exp_res.success:
                    has_failure = True
                    error_msg = (error_msg or "") + f" Snapshot expiration failed: {exp_res.error}"
            except Exception as e:
                has_failure = True
                error_msg = (error_msg or "") + f" Snapshot expiration exception: {e}"
                logger.error(f"Error expiring snapshots on {table_name}: {e}")

        # 3. Orphan File Cleanup
        if cleanup_orphans and not has_failure:
            try:
                orphan_res = self.snapshot_manager.cleanup_orphan_files(
                    table_name=table_name,
                    safety_buffer_seconds=orphan_safety_seconds,
                    dry_run=dry_run,
                )
                if not orphan_res.success:
                    has_failure = True
                    error_msg = (error_msg or "") + f" Orphan cleanup failed: {orphan_res.error}"
            except Exception as e:
                has_failure = True
                error_msg = (error_msg or "") + f" Orphan cleanup exception: {e}"
                logger.error(f"Error cleaning orphan files on {table_name}: {e}")

        elapsed = (time.perf_counter() - start_time) * 1000
        completed_at = datetime.now(timezone.utc)

        if has_failure:
            overall_status = "PARTIAL_SUCCESS" if (comp_res and comp_res.success) or (exp_res and exp_res.success) else "FAILED"
        else:
            overall_status = "SUCCESS"

        run_id = None
        # Record maintenance run to storage if available
        if self.storage is not None:
            try:
                files_before = comp_res.files_before if comp_res else 0
                files_after = comp_res.files_after if comp_res else 0
                recs_compacted = comp_res.records_compacted if comp_res else 0
                snaps_expired = exp_res.snapshots_expired if exp_res else 0
                orphans_deleted = orphan_res.orphan_files_deleted if orphan_res else 0
                bytes_reclaimed = orphan_res.bytes_reclaimed if orphan_res else 0

                run_id = self.storage.record_maintenance_run(
                    table_name=table_name,
                    operation="MAINTENANCE_PIPELINE",
                    status=overall_status,
                    files_before=files_before,
                    files_after=files_after,
                    records_compacted=recs_compacted,
                    snapshots_expired=snaps_expired,
                    orphan_files_deleted=orphans_deleted,
                    bytes_reclaimed=bytes_reclaimed,
                    started_at=started_at,
                    completed_at=completed_at,
                    duration_ms=elapsed,
                    error=error_msg,
                )
            except Exception as e:
                logger.warning(f"Failed to record maintenance run to storage: {e}")

        return MaintenanceRunResult(
            table_name=table_name,
            run_id=run_id,
            compaction=comp_res,
            snapshot_expiration=exp_res,
            orphan_cleanup=orphan_res,
            status=overall_status,
            error=error_msg,
            duration_ms=elapsed,
        )

    def run_all_tables_maintenance(self, **kwargs) -> Dict[str, MaintenanceRunResult]:
        """Run maintenance for all registered lakehouse tables."""
        results: Dict[str, MaintenanceRunResult] = {}
        for tbl in self.KNOWN_TABLES:
            try:
                results[tbl] = self.run_table_maintenance(table_name=tbl, **kwargs)
            except Exception as e:
                logger.error(f"Maintenance failed on {tbl}: {e}")
                results[tbl] = MaintenanceRunResult(
                    table_name=tbl,
                    status="FAILED",
                    error=str(e),
                )
        return results
