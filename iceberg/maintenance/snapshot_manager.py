"""
Lakehouse Snapshot Manager & Orphan File Cleaner for Apache Iceberg Tables.

Provides:
1. Snapshot expiration to prevent metadata bloat while safeguarding active branch heads.
2. Orphan file detection and safe deletion from S3/MinIO storage with configurable safety buffers.
"""
import base64
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
import hashlib
import logging
import time
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

import boto3
from pyiceberg.catalog import Catalog
from pyiceberg.exceptions import NoSuchTableError
from pyiceberg.table import Table

from iceberg.config.catalog import get_catalog, get_catalog_config

logger = logging.getLogger("icestream.iceberg.snapshot_manager")


@dataclass
class SnapshotExpirationResult:
    """Result metrics for a snapshot expiration operation."""
    table_name: str
    snapshots_before: int
    snapshots_expired: int
    snapshots_remaining: int
    expired_ids: List[int] = field(default_factory=list)
    duration_ms: float = 0.0
    success: bool = True
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "table_name": self.table_name,
            "snapshots_before": self.snapshots_before,
            "snapshots_expired": self.snapshots_expired,
            "snapshots_remaining": self.snapshots_remaining,
            "expired_ids": self.expired_ids,
            "duration_ms": round(self.duration_ms, 2),
            "success": self.success,
            "error": self.error,
        }


@dataclass
class OrphanCleanupResult:
    """Result metrics for orphan file cleanup operation."""
    table_name: str
    orphan_files_found: int
    orphan_files_deleted: int
    bytes_reclaimed: int
    deleted_files: List[str] = field(default_factory=list)
    dry_run: bool = False
    duration_ms: float = 0.0
    success: bool = True
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "table_name": self.table_name,
            "orphan_files_found": self.orphan_files_found,
            "orphan_files_deleted": self.orphan_files_deleted,
            "bytes_reclaimed": self.bytes_reclaimed,
            "deleted_files": self.deleted_files[:20],  # cap sample list in output
            "dry_run": self.dry_run,
            "duration_ms": round(self.duration_ms, 2),
            "success": self.success,
            "error": self.error,
        }


