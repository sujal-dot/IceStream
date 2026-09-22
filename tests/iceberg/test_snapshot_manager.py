"""Unit and Integration Tests for Snapshot Manager & Orphan Cleaner."""
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
import pytest

from pyiceberg.catalog import Catalog
from pyiceberg.exceptions import NoSuchTableError
from pyiceberg.table import Table

from iceberg.maintenance.snapshot_manager import SnapshotManager, SnapshotExpirationResult, OrphanCleanupResult


@pytest.fixture
def mock_table_with_snapshots():
    tbl = MagicMock(spec=Table)

    # Create 8 snapshots with timestamps spaced 1 hour apart
    snapshots = []
    base_time = datetime(2026, 9, 20, 12, 0, 0, tzinfo=timezone.utc)
    for i in range(8):
        s = MagicMock()
        s.snapshot_id = 1000 + i
        s.timestamp_ms = int((base_time + timedelta(hours=i)).timestamp() * 1000)
        s.manifest_list = f"s3://warehouse/bronze/checkout_events/metadata/snap-{1000+i}.avro"
        snapshots.append(s)

    tbl.snapshots.return_value = snapshots
    tbl.current_snapshot.return_value = snapshots[-1]
    tbl.location.return_value = "s3://warehouse/bronze/checkout_events"
    tbl.metadata_location = "s3://warehouse/bronze/checkout_events/metadata/v1.metadata.json"
    tbl.io = MagicMock()

    # Mock maintenance expire_snapshots
    mock_expire_builder = MagicMock()
    mock_expire_builder.by_id.return_value = mock_expire_builder
    mock_expire_builder.commit.return_value = None
    tbl.maintenance.expire_snapshots.return_value = mock_expire_builder

    return tbl


def test_expire_snapshots_retains_last_n(mock_table_with_snapshots):
    """Verify expire_snapshots retains the most recent N snapshots and expires older ones."""
    catalog = MagicMock(spec=Catalog)
    catalog.load_table.return_value = mock_table_with_snapshots

    manager = SnapshotManager(catalog=catalog)
    res = manager.expire_snapshots("bronze.test", retain_last=3)

    assert res.success is True
    assert res.snapshots_before == 8
    assert res.snapshots_expired == 5
    assert res.expired_ids == [1000, 1001, 1002, 1003, 1004]

    # Verify by_id was called for each expired snapshot
    builder = mock_table_with_snapshots.maintenance.expire_snapshots()
    assert builder.by_id.call_count == 5
    assert builder.commit.call_count == 5


def test_expire_snapshots_below_retention_limit(mock_table_with_snapshots):
    """Verify no snapshots are expired if snapshot count <= retain_last."""
    # Truncate snapshots to 3
    mock_table_with_snapshots.snapshots.return_value = mock_table_with_snapshots.snapshots.return_value[:3]

    catalog = MagicMock(spec=Catalog)
    catalog.load_table.return_value = mock_table_with_snapshots

    manager = SnapshotManager(catalog=catalog)
    res = manager.expire_snapshots("bronze.test", retain_last=5)

    assert res.success is True
    assert res.snapshots_before == 3
    assert res.snapshots_expired == 0
    mock_table_with_snapshots.maintenance.expire_snapshots().commit.assert_not_called()


def test_expire_snapshots_with_older_than(mock_table_with_snapshots):
    """Verify older_than cutoff expires only eligible snapshots."""
    catalog = MagicMock(spec=Catalog)
    catalog.load_table.return_value = mock_table_with_snapshots

    # Cutoff at hour 2
    cutoff = datetime(2026, 9, 20, 14, 30, 0, tzinfo=timezone.utc)

    manager = SnapshotManager(catalog=catalog)
    res = manager.expire_snapshots("bronze.test", older_than=cutoff, retain_last=3)

    assert res.success is True
    # Only snapshots 0, 1, 2 are older than cutoff
    assert res.snapshots_expired == 3
    assert res.expired_ids == [1000, 1001, 1002]


