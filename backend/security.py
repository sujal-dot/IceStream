"""Security, JWT Authentication, and Role-Based Access Control (RBAC) for IceStream API.

Provides:
1. Dual Authentication:
   - Signed JSON Web Tokens (HS256) with role and permission scopes.
   - Preshared API service tokens (ICESTREAM_API_TOKEN) with constant-time comparison.
2. Fine-grained Role-Based Access Control (RBAC) dependencies:
   - Roles: admin, operator, viewer.
   - Scopes: pipeline:control, lakehouse:maintain, metrics:read, etc.
3. 100% backward-compatible token validation.
"""
from dataclasses import dataclass, field
from enum import Enum
import logging
import os
import secrets
import time
from typing import Any, Dict, Iterable, List, Optional, Union

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt

logger = logging.getLogger("icestream.security")

# Security scheme for FastAPI OpenAPI docs
security_scheme = HTTPBearer(auto_error=False)

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "icestream_production_secret_change_in_prod_12345")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ISSUER = "icestream"


class UserRole(str, Enum):
    """Authoritative RBAC roles."""
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


ROLE_PERMISSIONS: Dict[str, List[str]] = {
    UserRole.ADMIN.value: [
        "pipeline:control",
        "lakehouse:maintain",
        "metrics:read",
        "schema:modify",
        "admin:all",
    ],
    UserRole.OPERATOR.value: [
        "pipeline:control",
        "lakehouse:maintain",
        "metrics:read",
    ],
    UserRole.VIEWER.value: [
        "metrics:read",
    ],
}


@dataclass
class AuthenticatedUser:
    """Represents a validated authenticated principal."""
    subject: str
    role: str
    permissions: List[str] = field(default_factory=list)
    auth_method: str = "jwt"  # "jwt" or "api_token"

    def has_role(self, required_roles: Union[str, Iterable[str]]) -> bool:
        """Check if the user possesses any of the required roles (or admin)."""
        if self.role == UserRole.ADMIN.value:
            return True
        if isinstance(required_roles, str):
            required_roles = [required_roles]
        return self.role in required_roles

    def has_permission(self, permission: str) -> bool:
        """Check if user has specific permission or admin wildcard."""
        if self.role == UserRole.ADMIN.value or "admin:all" in self.permissions:
            return True
        return permission in self.permissions


