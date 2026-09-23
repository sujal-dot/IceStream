"""Test Suite for JWT Token Generation, RBAC Role Enforcement, and Dual Authentication.

Validates:
- Cryptographic JWT signing, decoding, and expiration checks.
- RBAC role hierarchy: Admin, Operator, Viewer.
- Endpoint authorization: mutating operations (/pause, /resume, /recover, /compact)
  permitted for Admin & Operator, strictly rejected (403 Forbidden) for Viewer.
- Dual-auth fallback: static ICESTREAM_API_TOKEN seamlessly maps to operator role.
- /auth/token, /auth/exchange, and /auth/me endpoints.
"""

import os
import sys
import time
import pytest
from fastapi.testclient import TestClient

# Ensure backend and quality-engine are on sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for d in (BASE_DIR, os.path.join(BASE_DIR, "backend"), os.path.join(BASE_DIR, "quality-engine")):
    if d not in sys.path:
        sys.path.insert(0, d)

import jwt
from backend.app import create_app
from backend.security import (
    AuthenticatedUser,
    UserRole,
    ROLE_PERMISSIONS,
    create_jwt_token,
    decode_jwt_token,
    get_current_user,
    JWT_SECRET_KEY,
)
from backend.storage.db import StorageBackend, set_db_storage
from circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from metrics.error_rate import ErrorRateEngine
from remediation.controller import RemediationController
from remediation.state_manager import PipelineStateManager


TEST_STATIC_TOKEN = "test_secret_token_12345"


@pytest.fixture
def auth_client():
    """Fixture providing a test client configured with in-memory SQLite and test secret."""
    os.environ["ICESTREAM_API_TOKEN"] = f"{TEST_STATIC_TOKEN},test_secondary_key_67890"
    storage = StorageBackend(use_sqlite=True)
    set_db_storage(storage)

    state_mgr = PipelineStateManager(pipeline_id="icestream", storage=storage)
    breaker = CircuitBreaker(config=CircuitBreakerConfig(error_threshold=0.02))
    engine = ErrorRateEngine()
    controller = RemediationController(
        pipeline_id="icestream",
        state_manager=state_mgr,
        circuit_breaker=breaker,
        storage=storage,
    )

    app = create_app(
        engine=engine,
        breaker=breaker,
        state_manager=state_mgr,
        controller=controller,
    )
    client = TestClient(app)
    client.state_mgr = state_mgr
    client.controller = controller
    client.breaker = breaker
    return client


# ==============================================================================
# 1. Cryptographic JWT Unit Tests
# ==============================================================================

def test_create_and_decode_jwt_token():
    """Verify cryptographic token signing and full claims decoding."""
    token = create_jwt_token(
        subject="ops_engineer",
        role=UserRole.OPERATOR.value,
        expires_in_seconds=600,
    )
    assert isinstance(token, str)
    assert len(token.split(".")) == 3  # Header.Payload.Signature

    claims = decode_jwt_token(token)
    assert claims["sub"] == "ops_engineer"
    assert claims["role"] == UserRole.OPERATOR.value
    assert "pipeline:control" in claims["permissions"]
    assert claims["iss"] == "icestream"
    assert claims["exp"] > claims["iat"]


