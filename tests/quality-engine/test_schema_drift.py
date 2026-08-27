"""Comprehensive unit & integration tests for Schema Drift Detector (Day 17)."""

import json
import pytest
from schema.compatibility import SchemaComparator, check_compatibility
from schema.models import ChangeType, Classification, EventSchema, FieldSchema, SchemaChange, Severity
from schema.registry import SchemaRegistry
from detectors.schema_drift import SchemaDriftRule
from rules.engine import QualityEngine
from rules.base import EventStatus, ValidationResult
from schemas.event import QualityEvent


def get_test_registry():
    return SchemaRegistry()


def test_schema_v1_to_v1():
    """Step 33: Expected V1 -> V1 produces NO DRIFT, COMPATIBLE."""
    registry = get_test_registry()
    v1_old = registry.get("v1")
    v1_new = registry.get("v1")

    comparator = SchemaComparator()
    diff = comparator.compare(v1_old, v1_new)

    assert diff.compatible is True
    assert diff.classification == Classification.COMPATIBLE
    assert len(diff.changes) == 0
    assert diff.overall_severity == Severity.INFO


def test_schema_v1_to_v2():
    """Step 34: V1 -> V2 compatibility check with new optional fields."""
    registry = get_test_registry()
    v1 = registry.get("v1")
    v2 = registry.get("v2")

    comparator = SchemaComparator()
    diff = comparator.compare(v1, v2)

    assert diff.compatible is True
    assert diff.classification in (Classification.COMPATIBLE, Classification.WARNING)
    assert len(diff.changes) > 0

    change_fields = [c.field for c in diff.changes]
    assert "device_model" in change_fields or "coupon_code" in change_fields


def test_schema_v1_to_v3_mandatory():
    """Step 35 & 17: V1 -> V3 type change amount float -> string MUST be CRITICAL / BREAKING."""
    registry = get_test_registry()
    v1 = registry.get("v1")
    v3 = registry.get("v3")

    comparator = SchemaComparator()
    diff = comparator.compare(v1, v3)

    assert diff.compatible is False
    assert diff.classification == Classification.BREAKING
    assert diff.overall_severity == Severity.CRITICAL

    amount_changes = [c for c in diff.changes if c.field == "amount"]
    assert len(amount_changes) == 1

    amount_change = amount_changes[0]
    assert amount_change.change_type == ChangeType.TYPE_CHANGE
    assert amount_change.expected_type == "float"
    assert amount_change.actual_type == "string"
    assert amount_change.severity == Severity.CRITICAL
    assert "CRITICAL SCHEMA DRIFT" in amount_change.message


def test_missing_column_required_vs_optional():
    """Step 36: Test missing required vs optional column classification."""
    expected = EventSchema(
        schema_version="exp",
        fields={
            "req_col": FieldSchema(name="req_col", type="string", required=True),
            "opt_col": FieldSchema(name="opt_col", type="integer", required=False),
        },
    )
    actual = EventSchema(schema_version="act", fields={})

    comparator = SchemaComparator()
    diff = comparator.compare(expected, actual)

    req_change = next(c for c in diff.changes if c.field == "req_col")
    assert req_change.change_type == ChangeType.MISSING_COLUMN
    assert req_change.severity == Severity.CRITICAL

    opt_change = next(c for c in diff.changes if c.field == "opt_col")
    assert opt_change.change_type == ChangeType.REMOVED_COLUMN
    assert opt_change.severity == Severity.WARNING


def test_new_column_required_vs_optional():
    """Step 37: Test new required vs optional column classification."""
    expected = EventSchema(schema_version="exp", fields={})
    actual = EventSchema(
        schema_version="act",
        fields={
            "new_opt": FieldSchema(name="new_opt", type="string", required=False),
            "new_req": FieldSchema(name="new_req", type="string", required=True),
        },
    )

    comparator = SchemaComparator()
    diff = comparator.compare(expected, actual)

    opt_change = next(c for c in diff.changes if c.field == "new_opt")
    assert opt_change.change_type == ChangeType.NEW_COLUMN
    assert opt_change.severity == Severity.INFO

    req_change = next(c for c in diff.changes if c.field == "new_req")
    assert req_change.change_type == ChangeType.NEW_COLUMN
    assert req_change.severity in (Severity.WARNING, Severity.CRITICAL)


