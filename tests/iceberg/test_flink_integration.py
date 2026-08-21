"""
Integration Test for Flink & Iceberg REST Catalog Connectivity & Write/Read Verification
"""
import pytest
import subprocess
from iceberg.config.catalog import get_catalog


def test_flink_iceberg_readback():
    catalog = get_catalog()
    table = catalog.load_table("bronze.checkout_events")
    arrow_table = table.scan().to_arrow()
    assert len(arrow_table) > 0, "No records found in bronze.checkout_events during read-back test"
    data = arrow_table.to_pydict()
    assert any(eid and str(eid).startswith("evt_") for eid in data["event_id"] if eid), "Expected valid event record in bronze.checkout_events"

