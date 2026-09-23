"""Pydantic Models for Authentication, Token Issuance, and RBAC Claims."""
from typing import List, Optional
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Credentials payload for JWT token generation."""
    username: str = Field(..., example="operator_lead", description="Operator or administrator username")
    password: str = Field(..., example="secure_pipeline_pass", description="Account password")
    role: Optional[str] = Field(default=None, example="operator", description="Optional requested role override")


class TokenExchangeRequest(BaseModel):
    """Payload to exchange a preshared API service token for a scoped JWT."""
    api_token: str = Field(..., description="Preshared ICESTREAM_API_TOKEN string")


class TokenResponse(BaseModel):
    """JWT Bearer token response payload."""
    access_token: str = Field(..., description="Signed JSON Web Token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(default=3600, description="Token validity lifetime in seconds")
    role: str = Field(..., description="Assigned RBAC role")
    permissions: List[str] = Field(default_factory=list, description="Granted permission scopes")


class UserProfileResponse(BaseModel):
    """Profile of the currently authenticated principal."""
    subject: str = Field(..., description="Authenticated user or service identifier")
    role: str = Field(..., description="Active RBAC role")
    permissions: List[str] = Field(default_factory=list, description="List of granted permission scopes")
    auth_method: str = Field(..., description="Authentication method used (jwt or api_token)")
