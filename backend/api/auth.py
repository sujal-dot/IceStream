"""FastAPI Router for JWT Authentication, Token Issuance, and RBAC Identity."""
import logging
import os
import secrets
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status

from backend.models.auth import (
    LoginRequest,
    TokenExchangeRequest,
    TokenResponse,
    UserProfileResponse,
)
from backend.security import (
    ROLE_PERMISSIONS,
    AuthenticatedUser,
    UserRole,
    _get_valid_api_tokens,
    create_jwt_token,
    get_current_user,
)

logger = logging.getLogger("icestream.api.auth")

router = APIRouter(prefix="/auth", tags=["Authentication"])

AUTH_DEFAULT_USER = os.getenv("AUTH_DEFAULT_USER", "admin")
AUTH_DEFAULT_PASSWORD = os.getenv("AUTH_DEFAULT_PASSWORD", "icestream_secret_password")


@router.post("/token", response_model=TokenResponse)
def login_for_access_token(req: LoginRequest) -> TokenResponse:
    """Authenticate with username and password to receive a signed JWT access token.

    Default production roles:
    - Username 'admin': role 'admin' (full administrative access)
    - Username 'operator': role 'operator' (pipeline control & lakehouse maintenance)
    - Other users: role 'viewer' (read-only telemetry access)
    """
    configured_password = os.getenv("AUTH_PASSWORD", AUTH_DEFAULT_PASSWORD)
    is_valid_pass = secrets.compare_digest(req.password, configured_password)

    if not is_valid_pass:
        logger.warning(f"Failed login attempt for username '{req.username}'")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Determine role
    if req.role and req.role in [r.value for r in UserRole]:
        assigned_role = req.role
    elif req.username.lower() in ("admin", "root"):
        assigned_role = UserRole.ADMIN.value
    elif "operator" in req.username.lower():
        assigned_role = UserRole.OPERATOR.value
    else:
        assigned_role = UserRole.VIEWER.value

    permissions = ROLE_PERMISSIONS.get(assigned_role, [])
    token_lifetime = 3600  # 1 hour
    access_token = create_jwt_token(
        subject=req.username,
        role=assigned_role,
        permissions=permissions,
        expires_in_seconds=token_lifetime,
    )

    logger.info(f"Generated JWT token for user '{req.username}' with role '{assigned_role}'")
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=token_lifetime,
        role=assigned_role,
        permissions=permissions,
    )


@router.post("/exchange", response_model=TokenResponse)
def exchange_api_token(req: TokenExchangeRequest) -> TokenResponse:
    """Exchange an existing preshared API service token for a signed JWT token."""
    valid_tokens = _get_valid_api_tokens()
    if not valid_tokens:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server Security Configuration Error: ICESTREAM_API_TOKEN is not configured.",
        )

    is_valid = any(secrets.compare_digest(req.api_token.strip(), expected) for expected in valid_tokens)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API service token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    role = UserRole.OPERATOR.value
    permissions = ROLE_PERMISSIONS[role]
    token_lifetime = 7200  # 2 hours for service accounts
    access_token = create_jwt_token(
        subject="service_token_client",
        role=role,
        permissions=permissions,
        expires_in_seconds=token_lifetime,
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=token_lifetime,
        role=role,
        permissions=permissions,
    )


@router.get("/me", response_model=UserProfileResponse)
def get_user_profile(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> UserProfileResponse:
    """Retrieve identity, role, and permission scopes of currently authenticated user."""
    return UserProfileResponse(
        subject=current_user.subject,
        role=current_user.role,
        permissions=current_user.permissions,
        auth_method=current_user.auth_method,
    )
