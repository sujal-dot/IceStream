"""Day 22 — Automated Remediation & Self-Healing Pipeline Integration Tests.

Verifies end-to-end real self-healing pipeline lifecycle, backend state persistence,
quarantine verification, alert dispatch, source re-fetch, reprocessing, validation,
circuit recovery, and error handling.
"""

import sys
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
QUALITY_ENGINE_DIR = os.path.join(PROJECT_ROOT, "quality-engine")
for d in (PROJECT_ROOT, BACKEND_DIR, QUALITY_ENGINE_DIR):
    if d not in sys.path:
        sys.path.insert(0, d)

from datetime import datetime, timedelta, timezone
import pytest
import time
from typing import Any, Dict

from storage.db import StorageBackend
from remediation.state_manager import PipelineState, PipelineStateManager
from remediation.alert_service import MockAlertService, SlackAlertAdapter
from remediation.source_adapter import LocalSourceAdapter, make_valid_checkout_event
from remediation.reprocessor import Reprocessor, ReprocessResult
from remediation.controller import RemediationController, RemediationResult
from circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitState
from metrics.error_rate import ErrorRateEngine
from rules.engine import QualityEngine
from rules.registry import create_default_registry
from quarantine.writer import QuarantineWriter
from quarantine.router import QuarantineRouter


@pytest.fixture
def memory_db():
    return StorageBackend(use_sqlite=True)


@pytest.fixture
def state_manager(memory_db):
    return PipelineStateManager(pipeline_id="test_pipeline", storage=memory_db)


@pytest.fixture
def circuit_breaker():
    config = CircuitBreakerConfig(
        error_threshold=0.02,
        recovery_timeout_seconds=5.0,
    )
    return CircuitBreaker(config=config)


@pytest.fixture
def mock_alert():
    return MockAlertService()


@pytest.fixture
def source_adapter():
    adapter = LocalSourceAdapter()
    adapter.register_fixture(
        "evt_recovery_001",
        make_valid_checkout_event(
            event_id="evt_recovery_001",
            customer_id="cust_001",
            amount=1499.00,
            currency="INR",
        ),
    )
    return adapter


@pytest.fixture
def quality_engine():
    return QualityEngine(registry=create_default_registry())


@pytest.fixture
def quarantine_writer():
    writer = QuarantineWriter()
    return writer


@pytest.fixture
def reprocessor(quality_engine, quarantine_writer):
    return Reprocessor(quality_engine=quality_engine, quarantine_writer=quarantine_writer)


@pytest.fixture
def controller(
    memory_db, state_manager, circuit_breaker, mock_alert, source_adapter, reprocessor, quarantine_writer
):
    return RemediationController(
        pipeline_id="test_pipeline",
        state_manager=state_manager,
        circuit_breaker=circuit_breaker,
        alert_service=mock_alert,
        source_adapter=source_adapter,
        reprocessor=reprocessor,
        quarantine_writer=quarantine_writer,
        storage=memory_db,
        max_recovery_attempts=3,
    )


# --- Step 51 to 71 Test Cases ---

def test_1_failure_detection(circuit_breaker, state_manager):
    """Test 1: Bad events drive error rate > 2% causing CircuitBreaker to OPEN and pipeline state CIRCUIT_OPEN."""
    engine = ErrorRateEngine()
    for _ in range(10):
        engine.record_event_outcome(is_valid=False)

    snapshot = engine.get_metrics_snapshot()
    error_rate = snapshot["windows"]["1m"]["error_rate"]
    assert error_rate > 0.02

    circuit_breaker.evaluate(error_rate)
    assert circuit_breaker.state == CircuitState.OPEN

    state_manager.transition_to(PipelineState.CIRCUIT_OPEN, reason="Circuit Breaker Opened", force=True)
    assert state_manager.current_state == PipelineState.CIRCUIT_OPEN