def test_renamed_column_explicit_map():
    """Step 38: Test renamed column detection using explicit rename map."""
    expected = EventSchema(
        schema_version="exp",
        fields={"customer_id": FieldSchema(name="customer_id", type="string", required=True)},
    )
    actual = EventSchema(
        schema_version="act",
        fields={"customer": FieldSchema(name="customer", type="string", required=True)},
    )

    rename_map = {"customer_id": "customer"}
    comparator = SchemaComparator(rename_map=rename_map)
    diff = comparator.compare(expected, actual)

    rename_changes = [c for c in diff.changes if c.change_type == ChangeType.RENAMED_COLUMN]
    assert len(rename_changes) == 1
    assert rename_changes[0].field == "customer_id"
    assert rename_changes[0].old_value == "customer_id"
    assert rename_changes[0].new_value == "customer"
    assert rename_changes[0].severity == Severity.WARNING


def test_renamed_column_without_map_falls_back():
    """Step 38: Without explicit rename map, prefer missing + new column."""
    expected = EventSchema(
        schema_version="exp",
        fields={"customer_id": FieldSchema(name="customer_id", type="string", required=True)},
    )
    actual = EventSchema(
        schema_version="act",
        fields={"customer": FieldSchema(name="customer", type="string", required=True)},
    )

    comparator = SchemaComparator(rename_map={})
    diff = comparator.compare(expected, actual)

    change_types = [c.change_type for c in diff.changes]
    assert ChangeType.RENAMED_COLUMN not in change_types
    assert ChangeType.MISSING_COLUMN in change_types
    assert ChangeType.NEW_COLUMN in change_types


def test_removed_column_classification():
    """Step 39: Test removed column severity classification."""
    expected = EventSchema(
        schema_version="exp",
        fields={
            "coupon_code": FieldSchema(name="coupon_code", type="string", required=False),
            "order_id": FieldSchema(name="order_id", type="string", required=True),
        },
    )
    actual = EventSchema(schema_version="act", fields={})

    comparator = SchemaComparator()
    diff = comparator.compare(expected, actual)

    opt_rem = next(c for c in diff.changes if c.field == "coupon_code")
    assert opt_rem.severity == Severity.WARNING

    req_rem = next(c for c in diff.changes if c.field == "order_id")
    assert req_rem.severity == Severity.CRITICAL


def test_multiple_drift_changes():
    """Step 40: Test multiple drift changes returning overall CRITICAL severity."""
    expected = EventSchema(
        schema_version="exp",
        fields={
            "event_id": FieldSchema(name="event_id", type="string", required=True),
            "amount": FieldSchema(name="amount", type="float", required=True),
            "customer_id": FieldSchema(name="customer_id", type="string", required=True),
        },
    )
    actual = EventSchema(
        schema_version="act",
        fields={
            # Missing event_id
            "amount": FieldSchema(name="amount", type="string", required=True), # Type change
            "coupon_code": FieldSchema(name="coupon_code", type="string", required=False), # New optional
        },
    )

    comparator = SchemaComparator()
    diff = comparator.compare(expected, actual)

    assert len(diff.changes) >= 3
    assert diff.overall_severity == Severity.CRITICAL
    assert diff.classification == Classification.BREAKING


def test_field_order_independence():
    """Step 41: Field reordering MUST NOT trigger schema drift."""
    v1_fields = {
        "event_id": FieldSchema(name="event_id", type="string", required=True),
        "amount": FieldSchema(name="amount", type="float", required=True),
        "currency": FieldSchema(name="currency", type="string", required=True),
    }

    reordered_fields = {
        "currency": FieldSchema(name="currency", type="string", required=True),
        "event_id": FieldSchema(name="event_id", type="string", required=True),
        "amount": FieldSchema(name="amount", type="float", required=True),
    }

    schema1 = EventSchema(schema_version="v1", fields=v1_fields)
    schema2 = EventSchema(schema_version="v1", fields=reordered_fields)

    comparator = SchemaComparator()
    diff = comparator.compare(schema1, schema2)

    assert len(diff.changes) == 0
    assert diff.compatible is True
    assert diff.overall_severity == Severity.INFO


def test_unknown_schema_version():
    """Step 42: Unknown schema version (e.g., v999) must return SCHEMA_VERSION_UNKNOWN with CRITICAL severity."""
    rule = SchemaDriftRule(baseline_version="v1")
    event = QualityEvent.from_dict({
        "event_id": "evt_test_1",
        "event_time": "2026-08-27T10:00:00Z",
        "source_version": "v999",
        "amount": 100.0,
    })

    result = rule.validate(event)

    assert result.passed is False
    assert result.severity == Severity.CRITICAL
    assert "Unknown schema version: v999" in result.message
    assert result.metadata["error_type"] == "SCHEMA_VERSION_UNKNOWN"


