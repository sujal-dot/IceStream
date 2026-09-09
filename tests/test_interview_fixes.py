"""Unit and Integration Tests for Interview-Ready Fixes:
1. Flink Credential Handling & Environment Variable Expansion
2. Circuit Breaker <-> Flink REST Controller Integration & Failure Safety
3. Bounded Quarantine Write Batching, Time Flush, Shutdown Flush & Retries
"""
import os
import sys
import time
import pytest
from unittest.mock import MagicMock, patch

from flink.jobs.kafka_to_iceberg import FlinkBronzePipeline
from quarantine.models import QuarantineRecord
from quarantine.writer import QuarantineWriter
from remediation.flink_controller import FlinkController
from remediation.controller import RemediationController
from remediation.state_manager import PipelineStateManager
from circuit_breaker.breaker import CircuitBreaker, CircuitState


# ==============================================================================
# FIX 1 — FLINK CREDENTIALS TESTS
# ==============================================================================

def test_flink_sql_file_has_no_committed_secrets():
    """Verify flink/jobs/kafka_to_iceberg.sql contains no hardcoded passwords or keys."""
    sql_path = os.path.join(os.path.dirname(__file__), "..", "flink", "jobs", "kafka_to_iceberg.sql")
    with open(sql_path, "r", encoding="utf-8") as f:
        sql = f.read()

    assert "change-me-minio-secret" not in sql, "Hardcoded dummy secret found in SQL DDL"
    assert "icestream_minio_secret" not in sql, "Hardcoded production secret found in SQL DDL"
    assert "'s3.secret-access-key'='${MINIO_ROOT_PASSWORD}'" in sql
    assert "'s3.access-key-id'='${MINIO_ROOT_USER}'" in sql


def test_flink_pipeline_py_loads_env_credentials(monkeypatch):
    """Verify FlinkBronzePipeline dynamically loads S3 credentials from environment variables."""
    monkeypatch.setenv("MINIO_ROOT_USER", "custom_minio_user")
    monkeypatch.setenv("MINIO_ROOT_PASSWORD", "custom_minio_secret_999")

    pipeline = FlinkBronzePipeline()
    sql = pipeline.generate_sql_statement()

    assert "'s3.access-key-id'='custom_minio_user'" in sql
    assert "'s3.secret-access-key'='custom_minio_secret_999'" in sql


# ==============================================================================
# FIX 2 — CIRCUIT BREAKER <-> FLINK CONTROLLER INTEGRATION TESTS
# ==============================================================================

def test_flink_controller_discovery_and_idempotency():
    """Test FlinkController active job discovery and idempotent pause/resume operations."""
    mock_active_job = "job_abc123"

    with patch.object(FlinkController, "get_active_job_id", return_value=mock_active_job):
        controller = FlinkController(flink_url="http://localhost:8081")
        # Resume when already running should be a no-op (SKIPPED)
        resume_res = controller.resume_job()
        assert resume_res["status"] == "SKIPPED"
        assert resume_res["job_id"] == mock_active_job

    with patch.object(FlinkController, "get_active_job_id", return_value=None):
        controller = FlinkController(flink_url="http://localhost:8081")
        # Pause when no active job is running should be a no-op (SKIPPED)
        pause_res = controller.pause_job()
        assert pause_res["status"] == "SKIPPED"
        assert pause_res["job_id"] is None


def test_flink_controller_pause_success():
    """Test FlinkController.pause_job REST cancel call."""
    controller = FlinkController(flink_url="http://localhost:8081")
    with patch.object(controller, "get_active_job_id", side_effect=["job_xyz123", None]):
        with patch.object(controller, "get_job_status", return_value="CANCELED"):
            with patch("urllib.request.urlopen") as mock_urlopen:
                mock_resp = MagicMock()
                mock_resp.status = 200
                mock_resp.__enter__.return_value = mock_resp
                mock_urlopen.return_value = mock_resp

                res = controller.pause_job()
                assert res["status"] == "SUCCESS"
                assert res["job_id"] == "job_xyz123"


def test_flink_controller_api_unavailability_handling():
    """Test FlinkController safely returns FAILED status without crashing when Flink API is down."""
    controller = FlinkController(flink_url="http://invalid-host-999:8081")
    with patch.object(controller, "get_active_job_id", return_value="job_err123"):
        with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
            with patch("subprocess.run", side_effect=Exception("Docker failed")):
                res = controller.pause_job()
                assert res["status"] == "FAILED"
                assert "Failed to cancel" in res["error"]


def test_remediation_controller_triggers_flink_pause_and_resume(tmp_path):
    """Test RemediationController invokes FlinkController pause/resume during remediation cycle."""
    mock_flink = MagicMock()
    mock_flink.pause_job.return_value = {"status": "SUCCESS", "job_id": "job_123"}
    mock_flink.resume_job.return_value = {"status": "SUCCESS", "job_id": "job_456"}

    breaker = CircuitBreaker()
    breaker.transition_to(CircuitState.OPEN, reason="test_open")
    state_mgr = PipelineStateManager(pipeline_id="test_flink_ctrl")

    controller = RemediationController(
        pipeline_id="test_flink_ctrl",
        state_manager=state_mgr,
        circuit_breaker=breaker,
        flink_controller=mock_flink,
    )

    inc = controller.get_or_create_incident(trigger="TEST_TRIGGER", error_rate=0.05)
    res = controller.execute_remediation(incident_id=inc["incident_id"])

    assert mock_flink.pause_job.called
    assert mock_flink.resume_job.called
    assert res.success is True