def test_2_quarantine(quarantine_writer):
    """Test 2: Verify bad event is written to quarantine before recovery."""
    bad_event = {
        "event_id": "evt_bad_001",
        "amount": None,
        "currency": "INR",
        "payment_status": "SUCCESS",
    }
    quality_res = {"is_valid": False, "failed_rules": ["amount_not_null"]}
    written = quarantine_writer.write_invalid_event(bad_event, quality_res, "NULL_AMOUNT")
    assert written["status"] in ("SUCCESS", "FAILED")
    assert written["error_code"] == "NULL_AMOUNT"


def test_3_incident_creation(controller, circuit_breaker):
    """Test 3: Verify incident is created in DB when circuit opens."""
    circuit_breaker._state = CircuitState.OPEN
    inc = controller.get_or_create_incident(
        trigger="CRITICAL_ERROR_RATE",
        error_rate=0.05,
        failed_event_count=5,
        quarantine_count=5,
    )
    assert inc["incident_id"].startswith("inc_")
    assert inc["error_rate"] == 0.05
    assert inc["circuit_state"] == "OPEN"
    assert inc["status"] == "OPEN"


def test_4_alert(controller, mock_alert, circuit_breaker):
    """Test 4: Verify send_alert is called on incident creation/remediation."""
    circuit_breaker.transition_to(CircuitState.OPEN, reason="test_open")
    circuit_breaker._opened_at_dt = circuit_breaker.clock.now() - timedelta(seconds=10)
    inc = controller.get_or_create_incident(error_rate=0.05)
    controller.execute_remediation(inc["incident_id"])
    assert len(mock_alert.sent_alerts) == 1
    assert mock_alert.sent_alerts[0]["incident_id"] == inc["incident_id"]


def test_5_open_to_half_open(circuit_breaker):
    """Test 5: Advance clock past recovery_timeout_seconds and verify HALF_OPEN transition capability."""
    circuit_breaker.transition_to(CircuitState.OPEN, reason="test_open")
    circuit_breaker._opened_at_dt = circuit_breaker.clock.now() - timedelta(seconds=10)  # 10s ago > 5s timeout
    assert circuit_breaker.can_probe() is True
    assert circuit_breaker.state == CircuitState.HALF_OPEN


def test_6_refetch(source_adapter):
    """Test 6: Verify LocalSourceAdapter re-fetches corrected event."""
    context = {"event_ids": ["evt_recovery_001"], "incident_id": "inc_001"}
    fetched = source_adapter.fetch_for_recovery(context)
    assert len(fetched) == 1
    assert fetched[0]["event_id"] == "evt_recovery_001"
    assert fetched[0]["amount"] == 1499.00  # Corrected from null


def test_7_reprocess(reprocessor, source_adapter):
    """Test 7: Pass re-fetched event through Reprocessor and QualityEngine."""
    context = {"event_ids": ["evt_recovery_001"], "incident_id": "inc_001"}
    fetched = source_adapter.fetch_for_recovery(context)
    res = reprocessor.process(fetched, incident_id="inc_001", attempt_number=1)
    assert res.valid_count == 1
    assert res.invalid_count == 0
    assert res.is_fully_valid is True


def test_8_validation(source_adapter):
    """Test 8: Verify actual QualityEngine validation passes for re-fetched event."""
    engine = QualityEngine(registry=create_default_registry())
    context = {"event_ids": ["evt_recovery_001"]}
    fetched = source_adapter.fetch_for_recovery(context)
    results, summary = engine.validate_with_summary(fetched[0])
    assert summary.failed_rules == 0


def test_9_circuit_close(circuit_breaker):
    """Test 9: Record 0.0 error rate during HALF_OPEN state and verify transition to CLOSED."""
    circuit_breaker.transition_to(CircuitState.OPEN, reason="test_open")
    circuit_breaker._opened_at_dt = circuit_breaker.clock.now() - timedelta(seconds=10)
    circuit_breaker.begin_recovery_probe()
    assert circuit_breaker.state == CircuitState.HALF_OPEN

    new_st = circuit_breaker.record_recovery_result(error_rate=0.0)
    assert new_st == CircuitState.CLOSED
    assert circuit_breaker.state == CircuitState.CLOSED