def _get_valid_api_tokens() -> List[str]:
    """Retrieve configured static API tokens from environment or .env."""
    raw_env_tokens = os.getenv("ICESTREAM_API_TOKEN", "")
    if not raw_env_tokens and os.path.exists(".env"):
        try:
            with open(".env", "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("ICESTREAM_API_TOKEN="):
                        raw_env_tokens = line.split("=", 1)[1].strip("\"'")
                        break
        except Exception:
            pass
    return [t.strip() for t in raw_env_tokens.split(",") if t.strip()]


def create_jwt_token(
    subject: str,
    role: str = UserRole.OPERATOR.value,
    permissions: Optional[List[str]] = None,
    expires_in_seconds: int = 3600,
    secret_key: Optional[str] = None,
) -> str:
    """Create a signed JWT access token with role and permission claims.

    Args:
        subject: Principal identifier (e.g. username, service id).
        role: RBAC role (admin, operator, viewer).
        permissions: Optional list of granular permission scopes.
        expires_in_seconds: Token validity duration.
        secret_key: Optional key override (defaults to JWT_SECRET_KEY).

    Returns:
        Encoded JWT token string.
    """
    now = int(time.time())
    assigned_permissions = (
        permissions if permissions is not None else ROLE_PERMISSIONS.get(role, [])
    )
    payload = {
        "sub": subject,
        "role": role,
        "permissions": assigned_permissions,
        "iat": now,
        "exp": now + expires_in_seconds,
        "iss": JWT_ISSUER,
    }
    key = secret_key or JWT_SECRET_KEY
    return jwt.encode(payload, key, algorithm=JWT_ALGORITHM)


def decode_jwt_token(token: str, secret_key: Optional[str] = None) -> Dict[str, Any]:
    """Decode and validate a JWT access token.

    Args:
        token: Raw JWT string.
        secret_key: Optional key override.

    Returns:
        Decoded claims payload dictionary.

    Raises:
        jwt.ExpiredSignatureError: If token expired.
        jwt.InvalidTokenError: If signature or claims are invalid.
    """
    key = secret_key or JWT_SECRET_KEY
    return jwt.decode(
        token,
        key,
        algorithms=[JWT_ALGORITHM],
        issuer=JWT_ISSUER,
        options={"require": ["exp", "sub", "iat"]},
    )


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_scheme),
) -> AuthenticatedUser:
    """Authenticate incoming request using either JWT or API Service Token.

    Dual-mode authentication:
    1. Inspects Bearer token. If valid JWT, returns AuthenticatedUser with claims.
    2. If not a valid JWT, evaluates against preshared ICESTREAM_API_TOKEN with constant-time comparison.
    3. If neither matches, raises HTTP 401 Unauthorized.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Missing Authorization header or Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    provided_token = credentials.credentials.strip()
    if not provided_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Token cannot be empty.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 1. Attempt JWT decoding
    try:
        claims = decode_jwt_token(provided_token)
        subject = claims.get("sub", "unknown")
        role = claims.get("role", UserRole.VIEWER.value)
        permissions = claims.get("permissions", ROLE_PERMISSIONS.get(role, []))
        return AuthenticatedUser(
            subject=subject,
            role=role,
            permissions=permissions,
            auth_method="jwt",
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        # Not a valid JWT; fall back to API token evaluation below
        pass

    # 2. Attempt API Service Token matching (Backward compatibility)
    valid_tokens = _get_valid_api_tokens()
    if not valid_tokens:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server Security Configuration Error: ICESTREAM_API_TOKEN environment variable is not configured.",
        )

    is_valid_api_token = any(
        secrets.compare_digest(provided_token, expected) for expected in valid_tokens
    )
    if is_valid_api_token:
        # Service tokens default to operator role
        return AuthenticatedUser(
            subject="service_token",
            role=UserRole.OPERATOR.value,
            permissions=ROLE_PERMISSIONS[UserRole.OPERATOR.value],
            auth_method="api_token",
        )

    # 3. Authentication Failed
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized: Invalid API token or JWT.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def verify_api_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_scheme),
) -> str:
    """Backward-compatible token verification returning the principal subject string."""
    user = get_current_user(credentials)
    return user.subject


def require_role(allowed_roles: Union[str, Iterable[str]]):
    """FastAPI dependency factory enforcing role-based access control (RBAC).

    Usage:
        @router.post("/pause", dependencies=[Depends(require_role(["admin", "operator"]))])
    """
    if isinstance(allowed_roles, str):
        roles_set = {allowed_roles}
    else:
        roles_set = set(allowed_roles)

    def role_dependency(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        if not user.has_role(roles_set):
            logger.warning(
                f"Forbidden access: User '{user.subject}' with role '{user.role}' "
                f"does not have required role in {roles_set}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Insufficient privileges. Required role in {sorted(list(roles_set))}",
            )
        return user

    return role_dependency


def require_permission(required_permission: str):
    """FastAPI dependency factory enforcing granular permission scope.

    Usage:
        @router.post("/compact", dependencies=[Depends(require_permission("lakehouse:maintain"))])
    """
    def permission_dependency(
        user: AuthenticatedUser = Depends(get_current_user),
    ) -> AuthenticatedUser:
        if not user.has_permission(required_permission):
            logger.warning(
                f"Forbidden access: User '{user.subject}' lacks permission '{required_permission}'"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Insufficient privileges. Required permission: '{required_permission}'",
            )
        return user

    return permission_dependency
