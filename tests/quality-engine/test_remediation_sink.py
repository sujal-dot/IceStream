"""Tests for Lakehouse Sink and Re-Ingestion in Self-Healing Pipeline.

Validates:
1. MockLakehouseSink behavior (recording, error simulation, clearing).
2. IcebergLakehouseSink event normalization (timestamps, decimals, schema field filtering).
3. RemediationController integration (writes healed events, traverses RE_INGESTING state).
4. Failure handling (aborts recovery, marks RECOVERY_FAILED, prevents Flink resume).
5. Concurrency retry handling in IcebergLakehouseSink.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import os
import sys
from unittest.mock import MagicMock, patch
import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
QUALITY_ENGINE_DIR = os.path.join(PROJECT_ROOT, "quality-engine")
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
for p in (PROJECT_ROOT, QUALITY_ENGINE_DIR, BACKEND_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from storage.db import StorageBackend
from circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitState
from rules.engine import QualityEngine
from rules.registry import create_default_registry
from quarantine.writer import QuarantineWriter
from remediation.state_manager import PipelineState, PipelineStateManager
from remediation.alert_service import MockAlertService
from remediation.source_adapter import LocalSourceAdapter, make_valid_checkout_event
from remediation.reprocessor import Reprocessor
from remediation.flink_controller import FlinkController
from remediation.controller import RemediationController
from remediation.lakehouse_sink import (
    IcebergLakehouseSink,
    IngestionResult,
    MockLakehouseSink,
)
from pyiceberg.exceptions import CommitFailedException


@pytest.fixture
def memory_db():
    return StorageBackend(use_sqlite=True)


@pytest.fixture
def state_manager(memory_db):
    return PipelineStateManager(pipeline_id="sink_test_pipeline", storage=memory_db)


@pytest.fixture
def circuit_breaker():
    config = CircuitBreakerConfig(error_threshold=0.02, recovery_timeout_seconds=5.0)
    return CircuitBreaker(config=config)


@pytest.fixture
def source_adapter():
    adapter = LocalSourceAdapter()
    adapter.register_fixture(
        "evt_sink_001",
        make_valid_checkout_event(
            event_id="evt_sink_001",
            customer_id="cust_sink_001",
            amount=299.99,
            currency="USD",
        ),
    )
    return adapter


@pytest.fixture
def mock_sink():
    return MockLakehouseSink()


@pytest.fixture
def mock_flink():
    controller = MagicMock(spec=FlinkController)
    controller.pause_job.return_value = {"status": "SUCCESS", "mode": "savepoint"}
    controller.resume_job.return_value = {"status": "SUCCESS", "job_id": "job_new_123"}
    return controller


@pytest.fixture
def controller(
    memory_db, state_manager, circuit_breaker, source_adapter, mock_sink, mock_flink
):
    quality_eng = QualityEngine(registry=create_default_registry())
    quarantine = QuarantineWriter()
    reprocessor = Reprocessor(quality_engine=quality_eng, quarantine_writer=quarantine)
    return RemediationController(
        pipeline_id="sink_test_pipeline",
        state_manager=state_manager,
        circuit_breaker=circuit_breaker,
        alert_service=MockAlertService(),
        source_adapter=source_adapter,
        reprocessor=reprocessor,
        quarantine_writer=quarantine,
        storage=memory_db,
        flink_controller=mock_flink,
        lakehouse_sink=mock_sink,
        max_recovery_attempts=3,
    )


# --- Unit Tests for Lakehouse Sink ---

def test_mock_sink_basic_operations():
    sink = MockLakehouseSink(table_name="bronze.checkout_events")
    events = [{"event_id": "e1", "amount": 100.0}, {"event_id": "e2", "amount": 200.0}]

    res = sink.write_events(events)
    assert res.success is True
    assert res.records_written == 2
    assert res.event_ids == ["e1", "e2"]
    assert len(sink.written_events) == 2
    assert sink.write_calls == 1

    # Simulate failure
    sink.fail_next_write = True
    fail_res = sink.write_events([{"event_id": "e3"}])
    assert fail_res.success is False
    assert fail_res.records_written == 0
    assert "Simulated" in fail_res.error

    # Verify auto-reset of failure flag
    sink.clear()
    assert len(sink.written_events) == 0
    assert sink.write_calls == 0


def test_iceberg_sink_payload_normalization():
    """Verify IcebergLakehouseSink normalizes timestamps, amounts, and filters internal metadata."""
    sink = IcebergLakehouseSink(table_name="bronze.checkout_events")

    # Mock schema fields matching bronze schema
    field_event_id = MagicMock(name="event_id")
    field_event_id.name = "event_id"
    field_event_id.field_type = "string"

    field_event_time = MagicMock(name="event_time")
    field_event_time.name = "event_time"
    field_event_time.field_type = "timestamptz"

    field_amount = MagicMock(name="amount")
    field_amount.name = "amount"
    field_amount.field_type = "decimal(18, 2)"

    field_ingestion_time = MagicMock(name="ingestion_time")
    field_ingestion_time.name = "ingestion_time"
    field_ingestion_time.field_type = "timestamptz"

    fields = [field_event_id, field_event_time, field_amount, field_ingestion_time]

    raw_events = [
        {
            "event_id": "evt_norm_01",
            "event_time": "2026-09-18T10:00:00Z",
            "amount": 49.99,
            "currency": "USD",
            "_remediation_incident_id": "inc_secret_123",
            "_remediation_attempt": 1,
        },
        {
            "event_id": "evt_norm_02",
            "event_time": datetime(2026, 9, 18, 10, 5, 0, tzinfo=timezone.utc),
            "amount": "120.50",
            # ingestion_time omitted -> should default to now
        },
    ]

    normalized = sink._normalize_events_for_schema(raw_events, fields)

    # 1. Internal metadata is not included in output columns
    assert "_remediation_incident_id" not in normalized
    assert "_remediation_attempt" not in normalized

    # 2. String ISO timestamp converted to datetime
    assert isinstance(normalized["event_time"][0], datetime)
    assert normalized["event_time"][0].tzinfo is not None

    # 3. Numeric amounts converted to Decimal
    assert isinstance(normalized["amount"][0], Decimal)
    assert normalized["amount"][0] == Decimal("49.99")
    assert isinstance(normalized["amount"][1], Decimal)
    assert normalized["amount"][1] == Decimal("120.50")

    # 4. Default ingestion_time populated
    assert isinstance(normalized["ingestion_time"][1], datetime)


def test_iceberg_sink_optimistic_retry_success():
    """Verify IcebergLakehouseSink retries on CommitFailedException and commits successfully."""
    from pyiceberg.schema import Schema
    from pyiceberg.types import NestedField, StringType

    mock_catalog = MagicMock()
    mock_table = MagicMock()
    real_schema = Schema(NestedField(1, "event_id", StringType(), required=False))

    mock_table.schema.return_value = real_schema
    mock_snap = MagicMock()
    mock_snap.snapshot_id = 999888777
    mock_table.current_snapshot.return_value = mock_snap

    # Fail on first append with CommitFailedException, then succeed
    mock_table.append.side_effect = [
        CommitFailedException("Conflict detected on Iceberg commit"),
        None,
    ]

    mock_catalog.load_table.return_value = mock_table

    sink = IcebergLakehouseSink(catalog=mock_catalog, max_retries=3)
    res = sink.write_events([{"event_id": "evt_retry_1"}])

    assert res.success is True
    assert res.records_written == 1
    assert res.snapshot_id == 999888777
    assert mock_table.append.call_count == 2


# --- Integration Tests with RemediationController ---

def test_controller_reingests_valid_events(
    controller, state_manager, circuit_breaker, mock_sink, mock_flink, memory_db
):
    """Verify RemediationController persists healed events and traverses RE_INGESTING state."""
    circuit_breaker.transition_to(CircuitState.OPEN, reason="test_open")
    circuit_breaker._opened_at_dt = circuit_breaker.clock.now() - timedelta(seconds=10)

    inc = controller.get_or_create_incident(error_rate=0.05)
    ctx = {"event_ids": ["evt_sink_001"]}

    res = controller.execute_remediation(inc["incident_id"], context=ctx)

    assert res.success is True
    assert res.stage == "COMPLETE"
    assert res.recovered_events == 1

    # Verify state transitions included RE_INGESTING
    history = state_manager.get_history()
    states_traversed = [h["to_state"] for h in reversed(history)]
    assert "VALIDATING" in states_traversed
    assert "RE_INGESTING" in states_traversed
    assert "RESUMING" in states_traversed
    assert "RUNNING" in states_traversed

    # Verify sink received the event
    assert len(mock_sink.written_events) == 1
    assert mock_sink.written_events[0]["event_id"] == "evt_sink_001"

    # Verify Flink was resumed
    assert mock_flink.resume_job.called

    # Verify storage attempt recorded stage RE_INGESTING
    attempts = memory_db._get_connection().cursor().execute(
        "SELECT stage, status, recovered_event_count FROM remediation_attempts WHERE incident_id = ? AND stage = 'RE_INGESTING'",
        (inc["incident_id"],),
    ).fetchall()
    assert len(attempts) == 1
    assert attempts[0][0] == "RE_INGESTING"
    assert attempts[0][1] == "SUCCESS"
    assert attempts[0][2] == 1


def test_controller_aborts_when_sink_fails(
    controller, state_manager, circuit_breaker, mock_sink, mock_flink, memory_db
):
    """Verify that when the LakehouseSink fails, recovery is ABORTED and Flink is NOT resumed."""
    circuit_breaker.transition_to(CircuitState.OPEN, reason="test_open")
    circuit_breaker._opened_at_dt = circuit_breaker.clock.now() - timedelta(seconds=10)

    inc = controller.get_or_create_incident(error_rate=0.05)
    ctx = {"event_ids": ["evt_sink_001"]}

    # Instruct mock sink to fail
    mock_sink.fail_next_write = True
    mock_sink.failure_error = "MinIO storage volume connection refused"

    res = controller.execute_remediation(inc["incident_id"], context=ctx)

    # 1. Remediation must fail
    assert res.success is False
    assert res.stage == "RE_INGESTING"
    assert "MinIO storage volume connection refused" in res.error

    # 2. Pipeline state must become RECOVERY_FAILED (NOT RUNNING)
    assert state_manager.current_state == PipelineState.RECOVERY_FAILED

    # 3. Flink job must NEVER be resumed
    assert not mock_flink.resume_job.called

    # 4. Incident must remain RECOVERY_FAILED
    updated_inc = memory_db.get_incident(inc["incident_id"])
    assert updated_inc["status"] == "RECOVERY_FAILED"
    assert "Lakehouse re-ingestion failed" in updated_inc["last_error"]

    # 5. Storage attempt audit log reflects the failure
    attempts = memory_db._get_connection().cursor().execute(
        "SELECT stage, status, error FROM remediation_attempts WHERE incident_id = ? AND stage = 'RE_INGESTING'",
        (inc["incident_id"],),
    ).fetchall()
    assert len(attempts) == 1
    assert attempts[0][0] == "RE_INGESTING"
    assert attempts[0][1] == "FAILED"
    assert "MinIO storage volume connection refused" in attempts[0][2]
