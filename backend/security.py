"""Security and Authentication Dependencies for IceStream API.

Provides Bearer token authentication for state-modifying control endpoints
with constant-time token validation and non-leaking error responses.
"""

import os
import secrets
from typing import Optional
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# Security scheme for FastAPI OpenAPI docs
security_scheme = HTTPBearer(auto_error=False)


def verify_api_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_scheme),
) -> str:
    """Verify Bearer token for protected pipeline control endpoints using constant-time comparison."""
    expected_token = os.getenv("ICESTREAM_API_TOKEN")
    if not expected_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server Security Configuration Error: ICESTREAM_API_TOKEN environment variable is not configured.",
        )

    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Missing Authorization header or Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    provided_token = credentials.credentials.strip()
    if not secrets.compare_digest(provided_token, expected_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Invalid API token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return provided_token
