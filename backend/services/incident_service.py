"""Incident service layer managing incident lifecycle, deduplication, and Slack notifications."""

from datetime import datetime, timezone
import logging
import threading
from typing import Any, Dict, Optional
from fastapi import HTTPException, status

from backend.database.repositories.incident_repository import IncidentRepository
from backend.models.incidents import (
    IncidentActionResponse,
    IncidentDetailResponse,
    IncidentItem,
    IncidentListResponse,
)
from backend.services.slack_service import SlackService

logger = logging.getLogger("icestream.services.incident")

# Global thread lock for incident deduplication concurrency safety
_INCIDENT_LOCK = threading.Lock()


class IncidentService:
    """Service orchestrating incident persistence, deduplication, lifecycle, and alerting."""

    def __init__(
        self,
        repository: Optional[IncidentRepository] = None,
        slack_service: Optional[SlackService] = None,
    ):
        self.repository = repository or IncidentRepository()
        self.slack_service = slack_service or SlackService()

    def _raw_to_item(self, raw: Dict[str, Any]) -> IncidentItem:
        """Helper to convert raw DB dict to IncidentItem model."""
        return IncidentItem(
            incident_id=raw["incident_id"],
            pipeline_name=raw.get("pipeline_name") or raw.get("pipeline_id", "checkout-stream"),
            pipeline_id=raw.get("pipeline_id", "icestream"),
            status=raw.get("status", "OPEN"),
            severity=raw.get("severity", "CRITICAL"),
            error_rate=float(raw.get("error_rate", 0.0)),
            threshold=float(raw.get("threshold", 0.02)),
            failed_records=int(raw.get("failed_records") if raw.get("failed_records") is not None else raw.get("failed_event_count", 0)),
            total_records=int(raw.get("total_records", 0)),
            failed_event_count=int(raw.get("failed_event_count") if raw.get("failed_event_count") is not None else raw.get("failed_records", 0)),
            quarantine_count=int(raw.get("quarantine_count", 0)),
            trigger=raw.get("trigger", "CRITICAL_ERROR_RATE"),
            trigger_type=raw.get("trigger_type") or raw.get("trigger", "CRITICAL_ERROR_RATE"),
            circuit_state=raw.get("circuit_state", "OPEN"),
            action_taken=raw.get("action_taken", "Downstream pipeline paused."),
            message=raw.get("message"),
            slack_sent=bool(raw.get("slack_sent")),
            slack_sent_at=str(raw["slack_sent_at"]) if raw.get("slack_sent_at") else None,
            slack_error=raw.get("slack_error"),
            detected_at=str(raw["detected_at"]) if raw.get("detected_at") else str(raw.get("created_at")),
            created_at=str(raw["created_at"]),
            updated_at=str(raw["updated_at"]) if raw.get("updated_at") else str(raw.get("created_at")),
            resolved_at=str(raw["resolved_at"]) if raw.get("resolved_at") else None,
            recovery_attempt=int(raw.get("recovery_attempt", 0)),
            last_error=raw.get("last_error"),
        )

    def get_incidents(
        self,
        status_filter: Optional[str] = None,
        severity_filter: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> IncidentListResponse:
        """Fetch paginated incidents from repository."""
        limit = max(1, min(limit, 100))
        offset = max(0, offset)

        data = self.repository.list_incidents(
            status=status_filter, severity=severity_filter, limit=limit, offset=offset
        )
        items = [self._raw_to_item(raw) for raw in data.get("items", [])]
        return IncidentListResponse(items=items, total=data.get("total", len(items)))

    def get_incident_detail(
        self,
        incident_id: str,
        current_circuit_state: str = "OPEN",
        current_pipeline_state: str = "RUNNING",
    ) -> IncidentDetailResponse:
        """Fetch detailed incident record including remediation attempt history."""
        inc = self.repository.get_incident(incident_id)
        if not inc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Incident '{incident_id}' not found",
            )

        attempts = self.repository.get_remediation_attempts(incident_id)
        item = self._raw_to_item(inc)

        return IncidentDetailResponse(
            incident=item,
            circuit_state=inc.get("circuit_state", current_circuit_state),
            remediation_stage=current_pipeline_state,
            recovery_attempts=len(attempts),
            attempts_history=attempts,
            resolved_at=str(inc["resolved_at"]) if inc.get("resolved_at") else None,
        )

    def create_or_update_incident(
        self,
        pipeline_name: str = "checkout-stream",
        trigger: str = "CRITICAL_ERROR_RATE",
        error_rate: float = 0.0372,
        threshold: float = 0.02,
        failed_records: int = 372,
        total_records: int = 10000,
        quarantine_count: int = 0,
        circuit_state: str = "OPEN",
        action_taken: str = "Downstream pipeline paused.",
        message: Optional[str] = None,
        incident_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new incident or update active incident (thread-safe deduplication)."""
        now = datetime.now(timezone.utc)

        with _INCIDENT_LOCK:
            # 1. Deduplication check: look for active OPEN/ACKNOWLEDGED incident if incident_id not explicit
            if not incident_id:
                active = self.repository.find_active_incident(pipeline_name)
                if active:
                    logger.info(
                        f"[IncidentService] Active incident '{active['incident_id']}' exists for pipeline '{pipeline_name}'. "
                        f"Updating metrics instead of creating duplicate incident."
                    )
                    updates = {
                        "error_rate": error_rate,
                        "failed_records": failed_records,
                        "failed_event_count": failed_records,
                        "total_records": total_records,
                        "quarantine_count": max(int(active.get("quarantine_count", 0)), quarantine_count),
                        "circuit_state": circuit_state,
                        "updated_at": now,
                    }
                    updated_inc = self.repository.update_incident(active["incident_id"], updates)
                    return updated_inc or active

            # 2. No active incident: create new incident
            inc_id = incident_id or self.repository.generate_incident_id()
            severity = "CRITICAL" if error_rate > 0.02 else ("WARNING" if error_rate >= 0.01 else "HEALTHY")

            inc_data = {
                "incident_id": inc_id,
                "pipeline_name": pipeline_name,
                "pipeline_id": "icestream",
                "status": "OPEN",
                "severity": severity,
                "error_rate": error_rate,
                "threshold": threshold,
                "failed_records": failed_records,
                "failed_event_count": failed_records,
                "total_records": total_records,
                "quarantine_count": quarantine_count,
                "trigger_type": trigger,
                "trigger": trigger,
                "circuit_state": circuit_state,
                "action_taken": action_taken,
                "message": message or f"Pipeline error rate {error_rate * 100:.2f}% exceeded threshold {threshold * 100:.0f}%.",
                "slack_sent": False,
                "slack_sent_at": None,
                "slack_error": None,
                "detected_at": now,
                "created_at": now,
                "updated_at": now,
                "recovery_attempt": 0,
                "last_error": None,
                "resolved_at": None,
            }

            # 3. Commit DB record FIRST
            created = self.repository.create_incident(inc_data)
            logger.info(f"[IncidentService] Persisted new incident '{inc_id}' in PostgreSQL with status OPEN.")

        # 4. Dispatch Slack notification AFTER DB transaction commit (Fault Isolated)
        try:
            sent_ok = self.slack_service.send_incident_alert(created)
            if sent_ok:
                slack_updates = {
                    "slack_sent": True,
                    "slack_sent_at": datetime.now(timezone.utc),
                    "slack_error": None,
                }
            else:
                slack_updates = {
                    "slack_sent": False,
                    "slack_error": "Slack notification failed or unconfigured.",
                }
            updated = self.repository.update_incident(inc_id, slack_updates)
            return updated or created
        except Exception as e:
            logger.error(f"[IncidentService] Error dispatching Slack alert for incident '{inc_id}': {e}")
            self.repository.update_incident(inc_id, {"slack_sent": False, "slack_error": str(e)})
            return created

    def acknowledge_incident(self, incident_id: str) -> IncidentActionResponse:
        """Acknowledge an active incident (OPEN -> ACKNOWLEDGED)."""
        inc = self.repository.get_incident(incident_id)
        if not inc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Incident '{incident_id}' not found",
            )

        curr_status = inc.get("status", "OPEN")

        if curr_status == "RESOLVED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot acknowledge resolved incident '{incident_id}'",
            )

        if curr_status == "ACKNOWLEDGED":
            return IncidentActionResponse(
                incident_id=incident_id,
                status="ACKNOWLEDGED",
                message="Incident is already acknowledged.",
                updated_at=str(inc.get("updated_at") or inc.get("created_at")),
                incident=self._raw_to_item(inc),
            )

        now = datetime.now(timezone.utc)
        updates = {"status": "ACKNOWLEDGED", "updated_at": now}
        updated_inc = self.repository.update_incident(incident_id, updates) or inc
        logger.info(f"[IncidentService] Incident '{incident_id}' state updated to ACKNOWLEDGED.")

        return IncidentActionResponse(
            incident_id=incident_id,
            status="ACKNOWLEDGED",
            message="Incident acknowledged successfully.",
            updated_at=now.isoformat(),
            incident=self._raw_to_item(updated_inc),
        )

    def resolve_incident(
        self,
        incident_id: str,
        current_error_rate: Optional[float] = None,
        force: bool = False,
    ) -> IncidentActionResponse:
        """Resolve an active incident (OPEN/ACKNOWLEDGED -> RESOLVED) and send resolution alert."""
        inc = self.repository.get_incident(incident_id)
        if not inc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Incident '{incident_id}' not found",
            )

        curr_status = inc.get("status", "OPEN")
        now = datetime.now(timezone.utc)

        if curr_status == "RESOLVED":
            return IncidentActionResponse(
                incident_id=incident_id,
                status="RESOLVED",
                message="Incident is already resolved.",
                updated_at=str(inc.get("updated_at") or inc.get("created_at")),
                incident=self._raw_to_item(inc),
            )

        # Update metrics & status
        resolved_rate = current_error_rate if current_error_rate is not None else float(inc.get("error_rate", 0.0))
        updates = {
            "status": "RESOLVED",
            "error_rate": resolved_rate,
            "resolved_at": now,
            "updated_at": now,
        }
        updated_inc = self.repository.update_incident(incident_id, updates) or inc
        logger.info(f"[IncidentService] Incident '{incident_id}' resolved in PostgreSQL at {now.isoformat()}.")

        # Send Slack Resolution Alert
        try:
            self.slack_service.send_incident_resolution(updated_inc)
        except Exception as e:
            logger.error(f"[IncidentService] Failed to send Slack resolution alert for '{incident_id}': {e}")

        return IncidentActionResponse(
            incident_id=incident_id,
            status="RESOLVED",
            message="Incident resolved successfully.",
            updated_at=now.isoformat(),
            incident=self._raw_to_item(updated_inc),
        )
