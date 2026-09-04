"""API Contract and Unit Tests for Day 23 FastAPI Observability Backend."""

import os
import sys
import pytest
from fastapi.testclient import TestClient

# Ensure backend and quality-engine are on sys.path
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
from metrics.error_rate import ErrorRateEngine, ValidationSummary
from remediation.controller import RemediationController
from remediation.state_manager import PipelineState, PipelineStateManager
from backend.services.schema_service import set_drift_state


@pytest.fixture
def fresh_app():
    """Fixture providing clean FastAPI app with SQLite in-memory storage backend."""
    storage = StorageBackend(use_sqlite=True)
    state_mgr = PipelineStateManager(pipeline_id="icestream", storage=storage)
    breaker = CircuitBreaker(config=CircuitBreakerConfig(error_threshold=0.02))
    engine = ErrorRateEngine()
    controller = RemediationController(
        pipeline_id="icestream",
        state_manager=state_mgr,
        circuit_breaker=breaker,
        storage=storage,
    )

    set_db_storage(storage)
    set_state_manager(state_mgr)
    set_circuit_breaker(breaker)
    set_error_rate_engine(engine)
    set_remediation_controller(controller)
    set_drift_state(None)

    app = create_app(
        engine=engine, breaker=breaker, state_manager=state_mgr, controller=controller
    )
    client = TestClient(app)
    return client, state_mgr, breaker, engine, controller, storage


def test_health_endpoint(fresh_app):
    client, _, _, _, _, _ = fresh_app
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "icestream-backend"
    assert "timestamp" in data
    assert data["dependencies"]["postgres"] == "ok"


