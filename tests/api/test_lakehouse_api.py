"""API Integration Tests for Lakehouse Health, Compaction, and Maintenance Endpoints."""
from datetime import datetime, timezone
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.storage.db import StorageBackend
from iceberg.maintenance.compactor import CompactionResult
from iceberg.maintenance.manager import LakehouseMaintenanceService, TableHealthReport, MaintenanceRunResult
from iceberg.maintenance.snapshot_manager import SnapshotExpirationResult, OrphanCleanupResult


@pytest.fixture
def mock_storage():
    storage = MagicMock(spec=StorageBackend)
    storage.record_maintenance_run.return_value = 42
    storage.get_maintenance_history.return_value = [
        {
            "id": 1,
            "table_name": "bronze.checkout_events",
            "operation": "MAINTENANCE_PIPELINE",
            "status": "SUCCESS",
            "files_before": 10,
            "files_after": 1,
            "records_compacted": 1000,
            "snapshots_expired": 5,
            "orphan_files_deleted": 20,
            "bytes_reclaimed": 500000,
            "duration_ms": 250.5,
            "error": None,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
    ]
    return storage


@pytest.fixture
def mock_maintenance_service(mock_storage):
    service = MagicMock()
    service.storage = mock_storage

    # Mock health
    bronze_report = TableHealthReport(
        table_name="bronze.checkout_events",
        exists=True,
        total_files=24,
        total_records=3879,
        total_bytes=250000,
        avg_file_size_bytes=10416,
        small_files_count=24,
        snapshot_count=49,
        fragmentation_status="NEEDS_COMPACTION",
        partition_count=0,
        current_snapshot_id=987654321,
        last_updated_at=datetime.now(timezone.utc).isoformat(),
    )
    service.get_table_health.side_effect = lambda name: (
        bronze_report if name == "bronze.checkout_events" else TableHealthReport(table_name=name, exists=False)
    )
    service.get_all_tables_health.return_value = [bronze_report]

    # Mock compactor
    comp_res = CompactionResult(
        table_name="bronze.checkout_events",
        needed=True,
        files_before=24,
        files_after=1,
        bytes_before=250000,
        bytes_after=240000,
        records_compacted=3879,
        duration_ms=180.0,
        success=True,
        snapshot_id=987654322,
    )
    service.compactor.compact_table.return_value = comp_res

    # Mock full maintenance
    maint_res = MaintenanceRunResult(
        table_name="bronze.checkout_events",
        run_id=42,
        compaction=comp_res,
        snapshot_expiration=SnapshotExpirationResult(
            table_name="bronze.checkout_events",
            snapshots_before=49,
            snapshots_expired=44,
            snapshots_remaining=5,
            expired_ids=[i for i in range(44)],
            duration_ms=50.0,
            success=True,
        ),
        orphan_cleanup=OrphanCleanupResult(
            table_name="bronze.checkout_events",
            orphan_files_found=10,
            orphan_files_deleted=10,
            bytes_reclaimed=150000,
            dry_run=False,
            duration_ms=45.0,
            success=True,
        ),
        status="SUCCESS",
        duration_ms=275.0,
    )
    service.run_table_maintenance.return_value = maint_res

    return service


@pytest.fixture
def client(mock_maintenance_service, mock_storage):
    app = create_app(maintenance_service=mock_maintenance_service)
    # Also override database storage dependency
    from backend.storage.db import get_db_storage
    app.dependency_overrides[get_db_storage] = lambda: mock_storage
    return TestClient(app)


def test_get_all_tables_health(client):
    """Verify GET /lakehouse/health returns list of table diagnostics."""
    resp = client.get("/lakehouse/health")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["table_name"] == "bronze.checkout_events"
    assert data[0]["total_files"] == 24
    assert data[0]["fragmentation_status"] == "NEEDS_COMPACTION"


def test_get_single_table_health(client):
    """Verify GET /lakehouse/tables/{namespace}/{table}/health returns metrics for existing table."""
    resp = client.get("/lakehouse/tables/bronze/checkout_events/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["table_name"] == "bronze.checkout_events"
    assert data["total_records"] == 3879
    assert data["exists"] is True


def test_get_table_health_404_not_found(client):
    """Verify GET /lakehouse/tables/{namespace}/{table}/health returns 404 for missing table."""
    resp = client.get("/lakehouse/tables/unknown_ns/unknown_tbl/health")
    assert resp.status_code == 404
    assert "does not exist" in resp.json()["detail"]


AUTH_HEADERS = {"Authorization": "Bearer test_api_token_secret_12345"}


def test_post_compact_table_unauthenticated_returns_401(client):
    """Verify POST /lakehouse/compact without token returns 401 Unauthorized."""
    payload = {"table_name": "bronze.checkout_events"}
    resp = client.post("/lakehouse/compact", json=payload)
    assert resp.status_code == 401


def test_post_compact_table(client):
    """Verify POST /lakehouse/compact executes compaction and returns metrics with auth."""
    payload = {
        "table_name": "bronze.checkout_events",
        "target_file_size_mb": 128,
        "min_file_count": 2,
    }
    resp = client.post("/lakehouse/compact", json=payload, headers=AUTH_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["table_name"] == "bronze.checkout_events"
    assert data["success"] is True
    assert data["files_before"] == 24
    assert data["files_after"] == 1
    assert data["records_compacted"] == 3879


def test_post_maintenance_pipeline(client):
    """Verify POST /lakehouse/maintenance executes full workflow with auth."""
    payload = {
        "table_name": "bronze.checkout_events",
        "compact": True,
        "expire_snapshots": True,
        "cleanup_orphans": True,
        "retain_last": 5,
        "orphan_safety_seconds": 3600,
        "dry_run": False,
    }
    resp = client.post("/lakehouse/maintenance", json=payload, headers=AUTH_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["table_name"] == "bronze.checkout_events"
    assert data["status"] == "SUCCESS"
    assert data["run_id"] == 42
    assert data["compaction"]["files_after"] == 1
    assert data["snapshot_expiration"]["snapshots_expired"] == 44
    assert data["orphan_cleanup"]["orphan_files_deleted"] == 10


def test_get_maintenance_history(client, mock_storage):
    """Verify GET /lakehouse/maintenance/history returns audit records."""
    resp = client.get("/lakehouse/maintenance/history?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["runs"]) == 1
    run = data["runs"][0]
    assert run["table_name"] == "bronze.checkout_events"
    assert run["operation"] == "MAINTENANCE_PIPELINE"
    assert run["files_before"] == 10
    assert run["files_after"] == 1
    assert run["records_compacted"] == 1000
