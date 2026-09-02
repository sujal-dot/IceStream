"""Schema service layer interacting with SchemaDriftRule, SchemaComparator, and SchemaRegistry."""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

from backend.models.schema import SchemaChangeItem, SchemaDriftResponse

logger = logging.getLogger("icestream.services.schema")

# Global target schema drift state for runtime inspection
_global_drift_state: Optional[Dict[str, Any]] = None


def get_drift_state() -> Optional[Dict[str, Any]]:
    global _global_drift_state
    return _global_drift_state


def set_drift_state(state: Optional[Dict[str, Any]]) -> None:
    global _global_drift_state
    _global_drift_state = state


class SchemaService:
    """Service retrieving current schema drift information."""

    def __init__(self, registry=None, drift_rule=None):
        self.registry = registry
        self.drift_rule = drift_rule

    def get_schema_drift(self) -> SchemaDriftResponse:
        """Retrieve current schema drift status."""
        state = get_drift_state()
        if state:
            changes_list = []
            for ch in state.get("changes", []):
                changes_list.append(
                    SchemaChangeItem(
                        field=ch.get("field", "unknown"),
                        change=ch.get("change", "TYPE_CHANGE"),
                        expected=ch.get("expected"),
                        actual=ch.get("actual"),
                    )
                )
            return SchemaDriftResponse(
                drift_detected=bool(state.get("drift_detected", True)),
                current_version=str(state.get("current_version", "v3")),
                previous_version=str(state.get("previous_version", "v2")),
                severity=str(state.get("severity", "CRITICAL")),
                changes=changes_list,
                timestamp=str(state.get("timestamp", datetime.now(timezone.utc).isoformat())),
            )

        # Default clean schema state
        now_iso = datetime.now(timezone.utc).isoformat()
        return SchemaDriftResponse(
            drift_detected=False,
            current_version="v1",
            previous_version="v1",
            severity="NONE",
            changes=[],
            timestamp=now_iso,
        )
