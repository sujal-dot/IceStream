"""Slack Alerting Service for IceStream Real-Time Lakehouse Observability.

Handles sending formatted incident alerts and resolution notifications to Slack via incoming webhooks
with exponential backoff retries and non-blocking error handling.
"""

from datetime import datetime, timezone
import json
import logging
import os
import time
from typing import Any, Dict, Optional
import urllib.error
import urllib.request

logger = logging.getLogger("icestream.services.slack")


class SlackService:
    """Production-grade Slack Webhook Client with fault isolation and retries."""

    def __init__(
        self,
        webhook_url: Optional[str] = None,
        enabled: Optional[bool] = None,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
    ):
        self.webhook_url = webhook_url or os.getenv("SLACK_WEBHOOK_URL")
        env_enabled = os.getenv("SLACK_ALERTS_ENABLED", "true").lower() in ("true", "1", "yes")
        self.enabled = enabled if enabled is not None else env_enabled
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

    def format_incident_alert(self, incident: Dict[str, Any]) -> Dict[str, Any]:
        """Construct structured markdown payload for Incident Alert."""
        incident_id = incident.get("incident_id", "INC-UNKNOWN")
        pipeline_name = incident.get("pipeline_name") or incident.get("pipeline_id") or "checkout-stream"
        status = incident.get("status", "OPEN")
        severity = incident.get("severity", "CRITICAL")
        error_rate = float(incident.get("error_rate", 0.0))
        threshold = float(incident.get("threshold", 0.02))
        failed_records = int(incident.get("failed_records") if incident.get("failed_records") is not None else incident.get("failed_event_count", 0))
        action_taken = incident.get("action_taken") or "Downstream pipeline paused."

        # Format detected timestamp (HH:MM:SS format)
        detected_val = incident.get("detected_at") or incident.get("created_at") or datetime.now(timezone.utc)
        if isinstance(detected_val, str):
            try:
                dt = datetime.fromisoformat(detected_val.replace("Z", "+00:00"))
                detected_str = dt.strftime("%H:%M:%S")
            except Exception:
                detected_str = detected_val.split("T")[-1][:8] if "T" in detected_val else str(detected_val)
        elif isinstance(detected_val, datetime):
            detected_str = detected_val.strftime("%H:%M:%S")
        else:
            detected_str = str(detected_val)

        text_content = (
            f"*🚨 ICESTREAM INCIDENT*\n\n"
            f"*Pipeline:* {pipeline_name}\n"
            f"*Status:* {status}\n"
            f"*Severity:* {severity}\n\n"
            f"*Error rate:* {error_rate * 100:.2f}%\n"
            f"*Threshold:* {threshold * 100:.0f}%\n"
            f"*Failed records:* {failed_records}\n\n"
            f"*Detected:* {detected_str}\n\n"
            f"*Action:*\n"
            f"{action_taken}\n\n"
            f"*Incident ID:*\n"
            f"{incident_id}"
        )

        return {"text": text_content}

    def format_resolution_alert(self, incident: Dict[str, Any]) -> Dict[str, Any]:
        """Construct structured markdown payload for Incident Resolution."""
        incident_id = incident.get("incident_id", "INC-UNKNOWN")
        pipeline_name = incident.get("pipeline_name") or incident.get("pipeline_id") or "checkout-stream"
        status = incident.get("status", "RESOLVED")
        error_rate = float(incident.get("error_rate", 0.0))

        resolved_val = incident.get("resolved_at") or datetime.now(timezone.utc)
        if isinstance(resolved_val, str):
            try:
                dt = datetime.fromisoformat(resolved_val.replace("Z", "+00:00"))
                resolved_str = dt.strftime("%H:%M:%S")
            except Exception:
                resolved_str = resolved_val.split("T")[-1][:8] if "T" in resolved_val else str(resolved_val)
        elif isinstance(resolved_val, datetime):
            resolved_str = resolved_val.strftime("%H:%M:%S")
        else:
            resolved_str = str(resolved_val)

        text_content = (
            f"*✅ ICESTREAM INCIDENT RESOLVED*\n\n"
            f"*Pipeline:* {pipeline_name}\n\n"
            f"*Status:* {status}\n\n"
            f"*Error rate:* {error_rate * 100:.2f}%\n\n"
            f"*Recovered at:* {resolved_str}\n\n"
            f"*Incident ID:*\n"
            f"{incident_id}"
        )

        return {"text": text_content}

    def _post_payload(self, payload: Dict[str, Any]) -> bool:
        """Internal helper sending HTTP payload with retries. Returns True on success."""
        if not self.enabled:
            logger.info("[SlackService] Slack alerts disabled by configuration.")
            return False

        if not self.webhook_url or "YOUR/WEBHOOK/URL" in self.webhook_url:
            logger.info("[SlackService] Slack webhook URL not configured. Skipping external HTTP request.")
            return False

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        for attempt in range(1, self.max_retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=5) as resp:
                    if resp.status in (200, 204):
                        logger.info(f"[SlackService] Slack alert dispatched successfully (Attempt {attempt}).")
                        return True
                    else:
                        logger.warning(f"[SlackService] Slack HTTP status {resp.status} on attempt {attempt}.")
            except Exception as e:
                logger.warning(f"[SlackService] Slack HTTP request failed on attempt {attempt}/{self.max_retries}: {e}")

            if attempt < self.max_retries:
                time.sleep(self.backoff_factor * (2 ** (attempt - 1)))

        logger.error(f"[SlackService] Slack notification failed after {self.max_retries} attempts.")
        return False

    def send_incident_alert(self, incident: Dict[str, Any]) -> bool:
        """Send Incident Alert notification to Slack safely."""
        payload = self.format_incident_alert(incident)
        return self._post_payload(payload)

    def send_incident_resolution(self, incident: Dict[str, Any]) -> bool:
        """Send Incident Resolution notification to Slack safely."""
        payload = self.format_resolution_alert(incident)
        return self._post_payload(payload)