def test_pipeline_status_endpoint(fresh_app):
    client, state_mgr, _, _, _, _ = fresh_app
    resp = client.get("/pipeline/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["pipeline_id"] == "icestream"
    assert data["state"] == "RUNNING"

    # Transition state and verify status API updates
    state_mgr.transition_to(to_state=PipelineState.DEGRADED, reason="Degraded quality")
    resp2 = client.get("/pipeline/status")
    assert resp2.json()["state"] == "DEGRADED"


def test_metrics_endpoint(fresh_app):
    client, _, _, engine, _, _ = fresh_app
    from rules.base import EventStatus
    # Record valid & failed events deterministically
    for _ in range(990):
        engine.record_event(ValidationSummary(
            event_id="evt", total_rules=1, passed_rules=1, failed_rules=0, critical_failures=0, overall_status=EventStatus.HEALTHY
        ))
    for _ in range(10):
        engine.record_event(ValidationSummary(
            event_id="evt", total_rules=1, passed_rules=0, failed_rules=1, critical_failures=1, overall_status=EventStatus.FAILED
        ))

    resp = client.get("/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert "windows" in data
    w1m = data["windows"]["1m"]
    assert w1m["total_events"] == 1000
    assert w1m["valid_events"] == 990
    assert w1m["failed_events"] == 10
    assert w1m["error_rate"] == 0.01
    assert w1m["health"] == "WARNING"


def test_incidents_list_and_detail(fresh_app):
    client, _, _, _, controller, storage = fresh_app
    # Create incident in DB
    inc = controller.get_or_create_incident(
        trigger="ERROR_RATE_CRITICAL", error_rate=0.03, failed_event_count=30, quarantine_count=30
    )
    inc_id = inc["incident_id"]

    # Test GET /incidents
    resp = client.get("/incidents")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    items = data["items"]
    assert any(i["incident_id"] == inc_id for i in items)

    # Test GET /incidents/{id}
    resp_detail = client.get(f"/incidents/{inc_id}")
    assert resp_detail.status_code == 200
    detail = resp_detail.json()
    assert detail["incident"]["incident_id"] == inc_id
    assert detail["incident"]["trigger"] == "ERROR_RATE_CRITICAL"

    # Test GET /incidents/nonexistent -> 404
    resp_404 = client.get("/incidents/inc_nonexistent")
    assert resp_404.status_code == 404


def test_lineage_endpoint(fresh_app):
    client, _, _, _, _, _ = fresh_app
    resp = client.get("/lineage")
    assert resp.status_code == 200
    data = resp.json()
    assert "nodes" in data
    assert "edges" in data
    nodes = {n["id"]: n for n in data["nodes"]}
    assert "kafka" in nodes
    assert "flink" in nodes
    assert "quality-engine" in nodes
    assert "iceberg-bronze" in nodes
    assert "iceberg-silver" in nodes
    assert "analytics" in nodes
    assert "quarantine" in nodes
    assert "dlq" in nodes


def test_quality_endpoint(fresh_app):
    client, _, _, engine, _, _ = fresh_app
    from rules.base import EventStatus
    engine.record_event(ValidationSummary(
        event_id="e1", total_rules=1, passed_rules=1, failed_rules=0, critical_failures=0, overall_status=EventStatus.HEALTHY
    ))
    resp = client.get("/quality")
    assert resp.status_code == 200
    data = resp.json()
    assert data["overall_status"] == "HEALTHY"
    assert data["rules"]["passed"] >= 1


def test_schema_drift_endpoint(fresh_app):
    client, _, _, _, _, _ = fresh_app
    resp = client.get("/schema/drift")
    assert resp.status_code == 200
    data = resp.json()
    assert data["drift_detected"] is False

    # Simulate drift detection
    set_drift_state({
        "drift_detected": True,
        "current_version": "v3",
        "previous_version": "v2",
        "severity": "CRITICAL",
        "changes": [{"field": "amount", "change": "TYPE_CHANGE", "expected": "float", "actual": "string"}],
    })
    resp_drift = client.get("/schema/drift")
    assert resp_drift.status_code == 200
    drift_data = resp_drift.json()
    assert drift_data["drift_detected"] is True
    assert drift_data["severity"] == "CRITICAL"
    assert drift_data["changes"][0]["field"] == "amount"


def test_pipeline_pause_and_resume(fresh_app):
    client, state_mgr, _, _, _, _ = fresh_app
    # Pause pipeline
    resp_pause = client.post("/pipeline/pause")
    assert resp_pause.status_code == 200
    assert resp_pause.json()["state"] == "PAUSED"
    assert client.get("/pipeline/status").json()["state"] == "PAUSED"

    # Pause again (idempotent)
    resp_pause2 = client.post("/pipeline/pause")
    assert resp_pause2.status_code == 200

    # Resume pipeline
    resp_resume = client.post("/pipeline/resume")
    assert resp_resume.status_code == 200
    assert resp_resume.json()["state"] == "RUNNING"
    assert client.get("/pipeline/status").json()["state"] == "RUNNING"


def test_resume_blocked_by_open_circuit(fresh_app):
    client, state_mgr, breaker, _, _, _ = fresh_app
    state_mgr.transition_to(to_state=PipelineState.CIRCUIT_OPEN, reason="High error rate")
    breaker.evaluate(0.05)
    assert breaker.state == CircuitState.OPEN

    resp_resume = client.post("/pipeline/resume")
    assert resp_resume.status_code == 409
    data = resp_resume.json()
    assert "PIPELINE_PROTECTED" in str(data)
    assert client.get("/pipeline/status").json()["state"] == "CIRCUIT_OPEN"


def test_pipeline_recover(fresh_app):
    client, state_mgr, breaker, _, controller, _ = fresh_app
    inc = controller.get_or_create_incident(trigger="ERROR_RATE_CRITICAL", error_rate=0.05)
    state_mgr.transition_to(to_state=PipelineState.CIRCUIT_OPEN, reason="High error rate", incident_id=inc["incident_id"])
    breaker.evaluate(0.05)

    resp_rec = client.post("/pipeline/recover", json={"incident_id": inc["incident_id"]})
    assert resp_rec.status_code == 200
    rec_data = resp_rec.json()
    assert rec_data["incident_id"] == inc["incident_id"]
    assert rec_data["status"] == "STARTED"
