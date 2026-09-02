"""Health API response models."""

from typing import Dict, Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """API health status response model."""

    status: str = Field(..., example="ok")
    service: str = Field(default="icestream-backend", example="icestream-backend")
    version: str = Field(default="0.23.0", example="0.23.0")
    timestamp: str = Field(..., example="2026-09-02T10:00:00Z")
    dependencies: Optional[Dict[str, str]] = Field(
        default=None,
        example={"postgres": "ok", "quality_engine": "ok", "iceberg_catalog": "ok"},
    )