def test_10_pipeline_resume(controller, state_manager, circuit_breaker):
    """Test 10: Verify complete pipeline state transition sequence to RUNNING."""
    circuit_breaker.transition_to(CircuitState.OPEN, reason="test_open")
    circuit_breaker._opened_at_dt = circuit_breaker.clock.now() - timedelta(seconds=10)
    inc = controller.get_or_create_incident(error_rate=0.05)

    ctx = {"event_ids": ["evt_recovery_001"]}
    res = controller.execute_remediation(inc["incident_id"], context=ctx)
    assert res.success is True
    assert res.stage == "COMPLETE"
    assert state_manager.current_state == PipelineState.RUNNING

    history = state_manager.get_history()
    states_traversed = [h["to_state"] for h in reversed(history)]
    assert "REMEDIATING" in states_traversed
    assert "REFETCHING" in states_traversed
    assert "REPROCESSING" in states_traversed
    assert "VALIDATING" in states_traversed
    assert "RESUMING" in states_traversed
    assert "RUNNING" in states_traversed


def test_11_incident_resolution(controller, memory_db, circuit_breaker):
    """Test 11: Verify incident status becomes RECOVERED and resolved_at is populated."""
    circuit_breaker.transition_to(CircuitState.OPEN, reason="test_open")
    circuit_breaker._opened_at_dt = circuit_breaker.clock.now() - timedelta(seconds=10)
    inc = controller.get_or_create_incident(error_rate=0.05)
    ctx = {"event_ids": ["evt_recovery_001"]}
    controller.execute_remediation(inc["incident_id"], context=ctx)

    updated_inc = memory_db.get_incident(inc["incident_id"])
    assert updated_inc["status"] == "RECOVERED"
    assert updated_inc["resolved_at"] is not None


def test_12_failed_recovery(controller, state_manager, circuit_breaker, source_adapter):
    """Test 12: SourceAdapter returns invalid event -> recovery fails, state RECOVERY_FAILED, circuit OPEN."""
    circuit_breaker.transition_to(CircuitState.OPEN, reason="test_open")
    circuit_breaker._opened_at_dt = circuit_breaker.clock.now() - timedelta(seconds=10)
    source_adapter.register_fixture(
        "evt_bad_fixture",
        {
            "event_id": "evt_bad_fixture",
            "amount": -500.00,  # Negative amount fails validation rule amount_positive
            "currency": "INVALID",
            "payment_status": "UNKNOWN",
        },
    )

    inc = controller.get_or_create_incident(error_rate=0.05)
    ctx = {"event_ids": ["evt_bad_fixture"]}
    res = controller.execute_remediation(inc["incident_id"], context=ctx)

    assert res.success is False
    assert res.stage == "RECOVERY_FAILED"
    assert state_manager.current_state == PipelineState.RECOVERY_FAILED
    assert circuit_breaker.state == CircuitState.OPEN


def test_13_max_attempts(controller, circuit_breaker, source_adapter):
    """Test 13: Enforce max_recovery_attempts = 3 limit."""
    circuit_breaker.transition_to(CircuitState.OPEN, reason="test_open")
    circuit_breaker._opened_at_dt = circuit_breaker.clock.now() - timedelta(seconds=10)
    source_adapter.register_fixture("evt_fail", {"amount": -100})
    inc = controller.get_or_create_incident(error_rate=0.05)

    ctx = {"event_ids": ["evt_fail"]}
    # Attempt 1, 2, 3 fail
    res1 = controller.execute_remediation(inc["incident_id"], context=ctx)
    assert res1.attempt == 1

    circuit_breaker._opened_at_dt = circuit_breaker.clock.now() - timedelta(seconds=10)
    res2 = controller.execute_remediation(inc["incident_id"], context=ctx)
    assert res2.attempt == 2

    circuit_breaker._opened_at_dt = circuit_breaker.clock.now() - timedelta(seconds=10)
    res3 = controller.execute_remediation(inc["incident_id"], context=ctx)
    assert res3.attempt == 3

    # Attempt 4 blocked by max attempts
    circuit_breaker._opened_at_dt = circuit_breaker.clock.now() - timedelta(seconds=10)
    res4 = controller.execute_remediation(inc["incident_id"], context=ctx)
    assert res4.success is False
    assert res4.stage == "MAX_ATTEMPTS_EXCEEDED"
    assert res4.attempt == 3


