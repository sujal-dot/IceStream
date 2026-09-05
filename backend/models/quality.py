"""Data quality API Pydantic models."""

from typing import Dict, Optional
from pydantic import BaseModel, Field


class QualityRulesSummary(BaseModel):
    """Passed and failed quality rules counter."""

    passed: int = 0
    failed: int = 0


class QualitySeveritySummary(BaseModel):
    """Breakdown of quality issues by severity."""

    critical: int = 0
    high: int = 0
    warning: int = 0


class QualityResponse(BaseModel):
    """Data quality observability status response model."""

    overall_status: str = Field(..., example="HEALTHY")
    windows: Dict[str, dict] = Field(default_factory=dict)
    rules: QualityRulesSummary
    severity: QualitySeveritySummary
    total_events: int = 0
    valid_events: int = 0
    failed_events: int = 0
    current_error_rate: float = 0.0
    top_failures: Optional[Dict[str, int]] = Field(default_factory=dict)