# ==============================================================================
# FIX 3 — QUARANTINE BATCHING TESTS
# ==============================================================================

def test_quarantine_batch_threshold_flush():
    """Test QuarantineWriter buffers records until batch_size (50) is reached."""
    mock_catalog = MagicMock()
    mock_table = MagicMock()
    mock_catalog.load_table.return_value = mock_table

    writer = QuarantineWriter(catalog=mock_catalog, batch_size=50, flush_interval_seconds=60.0)

    # 1. Write 49 records -> should stay in buffer (0 appends)
    for i in range(49):
        rec = QuarantineRecord(
            quarantine_id=f"q_{i}",
            event_id=f"evt_{i}",
            event="{}",
            error_code="TEST_ERR",
            error_message="test",
            failed_rules=["r1"],
            detected_at="2026-09-09T00:00:00Z",
            pipeline_version="0.22.0",
            schema_version="v1.0",
        )
        res = writer.write_record(rec, immediate=False)
        assert res is True

    assert writer.buffer_size == 49
    assert writer.append_count == 0

    # 2. Write 50th record -> should trigger batch flush (1 append)
    rec_50 = QuarantineRecord(
        quarantine_id="q_49",
        event_id="evt_49",
        event="{}",
        error_code="TEST_ERR",
        error_message="test",
        failed_rules=["r1"],
        detected_at="2026-09-09T00:00:00Z",
        pipeline_version="0.22.0",
        schema_version="v1.0",
    )
    writer.write_record(rec_50, immediate=False)

    assert writer.buffer_size == 0
    assert writer.append_count == 1
    assert mock_table.append.called


def test_quarantine_batch_time_flush():
    """Test QuarantineWriter flushes buffered records when flush_interval_seconds expires."""
    mock_catalog = MagicMock()
    mock_table = MagicMock()
    mock_catalog.load_table.return_value = mock_table

    writer = QuarantineWriter(catalog=mock_catalog, batch_size=50, flush_interval_seconds=0.1)

    rec = QuarantineRecord(
        quarantine_id="q_time_1",
        event_id="evt_time_1",
        event="{}",
        error_code="TEST_ERR",
        error_message="test",
        failed_rules=["r1"],
        detected_at="2026-09-09T00:00:00Z",
        pipeline_version="0.22.0",
        schema_version="v1.0",
    )
    writer.write_record(rec, immediate=False)
    assert writer.buffer_size == 1

    time.sleep(0.15)

    rec2 = QuarantineRecord(
        quarantine_id="q_time_2",
        event_id="evt_time_2",
        event="{}",
        error_code="TEST_ERR",
        error_message="test",
        failed_rules=["r1"],
        detected_at="2026-09-09T00:00:00Z",
        pipeline_version="0.22.0",
        schema_version="v1.0",
    )
    writer.write_record(rec2, immediate=False)

    assert writer.buffer_size == 0
    assert writer.append_count >= 1


def test_quarantine_shutdown_flush():
    """Test QuarantineWriter.close() flushes remaining buffered records on shutdown."""
    mock_catalog = MagicMock()
    mock_table = MagicMock()
    mock_catalog.load_table.return_value = mock_table

    writer = QuarantineWriter(catalog=mock_catalog, batch_size=50, flush_interval_seconds=60.0)

    for i in range(10):
        rec = QuarantineRecord(
            quarantine_id=f"q_shut_{i}",
            event_id=f"evt_shut_{i}",
            event="{}",
            error_code="TEST_ERR",
            error_message="test",
            failed_rules=["r1"],
            detected_at="2026-09-09T00:00:00Z",
            pipeline_version="0.22.0",
            schema_version="v1.0",
        )
        writer.write_record(rec, immediate=False)

    assert writer.buffer_size == 10

    written, success = writer.close()
    assert success is True
    assert written == 10
    assert writer.buffer_size == 0


def test_quarantine_write_failure_buffer_preservation():
    """Test records remain preserved in buffer if Iceberg write_batch fails (failure safety)."""
    mock_catalog = MagicMock()
    mock_catalog.load_table.side_effect = Exception("S3 access denied")

    writer = QuarantineWriter(catalog=mock_catalog, batch_size=10, flush_interval_seconds=60.0)

    rec = QuarantineRecord(
        quarantine_id="q_fail_1",
        event_id="evt_fail_1",
        event="{}",
        error_code="TEST_ERR",
        error_message="test",
        failed_rules=["r1"],
        detected_at="2026-09-09T00:00:00Z",
        pipeline_version="0.22.0",
        schema_version="v1.0",
    )
    writer.write_record(rec, immediate=False)

    cnt, success = writer.flush()
    assert success is False
    assert cnt == 0
    assert writer.buffer_size == 1, "Buffered record must NOT be lost on write failure"
