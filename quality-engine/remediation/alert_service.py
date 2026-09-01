"""Alerting Service & Adapters for Self-Healing Remediation Pipeline.

Provides abstract AlertService interface, real Slack webhooks adapter, and MockAlertService for unit testing.
"""

from abc import ABC, abstractmethod
import json
import logging
import os
from typing import Any, Dict, List, Optional
import urllib.request
import urllib.error

logger = logging.getLogger("icestream.remediation.alert_service")


class AlertService(ABC):
    """Abstract interface for sending incident alerts."""

    @abstractmethod
    def send_alert(self, incident: Dict[str, Any]) -> bool:
        """Send incident alert payload to external destination.
        
        Returns True if sent successfully, False otherwise.
        """
        pass


class SlackAlertAdapter(AlertService):
    """Real Slack webhook notification adapter."""

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or os.getenv("SLACK_WEBHOOK_URL")

    def format_slack_message(self, incident: Dict[str, Any]) -> Dict[str, Any]:
        """Construct structured Slack card layout."""
        incident_id = incident.get("incident_id", "unknown")
        pipeline_id = incident.get("pipeline_id", "icestream")
        error_rate = incident.get("error_rate", 0.0)
        circuit_state = incident.get("circuit_state", "OPEN")
        failed_count = incident.get("failed_event_count", 0)
        quarantine_count = incident.get("quarantine_count", 0)
        status = incident.get("status", "OPEN")

        text_content = (
            f"*IceStream Pipeline Incident*\n"
            f"*Pipeline:* {pipeline_id}\n"
            f"*Incident:* `{incident_id}`\n"
            f"*Error rate:* {error_rate * 100:.2f}%\n"
            f"*Circuit:* {circuit_state}\n"
            f"*Failed events:* {failed_count}\n"
            f"*Quarantined:* {quarantine_count}\n"
            f"*Recovery:* {status}"
        )

        return {"text": text_content}

    def send_alert(self, incident: Dict[str, Any]) -> bool:
        if not self.webhook_url or "YOUR/WEBHOOK/URL" in self.webhook_url:
            logger.info(
                f"[SlackAlertAdapter] Slack webhook URL not configured/placeholder. Logging alert internally: "
                f"Incident '{incident.get('incident_id')}'"
            )
            return True

        payload = self.format_slack_message(incident)
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status in (200, 204):
                    logger.info(f"[SlackAlertAdapter] Slack alert sent successfully for incident {incident.get('incident_id')}")
                    return True
                else:
                    logger.warning(f"[SlackAlertAdapter] Unexpected response status: {resp.status}")
                    return False
        except Exception as e:
            logger.error(f"[SlackAlertAdapter] Failed to send Slack alert: {e}")
            return False


class MockAlertService(AlertService):
    """Test double for verifying alert invocation in unit/integration tests."""

    def __init__(self):
        self.sent_alerts: List[Dict[str, Any]] = []

    def send_alert(self, incident: Dict[str, Any]) -> bool:
        self.sent_alerts.append(incident.copy())
        logger.info(f"[MockAlertService] Recorded alert for incident '{incident.get('incident_id')}'")
        return True

    def clear(self):
        self.sent_alerts.clear()
