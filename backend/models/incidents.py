"""Incident API response and request models."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class IncidentItem(BaseModel):
    """Single incident summary item."""

    incident_id: str
    pipeline_name: str = "checkout-stream"
    pipeline_id: str = "icestream"
    status: str = "OPEN"
    severity: str = "CRITICAL"
    error_rate: float = 0.0
    threshold: float = 0.02
    failed_records: int = 0
    total_records: int = 0
    failed_event_count: int = 0
    quarantine_count: int = 0
    trigger: str = "CRITICAL_ERROR_RATE"
    trigger_type: str = "CRITICAL_ERROR_RATE"
    circuit_state: str = "OPEN"
    action_taken: Optional[str] = "Downstream pipeline paused."
    message: Optional[str] = None
    slack_sent: bool = False
    slack_sent_at: Optional[str] = None
    slack_error: Optional[str] = None
    detected_at: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None
    resolved_at: Optional[str] = None
    recovery_attempt: int = 0
    last_error: Optional[str] = None


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


class IncidentActionResponse(BaseModel):
    """Response model for incident status change actions (acknowledge/resolve)."""

    incident_id: str
    status: str
    message: str
    updated_at: str
    incident: IncidentItem
