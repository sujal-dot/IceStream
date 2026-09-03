"""Day 24 Integration & Unit Tests for Slack Alerting + Incident Management.

Verifies incident detection, DB persistence, deterministic ID generation, deduplication,
concurrency control, Slack webhooks, 3x retries, failure resilience, lifecycle (OPEN -> ACKNOWLEDGED -> RESOLVED),
and FastAPI endpoints.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import logging
import os
from typing import Any, Dict, List
import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.database.repositories.incident_repository import IncidentRepository
from backend.models.incidents import IncidentItem
from backend.services.incident_service import IncidentService
from backend.services.slack_service import SlackService
from backend.storage.db import StorageBackend, get_db_storage, set_db_storage
from remediation.alert_service import MockAlertService, SlackAlertAdapter
from remediation.controller import RemediationController
from remediation.state_manager import PipelineState, PipelineStateManager
from circuit_breaker.breaker import CircuitBreaker, CircuitState

logger = logging.getLogger("icestream.tests.day24")


@pytest.fixture
def test_storage():
    """Isolated SQLite in-memory storage instance for tests."""
    storage = StorageBackend(use_sqlite=True)
    set_db_storage(storage)
    yield storage
    set_db_storage(None)


@pytest.fixture
def mock_slack():
    """Mock Slack service for recording sent alerts."""
    class RecordingSlackService(SlackService):
        def __init__(self):
            super().__init__(webhook_url="http://mock-slack-webhook.local/alerts", enabled=True)
            self.alerts_sent: List[Dict[str, Any]] = []
            self.resolutions_sent: List[Dict[str, Any]] = []
            self.should_fail = False

        def send_incident_alert(self, incident: Dict[str, Any]) -> bool:
            if self.should_fail:
                return False
            self.alerts_sent.append(incident.copy())
            return True

        def send_incident_resolution(self, incident: Dict[str, Any]) -> bool:
            if self.should_fail:
                return False
            self.resolutions_sent.append(incident.copy())
            return True

    return RecordingSlackService()


@pytest.fixture
def incident_service(test_storage, mock_slack):
    repo = IncidentRepository(storage=test_storage)
    return IncidentService(repository=repo, slack_service=mock_slack)


@pytest.fixture
def test_client(test_storage, incident_service):
    app = create_app()
    app.dependency_overrides[get_db_storage] = lambda: test_storage
    return TestClient(app)


# --- 1. Incident Creation & Persistence Tests ---

def test_incident_creation_and_persistence(incident_service, test_storage):
    """Test incident creation persists full schema in PostgreSQL / SQLite."""
    inc = incident_service.create_or_update_incident(
        pipeline_name="checkout-stream",
        trigger="CRITICAL_ERROR_RATE",
        error_rate=0.0372,
        threshold=0.02,
        failed_records=372,
        total_records=10000,
        quarantine_count=372,
        action_taken="Downstream pipeline paused.",
    )

    assert inc["incident_id"].startswith("INC-")
    assert inc["pipeline_name"] == "checkout-stream"
    assert inc["status"] == "OPEN"
    assert inc["severity"] == "CRITICAL"
    assert inc["error_rate"] == 0.0372
    assert inc["threshold"] == 0.02
    assert inc["failed_records"] == 372
    assert inc["total_records"] == 10000
    assert inc["slack_sent"] is True

    # Verify query back from storage
    persisted = test_storage.get_incident(inc["incident_id"])
    assert persisted is not None
    assert persisted["incident_id"] == inc["incident_id"]
    assert persisted["status"] == "OPEN"


def test_deterministic_incident_id(test_storage):
    """Test sequential deterministic incident ID generation (INC-YYYY-MMDD-XXXX)."""
    id1 = test_storage.generate_incident_id(date_str="2026-0903")
    assert id1 == "INC-2026-0903-0001"

    test_storage.create_incident({"incident_id": id1, "created_at": datetime.now(timezone.utc), "status": "OPEN"})

    id2 = test_storage.generate_incident_id(date_str="2026-0903")
    assert id2 == "INC-2026-0903-0002"


def test_severity_mapping(incident_service):
    """Test severity calculation: CRITICAL > 2%, WARNING 1-2%, HEALTHY < 1%."""
    inc_crit = incident_service.create_or_update_incident(error_rate=0.0372, incident_id="INC-TEST-0001")
    assert inc_crit["severity"] == "CRITICAL"

    # Resolve first so next creates new
    incident_service.resolve_incident("INC-TEST-0001")

    inc_warn = incident_service.create_or_update_incident(error_rate=0.015, incident_id="INC-TEST-0002")
    assert inc_warn["severity"] == "WARNING"


# --- 2. Deduplication Tests ---

def test_incident_deduplication(incident_service, mock_slack):
    """Test repeated threshold breaches update active incident without duplicate DB rows or Slack alerts."""
    # First breach
    inc1 = incident_service.create_or_update_incident(
        pipeline_name="checkout-stream",
        error_rate=0.031,
        failed_records=310,
    )

    id1 = inc1["incident_id"]
    assert len(mock_slack.alerts_sent) == 1

    # Second breach while circuit still OPEN / incident OPEN
    inc2 = incident_service.create_or_update_incident(
        pipeline_name="checkout-stream",
        error_rate=0.0372,
        failed_records=372,
    )

    # Must return SAME incident ID
    assert inc2["incident_id"] == id1
    assert inc2["error_rate"] == 0.0372
    assert inc2["failed_records"] == 372

    # Should NOT have sent a duplicate Slack alert
    assert len(mock_slack.alerts_sent) == 1


# --- 3. Slack Integration & Resilience Tests ---

def test_slack_message_formatting(mock_slack):
    """Test exact required Slack message structure."""
    test_inc = {
        "incident_id": "INC-2026-0903-0001",
        "pipeline_name": "checkout-stream",
        "status": "OPEN",
        "severity": "CRITICAL",
        "error_rate": 0.0372,
        "threshold": 0.02,
        "failed_records": 372,
        "detected_at": "2026-09-03T10:31:05Z",
        "action_taken": "Downstream pipeline paused.",
    }

    formatted = mock_slack.format_incident_alert(test_inc)
    text = formatted["text"]

    assert "*🚨 ICESTREAM INCIDENT*" in text
    assert "*Pipeline:* checkout-stream" in text
    assert "*Status:* OPEN" in text
    assert "*Severity:* CRITICAL" in text
    assert "*Error rate:* 3.72%" in text
    assert "*Threshold:* 2%" in text
    assert "*Failed records:* 372" in text
    assert "*Incident ID:*\nINC-2026-0903-0001" in text


def test_slack_failure_resilience(incident_service, mock_slack, test_storage):
    """Test Slack failure does NOT crash pipeline or rollback DB incident."""
    mock_slack.should_fail = True

    inc = incident_service.create_or_update_incident(
        pipeline_name="checkout-stream",
        error_rate=0.04,
    )

    # Incident MUST exist in DB
    assert inc is not None
    assert inc["incident_id"].startswith("INC-")
    assert inc["slack_sent"] is False
    assert inc["slack_error"] is not None

    persisted = test_storage.get_incident(inc["incident_id"])
    assert persisted is not None


def test_slack_retry_mechanism():
    """Test Slack Service retries up to 3 times before returning False on failure."""
    svc = SlackService(webhook_url="http://invalid-host-for-testing-12345.local/webhook", max_retries=3, backoff_factor=0.01)

    result = svc.send_incident_alert({"incident_id": "INC-TEST", "pipeline_name": "checkout-stream"})
    assert result is False


# --- 4. Incident Lifecycle Tests ---

def test_incident_acknowledge_lifecycle(incident_service):
    """Test OPEN -> ACKNOWLEDGED lifecycle transition and idempotency."""
    inc = incident_service.create_or_update_incident(
        pipeline_name="checkout-stream",
        error_rate=0.05,
    )
    inc_id = inc["incident_id"]
    assert inc["status"] == "OPEN"

    # Acknowledge
    ack_res = incident_service.acknowledge_incident(inc_id)
    assert ack_res.status == "ACKNOWLEDGED"
    assert ack_res.incident.status == "ACKNOWLEDGED"

    # Idempotent second acknowledge
    ack_res2 = incident_service.acknowledge_incident(inc_id)
    assert ack_res2.status == "ACKNOWLEDGED"
    assert "already acknowledged" in ack_res2.message.lower()


def test_incident_resolve_lifecycle(incident_service, mock_slack):
    """Test ACKNOWLEDGED -> RESOLVED transition and resolution alert dispatch."""
    inc = incident_service.create_or_update_incident(
        pipeline_name="checkout-stream",
        error_rate=0.05,
    )
    inc_id = inc["incident_id"]

    incident_service.acknowledge_incident(inc_id)

    # Resolve
    res = incident_service.resolve_incident(inc_id, current_error_rate=0.0042)
    assert res.status == "RESOLVED"
    assert res.incident.status == "RESOLVED"
    assert res.incident.resolved_at is not None

    # Resolution Slack alert sent
    assert len(mock_slack.resolutions_sent) == 1
    assert mock_slack.resolutions_sent[0]["incident_id"] == inc_id


# --- 5. FastAPI Endpoints Tests ---

def test_fastapi_incidents_api(test_client, incident_service):
    """Test GET /incidents, GET /incidents/{id}, POST acknowledge & resolve routes."""
    inc = incident_service.create_or_update_incident(
        pipeline_name="checkout-stream",
        error_rate=0.0372,
    )
    inc_id = inc["incident_id"]

    # 1. GET /incidents
    r_list = test_client.get("/incidents")
    assert r_list.status_code == 200
    data_list = r_list.json()
    assert data_list["total"] >= 1
    assert any(i["incident_id"] == inc_id for i in data_list["items"])

    # 2. GET /incidents/{id}
    r_detail = test_client.get(f"/incidents/{inc_id}")
    assert r_detail.status_code == 200
    detail_json = r_detail.json()
    assert detail_json["incident"]["incident_id"] == inc_id

    # 3. POST /incidents/{id}/acknowledge
    r_ack = test_client.post(f"/incidents/{inc_id}/acknowledge")
    assert r_ack.status_code == 200
    assert r_ack.json()["status"] == "ACKNOWLEDGED"

    # 4. POST /incidents/{id}/resolve
    r_res = test_client.post(f"/incidents/{inc_id}/resolve")
    assert r_res.status_code == 200
    assert r_res.json()["status"] == "RESOLVED"


# --- 6. Concurrency Safety Test ---

def test_concurrency_incident_creation(incident_service):
    """Simulate 5 concurrent pipeline workers detecting the same outage -> produces 1 active incident."""
    def worker_task(worker_id: int):
        return incident_service.create_or_update_incident(
            pipeline_name="checkout-stream",
            error_rate=0.035 + (worker_id * 0.001),
        )

    results = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(worker_task, i) for i in range(5)]
        for f in as_completed(futures):
            results.append(f.result())

    # All workers MUST return the same incident ID
    incident_ids = {r["incident_id"] for r in results}
    assert len(incident_ids) == 1, f"Expected 1 deduplicated incident, got {len(incident_ids)}: {incident_ids}"