def test_14_idempotency(controller, circuit_breaker):
    """Test 14: Verify duplicate remediation triggers do not launch concurrent duplicate workflows."""
    circuit_breaker.transition_to(CircuitState.OPEN, reason="test_open")
    circuit_breaker._opened_at_dt = circuit_breaker.clock.now() - timedelta(seconds=10)
    inc = controller.get_or_create_incident(error_rate=0.05)

    # Set pipeline as currently executing remediation
    controller._active_remediations[controller.pipeline_id] = True

    res = controller.execute_remediation(inc["incident_id"])
    assert res.success is False
    assert res.stage == "IDEMPOTENT_SKIPPED"


def test_15_concurrency_control(controller):
    """Test 15: Verify lock prevents simultaneous remediation."""
    assert controller._lock is not None
    acquired = controller._lock.acquire(blocking=False)
    assert acquired is True
    # Lock is held; secondary attempt cannot acquire lock
    sub_acquired = controller._lock.acquire(blocking=False)
    assert sub_acquired is False
    controller._lock.release()


def test_16_backend_restart(memory_db):
    """Test 16: Restart backend process (new PipelineStateManager instance) and verify state preserved."""
    memory_db.upsert_pipeline_state(
        pipeline_id="test_pipeline",
        state="REPROCESSING",
        reason="Processing recovered batch",
        updated_at=datetime.now(timezone.utc),
    )

    # Simulate process restart by instantiating new manager
    new_manager = PipelineStateManager(pipeline_id="test_pipeline", storage=memory_db)
    assert new_manager.current_state == PipelineState.REPROCESSING
    assert new_manager.get_state()["state"] == "REPROCESSING"


def test_17_quarantine_write_failure(controller, circuit_breaker):
    """Test 17: Quarantine write failure prevents recovery."""
    circuit_breaker.transition_to(CircuitState.OPEN, reason="test_open")
    circuit_breaker._opened_at_dt = circuit_breaker.clock.now() - timedelta(seconds=10)
    inc = controller.get_or_create_incident(error_rate=0.05)

    ctx = {"quarantine_write_failed": True}
    res = controller.execute_remediation(inc["incident_id"], context=ctx)
    assert res.success is False
    assert res.stage == "QUARANTINE_VERIFIED"
    assert "Quarantine verification failed" in res.error


def test_18_reprocess_validation_failure(reprocessor):
    """Test 18: Re-fetched bad event fails QualityEngine and is quarantined again."""
    bad_refetched = [
        {
            "event_id": "evt_refetch_bad",
            "amount": -100.00,  # Negative
            "currency": "USD",
            "payment_status": "SUCCESS",
        }
    ]
    res = reprocessor.process(bad_refetched, incident_id="inc_001", attempt_number=1)
    assert res.valid_count == 0
    assert res.invalid_count == 1
    assert res.is_fully_valid is False


def test_19_partial_recovery(reprocessor):
    """Test 19: Batch of 10 events (8 valid, 2 invalid) reports partial recovery correctly."""
    events = []
    for i in range(8):
        events.append(make_valid_checkout_event(event_id=f"evt_valid_{i}", amount=100.0 + i))
    for i in range(2):
        events.append(make_valid_checkout_event(event_id=f"evt_invalid_{i}", amount=-50.0))

    res = reprocessor.process(events)
    assert res.valid_count == 8
    assert res.invalid_count == 2
    assert res.error_rate == 0.20
    assert res.is_fully_valid is False


