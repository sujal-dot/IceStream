"""Incident API response and request models."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class IncidentItem(BaseModel):
    """Single incident summary item."""

    incident_id: str
    pipeline_id: str = "icestream"
    created_at: str
    trigger: str
    error_rate: float
    circuit_state: str
    failed_event_count: int = 0
    quarantine_count: int = 0
    status: str
    recovery_attempt: int = 0
    last_error: Optional[str] = None
    resolved_at: Optional[str] = None


class IncidentListResponse(BaseModel):
    """Paginated list of incidents response."""

    items: List[IncidentItem]
    total: int


class IncidentDetailResponse(BaseModel):
    """Detailed incident record response."""

    incident: IncidentItem
    circuit_state: str
    remediation_stage: str
    recovery_attempts: int
    attempts_history: List[Dict[str, Any]] = Field(default_factory=list)
    resolved_at: Optional[str] = None
