"""Quality Engine CLI Entry Point & Demonstration Runner.

Demonstrates:
1. Loading Day 15 configuration from rules.yaml.
2. Initializing RuleRegistry with registered quality rules.
3. Executing QualityEngine against valid and invalid events.
4. Displaying structured validation results and health status summaries.
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
from rules.base import EventStatus, Severity
from rules.engine import QualityEngine
from rules.registry import create_default_registry
from schemas.event import QualityEvent


def build_sample_valid_event() -> QualityEvent:
    """Construct a clean, valid sample checkout event."""
    return QualityEvent(
        event_id="evt_day15_demo",
        event_time="2026-08-25T10:00:00.000Z",
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
        device="mobile",
        country="IN",
        source="checkout-service",
        source_version="v1",
        ingestion_time="2026-08-25T10:00:01.000Z",
    )


def build_sample_invalid_event() -> QualityEvent:
    """Construct a heavily corrupted checkout event with multiple rule failures."""
    return QualityEvent(
        event_id="evt_day15_bad",
        event_time="2026-08-25T10:00:02.000Z",
        customer_id="CUST_1002",
        session_id="SESS_9002",
        order_id="ORD_5002",
        product_id="PROD_3002",
        amount=-500.00,  # Fails amount_positive
        currency="XYZ",  # Fails currency_valid
        payment_method=None,  # Fails payment_method_not_null
        payment_status="UNKNOWN",  # Fails payment_status_valid
        device="desktop",
        country="IN",
        source="checkout-service",
        source_version="v1",
        ingestion_time="invalid_timestamp",  # Fails ingestion_time_valid
    )


def run_demonstration(config_path: Optional[str] = None) -> int:
    """Run full demonstration workflow."""
    print("========================================")
    print("IceStream Quality Engine — Day 15")
    print("========================================")
    print()

    # 1. Initialize Registry
    registry = create_default_registry()

    # 2. Load Configuration if provided or default
    default_cfg_path = os.path.join(SCRIPT_DIR, "config", "rules.yaml")
    cfg_to_load = config_path if config_path else (default_cfg_path if os.path.exists(default_cfg_path) else None)

    if cfg_to_load and os.path.exists(cfg_to_load):
        load_rule_config(cfg_to_load, registry=registry)
        print(f"Loaded configuration from: {cfg_to_load}")
    else:
        print("Using default in-memory configuration.")

    print(f"Rules active: {len(registry.all())}")
    print()

    # 3. Create Quality Engine
    engine = QualityEngine(registry=registry)

    # 4. Demonstrate Valid Event
    valid_event = build_sample_valid_event()
    print("Event:")
    print(valid_event.event_id)
    print()
    print("Results:")
    results, summary = engine.validate_with_summary(valid_event)
    for res in results:
        status_str = "PASSED" if res.passed else f"FAILED  {res.severity.value}"
        print(f"{res.rule_name:<24} {status_str}")
    print()
    print("Overall:")
    print(summary.overall_status.value)
    print()
    print("========================================")
    print()

    # 5. Demonstrate Invalid Event
    invalid_event = build_sample_invalid_event()
    print("Event:")
    print(invalid_event.event_id)
    print()
    print("Results:")
    results_inv, summary_inv = engine.validate_with_summary(invalid_event)
    for res in results_inv:
        status_str = "PASSED" if res.passed else f"FAILED  {res.severity.value}"
        print(f"{res.rule_name:<24} {status_str}")
    print()
    print("Overall:")
    print(summary_inv.overall_status.value)
    print()
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
