"""Unit and Integration Tests for Lakehouse Small-File Compactor."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import pytest

import pyarrow as pa
from pyiceberg.catalog import Catalog
from pyiceberg.exceptions import CommitFailedException, NoSuchTableError
from pyiceberg.manifest import DataFile
from pyiceberg.schema import Schema
from pyiceberg.table import Table
from pyiceberg.types import NestedField, StringType, IntegerType

from iceberg.maintenance.compactor import TableCompactor, CompactionResult


@pytest.fixture
def mock_table():
    tbl = MagicMock(spec=Table)
    tbl.current_snapshot.return_value = MagicMock(snapshot_id=123456789)

    # 3 mock scan tasks with files < 128 MB
    mock_file1 = MagicMock()
    mock_file1.file_size_in_bytes = 5000
    mock_file1.record_count = 100
    mock_task1 = MagicMock()
    mock_task1.file = mock_file1

    mock_file2 = MagicMock()
    mock_file2.file_size_in_bytes = 6000
    mock_file2.record_count = 150
    mock_task2 = MagicMock()
    mock_task2.file = mock_file2

    mock_file3 = MagicMock()
    mock_file3.file_size_in_bytes = 7000
    mock_file3.record_count = 200
    mock_task3 = MagicMock()
    mock_task3.file = mock_file3

    mock_scan = MagicMock()
    mock_scan.plan_files.return_value = [mock_task1, mock_task2, mock_task3]

    # Arrow dataset with 450 total rows
    arrow_tbl = pa.Table.from_pydict({
        "id": [f"id_{i}" for i in range(450)],
        "val": list(range(450)),
    })
    mock_scan.to_arrow.return_value = arrow_tbl
    tbl.scan.return_value = mock_scan

    return tbl


def test_compaction_not_needed_when_below_min_file_count():
    """Verify compaction is skipped when file count is less than threshold."""
    mock_tbl = MagicMock(spec=Table)
    mock_task = MagicMock()
    mock_task.file.file_size_in_bytes = 5000
    mock_scan = MagicMock()
    mock_scan.plan_files.return_value = [mock_task]  # only 1 file
    mock_tbl.scan.return_value = mock_scan
    mock_tbl.current_snapshot.return_value = MagicMock(snapshot_id=111)

    catalog = MagicMock(spec=Catalog)
    catalog.load_table.return_value = mock_tbl

    compactor = TableCompactor(catalog=catalog)
    res = compactor.compact_table("bronze.test", min_file_count=2)

    assert res.success is True
    assert res.needed is False
    assert res.files_before == 1
    assert res.files_after == 1
    assert res.records_compacted == 0
    mock_tbl.overwrite.assert_not_called()


def test_compactor_empty_table():
    """Verify compaction gracefully handles empty tables."""
    mock_tbl = MagicMock(spec=Table)
    mock_scan = MagicMock()
    mock_scan.plan_files.return_value = []
    mock_tbl.scan.return_value = mock_scan
    mock_tbl.current_snapshot.return_value = None

    catalog = MagicMock(spec=Catalog)
    catalog.load_table.return_value = mock_tbl

    compactor = TableCompactor(catalog=catalog)
    res = compactor.compact_table("bronze.empty_test", min_file_count=2)

    assert res.success is True
    assert res.needed is False
    assert res.files_before == 0
    assert res.records_compacted == 0


def test_compactor_table_not_found():
    """Verify NoSuchTableError is reported cleanly without raising."""
    catalog = MagicMock(spec=Catalog)
    catalog.load_table.side_effect = NoSuchTableError("Table missing")

    compactor = TableCompactor(catalog=catalog)
    res = compactor.compact_table("bronze.missing_table")

    assert res.success is False
    assert "does not exist" in res.error


def test_compactor_consolidates_files(mock_table):
    """Verify successful compaction consolidates small files and preserves all records."""
    catalog = MagicMock(spec=Catalog)
    catalog.load_table.return_value = mock_table

    # After overwrite, plan_files returns 1 consolidated file
    mock_compacted_file = MagicMock()
    mock_compacted_file.file_size_in_bytes = 17500
    mock_compacted_task = MagicMock()
    mock_compacted_task.file = mock_compacted_file

    mock_initial_tasks = mock_table.scan.return_value.plan_files.return_value

    def mock_plan_files_side_effect():
        # If overwrite was called, return 1 file, else return 3 files
        if mock_table.overwrite.called:
            return [mock_compacted_task]
        return mock_initial_tasks

    mock_table.scan.return_value.plan_files = mock_plan_files_side_effect

    compactor = TableCompactor(catalog=catalog)
    res = compactor.compact_table("bronze.test", min_file_count=2)

    assert res.success is True
    assert res.needed is True
    assert res.files_before == 3
    assert res.files_after == 1
    assert res.records_compacted == 450
    assert res.snapshot_id == 123456789
    mock_table.overwrite.assert_called_once()


def test_compactor_retries_on_commit_failed_exception(mock_table):
    """Verify optimistic concurrency retry logic catches CommitFailedException."""
    catalog = MagicMock(spec=Catalog)
    catalog.load_table.return_value = mock_table

    # Overwrite fails on first call, succeeds on second call
    mock_table.overwrite.side_effect = [
        CommitFailedException("Conflict: concurrent commit detected"),
        None,
    ]

    mock_compacted_file = MagicMock()
    mock_compacted_file.file_size_in_bytes = 18000
    mock_compacted_task = MagicMock()
    mock_compacted_task.file = mock_compacted_file

    def mock_plan_files_side_effect():
        if mock_table.overwrite.call_count >= 2:
            return [mock_compacted_task]
        return [MagicMock(), MagicMock(), MagicMock()]

    mock_table.scan.return_value.plan_files = mock_plan_files_side_effect

    compactor = TableCompactor(catalog=catalog, max_retries=3, retry_delay_seconds=0.01)
    res = compactor.compact_table("bronze.test", min_file_count=2)

    assert res.success is True
    assert mock_table.overwrite.call_count == 2
    assert res.records_compacted == 450


def test_compactor_integrity_error_on_record_mismatch(mock_table):
    """Verify compaction fails if records after compaction differ from before."""
    catalog = MagicMock(spec=Catalog)
    catalog.load_table.return_value = mock_table

    arrow_tbl_corrupt = pa.Table.from_pydict({
        "id": ["id_1"],
        "val": [1],
    })

    # Return 450 rows first, but only 1 row after overwrite
    def mock_to_arrow():
        if mock_table.overwrite.called:
            return arrow_tbl_corrupt
        return pa.Table.from_pydict({"id": [f"id_{i}" for i in range(450)], "val": list(range(450))})

    mock_table.scan.return_value.to_arrow = mock_to_arrow

    compactor = TableCompactor(catalog=catalog, max_retries=1, retry_delay_seconds=0.01)
    res = compactor.compact_table("bronze.test", min_file_count=2)

    assert res.success is False
    assert "Compaction record count mismatch" in res.error
