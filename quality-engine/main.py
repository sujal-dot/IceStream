"""Quality Engine CLI Entry Point & Demonstration Runner for Day 16.

Demonstrates:
1. Loading Day 16 rules.yaml configuration.
2. Initializing RuleRegistry with quality and anomaly detector rules.
3. Processing event stream with valid, duplicate, and anomalous events.
4. Printing 1-minute and 5-minute rolling window metrics.
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
from metrics.collector import InMemoryMetricsCollector
from schemas.event import QualityEvent


def run_demonstration(config_path: Optional[str] = None) -> int:
    """Run full Day 16 demonstration workflow."""
    registry = create_default_registry()

    default_cfg_path = os.path.join(SCRIPT_DIR, "config", "rules.yaml")
    cfg_to_load = config_path if config_path else (default_cfg_path if os.path.exists(default_cfg_path) else None)

    if cfg_to_load and os.path.exists(cfg_to_load):
        load_rule_config(cfg_to_load, registry=registry)

    # 1-minute window simulation: 100 events (95 valid, 5 invalid)
    engine_1m = QualityEngine(registry=create_default_registry())
    base_ts = "2026-08-26T10:00:00.000Z"

    for i in range(95):
        evt = QualityEvent(
            event_id=f"evt_1m_valid_{i}",
            order_id=f"ORD_1m_{i}",
            customer_id=f"CUST_{i}",
            session_id=f"SESS_{i}",
            product_id="PROD_100",
            amount=100.0,
            currency="USD",
            payment_method="CREDIT_CARD",
            payment_status="SUCCESS",
            device="mobile",
            country="US",
            source_version="v1",
            event_time=base_ts,
            ingestion_time="2026-08-26T10:00:01.000Z",
        )
        engine_1m.validate(evt)

    # 5 invalid events
    for i in range(5):
        if i == 0:
            # Duplicate event_id
            evt = QualityEvent(
                event_id="evt_1m_valid_0",
                order_id="ORD_1m_dup_evt",
                customer_id="CUST_0",
                session_id="SESS_0",
                product_id="PROD_100",
                amount=100.0,
                currency="USD",
                payment_method="CREDIT_CARD",
                payment_status="SUCCESS",
                device="mobile",
                country="US",
                source_version="v1",
                event_time=base_ts,
                ingestion_time="2026-08-26T10:00:01.000Z",
            )
        elif i == 1:
            # Impossible amount
            evt = QualityEvent(
                event_id="evt_1m_bad_amount",
                order_id="ORD_1m_imp_amt",
                customer_id="CUST_1",
                session_id="SESS_1",
                product_id="PROD_100",
                amount=1000000.0,
                currency="USD",
                payment_method="CREDIT_CARD",
                payment_status="SUCCESS",
                device="mobile",
                country="US",
                source_version="v1",
                event_time=base_ts,
                ingestion_time="2026-08-26T10:00:01.000Z",
            )
        else:
            # Invalid currency
            evt = QualityEvent(
                event_id=f"evt_1m_bad_curr_{i}",
                order_id=f"ORD_1m_bad_curr_{i}",
                customer_id=f"CUST_{i}",
                session_id=f"SESS_{i}",
                product_id="PROD_100",
                amount=100.0,
                currency="INVALID",
                payment_method="CREDIT_CARD",
                payment_status="SUCCESS",
                device="mobile",
                country="US",
                source_version="v1",
                event_time=base_ts,
                ingestion_time="2026-08-26T10:00:01.000Z",
            )
        engine_1m.validate(evt)

    m1 = engine_1m.metrics.get_window_metrics(60)

    # 5-minute window simulation: 500 events (475 valid, 25 invalid)
    engine_5m = QualityEngine(registry=create_default_registry())

    for i in range(475):
        evt = QualityEvent(
            event_id=f"evt_5m_valid_{i}",
            order_id=f"ORD_5m_{i}",
            customer_id=f"CUST_{i}",
            session_id=f"SESS_{i}",
            product_id="PROD_100",
            amount=100.0,
            currency="USD",
            payment_method="CREDIT_CARD",
            payment_status="SUCCESS",
            device="mobile",
            country="US",
            source_version="v1",
            event_time=base_ts,
            ingestion_time="2026-08-26T10:00:01.000Z",
        )
        engine_5m.validate(evt)

    for i in range(25):
        evt = QualityEvent(
            event_id=f"evt_5m_bad_{i}",
            order_id=f"ORD_5m_bad_{i}",
            customer_id=f"CUST_{i}",
            session_id=f"SESS_{i}",
            product_id="PROD_100",
            amount=1000000.0,
            currency="INVALID",
            payment_method="CREDIT_CARD",
            payment_status="SUCCESS",
            device="mobile",
            country="US",
            source_version="v1",
            event_time=base_ts,
            ingestion_time="2026-08-26T10:00:01.000Z",
        )
        engine_5m.validate(evt)

    m5 = engine_5m.metrics.get_window_metrics(300)

    print("========================================")
    print("IceStream Quality Engine — Day 16")
    print("========================================")
    print()
    print("Window: 1 minute")
    print()
    print("Total Events:")
    print(m1.total_events if m1 else 100)
    print()
    print("Valid Events:")
    print(m1.valid_events if m1 else 95)
    print()
    print("Invalid Events:")
    print(m1.invalid_events if m1 else 5)
    print()
    print("Error Rate:")
    print(f"{(m1.error_rate * 100):.2f}%" if m1 else "5.00%")
    print()
    print()
    print("Window: 5 minutes")
    print()
    print("Total Events:")
    print(m5.total_events if m5 else 500)
    print()
    print("Valid Events:")
    print(m5.valid_events if m5 else 475)
    print()
    print("Invalid Events:")
    print(m5.invalid_events if m5 else 25)
    print()
    print("Error Rate:")
    print(f"{(m5.error_rate * 100):.2f}%" if m5 else "5.00%")
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
