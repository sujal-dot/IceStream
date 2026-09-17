"""
Unit and Integration Tests for Zero-Data-Loss Pipeline Ingestion:
1. Kafka committed group offsets & earliest reset verification in SQL and Python DDL.
2. FlinkController savepoint-aware pause (graceful stop with trigger polling).
3. FlinkController savepoint-aware resume (injecting execution.savepoint.path into SQL).
4. Fallback resilience when savepoint is not available.
"""
import json
import os
import sys
from unittest.mock import MagicMock, patch
import pytest

from flink.jobs.kafka_to_iceberg import FlinkBronzePipeline, KafkaSourceConfig, IcebergSinkConfig
from remediation.flink_controller import FlinkController


def test_kafka_sql_zero_data_loss_properties():
    """Verify flink/jobs/kafka_to_iceberg.sql uses group-offsets and earliest fallback."""
    sql_path = os.path.join(os.path.dirname(__file__), "..", "..", "flink", "jobs", "kafka_to_iceberg.sql")
    with open(sql_path, "r", encoding="utf-8") as f:
        sql = f.read()

    assert "'scan.startup.mode' = 'group-offsets'" in sql, "Must use group-offsets to prevent skipping Kafka records"
    assert "'properties.auto.offset.reset' = 'earliest'" in sql, "Must fallback to earliest on first boot"
    assert "'properties.enable.auto.commit' = 'true'" in sql, "Must enable auto-commit for consumer group tracking"
    assert "state.savepoints.dir" in sql, "Must declare savepoints directory"
    assert "s3://checkpoints/flink-savepoints/" in sql


def test_kafka_python_pipeline_zero_data_loss():
    """Verify FlinkBronzePipeline defaults to group-offsets and supports savepoints."""
    config = KafkaSourceConfig()
    assert config.startup_mode == "group-offsets"
    assert config.auto_offset_reset == "earliest"
    assert config.enable_auto_commit is True

    pipeline = FlinkBronzePipeline()
    sql_default = pipeline.generate_sql_statement()
    assert "'scan.startup.mode' = 'group-offsets'" in sql_default
    assert "'properties.auto.offset.reset' = 'earliest'" in sql_default
    assert "execution.savepoint.path" not in sql_default

    # Test with savepoint path
    sp_path = "s3://checkpoints/flink-savepoints/savepoint-snap-001"
    sql_with_sp = pipeline.generate_sql_statement(savepoint_path=sp_path)
    assert f"SET 'execution.savepoint.path' = '{sp_path}';" in sql_with_sp
    assert "SET 'execution.savepoint.ignore-unclaimed-state' = 'false';" in sql_with_sp


def test_flink_controller_savepoint_stop_and_status():
    """Test FlinkController.pause_job issues stop with savepoint and extracts path."""
    controller = FlinkController(flink_url="http://localhost:8081")

    with patch.object(controller, "get_active_job_id", side_effect=["job_sp_123", None]):
        with patch.object(controller, "get_job_status", return_value="FINISHED"):
            with patch("urllib.request.urlopen") as mock_urlopen:
                # 1. Stop request response
                mock_stop_resp = MagicMock()
                mock_stop_resp.status = 202
                mock_stop_resp.read.return_value = json.dumps({"request-id": "trig_abc"}).encode("utf-8")
                mock_stop_resp.__enter__.return_value = mock_stop_resp

                # 2. Polling response for savepoint trigger
                mock_poll_resp = MagicMock()
                mock_poll_resp.status = 200
                mock_poll_resp.read.return_value = json.dumps({
                    "status": {"id": "COMPLETED"},
                    "operation": {"location": "s3://checkpoints/flink-savepoints/savepoint-job_sp_123-abc"}
                }).encode("utf-8")
                mock_poll_resp.__enter__.return_value = mock_poll_resp

                mock_urlopen.side_effect = [mock_stop_resp, mock_poll_resp]

                res = controller.pause_job()
                assert res["status"] == "SUCCESS"
                assert res["job_id"] == "job_sp_123"
                assert res["savepoint_path"] == "s3://checkpoints/flink-savepoints/savepoint-job_sp_123-abc"
                assert controller._last_savepoint_path == "s3://checkpoints/flink-savepoints/savepoint-job_sp_123-abc"


def test_flink_controller_resume_injects_savepoint():
    """Test FlinkController.resume_job injects savepoint path into sql-client stdin."""
    controller = FlinkController(flink_url="http://localhost:8081")
    controller._last_savepoint_path = "s3://checkpoints/flink-savepoints/savepoint-test-restore"

    captured_sql = []

    def mock_popen(cmd, stdin=None, stdout=None, stderr=None, text=True):
        mock_proc = MagicMock()
        def mock_communicate(input=None, timeout=None):
            captured_sql.append(input)
            return ("", "")
        mock_proc.communicate = mock_communicate
        return mock_proc

    with patch.object(controller, "get_active_job_id", side_effect=[None, "job_new_restored_999"]):
        with patch("subprocess.Popen", side_effect=mock_popen):
            res = controller.resume_job()
            assert res["status"] == "SUCCESS"
            assert res["job_id"] == "job_new_restored_999"
            assert res.get("resumed_from_savepoint") == "s3://checkpoints/flink-savepoints/savepoint-test-restore"
            assert len(captured_sql) == 1
            assert "SET 'execution.savepoint.path' = 's3://checkpoints/flink-savepoints/savepoint-test-restore';" in captured_sql[0]
            # Verify internal savepoint pointer is cleared after consumption
            assert controller._last_savepoint_path is None


def test_flink_controller_pause_fallback_to_cancel_when_savepoint_fails():
    """Test FlinkController falls back to REST cancel when savepoint call raises error."""
    controller = FlinkController(flink_url="http://localhost:8081")

    with patch.object(controller, "get_active_job_id", side_effect=["job_fallback_1", None]):
        with patch.object(controller, "get_job_status", return_value="CANCELED"):
            with patch("urllib.request.urlopen") as mock_urlopen:
                # 1. Stop call fails (e.g. 500 error or unsupported)
                mock_cancel_resp = MagicMock()
                mock_cancel_resp.status = 200
                mock_cancel_resp.__enter__.return_value = mock_cancel_resp

                # First call (stop) raises, second call (cancel) succeeds
                mock_urlopen.side_effect = [Exception("Savepoint storage unavailable"), mock_cancel_resp]

                res = controller.pause_job()
                assert res["status"] == "SUCCESS"
                assert res["job_id"] == "job_fallback_1"
                assert res["savepoint_path"] is None
