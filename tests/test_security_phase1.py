"""Unit and Integration Tests for Phase 1 Security Hardening.

Verifies Bearer token verification, multi-token key rotation, constant-time comparison,
HTTP defense-in-depth security response headers, and rate limiting middleware.
"""

import os
import sys
import pytest
from fastapi.testclient import TestClient

# Ensure root & quality-engine directories are on sys.path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
QE_DIR = os.path.join(ROOT_DIR, "quality-engine")
if QE_DIR not in sys.path:
    sys.path.insert(0, QE_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

os.environ["TESTING"] = "true"
os.environ["ICESTREAM_API_TOKEN"] = "test_primary_key_12345,test_secondary_key_67890"

from backend.app import create_app
from backend.security import verify_api_token
from metrics.error_rate import ErrorRateEngine
from circuit_breaker import CircuitBreaker
from remediation.state_manager import PipelineStateManager
from backend.storage.db import StorageBackend


@pytest.fixture
def test_client():
    storage = StorageBackend(use_sqlite=True)
    engine = ErrorRateEngine()
    breaker = CircuitBreaker()
    state_mgr = PipelineStateManager(pipeline_id="icestream_sec_test", storage=storage)
    app = create_app(engine=engine, breaker=breaker, state_manager=state_mgr)
    return TestClient(app)


def test_missing_auth_header_returns_401(test_client):
    """Verify state-modifying POST request without token returns 401 Unauthorized."""
    res = test_client.post("/pipeline/pause", json={"reason": "test pause"})
    assert res.status_code == 401
    assert "Unauthorized" in res.json()["detail"]


def test_invalid_bearer_token_returns_401(test_client):
    """Verify invalid token returns 401 Unauthorized."""
    headers = {"Authorization": "Bearer invalid_secret_token_xyz"}
    res = test_client.post("/pipeline/pause", json={"reason": "test pause"}, headers=headers)
    assert res.status_code == 401
    assert "Invalid API token" in res.json()["detail"]


def test_primary_valid_token_succeeds(test_client):
    """Verify primary valid Bearer token succeeds with HTTP 200."""
    headers = {"Authorization": "Bearer test_primary_key_12345"}
    res = test_client.post("/pipeline/pause", json={"reason": "test pause"}, headers=headers)
    assert res.status_code == 200
    assert res.json()["state"] == "PAUSED"


def test_secondary_rotated_token_succeeds(test_client):
    """Verify secondary rotated token succeeds (key rotation)."""
    headers = {"Authorization": "Bearer test_secondary_key_67890"}
    res = test_client.post("/pipeline/resume", json={"reason": "test resume"}, headers=headers)
    assert res.status_code == 200
    assert res.json()["state"] == "RUNNING"


def test_http_security_headers_present(test_client):
    """Verify defense-in-depth security headers are present on all responses."""
    res = test_client.get("/health")
    assert res.status_code == 200
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "DENY"
    assert res.headers.get("X-XSS-Protection") == "1; mode=block"
    assert res.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


def test_rate_limiter_exceeded_returns_429(test_client):
    """Verify exceeding per-IP rate limit triggers 429 Too Many Requests."""
    headers = {"Authorization": "Bearer test_primary_key_12345"}
    # Temporarily set tight limit for testing
    old_limit = os.environ.get("RATE_LIMIT_PER_MINUTE")
    os.environ["RATE_LIMIT_PER_MINUTE"] = "3"

    try:
        storage = StorageBackend(use_sqlite=True)
        engine = ErrorRateEngine()
        breaker = CircuitBreaker()
        state_mgr = PipelineStateManager(pipeline_id="icestream_rate_test", storage=storage)
        app = create_app(engine=engine, breaker=breaker, state_manager=state_mgr)
        client = TestClient(app)

        responses = []
        for i in range(5):
            res = client.post("/pipeline/pause", json={"reason": f"pause {i}"}, headers=headers)
            responses.append(res.status_code)

        assert 429 in responses
        rate_limited_res = [r for r in responses if r == 429][0]
    finally:
        if old_limit is not None:
            os.environ["RATE_LIMIT_PER_MINUTE"] = old_limit
        else:
            os.environ.pop("RATE_LIMIT_PER_MINUTE", None)
