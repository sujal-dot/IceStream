"""Unit and integration tests for API security and Bearer token authentication."""

import os
import pytest
from fastapi.testclient import TestClient

from backend.app import create_app


@pytest.fixture
def client():
    os.environ["ICESTREAM_API_TOKEN"] = "test_secret_token_12345"
    app = create_app()
    return TestClient(app)


def test_public_health_endpoint_accessible_without_token(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_protected_pause_endpoint_without_token_returns_401(client):
    response = client.post("/pipeline/pause")
    assert response.status_code == 401
    assert "Unauthorized" in response.json()["detail"]


def test_protected_pause_endpoint_with_invalid_token_returns_401(client):
    headers = {"Authorization": "Bearer wrong_token_999"}
    response = client.post("/pipeline/pause", headers=headers)
    assert response.status_code == 401
    assert "Unauthorized" in response.json()["detail"]


def test_protected_pause_endpoint_with_malformed_header_returns_401(client):
    headers = {"Authorization": "Basic dXNlcjpwYXNz"}
    response = client.post("/pipeline/pause", headers=headers)
    assert response.status_code == 401


def test_protected_pause_endpoint_with_valid_token_succeeds(client):
    headers = {"Authorization": "Bearer test_secret_token_12345"}
    response = client.post("/pipeline/pause", json={"reason": "Testing auth"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["state"] == "PAUSED"


def test_protected_resume_endpoint_requires_auth(client):
    response = client.post("/pipeline/resume")
    assert response.status_code == 401

    headers = {"Authorization": "Bearer test_secret_token_12345"}
    response = client.post("/pipeline/resume", json={"reason": "Resume test"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["state"] == "RUNNING"


def test_protected_remediate_endpoint_requires_auth(client):
    response = client.post("/pipeline/remediate")
    assert response.status_code == 401

    headers = {"Authorization": "Bearer test_secret_token_12345"}
    response = client.post("/pipeline/remediate", json={}, headers=headers)
    assert response.status_code != 401
