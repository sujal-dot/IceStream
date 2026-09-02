"""End-to-End Backend Integration Test Suite for Day 23.

Validates full lifecycle from clean RUNNING state -> invalid data injection ->
error rate escalation -> circuit open -> incident creation -> API observability ->
self-healing remediation trigger -> source re-fetch -> reprocessing & validation ->
circuit recovery -> pipeline state RUNNING -> incident RECOVERED.
"""

import os
import sys
import pytest
from fastapi.testclient import TestClient

# Ensure sys.path includes workspace roots
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
QUALITY_ENGINE_DIR = os.path.join(BASE_DIR, "quality-engine")

for d in (BASE_DIR, BACKEND_DIR, QUALITY_ENGINE_DIR):
    if d not in sys.path:
        sys.path.insert(0, d)

from backend.app import (
    create_app,
    set_circuit_breaker,
    set_error_rate_engine,
    set_remediation_controller,
    set_state_manager,
)
from backend.storage.db import StorageBackend, set_db_storage
from circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitState
from hybrid_engine import QualityEngine
from metrics.error_rate import ErrorRateConfig, ErrorRateEngine, HealthStatus, ValidationSummary
from quarantine.writer import QuarantineWriter
from remediation.controller import RemediationController
from remediation.reprocessor import Reprocessor
from remediation.source_adapter import LocalSourceAdapter
from remediation.state_manager import PipelineState, PipelineStateManager
from backend.services.schema_service import set_drift_state


def test_day23_full_backend_integration_lifecycle():
    """Full Day 23 E2E test verifying API observability and self-healing lifecycle."""
    # 1. Setup backend storage and domain engines
    storage = StorageBackend(use_sqlite=True)
    state_mgr = PipelineStateManager(pipeline_id="icestream", storage=storage)
    breaker = CircuitBreaker(config=CircuitBreakerConfig(error_threshold=0.02))
    error_engine = ErrorRateEngine(config=ErrorRateConfig(healthy_max=0.01, warning_max=0.02))
    quality_engine = QualityEngine()
    quarantine_writer = QuarantineWriter(catalog=None)

    # Configure mockable source adapter with invalid and corrected events
    from remediation.source_adapter import make_valid_checkout_event
    corrected_events = [
        make_valid_checkout_event(event_id="evt_e2e_1", amount=50.0)
    ]
    source_adapter = LocalSourceAdapter()
    source_adapter.set_default_recovery_events(corrected_events)
    reprocessor = Reprocessor(quarantine_writer=quarantine_writer, quality_engine=quality_engine)

    controller = RemediationController(
        pipeline_id="icestream",
        state_manager=state_mgr,
        circuit_breaker=breaker,
        source_adapter=source_adapter,
        reprocessor=reprocessor,
        storage=storage,
    )

    set_db_storage(storage)
    set_state_manager(state_mgr)
    set_circuit_breaker(breaker)
    set_error_rate_engine(error_engine)
    set_remediation_controller(controller)
    set_drift_state(None)

    app = create_app(
        engine=error_engine, breaker=breaker, state_manager=state_mgr, controller=controller
    )
    client = TestClient(app)

    # 1. Pipeline starts RUNNING
    status_res1 = client.get("/pipeline/status")
    assert status_res1.status_code == 200
    assert status_res1.json()["state"] == "RUNNING"

    health_res1 = client.get("/health")
    assert health_res1.status_code == 200
    assert health_res1.json()["status"] == "ok"

    from rules.base import EventStatus
    # 2. Inject invalid events exceeding 2% error rate threshold
    for _ in range(100):
        # 95 valid, 5 invalid -> 5% error rate
        error_engine.record_event(ValidationSummary(
            event_id="evt_v", total_rules=1, passed_rules=1, failed_rules=0, critical_failures=0, overall_status=EventStatus.HEALTHY
        ))
    for _ in range(5):
        error_engine.record_event(ValidationSummary(
            event_id="evt_i", total_rules=1, passed_rules=0, failed_rules=1, critical_failures=1, overall_status=EventStatus.FAILED
        ))

    # 3. Quality engine detects failures & circuit opens
    snap = error_engine.get_metrics_snapshot()
    error_rate = snap["windows"]["1m"]["error_rate"]
    assert error_rate > 0.02
    assert snap["windows"]["1m"]["health"] == "CRITICAL"

    breaker.evaluate(error_rate)
    assert breaker.state == CircuitState.OPEN

    inc = controller.get_or_create_incident(
        trigger="ERROR_RATE_CRITICAL",
        error_rate=error_rate,
        failed_event_count=5,
        quarantine_count=5,
    )
    inc_id = inc["incident_id"]

    # Transition pipeline state & link incident
    state_mgr.transition_to(
        to_state=PipelineState.CIRCUIT_OPEN,
        reason="Critical error rate detected",
        incident_id=inc_id,
    )

    # 4. Verify observability APIs report CIRCUIT_OPEN, CRITICAL, and Incident
    status_res2 = client.get("/pipeline/status")
    assert status_res2.json()["state"] == "CIRCUIT_OPEN"
    assert status_res2.json()["incident_id"] == inc_id

    metrics_res = client.get("/metrics")
    assert metrics_res.json()["circuit_breaker"]["state"] == "OPEN"

    incidents_res = client.get("/incidents")
    assert incidents_res.json()["total"] >= 1
    assert incidents_res.json()["items"][0]["incident_id"] == inc_id

    detail_res = client.get(f"/incidents/{inc_id}")
    assert detail_res.status_code == 200
    assert detail_res.json()["incident"]["status"] == "OPEN"

    quality_res = client.get("/quality")
    assert quality_res.json()["overall_status"] == "CRITICAL"

    schema_res = client.get("/schema/drift")
    assert schema_res.status_code == 200

    # 5. Trigger self-healing recovery via API
    source_adapter.set_default_recovery_events(corrected_events)  # Fix source data for re-fetch
    recover_res = client.post("/pipeline/recover", json={"incident_id": inc_id})
    assert recover_res.status_code == 200
    assert recover_res.json()["status"] == "STARTED"

    # 6. Verify pipeline state recovers to RUNNING and incident is RECOVERED
    final_status = client.get("/pipeline/status").json()
    assert final_status["state"] == "RUNNING"
    assert breaker.state == CircuitState.CLOSED

    final_inc = client.get(f"/incidents/{inc_id}").json()
    assert final_inc["incident"]["status"] == "RECOVERED"
    assert final_inc["incident"]["resolved_at"] is not None
