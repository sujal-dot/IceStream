"""Integration tests for QualityEngine with Day 15 Null + Validity rules."""

import json
import os
import pytest
from config.loader import load_rule_config
from rules.base import EventStatus, RuleStatus, Severity
from rules.engine import QualityEngine
from rules.registry import RuleRegistry, create_default_registry
from schemas.event import QualityEvent


@pytest.fixture
def day15_engine():
    """Create QualityEngine loaded with Day 15 configuration rules.yaml."""
    registry = create_default_registry()
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "config", "rules.yaml"
    )
    if os.path.exists(config_path):
        load_rule_config(config_path, registry=registry)
    return QualityEngine(registry=registry)


def test_quality_engine_valid_event(day15_engine):
    """Verify that a fully valid event passes all active Day 15 rules."""
    valid_payload = {
        "event_id": "evt_day15_001",
        "event_time": "2026-08-25T10:00:00.000Z",
        "customer_id": "CUST_1001",
        "session_id": "SESS_9001",
        "order_id": "ORD_5001",
        "product_id": "PROD_3001",
        "amount": 1499.00,
        "currency": "INR",
        "payment_method": "UPI",
        "payment_status": "SUCCESS",
        "device": "mobile",
        "country": "IN",
        "source_version": "v1",
        "ingestion_time": "2026-08-25T10:00:01.000Z",
    }

    results, summary = day15_engine.validate_with_summary(valid_payload)

    assert len(results) >= 19
    assert summary.overall_status == EventStatus.HEALTHY
    assert summary.failed_rules == 0
    assert summary.critical_failures == 0
    assert all(r.passed for r in results)


def test_quality_engine_partially_invalid_event(day15_engine):
    """Verify that a partially invalid event produces specific expected failures."""
    partially_invalid = {
        "event_id": "evt_day15_partial",
        "event_time": "2026-08-25T10:00:00.000Z",
        "customer_id": "CUST_1002",
        "session_id": "SESS_9002",
        "order_id": "ORD_5002",
        "product_id": "PROD_3002",
        "amount": -50.00,  # Fails amount_positive
        "currency": "GBP",  # Fails currency_valid
        "payment_method": "CREDIT_CARD",
        "payment_status": "SUCCESS",
        "device": "desktop",
        "country": "IN",
        "source_version": "v1",
        "ingestion_time": "2026-08-25T10:00:01.000Z",
    }

    results, summary = day15_engine.validate_with_summary(partially_invalid)

    assert summary.overall_status in (EventStatus.FAILED, EventStatus.WARNING)
    assert summary.failed_rules == 2

    failed_rule_names = {r.rule_name for r in results if not r.passed}
    assert "amount_positive" in failed_rule_names
    assert "currency_valid" in failed_rule_names


def test_quality_engine_heavily_corrupted_event(day15_engine):
    """Verify that a heavily corrupted event triggers multiple rule failures cleanly."""
    corrupted = {
        "event_id": None,  # Fails event_id_not_null
        "event_time": "not-a-timestamp",  # Fails event_time_valid
        "customer_id": None,  # Fails customer_id_not_null
        "amount": -100.00,  # Fails amount_positive
        "currency": "XYZ",  # Fails currency_valid
        "payment_status": "UNKNOWN",  # Fails payment_status_valid
        "ingestion_time": None,  # Fails ingestion_time_not_null & ingestion_time_valid
    }

    results, summary = day15_engine.validate_with_summary(corrupted)

    assert summary.overall_status == EventStatus.FAILED
    assert summary.failed_rules >= 6

    failed_rule_names = {r.rule_name for r in results if not r.passed}
    assert "event_id_not_null" in failed_rule_names
    assert "event_time_valid" in failed_rule_names
    assert "customer_id_not_null" in failed_rule_names
    assert "amount_positive" in failed_rule_names
    assert "currency_valid" in failed_rule_names
    assert "payment_status_valid" in failed_rule_names


def test_validation_result_json_serialization(day15_engine):
    """Verify ValidationResult serializes cleanly to valid JSON."""
    event = QualityEvent(event_id="evt_test", amount=-10.0)
    results = day15_engine.validate(event)

    for res in results:
        res_dict = res.to_dict()
        json_str = json.dumps(res_dict)

        # Deserialize to confirm valid JSON
        parsed = json.loads(json_str)
        assert parsed["rule"] == res.rule_name
        assert parsed["rule_name"] == res.rule_name
        assert parsed["status"] in ("PASS", "FAIL")
        assert "severity" in parsed
        assert "message" in parsed


def test_null_event_fields_matrix(day15_engine):
    """Test every required nullable field produces a failure when set to None."""
    required_fields = [
        "event_id",
        "customer_id",
        "session_id",
        "order_id",
        "product_id",
        "amount",
        "currency",
        "payment_method",
        "payment_status",
        "device",
        "country",
        "source_version",
        "event_time",
        "ingestion_time",
    ]

    for field_name in required_fields:
        payload = {
            "event_id": "evt_matrix",
            "event_time": "2026-08-25T10:00:00Z",
            "customer_id": "CUST_1",
            "session_id": "SESS_1",
            "order_id": "ORD_1",
            "product_id": "PROD_1",
            "amount": 100.0,
            "currency": "INR",
            "payment_method": "UPI",
            "payment_status": "SUCCESS",
            "device": "mobile",
            "country": "IN",
            "source_version": "v1",
            "ingestion_time": "2026-08-25T10:00:01Z",
        }
        # Set target field to None
        payload[field_name] = None

        results = day15_engine.validate(payload)
        expected_rule_name = f"{field_name}_not_null"

        matching_results = [r for r in results if r.rule_name == expected_rule_name]
        assert len(matching_results) == 1, f"Expected rule {expected_rule_name} to execute"
        assert (
            matching_results[0].passed is False
        ), f"Expected rule {expected_rule_name} to fail for null {field_name}"