def test_null_schema_version():
    """Step 43: Test behavior when source_version is None."""
    rule = SchemaDriftRule(baseline_version="v1")
    event = QualityEvent.from_dict({
        "event_id": "evt_test_null_ver",
        "event_time": "2026-08-27T10:00:00Z",
        "source_version": None,
        "event_type": "checkout",
        "customer_id": "cust_1",
        "session_id": "sess_1",
        "order_id": "ord_1",
        "product_id": "prod_1",
        "quantity": 1,
        "unit_price": 10.0,
        "amount": 10.0,
        "currency": "USD",
        "payment_method": "UPI",
        "payment_status": "SUCCESS",
        "device": "mobile",
        "country": "US",
        "source": "web",
    })

    result = rule.validate(event)
    assert isinstance(result, ValidationResult)


def test_type_compatibility_matrix():
    """Step 44: Test type compatibility matrix rules."""
    # Compatible: integer -> long, integer -> float, float -> double
    comparator = SchemaComparator()

    int_to_float = comparator.compare(
        EventSchema("1", {"val": FieldSchema("val", "integer")}),
        EventSchema("2", {"val": FieldSchema("val", "float")}),
    )
    assert int_to_float.compatible is True

    # Breaking: float -> string
    float_to_str = comparator.compare(
        EventSchema("1", {"val": FieldSchema("val", "float")}),
        EventSchema("2", {"val": FieldSchema("val", "string")}),
    )
    assert float_to_str.compatible is False
    assert float_to_str.overall_severity == Severity.CRITICAL

    # Breaking: string -> float
    str_to_float = comparator.compare(
        EventSchema("1", {"val": FieldSchema("val", "string")}),
        EventSchema("2", {"val": FieldSchema("val", "float")}),
    )
    assert str_to_float.compatible is False
    assert str_to_float.overall_severity == Severity.CRITICAL


def test_determinism():
    """Step 45: Verify identical schema comparison outputs across multiple executions."""
    registry = get_test_registry()
    v1 = registry.get("v1")
    v3 = registry.get("v3")

    comparator = SchemaComparator()
    first_run = comparator.compare(v1, v3)

    for _ in range(50):
        run = comparator.compare(v1, v3)
        assert run.overall_severity == first_run.overall_severity
        assert run.classification == first_run.classification
        assert len(run.changes) == len(first_run.changes)
        assert [c.to_dict() for c in run.changes] == [c.to_dict() for c in first_run.changes]


def test_result_json_serialization():
    """Step 46: Ensure schema drift validation result serializes to clean valid JSON."""
    rule = SchemaDriftRule(baseline_version="v1")
    event = QualityEvent.from_dict({
        "event_id": "evt_v3_test",
        "event_time": "2026-08-27T10:00:00Z",
        "source_version": "v3",
        "amount": "100.00",
    })

    val_res = rule.validate(event)
    res_dict = val_res.to_dict()

    json_str = json.dumps(res_dict)
    loaded = json.loads(json_str)

    assert loaded["rule"] == "schema_drift"
    assert loaded["severity"] == "CRITICAL"
    assert loaded["metadata"]["change_type"] == "TYPE_CHANGE"
    assert loaded["metadata"]["expected_type"] == "float"
    assert loaded["metadata"]["actual_type"] == "string"


def test_quality_engine_integration_and_event_counting():
    """Step 47 & 48: QualityEngine integration and event-level invalid count."""
    engine = QualityEngine()
    
    # Event with V3 breaking schema change (float -> string)
    v3_event = QualityEvent.from_dict({
        "event_id": "evt_v3_integration",
        "event_time": "2026-08-27T10:00:00Z",
        "source_version": "v3",
        "event_type": "checkout",
        "customer_id": "cust_1",
        "session_id": "sess_1",
        "order_id": "ord_1",
        "product_id": "prod_1",
        "quantity": 1,
        "unit_price": 10.0,
        "amount": "100.00",
        "currency": "USD",
        "payment_method": "UPI",
        "payment_status": "SUCCESS",
        "device": "mobile",
        "country": "US",
        "source": "web",
    })

    results, summary = engine.validate_with_summary(v3_event)

    schema_results = [r for r in results if r.rule_name == "schema_drift"]
    assert len(schema_results) == 1
    assert schema_results[0].passed is False
    assert schema_results[0].severity == Severity.CRITICAL
    assert "CRITICAL SCHEMA DRIFT: amount changed from float to string" in schema_results[0].message

    assert summary.overall_status == EventStatus.FAILED
    
    # Check metrics
    metrics = engine.metrics.get_metrics()
    assert metrics["total_events"] == 1
    assert metrics["invalid_events"] == 1  # Incremented exactly ONCE per event
    assert metrics["schema_drift_total"] == 1
    assert metrics["schema_drift_critical"] == 1
    assert metrics["schema_type_change_total"] == 1
