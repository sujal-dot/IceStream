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

    def send_resolution_alert(self, incident: Dict[str, Any]) -> bool:
        """Send resolution alert payload to external destination. Optional override."""
        return True


class SlackAlertAdapter(AlertService):
    """Real Slack webhook notification adapter powered by SlackService."""

    def __init__(self, webhook_url: Optional[str] = None):
        from backend.services.slack_service import SlackService
        self.slack_service = SlackService(webhook_url=webhook_url)

    def format_slack_message(self, incident: Dict[str, Any]) -> Dict[str, Any]:
        """Construct structured Slack card layout (delegates to SlackService)."""
        return self.slack_service.format_incident_alert(incident)

    def send_alert(self, incident: Dict[str, Any]) -> bool:
        if not self.slack_service.webhook_url or "YOUR/WEBHOOK/URL" in self.slack_service.webhook_url:
            logger.info(
                f"[SlackAlertAdapter] Slack webhook URL not configured/placeholder. Logging alert internally: "
                f"Incident '{incident.get('incident_id')}'"
            )
            return True

        return self.slack_service.send_incident_alert(incident)

    def send_resolution_alert(self, incident: Dict[str, Any]) -> bool:
        if not self.slack_service.webhook_url or "YOUR/WEBHOOK/URL" in self.slack_service.webhook_url:
            logger.info(
                f"[SlackAlertAdapter] Slack webhook URL not configured/placeholder. Logging resolution alert internally: "
                f"Incident '{incident.get('incident_id')}'"
            )
            return True

        return self.slack_service.send_incident_resolution(incident)


class MockAlertService(AlertService):
    """Test double for verifying alert invocation in unit/integration tests."""

    def __init__(self):
        self.sent_alerts: List[Dict[str, Any]] = []
        self.sent_resolutions: List[Dict[str, Any]] = []

    def send_alert(self, incident: Dict[str, Any]) -> bool:
        self.sent_alerts.append(incident.copy())
        logger.info(f"[MockAlertService] Recorded alert for incident '{incident.get('incident_id')}'")
        return True

    def send_resolution_alert(self, incident: Dict[str, Any]) -> bool:
        self.sent_resolutions.append(incident.copy())
        logger.info(f"[MockAlertService] Recorded resolution for incident '{incident.get('incident_id')}'")
        return True

    def clear(self):
        self.sent_alerts.clear()
        self.sent_resolutions.clear()

