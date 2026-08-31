"""
Integration Tests for Iceberg Tables and Schemas
"""
import pytest
from iceberg.config.catalog import get_catalog

EXPECTED_TABLES = [
    ("bronze", "checkout_events"),
    ("silver", "valid_checkout_events"),
    ("quarantine", "invalid_checkout_events"),
    ("audit", "data_quality_results"),
]


@pytest.mark.parametrize("namespace,table_name", EXPECTED_TABLES)
def test_table_exists(namespace, table_name):
    catalog = get_catalog()
    tables_in_ns = [t[1] for t in catalog.list_tables(namespace)]
    assert table_name in tables_in_ns, f"Table {namespace}.{table_name} not found in catalog"


def test_bronze_checkout_events_schema():
    catalog = get_catalog()
    table = catalog.load_table("bronze.checkout_events")
    field_names = [field.name for field in table.schema().fields]
    assert "event_id" in field_names
    assert "event_time" in field_names
    assert "customer_id" in field_names
    assert "amount" in field_names


def test_quarantine_table_schema():
    catalog = get_catalog()
    table = catalog.load_table("quarantine.invalid_checkout_events")
    field_names = [field.name for field in table.schema().fields]
    assert "quarantine_id" in field_names
    assert "error_code" in field_names
    assert "failed_rules" in field_names
    assert "pipeline_version" in field_names


def test_audit_table_schema():
    catalog = get_catalog()
    table = catalog.load_table("audit.data_quality_results")
    field_names = [field.name for field in table.schema().fields]
    assert "check_id" in field_names
    assert "check_name" in field_names
    assert "status" in field_names
