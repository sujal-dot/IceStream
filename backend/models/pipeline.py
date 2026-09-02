"""Pipeline status and control Pydantic models."""

from typing import Optional
from pydantic import BaseModel, Field


class PipelineStatusResponse(BaseModel):
    """Authoritative backend pipeline status model."""

    pipeline_id: str = "icestream"
    state: str
    previous_state: Optional[str] = None
    reason: Optional[str] = None
    incident_id: Optional[str] = None
    recovery_attempt: int = 0
    stage: Optional[str] = None
    last_error: Optional[str] = None
    updated_at: Optional[str] = None


class PipelineControlRequest(BaseModel):
    """Optional payload for pause/resume control requests."""

    reason: Optional[str] = Field(default=None, example="Scheduled maintenance")


class PipelineControlResponse(BaseModel):
    """Response model for pause/resume state control operations."""

    pipeline_id: str = "icestream"
    state: str
    previous_state: Optional[str] = None
    message: str
    updated_at: str


class RecoverRequest(BaseModel):
    """Payload for pipeline recovery request."""

    incident_id: Optional[str] = Field(default=None, example="inc_123")
    context: Optional[dict] = Field(default=None)


class RecoveryResponse(BaseModel):
    """Response model for POST /pipeline/recover."""

    incident_id: str
    status: str
    pipeline_state: str
    recovery_attempt: int = 0
    message: Optional[str] = None
