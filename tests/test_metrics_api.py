"""API Test Suite for Day 19 /metrics REST Endpoint using FastAPI TestClient."""

import os
import sys
import pytest
from fastapi.testclient import TestClient

# Ensure backend and quality-engine are on sys.path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
QUALITY_ENGINE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "quality-engine"))
for d in [BACKEND_DIR, QUALITY_ENGINE_DIR]:
    if d not in sys.path:
        sys.path.insert(0, d)

from backend.app import create_app
from metrics.error_rate import ErrorRateEngine, HealthStatus


@pytest.fixture
def test_engine():
    """Fresh ErrorRateEngine fixture."""
    return ErrorRateEngine()


@pytest.fixture
def client(test_engine):
    """FastAPI TestClient with isolated ErrorRateEngine."""
    app = create_app(engine=test_engine)
    return TestClient(app)


def test_metrics_returns_200(client):
    """Verify GET /metrics returns HTTP 200 OK."""
    response = client.get("/metrics")
    assert response.status_code == 200


def test_metrics_returns_json(client):
    """Verify GET /metrics returns application/json content type."""
    response = client.get("/metrics")
    assert response.headers["content-type"].startswith("application/json")
    data = response.json()
    assert isinstance(data, dict)
    assert data["service"] == "icestream-quality-engine"
    assert data["status"] == "ok"


def test_metrics_contains_1m_and_5m_windows(client):
    """Verify GET /metrics payload contains '1m' and '5m' window structures."""
    response = client.get("/metrics")
    data = response.json()
    assert "windows" in data
    assert "1m" in data["windows"]
    assert "5m" in data["windows"]

    for win_key in ["1m", "5m"]:
        win = data["windows"][win_key]
        assert "total_events" in win
        assert "valid_events" in win
        assert "failed_events" in win
        assert "error_rate" in win
        assert "error_rate_percent" in win
        assert "health" in win
        assert "data_available" in win


def test_metrics_zero_traffic(client):
    """Verify GET /metrics before processing events returns zero total_events and data_available=False."""
    response = client.get("/metrics")
    data = response.json()
    m1 = data["windows"]["1m"]
    assert m1["total_events"] == 0
    assert m1["failed_events"] == 0
    assert m1["error_rate"] == 0.0
    assert m1["health"] == "HEALTHY"
    assert m1["data_available"] is False


def test_metrics_healthy(client, test_engine):
    """Feed 1000 events (5 failed) -> GET /metrics returns error_rate=0.005, error_rate_percent=0.5, health=HEALTHY."""
    for _ in range(995):
        test_engine.record_event_outcome(is_valid=True)
    for _ in range(5):
        test_engine.record_event_outcome(is_valid=False)

    response = client.get("/metrics")
    data = response.json()
    m1 = data["windows"]["1m"]

    assert m1["total_events"] == 1000
    assert m1["valid_events"] == 995
    assert m1["failed_events"] == 5
    assert m1["error_rate"] == 0.005
    assert m1["error_rate_percent"] == 0.5
    assert m1["health"] == "HEALTHY"
    assert m1["data_available"] is True


def test_metrics_warning(client, test_engine):
    """Feed 1000 events (10 failed) -> GET /metrics returns error_rate=0.01, error_rate_percent=1.0, health=WARNING."""
    for _ in range(990):
        test_engine.record_event_outcome(is_valid=True)
    for _ in range(10):
        test_engine.record_event_outcome(is_valid=False)

    response = client.get("/metrics")
    data = response.json()
    m1 = data["windows"]["1m"]

    assert m1["total_events"] == 1000
    assert m1["failed_events"] == 10
    assert m1["error_rate"] == 0.01
    assert m1["error_rate_percent"] == 1.0
    assert m1["health"] == "WARNING"


def test_metrics_critical(client, test_engine):
    """Feed 1000 events (21 failed) -> GET /metrics returns error_rate=0.021, error_rate_percent=2.1, health=CRITICAL."""
    for _ in range(979):
        test_engine.record_event_outcome(is_valid=True)
    for _ in range(21):
        test_engine.record_event_outcome(is_valid=False)

    response = client.get("/metrics")
    data = response.json()
    m1 = data["windows"]["1m"]

    assert m1["total_events"] == 1000
    assert m1["failed_events"] == 21
    assert m1["error_rate"] == 0.021
    assert m1["error_rate_percent"] == 2.1
    assert m1["health"] == "CRITICAL"


def test_metrics_does_not_mutate_state(client, test_engine):
    """Verify calling GET /metrics 10 times does not alter total_events, failed_events, or error_rate."""
    for _ in range(95):
        test_engine.record_event_outcome(is_valid=True)
    for _ in range(5):
        test_engine.record_event_outcome(is_valid=False)

    first_resp = client.get("/metrics").json()

    for _ in range(10):
        subsequent_resp = client.get("/metrics").json()
        assert subsequent_resp["windows"]["1m"]["total_events"] == first_resp["windows"]["1m"]["total_events"]
        assert subsequent_resp["windows"]["1m"]["failed_events"] == first_resp["windows"]["1m"]["failed_events"]
        assert subsequent_resp["windows"]["1m"]["error_rate"] == first_resp["windows"]["1m"]["error_rate"]


def test_health_endpoint(client):
    """Verify GET /health returns service status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "icestream-backend"
    assert data["status"] == "ok"
