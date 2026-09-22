"""Unit tests for Lakehouse Partition Manager."""
from unittest.mock import MagicMock
import pytest

from pyiceberg.catalog import Catalog
from pyiceberg.table import Table

from iceberg.maintenance.partition_manager import PartitionManager, PartitionStats


def test_partition_stats_unpartitioned():
    """Verify partition stats calculation for an unpartitioned table."""
    mock_tbl = MagicMock(spec=Table)
    spec = MagicMock()
    spec.is_unpartitioned.return_value = True
    spec.spec_id = 0
    spec.fields = []
    mock_tbl.spec.return_value = spec

    # 2 files with 100 records each
    f1 = MagicMock(partition="()", record_count=100, file_size_in_bytes=5000)
    t1 = MagicMock(file=f1)
    f2 = MagicMock(partition="()", record_count=200, file_size_in_bytes=8000)
    t2 = MagicMock(file=f2)

    mock_tbl.scan.return_value.plan_files.return_value = [t1, t2]

    catalog = MagicMock(spec=Catalog)
    catalog.load_table.return_value = mock_tbl

    mgr = PartitionManager(catalog=catalog)
    stats = mgr.get_partition_stats("bronze.unpart_table")

    assert stats.is_partitioned is False
    assert stats.partition_count == 0
    assert stats.total_files == 2
    assert stats.total_records == 300
    assert stats.total_bytes == 13000
    assert "unpartitioned" in stats.partitions
    assert stats.partitions["unpartitioned"]["file_count"] == 2
    assert stats.partitions["unpartitioned"]["record_count"] == 300


def test_partition_stats_partitioned():
    """Verify partition stats calculation grouping metrics across distinct partitions."""
    mock_tbl = MagicMock(spec=Table)
    spec = MagicMock()
    spec.is_unpartitioned.return_value = False
    spec.spec_id = 1
    field_mock = MagicMock()
    field_mock.source_id = 2
    field_mock.field_id = 1000
    field_mock.name = "country"
    field_mock.transform = "identity"
    spec.fields = [field_mock]
    mock_tbl.spec.return_value = spec

    # 3 files across 2 partitions ('US' and 'EU')
    f1 = MagicMock(partition="Record[US]", record_count=50, file_size_in_bytes=3000)
    t1 = MagicMock(file=f1)
    f2 = MagicMock(partition="Record[US]", record_count=70, file_size_in_bytes=4000)
    t2 = MagicMock(file=f2)
    f3 = MagicMock(partition="Record[EU]", record_count=80, file_size_in_bytes=4500)
    t3 = MagicMock(file=f3)

    mock_tbl.scan.return_value.plan_files.return_value = [t1, t2, t3]

    catalog = MagicMock(spec=Catalog)
    catalog.load_table.return_value = mock_tbl

    mgr = PartitionManager(catalog=catalog)
    stats = mgr.get_partition_stats("bronze.part_table")

    assert stats.is_partitioned is True
    assert stats.partition_count == 2
    assert stats.total_files == 3
    assert stats.total_records == 200
    assert stats.total_bytes == 11500
    assert "Record[US]" in stats.partitions
    assert stats.partitions["Record[US]"]["file_count"] == 2
    assert stats.partitions["Record[US]"]["record_count"] == 120
    assert "Record[EU]" in stats.partitions
    assert stats.partitions["Record[EU]"]["file_count"] == 1
    assert stats.partitions["Record[EU]"]["record_count"] == 80


def test_add_identity_partition():
    """Verify evolving partition spec via update_spec context."""
    mock_tbl = MagicMock(spec=Table)
    mock_update = MagicMock()
    mock_tbl.update_spec.return_value.__enter__.return_value = mock_update

    catalog = MagicMock(spec=Catalog)
    catalog.load_table.return_value = mock_tbl

    mgr = PartitionManager(catalog=catalog)
    res = mgr.add_identity_partition("bronze.test", "payment_status")

    assert res is True
    mock_update.add_identity.assert_called_once_with("payment_status")
