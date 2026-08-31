"""
IceStream Quarantine Models
Defines typed models for quarantine records and routing outcomes.
"""
from dataclasses import dataclass, field as dc_field
import json
from typing import Any, Dict, List, Optional
import pyarrow as pa


@dataclass
class QuarantineRecord:
    """Authoritative data model for an invalid event isolated in quarantine."""

    quarantine_id: str
    event_id: Optional[str]
    event: str  # Preserved original event payload (JSON string)
    error_code: str
    error_message: str
    failed_rules: List[str]
    detected_at: str
    pipeline_version: str
    schema_version: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert record to standard Python dictionary."""
        return {
            "quarantine_id": self.quarantine_id,
            "event_id": self.event_id,
            "event": self.event,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "failed_rules": list(self.failed_rules),
            "detected_at": self.detected_at,
            "pipeline_version": self.pipeline_version,
            "schema_version": self.schema_version,
        }

    def get_parsed_event(self) -> Dict[str, Any]:
        """Parse preserved event JSON payload into a dictionary."""
        try:
            return json.loads(self.event)
        except Exception:
            return {"raw_event": self.event}

    def to_arrow_record(self) -> Dict[str, List[Any]]:
        """Format record as columnar dict ready for PyArrow Table creation."""
        return {
            "quarantine_id": [self.quarantine_id],
            "event_id": [self.event_id],
            "event": [self.event],
            "error_code": [self.error_code],
            "error_message": [self.error_message],
            "failed_rules": [self.failed_rules],
            "detected_at": [self.detected_at],
            "pipeline_version": [self.pipeline_version],
            "schema_version": [self.schema_version],
        }


@dataclass
class QuarantineRouteResult:
    """Encapsulates the status and result of a quarantine routing operation."""

    quarantine_record: Optional[QuarantineRecord]
    success: bool
    error: Optional[str] = None
    skipped_reason: Optional[str] = None
