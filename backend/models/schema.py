"""Schema drift API Pydantic models."""

from typing import Any, List, Optional
from pydantic import BaseModel, Field


class SchemaChangeItem(BaseModel):
    """Single detected schema drift change."""

    field: str
    change: str
    expected: Optional[Any] = None
    actual: Optional[Any] = None


class SchemaDriftResponse(BaseModel):
    """Schema drift detection response model."""

    drift_detected: bool
    current_version: str
    previous_version: str
    severity: str
    changes: List[SchemaChangeItem] = Field(default_factory=list)
    timestamp: str