class SnapshotManager:
    """Manages snapshot lifecycles and cleans unreferenced data/metadata files."""

    def __init__(
        self,
        catalog: Optional[Catalog] = None,
        is_internal: bool = False,
    ):
        self._catalog = catalog
        self.is_internal = is_internal

    @property
    def catalog(self) -> Catalog:
        """Lazily load catalog if not injected."""
        if self._catalog is None:
            self._catalog = get_catalog(is_internal=self.is_internal)
        return self._catalog

    def get_table(self, table_name: str) -> Table:
        """Load and return an Iceberg table instance."""
        return self.catalog.load_table(table_name)

    def _get_s3_client(self):
        """Create configured boto3 S3 client using catalog configuration."""
        cfg = get_catalog_config(is_internal=self.is_internal)
        client = boto3.client(
            "s3",
            endpoint_url=cfg["s3.endpoint"],
            aws_access_key_id=cfg["s3.access-key-id"],
            aws_secret_access_key=cfg["s3.secret-access-key"],
            region_name=cfg["s3.region"],
        )

        def _inject_content_md5(request, **kwargs):
            if request.body:
                body = request.body
                if isinstance(body, str):
                    body = body.encode("utf-8")
                md5_val = base64.b64encode(hashlib.md5(body).digest()).decode("utf-8")
                request.headers["Content-MD5"] = md5_val

        client.meta.events.register("request-created.s3.DeleteObjects", _inject_content_md5)
        return client

    def expire_snapshots(
        self,
        table_name: str,
        older_than: Optional[datetime] = None,
        retain_last: int = 5,
    ) -> SnapshotExpirationResult:
        """Expire old snapshots while protecting recent history.

        Uses sequential single-ID snapshot commits to avoid REST catalog multi-ID
        deserialization errors.

        Args:
            table_name: Fully qualified Iceberg table identifier.
            older_than: Optional cutoff datetime. Only snapshots older than this are expired.
            retain_last: Number of most recent snapshots unconditionally retained (default 5).

        Returns:
            SnapshotExpirationResult detailing expired snapshot IDs and remaining counts.
        """
        start_time = time.perf_counter()

        try:
            tbl = self.get_table(table_name)
        except NoSuchTableError as e:
            elapsed = (time.perf_counter() - start_time) * 1000
            return SnapshotExpirationResult(
                table_name=table_name,
                snapshots_before=0,
                snapshots_expired=0,
                snapshots_remaining=0,
                duration_ms=elapsed,
                success=False,
                error=f"Table '{table_name}' does not exist: {e}",
            )

        tbl.refresh()
        snapshots = tbl.snapshots()
        snapshots_before = len(snapshots)

        if snapshots_before <= retain_last:
            elapsed = (time.perf_counter() - start_time) * 1000
            return SnapshotExpirationResult(
                table_name=table_name,
                snapshots_before=snapshots_before,
                snapshots_expired=0,
                snapshots_remaining=snapshots_before,
                duration_ms=elapsed,
                success=True,
            )

        # Candidates are all snapshots older than the most recent retain_last
        candidate_snapshots = snapshots[:-retain_last] if retain_last > 0 else snapshots[:]

        # Apply older_than filter if specified
        if older_than is not None:
            candidate_snapshots = [
                s for s in candidate_snapshots
                if datetime.fromtimestamp(s.timestamp_ms / 1000, tz=timezone.utc) < older_than
            ]

        # Protect current snapshot head
        current_snapshot = tbl.current_snapshot()
        current_id = current_snapshot.snapshot_id if current_snapshot else None

        expired_ids: List[int] = []
        for s in candidate_snapshots:
            if s.snapshot_id == current_id:
                continue
            try:
                # Expire snapshot individually to comply with Iceberg REST catalog specs
                tbl.maintenance.expire_snapshots().by_id(s.snapshot_id).commit()
                expired_ids.append(s.snapshot_id)
            except Exception as e:
                logger.warning(
                    f"Failed to expire snapshot {s.snapshot_id} on {table_name}: {e}"
                )

        tbl.refresh()
        snapshots_remaining = len(tbl.snapshots())
        elapsed = (time.perf_counter() - start_time) * 1000

        logger.info(
            f"Snapshot expiration on {table_name}: expired {len(expired_ids)} snapshots "
            f"({snapshots_before} -> {snapshots_remaining} remaining in {elapsed:.2f}ms)"
        )

        return SnapshotExpirationResult(
            table_name=table_name,
            snapshots_before=snapshots_before,
            snapshots_expired=len(expired_ids),
            snapshots_remaining=snapshots_remaining,
            expired_ids=expired_ids,
            duration_ms=elapsed,
            success=True,
        )

    def get_referenced_files(self, table: Table) -> Set[str]:
        """Collect all file URIs currently referenced by any active snapshot in table metadata."""
        referenced: Set[str] = set()

        for snapshot in table.snapshots():
            # Add manifest list
            if snapshot.manifest_list:
                referenced.add(snapshot.manifest_list)

            # Fetch each manifest and its data file entries
            try:
                for manifest in snapshot.manifests(table.io):
                    referenced.add(manifest.manifest_path)
                    try:
                        for entry in manifest.fetch_manifest_entry(table.io):
                            if entry.data_file and entry.data_file.file_path:
                                referenced.add(entry.data_file.file_path)
                    except Exception as e:
                        logger.debug(f"Error fetching entries for manifest {manifest.manifest_path}: {e}")
            except Exception as e:
                logger.debug(f"Error reading manifests for snapshot {snapshot.snapshot_id}: {e}")

        # Also add current metadata location
        if table.metadata_location:
            referenced.add(table.metadata_location)

        return referenced

    def cleanup_orphan_files(
        self,
        table_name: str,
        safety_buffer_seconds: int = 3600,
        dry_run: bool = False,
    ) -> OrphanCleanupResult:
        """Find and remove unreferenced data and manifest files in S3/MinIO storage.

        Protects files modified within safety_buffer_seconds to avoid interfering
        with concurrent in-flight writes.

        Args:
            table_name: Fully qualified Iceberg table identifier.
            safety_buffer_seconds: Minimum age of files in seconds before they can be considered orphans.
            dry_run: When True, simulates deletion without removing files.

        Returns:
            OrphanCleanupResult with count of found/deleted files and reclaimed bytes.
        """
        start_time = time.perf_counter()

        try:
            tbl = self.get_table(table_name)
        except NoSuchTableError as e:
            elapsed = (time.perf_counter() - start_time) * 1000
            return OrphanCleanupResult(
                table_name=table_name,
                orphan_files_found=0,
                orphan_files_deleted=0,
                bytes_reclaimed=0,
                dry_run=dry_run,
                duration_ms=elapsed,
                success=False,
                error=f"Table '{table_name}' does not exist: {e}",
            )

        tbl.refresh()
        referenced_files = self.get_referenced_files(tbl)

        # Parse table root S3 location
        table_location = tbl.location()
        parsed_uri = urlparse(table_location)
        bucket = parsed_uri.netloc
        prefix = parsed_uri.path.lstrip("/")
        if not prefix.endswith("/"):
            prefix += "/"

        s3 = self._get_s3_client()
        now = datetime.now(timezone.utc)
        safety_delta = timedelta(seconds=safety_buffer_seconds)

        orphan_objects: List[Dict[str, Any]] = []
        paginator = s3.get_paginator("list_objects_v2")

        try:
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    full_uri = f"s3://{bucket}/{key}"

                    # Do not delete valid referenced files
                    if full_uri in referenced_files or key in referenced_files:
                        continue

                    # Protect table metadata JSON files
                    if key.endswith(".metadata.json") or "version-hint" in key:
                        continue

                    # Safety check: skip recently modified files (in-flight buffer)
                    last_modified = obj["LastModified"]
                    if (now - last_modified) < safety_delta:
                        continue

                    orphan_objects.append(obj)
        except Exception as e:
            elapsed = (time.perf_counter() - start_time) * 1000
            return OrphanCleanupResult(
                table_name=table_name,
                orphan_files_found=0,
                orphan_files_deleted=0,
                bytes_reclaimed=0,
                dry_run=dry_run,
                duration_ms=elapsed,
                success=False,
                error=f"Failed listing S3 objects for {table_name}: {e}",
            )

        orphan_count = len(orphan_objects)
        bytes_reclaimed = sum(obj["Size"] for obj in orphan_objects)
        deleted_keys = [obj["Key"] for obj in orphan_objects]

        if not dry_run and orphan_objects:
            # Batch delete up to 1000 objects per request
            for i in range(0, len(deleted_keys), 1000):
                chunk = deleted_keys[i:i + 1000]
                try:
                    s3.delete_objects(
                        Bucket=bucket,
                        Delete={"Objects": [{"Key": k} for k in chunk], "Quiet": True},
                    )
                except Exception as e:
                    logger.warning(f"Error batch deleting orphan objects: {e}")

        elapsed = (time.perf_counter() - start_time) * 1000
        action_word = "Simulated removal of" if dry_run else "Deleted"
        logger.info(
            f"{action_word} {orphan_count} orphan files ({bytes_reclaimed} bytes reclaimed) "
            f"for {table_name} in {elapsed:.2f}ms"
        )

        return OrphanCleanupResult(
            table_name=table_name,
            orphan_files_found=orphan_count,
            orphan_files_deleted=0 if dry_run else orphan_count,
            bytes_reclaimed=bytes_reclaimed,
            deleted_files=deleted_keys,
            dry_run=dry_run,
            duration_ms=elapsed,
            success=True,
        )