def test_jwt_expired_token_raises_error():
    """Verify that an expired token immediately raises ExpiredSignatureError."""
    expired_token = create_jwt_token(
        subject="expired_user",
        role=UserRole.VIEWER.value,
        expires_in_seconds=-60,  # 1 minute in the past
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_jwt_token(expired_token)


def test_jwt_invalid_signature_raises_error():
    """Verify that tampering or mismatching secret key raises InvalidTokenError."""
    token = create_jwt_token(
        subject="alice",
        secret_key="secret_key_aaa_very_long_secret_32bytes_min",
    )
    with pytest.raises(jwt.InvalidTokenError):
        decode_jwt_token(token, secret_key="secret_key_bbb_very_long_secret_32bytes_min")


# ==============================================================================
# 2. Authentication API Endpoints (/auth/*)
# ==============================================================================

def test_auth_token_endpoint_returns_valid_jwt(auth_client):
    """POST /auth/token issues a valid signed JWT."""
    response = auth_client.post(
        "/auth/token",
        json={"username": "admin_user", "password": "icestream_secret_password", "role": "admin"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["role"] == "admin"
    assert "lakehouse:maintain" in data["permissions"]

    claims = decode_jwt_token(data["access_token"])
    assert claims["sub"] == "admin_user"
    assert claims["role"] == "admin"


def test_auth_exchange_endpoint_with_valid_api_token(auth_client):
    """POST /auth/exchange exchanges a valid static API token for an operator JWT."""
    response = auth_client.post(
        "/auth/exchange",
        json={"api_token": TEST_STATIC_TOKEN},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["role"] == "operator"

    claims = decode_jwt_token(data["access_token"])
    assert claims["sub"] == "service_token_client"
    assert claims["role"] == "operator"


def test_auth_exchange_endpoint_with_invalid_api_token(auth_client):
    """POST /auth/exchange rejects invalid static tokens with 401."""
    response = auth_client.post(
        "/auth/exchange",
        json={"api_token": "completely_invalid_token_999"},
    )
    assert response.status_code == 401
    assert "Invalid API service token" in response.json()["detail"]


def test_auth_me_endpoint_returns_user_profile(auth_client):
    """GET /auth/me returns current user subject, role, and permissions."""
    token = create_jwt_token(subject="charlie", role=UserRole.OPERATOR.value)
    headers = {"Authorization": f"Bearer {token}"}

    response = auth_client.get("/auth/me", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["subject"] == "charlie"
    assert data["role"] == "operator"
    assert "pipeline:control" in data["permissions"]
    assert data["auth_method"] == "jwt"


# ==============================================================================
# 3. RBAC Enforcement on Mutating & Control Endpoints
# ==============================================================================

def test_rbac_admin_can_execute_mutating_actions(auth_client):
    """Admin role has unrestricted access to pause, resume, and recover."""
    admin_token = create_jwt_token(subject="super_admin", role=UserRole.ADMIN.value)
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Pause
    resp_pause = auth_client.post("/pipeline/pause", json={"reason": "Admin test"}, headers=headers)
    assert resp_pause.status_code == 200
    assert resp_pause.json()["state"] == "PAUSED"

    # Resume
    resp_resume = auth_client.post("/pipeline/resume", json={"reason": "Admin test"}, headers=headers)
    assert resp_resume.status_code == 200
    assert resp_resume.json()["state"] == "RUNNING"

    # Recover (eligible when circuit open or incident exists)
    from remediation.state_manager import PipelineState
    inc = auth_client.controller.get_or_create_incident(trigger="ERROR_RATE_CRITICAL", error_rate=0.05)
    auth_client.state_mgr.transition_to(
        to_state=PipelineState.CIRCUIT_OPEN,
        reason="Recovery test incident",
        incident_id=inc["incident_id"],
    )
    auth_client.breaker.evaluate(0.05)
    resp_rec = auth_client.post("/pipeline/recover", json={"incident_id": inc["incident_id"]}, headers=headers)
    assert resp_rec.status_code == 200
    assert resp_rec.json()["status"] == "STARTED"


def test_rbac_operator_can_execute_mutating_actions(auth_client):
    """Operator role is authorized to pause, resume, and recover."""
    op_token = create_jwt_token(subject="operator_bob", role=UserRole.OPERATOR.value)
    headers = {"Authorization": f"Bearer {op_token}"}

    resp = auth_client.post("/pipeline/pause", json={"reason": "Operator maintenance"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["state"] == "PAUSED"

    resp2 = auth_client.post("/pipeline/resume", headers=headers)
    assert resp2.status_code == 200
    assert resp2.json()["state"] == "RUNNING"


def test_rbac_viewer_blocked_with_403_on_pipeline_control(auth_client):
    """Viewer role is strictly forbidden (HTTP 403) from pause, resume, recover."""
    viewer_token = create_jwt_token(subject="readonly_viewer", role=UserRole.VIEWER.value)
    headers = {"Authorization": f"Bearer {viewer_token}"}

    # Pause attempt
    resp_pause = auth_client.post("/pipeline/pause", headers=headers)
    assert resp_pause.status_code == 403
    assert "Forbidden: Insufficient privileges" in resp_pause.json()["detail"]

    # Resume attempt
    resp_resume = auth_client.post("/pipeline/resume", headers=headers)
    assert resp_resume.status_code == 403
    assert "Forbidden: Insufficient privileges" in resp_resume.json()["detail"]

    # Recover attempt
    resp_rec = auth_client.post("/pipeline/recover", headers=headers)
    assert resp_rec.status_code == 403
    assert "Forbidden: Insufficient privileges" in resp_rec.json()["detail"]


def test_rbac_viewer_can_read_telemetry_and_status(auth_client):
    """Viewer role has full read access to telemetry, pipeline status, and health."""
    viewer_token = create_jwt_token(subject="dashboard_viewer", role=UserRole.VIEWER.value)
    headers = {"Authorization": f"Bearer {viewer_token}"}

    resp_status = auth_client.get("/pipeline/status", headers=headers)
    assert resp_status.status_code == 200
    assert resp_status.json()["pipeline_id"] == "icestream"

    resp_metrics = auth_client.get("/metrics", headers=headers)
    assert resp_metrics.status_code == 200

    resp_health = auth_client.get("/health")
    assert resp_health.status_code == 200


def test_rbac_lakehouse_endpoints_restricted(auth_client):
    """Lakehouse compaction and maintenance endpoints reject viewer with 403."""
    viewer_token = create_jwt_token(subject="viewer_1", role=UserRole.VIEWER.value)
    headers = {"Authorization": f"Bearer {viewer_token}"}

    # Compact
    resp_compact = auth_client.post(
        "/lakehouse/compact",
        json={"table_name": "bronze.checkout_events"},
        headers=headers,
    )
    assert resp_compact.status_code == 403
    assert "Forbidden" in resp_compact.json()["detail"]

    # Maintenance
    resp_maint = auth_client.post(
        "/lakehouse/maintenance",
        json={"table_name": "bronze.checkout_events"},
        headers=headers,
    )
    assert resp_maint.status_code == 403
    assert "Forbidden" in resp_maint.json()["detail"]


# ==============================================================================
# 4. Dual-Auth Backward Compatibility
# ==============================================================================

def test_dual_auth_static_api_token_maps_to_operator(auth_client):
    """Existing services and tests using static ICESTREAM_API_TOKEN continue to work.
    
    Static service tokens default to the operator role, permitting pause/resume.
    """
    headers = {"Authorization": f"Bearer {TEST_STATIC_TOKEN}"}

    # Pause works seamlessly via static token
    resp_pause = auth_client.post(
        "/pipeline/pause",
        json={"reason": "Legacy service token call"},
        headers=headers,
    )
    assert resp_pause.status_code == 200
    assert resp_pause.json()["state"] == "PAUSED"

    # Resume works seamlessly via static token
    resp_resume = auth_client.post(
        "/pipeline/resume",
        headers=headers,
    )
    assert resp_resume.status_code == 200
    assert resp_resume.json()["state"] == "RUNNING"


def test_dual_auth_invalid_credentials_rejected(auth_client):
    """Missing or invalid credentials return HTTP 401."""
    # No auth header
    assert auth_client.post("/pipeline/pause").status_code == 401

    # Empty token
    assert auth_client.post("/pipeline/pause", headers={"Authorization": "Bearer "}).status_code == 401

    # Completely bogus token
    assert auth_client.post("/pipeline/pause", headers={"Authorization": "Bearer bogus_token"}).status_code == 401
