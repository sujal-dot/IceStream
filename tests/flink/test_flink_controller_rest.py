"""Tests for Native Flink REST API Integration and Telemetry in FlinkController and Backend."""

import json
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from backend.app import create_app, set_flink_controller
from backend.storage.db import StorageBackend
from remediation.flink_controller import FlinkController


@pytest.fixture
def mock_flink_controller():
    fc = FlinkController(flink_url="http://mock-flink:8081")
    return fc


def test_cluster_overview_mocked(mock_flink_controller):
    """Verify cluster capacity parsing from Flink REST /overview and /config."""
    with patch.object(mock_flink_controller, "_rest_request") as mock_req:
        mock_req.side_effect = lambda method, path, **kwargs: (
            {"taskmanagers": 2, "slots-total": 8, "slots-available": 6, "jobs-running": 1, "jobs-finished": 4}
            if path == "/overview"
            else {"flink-version": "1.18.1"}
        )
        overview = mock_flink_controller.get_cluster_overview()
        assert overview["taskmanagers"] == 2
        assert overview["slots_total"] == 8
        assert overview["slots_available"] == 6
        assert overview["jobs_running"] == 1
        assert overview["flink_version"] == "1.18.1"


def test_checkpoint_metrics_parsing_mocked(mock_flink_controller):
    """Verify checkpoint statistics parsing including latest checkpoint, savepoint, and duration."""
    chk_response = {
        "counts": {"total": 50, "completed": 48, "failed": 2, "in_progress": 0, "restored": 1},
        "latest": {
            "completed": {
                "id": 48,
                "status": "COMPLETED",
                "external_path": "s3://checkpoints/flink/chk-48",
                "state_size": 2048,
                "end_to_end_duration": 145,
                "trigger_timestamp": 1789965000000,
            },
            "savepoint": {
                "id": 10,
                "status": "COMPLETED",
                "external_path": "s3://checkpoints/flink-savepoints/sp-10",
                "state_size": 4096,
                "trigger_timestamp": 1789964000000,
            },
            "failed": {
                "id": 47,
                "status": "FAILED",
                "failure_message": "Network timeout",
                "failure_timestamp": 1789964900000,
            },
        },
        "summary": {
            "end_to_end_duration": {"avg": 130.5},
            "state_size": {"avg": 2000.0},
        },
    }

    with patch.object(mock_flink_controller, "_rest_request") as mock_req:
        mock_req.return_value = chk_response
        metrics = mock_flink_controller.get_checkpoint_metrics("test_job_123")

        assert metrics["available"] is True
        assert metrics["job_id"] == "test_job_123"
        assert metrics["counts"]["completed"] == 48
        assert metrics["counts"]["failed"] == 2
        assert metrics["latest_checkpoint"]["id"] == 48
        assert metrics["latest_checkpoint"]["external_path"] == "s3://checkpoints/flink/chk-48"
        assert metrics["latest_savepoint"]["external_path"] == "s3://checkpoints/flink-savepoints/sp-10"
        assert metrics["latest_failed"]["failure_message"] == "Network timeout"
        assert metrics["summary"]["avg_duration_ms"] == 130.5


def test_checkpoint_metrics_when_no_active_job(mock_flink_controller):
    """Verify fallback structure when no Flink job is active."""
    with patch.object(mock_flink_controller, "get_active_job_id", return_value=None):
        metrics = mock_flink_controller.get_checkpoint_metrics(None)
        assert metrics["available"] is False
        assert metrics["job_id"] is None
        assert metrics["counts"]["total"] == 0


def test_job_exceptions_parsing_mocked(mock_flink_controller):
    """Verify job exceptions and root-cause extraction."""
    exc_response = {
        "root-exception": "java.lang.RuntimeException: Sink table write failed",
        "all-exceptions": [{"exception": "details"}],
        "timestamp": 1789965100000,
        "truncated": False,
    }

    with patch.object(mock_flink_controller, "_rest_request", return_value=exc_response):
        exc = mock_flink_controller.get_job_exceptions("job_abc")
        assert exc["has_exceptions"] is True
        assert "Sink table write failed" in exc["root_exception"]
        assert exc["truncated"] is False


def test_trigger_savepoint_lifecycle_mocked(mock_flink_controller):
    """Verify asynchronous savepoint triggering and polling cycle."""
    responses = [
        {"request-id": "trig_001"},  # POST response
        {"status": {"id": "IN_PROGRESS"}},  # 1st poll
        {"status": {"id": "COMPLETED"}, "operation": {"location": "s3://checkpoints/savepoints/sp-999"}},  # 2nd poll
    ]

    with patch.object(mock_flink_controller, "_rest_request", side_effect=responses):
        res = mock_flink_controller.trigger_savepoint("job_abc", cancel=False)
        assert res["status"] == "SUCCESS"
        assert res["savepoint_path"] == "s3://checkpoints/savepoints/sp-999"
        assert res["trigger_id"] == "trig_001"


def test_fastapi_pipeline_flink_and_status_endpoints():
    """Verify GET /pipeline/flink and GET /pipeline/status in FastAPI."""
    fc = FlinkController(flink_url="http://mock-flink:8081")

    with patch.object(fc, "get_active_job_id", return_value="job_test_123"), \
         patch.object(fc, "get_job_status", return_value="RUNNING"), \
         patch.object(fc, "get_checkpoint_metrics", return_value={
             "available": True,
             "counts": {"completed": 15},
             "latest_checkpoint": {"external_path": "s3://checkpoints/test/chk-15"},
         }), \
         patch.object(fc, "get_cluster_overview", return_value={"taskmanagers": 1, "jobs_running": 1}), \
         patch.object(fc, "get_telemetry_summary", return_value={
             "cluster": {"taskmanagers": 1, "jobs_running": 1},
             "active_job": {"job_id": "job_test_123", "status": "RUNNING"},
         }):

        app = create_app(flink_controller=fc)
        client = TestClient(app)

        # 1. Test /pipeline/status includes enriched Flink fields
        res_status = client.get("/pipeline/status")
        assert res_status.status_code == 200
        data_status = res_status.json()
        assert data_status["flink_job_id"] == "job_test_123"
        assert data_status["flink_job_state"] == "RUNNING"
        assert data_status["latest_checkpoint_path"] == "s3://checkpoints/test/chk-15"
        assert data_status["checkpoints_completed"] == 15

        # 2. Test /pipeline/flink
        res_flink = client.get("/pipeline/flink")
        assert res_flink.status_code == 200
        data_flink = res_flink.json()
        assert data_flink["cluster"]["taskmanagers"] == 1
        assert data_flink["active_job"]["job_id"] == "job_test_123"
        assert "retrieved_at" in data_flink
