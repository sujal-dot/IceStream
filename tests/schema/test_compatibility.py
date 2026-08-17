"""Comprehensive unit tests for Schema Compatibility Engine."""

from schema.compatibility import check_compatibility, is_type_compatible
from schema.loader import load_schema
from schema.models import ChangeType, Classification, EventSchema, FieldSchema, Severity


def test_type_compatibility_matrix():
    assert is_type_compatible("float", "float") is True
    assert is_type_compatible("string", "string") is True
    assert is_type_compatible("integer", "integer") is True
    assert is_type_compatible("integer", "float") is True  # Safe numeric promotion

    assert is_type_compatible("float", "string") is False
    assert is_type_compatible("string", "float") is False
    assert is_type_compatible("integer", "string") is False
    assert is_type_compatible("string", "object") is False
    assert is_type_compatible("object", "string") is False


def test_v1_to_v2_compatibility():
    v1 = load_schema("schema/v1.json")
    v2 = load_schema("schema/v2.json")
    result = check_compatibility(v1, v2)

    assert result.compatible is True
    assert result.classification == Classification.COMPATIBLE
    assert result.old_version == "v1"
    assert result.new_version == "v2"
    assert len(result.changes) > 0

    # Ensure added optional fields are recorded
    added_fields = [c.field for c in result.changes if c.change_type == ChangeType.FIELD_ADDED]
    assert "coupon_code" in added_fields
    assert "device_model" in added_fields


def test_v2_to_v3_breaking():
    v2 = load_schema("schema/v2.json")
    v3 = load_schema("schema/v3.json")
    result = check_compatibility(v2, v3)

    assert result.compatible is False
    assert result.classification == Classification.BREAKING
    assert result.old_version == "v2"
    assert result.new_version == "v3"

    type_change = next(c for c in result.changes if c.field == "amount")
    assert type_change.change_type == ChangeType.FIELD_TYPE_CHANGED
    assert type_change.old_value == "float"
    assert type_change.new_value == "string"
    assert type_change.classification == Classification.BREAKING
    assert type_change.severity == Severity.BREAKING


def test_adding_required_field_is_breaking():
    v1 = load_schema("schema/v1.json")
    new_fields = dict(v1.fields)
    new_fields["tax_id"] = FieldSchema(name="tax_id", type="string", required=True)

    v1_plus_req = EventSchema(schema_version="v1_req", fields=new_fields)
    result = check_compatibility(v1, v1_plus_req)

    assert result.compatible is False
    assert result.classification == Classification.BREAKING
    change = next(c for c in result.changes if c.field == "tax_id")
    assert change.change_type == ChangeType.FIELD_ADDED
    assert change.classification == Classification.BREAKING


def test_removing_required_field_is_breaking():
    v1 = load_schema("schema/v1.json")
    new_fields = {k: v for k, v in v1.fields.items() if k != "customer_id"}

    v1_minus_cust = EventSchema(schema_version="v1_less", fields=new_fields)
    result = check_compatibility(v1, v1_minus_cust)

    assert result.compatible is False
    assert result.classification == Classification.BREAKING
    change = next(c for c in result.changes if c.field == "customer_id")
    assert change.change_type == ChangeType.FIELD_REMOVED
    assert change.classification == Classification.BREAKING


def test_changing_optional_to_required_is_breaking():
    v2 = load_schema("schema/v2.json")
    new_fields = dict(v2.fields)
    # coupon_code was optional in v2, make it required
    new_fields["coupon_code"] = FieldSchema(name="coupon_code", type="string", required=True)

    v2_strict = EventSchema(schema_version="v2_strict", fields=new_fields)
    result = check_compatibility(v2, v2_strict)

    assert result.compatible is False
    change = next(c for c in result.changes if c.field == "coupon_code")
    assert change.change_type == ChangeType.FIELD_REQUIRED_CHANGED
    assert change.classification == Classification.BREAKING


def test_enum_expansion_compatible_and_reduction_breaking():
    v1 = load_schema("schema/v1.json")

    # Expand enum
    v1_enum_expand = load_schema("schema/v2.json")
    res_expand = check_compatibility(v1, v1_enum_expand)
    assert res_expand.compatible is True
    enum_change = next(c for c in res_expand.changes if c.field == "payment_status")
    assert enum_change.change_type == ChangeType.ENUM_VALUE_ADDED
    assert enum_change.classification == Classification.COMPATIBLE

    # Reduce enum (remove SUCCESS from payment_status)
    v1_enum_reduced_fields = dict(v1.fields)
    v1_enum_reduced_fields["payment_status"] = FieldSchema(
        name="payment_status", type="string", required=True, enum=["FAILED", "PENDING"]
    )
    v1_enum_reduced = EventSchema(schema_version="v1_reduced", fields=v1_enum_reduced_fields)

    res_reduce = check_compatibility(v1, v1_enum_reduced)
    assert res_reduce.compatible is False
    reduce_change = next(c for c in res_reduce.changes if c.field == "payment_status")
    assert reduce_change.change_type == ChangeType.ENUM_VALUE_REMOVED
    assert reduce_change.classification == Classification.BREAKING


def test_safe_numeric_promotion():
    old_fields = {"quantity": FieldSchema(name="quantity", type="integer", required=True)}
    new_fields = {"quantity": FieldSchema(name="quantity", type="float", required=True)}

    s_old = EventSchema(schema_version="s1", fields=old_fields)
    s_new = EventSchema(schema_version="s2", fields=new_fields)

    res = check_compatibility(s_old, s_new)
    assert res.compatible is True
    assert res.changes[0].change_type == ChangeType.FIELD_TYPE_CHANGED
    assert res.changes[0].classification == Classification.COMPATIBLE
