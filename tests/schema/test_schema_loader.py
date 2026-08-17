"""Unit tests for Schema Loader and Validation module."""

import json
from pathlib import Path
import pytest

from schema.loader import SchemaValidationError, load_schema, validate_schema_dict


def test_load_valid_v1_schema():
    schema_path = Path("schema/v1.json")
    schema = load_schema(schema_path)
    assert schema.schema_version == "v1"
    assert "amount" in schema.fields
    assert schema.fields["amount"].type == "float"
    assert schema.fields["amount"].required is True
    assert schema.fields["payment_method"].enum is not None
    assert "UPI" in schema.fields["payment_method"].enum


def test_load_valid_v2_schema():
    schema_path = Path("schema/v2.json")
    schema = load_schema(schema_path)
    assert schema.schema_version == "v2"
    assert "coupon_code" in schema.fields
    assert schema.fields["coupon_code"].required is False
    assert "REFUNDED" in schema.fields["payment_status"].enum


def test_load_non_existent_file():
    with pytest.raises(FileNotFoundError):
        load_schema("schema/non_existent.json")


def test_validate_invalid_json_format(tmp_path):
    bad_json_file = tmp_path / "bad.json"
    bad_json_file.write_text("{ malformed json content ", encoding="utf-8")
    with pytest.raises(SchemaValidationError) as exc_info:
        load_schema(bad_json_file)
    assert "Invalid JSON" in str(exc_info.value)


def test_validate_missing_schema_version():
    data = {"fields": {"amount": {"type": "float"}}}
    with pytest.raises(SchemaValidationError) as exc_info:
        validate_schema_dict(data)
    assert "schema_version" in str(exc_info.value)


def test_validate_missing_fields():
    data = {"schema_version": "v1"}
    with pytest.raises(SchemaValidationError) as exc_info:
        validate_schema_dict(data)
    assert "fields" in str(exc_info.value)


def test_validate_unsupported_type():
    data = {
        "schema_version": "v1",
        "fields": {
            "amount": {
                "type": "money",
                "required": True,
            }
        },
    }
    with pytest.raises(SchemaValidationError) as exc_info:
        validate_schema_dict(data)
    assert "unsupported type 'money'" in str(exc_info.value)
    assert "Supported types:" in str(exc_info.value)


def test_validate_invalid_required_value():
    data = {
        "schema_version": "v1",
        "fields": {
            "amount": {
                "type": "float",
                "required": "yes",
            }
        },
    }
    with pytest.raises(SchemaValidationError) as exc_info:
        validate_schema_dict(data)
    assert "required" in str(exc_info.value)


def test_validate_invalid_enum_definition():
    data = {
        "schema_version": "v1",
        "fields": {
            "payment_method": {
                "type": "string",
                "required": True,
                "enum": [],
            }
        },
    }
    with pytest.raises(SchemaValidationError) as exc_info:
        validate_schema_dict(data)
    assert "enum" in str(exc_info.value)