def test_get_referenced_files(mock_table_with_snapshots):
    """Verify referenced files set gathers active manifest and data file paths."""
    # Mock manifest and entries
    mock_manifest = MagicMock()
    mock_manifest.manifest_path = "s3://warehouse/bronze/checkout_events/metadata/m1.avro"

    mock_entry = MagicMock()
    mock_entry.data_file.file_path = "s3://warehouse/bronze/checkout_events/data/file1.parquet"
    mock_manifest.fetch_manifest_entry.return_value = [mock_entry]

    for s in mock_table_with_snapshots.snapshots.return_value:
        s.manifests.return_value = [mock_manifest]

    manager = SnapshotManager()
    referenced = manager.get_referenced_files(mock_table_with_snapshots)

    assert "s3://warehouse/bronze/checkout_events/data/file1.parquet" in referenced
    assert "s3://warehouse/bronze/checkout_events/metadata/m1.avro" in referenced
    assert "s3://warehouse/bronze/checkout_events/metadata/v1.metadata.json" in referenced


@patch("boto3.client")
def test_cleanup_orphan_files_dry_run(mock_boto, mock_table_with_snapshots):
    """Verify orphan detection in dry run mode identifies orphans without deleting."""
    catalog = MagicMock(spec=Catalog)
    catalog.load_table.return_value = mock_table_with_snapshots

    # Mock S3 objects
    now = datetime.now(timezone.utc)
    old_time = now - timedelta(hours=5)
    recent_time = now - timedelta(minutes=5)

    mock_s3 = MagicMock()
    mock_boto.return_value = mock_s3
    paginator = MagicMock()
    paginator.paginate.return_value = [{
        "Contents": [
            # 1. Active data file (referenced)
            {"Key": "bronze/checkout_events/data/active.parquet", "Size": 10000, "LastModified": old_time},
            # 2. Metadata file (protected)
            {"Key": "bronze/checkout_events/metadata/v1.metadata.json", "Size": 2000, "LastModified": old_time},
            # 3. Unreferenced orphan file (older than safety buffer)
            {"Key": "bronze/checkout_events/data/orphan_old.parquet", "Size": 5000, "LastModified": old_time},
            # 4. Unreferenced recent file (within safety buffer, should NOT be deleted)
            {"Key": "bronze/checkout_events/data/recent_inflight.parquet", "Size": 6000, "LastModified": recent_time},
        ]
    }]
    mock_s3.get_paginator.return_value = paginator

    manager = SnapshotManager(catalog=catalog)
    with patch.object(manager, "get_referenced_files", return_value={"s3://warehouse/bronze/checkout_events/data/active.parquet"}):
        with patch.object(manager, "_get_s3_client", return_value=mock_s3):
            res = manager.cleanup_orphan_files("bronze.checkout_events", safety_buffer_seconds=3600, dry_run=True)

    assert res.success is True
    assert res.dry_run is True
    assert res.orphan_files_found == 1
    assert res.orphan_files_deleted == 0
    assert res.bytes_reclaimed == 5000
    assert "bronze/checkout_events/data/orphan_old.parquet" in res.deleted_files
    mock_s3.delete_objects.assert_not_called()


@patch("boto3.client")
def test_cleanup_orphan_files_live_deletion(mock_boto, mock_table_with_snapshots):
    """Verify orphan detection and batch deletion when dry_run=False."""
    catalog = MagicMock(spec=Catalog)
    catalog.load_table.return_value = mock_table_with_snapshots

    old_time = datetime.now(timezone.utc) - timedelta(hours=3)
    mock_s3 = MagicMock()
    paginator = MagicMock()
    paginator.paginate.return_value = [{
        "Contents": [
            {"Key": "bronze/checkout_events/data/orphan1.parquet", "Size": 3000, "LastModified": old_time},
            {"Key": "bronze/checkout_events/data/orphan2.parquet", "Size": 4000, "LastModified": old_time},
        ]
    }]
    mock_s3.get_paginator.return_value = paginator

    manager = SnapshotManager(catalog=catalog)
    with patch.object(manager, "get_referenced_files", return_value=set()):
        with patch.object(manager, "_get_s3_client", return_value=mock_s3):
            res = manager.cleanup_orphan_files("bronze.checkout_events", safety_buffer_seconds=3600, dry_run=False)

    assert res.success is True
    assert res.dry_run is False
    assert res.orphan_files_found == 2
    assert res.orphan_files_deleted == 2
    assert res.bytes_reclaimed == 7000
    mock_s3.delete_objects.assert_called_once()
