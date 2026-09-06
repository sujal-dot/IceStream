"""Pytest configuration and environment fixtures for IceStream tests.

Ensures safe, explicit test environment variables are loaded prior to test executions.
"""

import os
import pytest

# Inject clean test environment variables before tests execute
os.environ.setdefault("POSTGRES_USER", "test_icestream_user")
os.environ.setdefault("POSTGRES_PASSWORD", "test_icestream_password")
os.environ.setdefault("POSTGRES_HOST", "127.0.0.1")
os.environ.setdefault("POSTGRES_PORT", "5433")
os.environ.setdefault("POSTGRES_DB", "icestream_db")

os.environ.setdefault("MINIO_ROOT_USER", "icestream_minio")
os.environ.setdefault("MINIO_ROOT_PASSWORD", "icestream_minio_secret")
os.environ.setdefault("MINIO_ACCESS_KEY", "icestream_minio")
os.environ.setdefault("MINIO_SECRET_KEY", "icestream_minio_secret")
os.environ.setdefault("MINIO_ENDPOINT", "http://localhost:9000")

os.environ.setdefault("ICESTREAM_API_TOKEN", "test_api_token_secret_12345")


@pytest.fixture(autouse=True)
def setup_test_env():
    """Ensure test environment variables remain set during test execution."""
    os.environ["POSTGRES_USER"] = os.environ.get("POSTGRES_USER", "test_icestream_user")
    os.environ["POSTGRES_PASSWORD"] = os.environ.get("POSTGRES_PASSWORD", "test_icestream_password")
    os.environ["POSTGRES_HOST"] = os.environ.get("POSTGRES_HOST", "127.0.0.1")
    os.environ["POSTGRES_PORT"] = os.environ.get("POSTGRES_PORT", "5433")
    os.environ["POSTGRES_DB"] = os.environ.get("POSTGRES_DB", "icestream_db")

    os.environ["MINIO_ROOT_USER"] = os.environ.get("MINIO_ROOT_USER", "icestream_minio")
    os.environ["MINIO_ROOT_PASSWORD"] = os.environ.get("MINIO_ROOT_PASSWORD", "icestream_minio_secret")
    os.environ["ICESTREAM_API_TOKEN"] = os.environ.get("ICESTREAM_API_TOKEN", "test_api_token_secret_12345")