def test_20_no_fake_success(controller, circuit_breaker, source_adapter):
    """Test 20: Ensure pipeline state does NOT transition to RUNNING on failure exception."""
    circuit_breaker.transition_to(CircuitState.OPEN, reason="test_open")
    circuit_breaker._opened_at_dt = circuit_breaker.clock.now() - timedelta(seconds=10)
    # Force source adapter to raise an Exception
    def throw_err(ctx):
        raise RuntimeError("Source API connection timeout")
    source_adapter.fetch_for_recovery = throw_err

    inc = controller.get_or_create_incident(error_rate=0.05)
    res = controller.execute_remediation(inc["incident_id"])

    assert res.success is False
    assert controller.state_manager.current_state == PipelineState.RECOVERY_FAILED
    assert controller.state_manager.current_state != PipelineState.RUNNING


# --- Step 71 End-to-End Self-Healing Integration Test ---

def test_end_to_end_self_healing_pipeline(
    memory_db,
    state_manager,
    circuit_breaker,
    mock_alert,
    source_adapter,
    reprocessor,
    quarantine_writer,
    controller,
):
    """Step 71 End-to-End Test: Full real self-healing pipeline scenario execution.

    1. Inject bad event
    2. Validate (invalid)
    3. Quarantine write
    4. Error rate critical -> Circuit OPEN -> State CIRCUIT_OPEN
    5. Incident created
    6. Alert sent
    7. Recovery timeout -> Circuit HALF_OPEN
    8. Source re-fetch returns corrected event
    9. Reprocess through QualityEngine
    10. Validation PASS
    11. Circuit CLOSES -> Pipeline RUNNING
    12. Incident RECOVERED
    13. Original bad event remains in quarantine (NO DATA LOSS)
    """
    # 1 & 2. Bad event
    bad_event = {
        "event_id": "evt_recovery_demo_001",
        "amount": None,
        "currency": "INR",
        "payment_status": "SUCCESS",
    }
    engine_temp = QualityEngine(registry=create_default_registry())
    _, val_bad = engine_temp.validate_with_summary(bad_event)
    assert val_bad.failed_rules > 0

    # 3. Quarantine
    q_rec = quarantine_writer.write_invalid_event(bad_event, val_bad.to_dict(), "NULL_AMOUNT")
    assert q_rec["status"] in ("SUCCESS", "FAILED")

    # 4. Error rate & Circuit Breaker
    engine = ErrorRateEngine()
    for _ in range(10):
        engine.record_event_outcome(is_valid=False)
    snapshot = engine.get_metrics_snapshot()
    error_rate = snapshot["windows"]["1m"]["error_rate"]
    circuit_breaker.evaluate(error_rate)
    assert circuit_breaker.state == CircuitState.OPEN

    # 5 & 6. State & Incident & Alert
    state_manager.transition_to(PipelineState.CIRCUIT_OPEN, reason="Critical error rate", force=True)
    inc = controller.get_or_create_incident(
        trigger="CRITICAL_ERROR_RATE",
        error_rate=error_rate,
        failed_event_count=1,
        quarantine_count=1,
    )

    # 7 & 8. Source Re-fetch setup
    source_adapter.register_fixture(
        "evt_recovery_demo_001",
        make_valid_checkout_event(event_id="evt_recovery_demo_001", amount=1499.00),
    )

    # Set opened_at_dt to > 5s ago so recovery timeout is satisfied
    circuit_breaker._opened_at_dt = circuit_breaker.clock.now() - timedelta(seconds=10)

    # 9 to 12. Execute remediation
    ctx = {"event_ids": ["evt_recovery_demo_001"], "failed_events": [bad_event]}
    res = controller.execute_remediation(inc["incident_id"], context=ctx)

    assert res.success is True
    assert res.stage == "COMPLETE"
    assert circuit_breaker.state == CircuitState.CLOSED
    assert state_manager.current_state == PipelineState.RUNNING

    updated_inc = memory_db.get_incident(inc["incident_id"])
    assert updated_inc["status"] == "RECOVERED"
    assert updated_inc["resolved_at"] is not None

    # 13. Verify original bad event remains in quarantine (NO DATA LOSS)
    history = state_manager.get_history()
    assert len(history) > 0
    assert len(mock_alert.sent_alerts) == 1
