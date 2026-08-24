"""Quality Engine CLI Entry Point & Demonstration Runner.

Demonstrates:
1. Loading configuration from YAML.
2. Initializing the RuleRegistry and registering quality rules.
3. Constructing QualityEngine instance.
4. Validating a valid checkout event.
5. Validating an invalid checkout event (null event_id).
6. Displaying structured validation results and health status summaries.
"""

import argparse
import json
import os
import sys
from typing import Optional

# Ensure package root is in sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from config.loader import load_rule_config
from rules.base import EventIdNotNullRule, EventStatus, Severity
from rules.engine import QualityEngine
from rules.registry import RuleRegistry
from schemas.event import QualityEvent


def build_sample_valid_event() -> QualityEvent:
    """Construct a clean, valid sample checkout event."""
    return QualityEvent(
        event_id="evt_demo_001",
        event_time="2026-08-24T10:00:00Z",
        customer_id="CUST_1001",
        session_id="SESS_9001",
        order_id="ORD_5001",
        product_id="PROD_3001",
        quantity=2,
        unit_price=749.50,
        amount=1499.00,
        currency="INR",
        payment_method="UPI",
        payment_status="SUCCESS",
        device="MOBILE_IOS",
        country="IN",
        source="checkout-service",
        source_version="v1",
        ingestion_time="2026-08-24T10:00:01Z",
    )


def build_sample_invalid_event() -> QualityEvent:
    """Construct an invalid sample checkout event with null event_id."""
    return QualityEvent(
        event_id=None,
        event_time="2026-08-24T10:00:02Z",
        customer_id="CUST_1002",
        session_id="SESS_9002",
        order_id="ORD_5002",
        product_id="PROD_3002",
        quantity=1,
        unit_price=499.00,
        amount=499.00,
        currency="INR",
        payment_method="CREDIT_CARD",
        payment_status="SUCCESS",
        device="DESKTOP_WEB",
        country="IN",
        source="checkout-service",
        source_version="v1",
        ingestion_time="2026-08-24T10:00:03Z",
    )


def run_demonstration(config_path: Optional[str] = None) -> int:
    """Run full demonstration workflow."""
    print("========================================")
    print("IceStream Quality Engine")
    print("========================================")
    print()

    # 1. Initialize Registry
    registry = RuleRegistry()
    registry.register(EventIdNotNullRule())

    # 2. Load Configuration if provided or default
    default_cfg_path = os.path.join(SCRIPT_DIR, "config", "rules.yaml")
    cfg_to_load = config_path if config_path else (default_cfg_path if os.path.exists(default_cfg_path) else None)

    if cfg_to_load and os.path.exists(cfg_to_load):
        load_rule_config(cfg_to_load, registry=registry)
        print(f"Loaded config from: {cfg_to_load}")
    else:
        print("Using default in-memory configuration.")

    print(f"Rules loaded:")
    print(len(registry.all()))
    for r in registry.all():
        print(f"  - {r.name} (enabled={r.enabled}, severity={r.severity.value})")
    print()

    # 3. Create Quality Engine
    engine = QualityEngine(registry=registry)

    # 4. Demonstrate Valid Event
    valid_event = build_sample_valid_event()
    print("----------------------------------------")
    print("DEMO 1: Valid Event Evaluation")
    print("----------------------------------------")
    print(f"Event:")
    print(valid_event.event_id)
    print()
    print("Validation:")
    results, summary = engine.validate_with_summary(valid_event)
    for res in results:
        status_str = "PASS" if res.passed else f"FAIL ({res.severity.value})"
        print(f"{res.rule_name:<24} {status_str}")
        print(f"  Message: {res.message}")
    print()
    print("Overall:")
    print(summary.overall_status.value)
    print()

    # 5. Demonstrate Invalid Event
    invalid_event = build_sample_invalid_event()
    print("----------------------------------------")
    print("DEMO 2: Corrupted Event Evaluation (Null event_id)")
    print("----------------------------------------")
    print(f"Event:")
    print(str(invalid_event.event_id))
    print()
    print("Validation:")
    results_inv, summary_inv = engine.validate_with_summary(invalid_event)
    for res in results_inv:
        status_str = "PASS" if res.passed else f"FAIL ({res.severity.value})"
        print(f"{res.rule_name:<24} {status_str}")
        print(f"  Message: {res.message}")
    print()
    print("Overall:")
    print(summary_inv.overall_status.value)
    print()

    # 6. Metrics Summary
    print("----------------------------------------")
    print("Engine Metrics Snapshot")
    print("----------------------------------------")
    metrics_data = engine.metrics.get_metrics()
    print(json.dumps(metrics_data, indent=2))
    print()

    print("========================================")
    print("Demonstration Completed Successfully.")
    print("========================================")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="IceStream Quality Engine Runner")
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default=None,
        help="Path to rules YAML configuration file",
    )
    args = parser.parse_args()
    return run_demonstration(config_path=args.config)


if __name__ == "__main__":
    sys.exit(main())
