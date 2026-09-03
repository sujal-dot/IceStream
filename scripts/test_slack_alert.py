#!/usr/bin/env python3
"""Manual test script to send a test incident or resolution alert to Slack.

Usage:
    python scripts/test_slack_alert.py [--webhook URL] [--resolve] [--mock]
"""

import argparse
from datetime import datetime, timezone
import os
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.services.slack_service import SlackService
from remediation.alert_service import MockAlertService, SlackAlertAdapter


def main():
    parser = argparse.ArgumentParser(description="IceStream Slack Alert Integration Test CLI")
    parser.add_argument("--webhook", type=str, default=None, help="Slack incoming webhook URL")
    parser.add_argument("--resolve", action="store_true", help="Send incident resolution alert instead of opening incident")
    parser.add_argument("--mock", action="store_true", help="Run in mock mode without making real HTTP requests")
    parser.add_argument("--pipeline", type=str, default="checkout-stream", help="Pipeline name")
    parser.add_argument("--error-rate", type=float, default=0.0372, help="Error rate percentage float (e.g. 0.0372 for 3.72%)")

    args = parser.parse_args()

    webhook_url = args.webhook or os.getenv("SLACK_WEBHOOK_URL")

    test_incident = {
        "incident_id": "INC-2026-0903-0001",
        "pipeline_name": args.pipeline,
        "pipeline_id": "icestream",
        "status": "RESOLVED" if args.resolve else "OPEN",
        "severity": "CRITICAL",
        "error_rate": args.error_rate,
        "threshold": 0.02,
        "failed_records": int(args.error_rate * 10000),
        "failed_event_count": int(args.error_rate * 10000),
        "total_records": 10000,
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "resolved_at": datetime.now(timezone.utc).isoformat() if args.resolve else None,
        "action_taken": "Downstream pipeline paused.",
    }

    print("==================================================")
    print("IceStream Slack Alerting Test Script")
    print("==================================================")

    if args.mock:
        print("[MODE]: MOCK (No HTTP network call)")
        mock_svc = MockAlertService()
        if args.resolve:
            mock_svc.send_resolution_alert(test_incident)
            print("Formatted Mock Resolution Payload:")
            print(SlackService().format_resolution_alert(test_incident)["text"])
        else:
            mock_svc.send_alert(test_incident)
            print("Formatted Mock Incident Payload:")
            print(SlackService().format_incident_alert(test_incident)["text"])
        print("\nMock test completed successfully!")
        return 0

    if not webhook_url or "YOUR/WEBHOOK/URL" in webhook_url:
        print("[ERROR] No SLACK_WEBHOOK_URL configured!")
        print("Please set SLACK_WEBHOOK_URL environment variable or pass --webhook <URL>")
        print("Or run with --mock to test payload formatting locally.")
        return 1

    print(f"[MODE]: REAL HTTP WEBHOOK")
    print(f"Pipeline: {args.pipeline}")
    print(f"Incident ID: {test_incident['incident_id']}")
    print(f"Type: {'RESOLUTION' if args.resolve else 'ALERT'}")

    adapter = SlackAlertAdapter(webhook_url=webhook_url)

    if args.resolve:
        success = adapter.send_resolution_alert(test_incident)
    else:
        success = adapter.send_alert(test_incident)

    if success:
        print("\n✅ Slack alert dispatched successfully to webhook!")
        return 0
    else:
        print("\n❌ Slack alert dispatch failed. Check network connection or webhook URL.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
