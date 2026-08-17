"""Unit tests for Schema Registry abstraction."""

from pathlib import Path
import pytest

from schema.models import Classification, EventSchema, FieldSchema
from schema.registry import SchemaRegistry


def test_registry_load_and_list():
    registry = SchemaRegistry(schema_dir=Path("schema"))
    versions = registry.list_versions()
    assert "v1" in versions
    assert "v2" in versions
    assert "v3" in versions


def test_registry_get_versions():
    registry = SchemaRegistry(schema_dir=Path("schema"))
    v1 = registry.get("v1")
    v2 = registry.get("v2")
    assert v1.schema_version == "v1"
    assert v2.schema_version == "v2"


def test_registry_get_unknown_version():
    registry = SchemaRegistry(schema_dir=Path("schema"))
    with pytest.raises(KeyError):
        registry.get("v999")


def test_registry_current():
    registry = SchemaRegistry(schema_dir=Path("schema"))
    current_schema = registry.current()
    assert current_schema.schema_version == "v2"


def test_registry_compare_versions():
    registry = SchemaRegistry(schema_dir=Path("schema"))
    res_v1_v2 = registry.compare_versions("v1", "v2")
    assert res_v1_v2.compatible is True
    assert res_v1_v2.classification == Classification.COMPATIBLE

    res_v2_v3 = registry.compare_versions("v2", "v3")
    assert res_v2_v3.compatible is False
    assert res_v2_v3.classification == Classification.BREAKING


def test_registry_register_dynamic_schema():
    registry = SchemaRegistry(schema_dir=Path("schema"))
    new_schema = EventSchema(
        schema_version="v4",
        fields={
            "amount": FieldSchema(name="amount", type="float", required=True),
        },
    )
    reg_schema = registry.register("v4", new_schema)
    assert "v4" in registry.list_versions()
    assert registry.get("v4").schema_version == "v4"
