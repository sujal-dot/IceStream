#!/usr/bin/env python3
"""
IceStream Iceberg Catalog Initialization Script
"""
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pyiceberg.exceptions import NamespaceAlreadyExistsError, TableAlreadyExistsError
from iceberg.config.catalog import get_catalog
from iceberg.schemas.table_schemas import (
    BRONZE_CHECKOUT_EVENTS_SCHEMA,
    BRONZE_TABLE_PROPERTIES,
    SILVER_VALID_CHECKOUT_EVENTS_SCHEMA,
    QUARANTINE_INVALID_CHECKOUT_EVENTS_SCHEMA,
    AUDIT_DATA_QUALITY_RESULTS_SCHEMA,
)

NAMESPACES = ["bronze", "silver", "quarantine", "audit"]
TABLE_DEFINITIONS = [
    ("bronze", "checkout_events", BRONZE_CHECKOUT_EVENTS_SCHEMA, BRONZE_TABLE_PROPERTIES),
    ("silver", "valid_checkout_events", SILVER_VALID_CHECKOUT_EVENTS_SCHEMA, {}),
    ("quarantine", "invalid_checkout_events", QUARANTINE_INVALID_CHECKOUT_EVENTS_SCHEMA, {}),
    ("audit", "data_quality_results", AUDIT_DATA_QUALITY_RESULTS_SCHEMA, {}),
]


def init_catalog():
    print("========================================")
    print("IceStream Iceberg Catalog Initialization")
    print("========================================")
    print()
    
    catalog = get_catalog()
    print(f"Catalog: {catalog.name}\n")

    # 1. Create and verify namespaces
    for ns in NAMESPACES:
        try:
            catalog.create_namespace(ns)
            status = "✓"
        except NamespaceAlreadyExistsError:
            status = "✓ (exists)"
        except Exception as e:
            status = f"✗ ({e})"
        print(f"{ns:<13} {status}")
    print()

    # 2. Create tables
    for ns, table_name, schema, properties in TABLE_DEFINITIONS:
        identifier = f"{ns}.{table_name}"
        try:
            if catalog.table_exists(identifier):
                tbl = catalog.load_table(identifier)
                # If schema fields don't match Day 10 definition for bronze, drop and recreate safely
                if identifier == "bronze.checkout_events" and len(tbl.schema().fields) != len(schema.fields):
                    catalog.drop_table(identifier)
                    catalog.create_table(identifier, schema=schema, properties=properties)
                    table_status = "✓ (recreated to match Day 10 contract)"
                else:
                    table_status = "✓ (exists)"
            else:
                catalog.create_table(identifier, schema=schema, properties=properties)
                table_status = "✓"
        except Exception as e:
            table_status = f"✗ ({e})"
        print(f"Table {identifier:<40} {table_status}")

    print()
    print("Catalog initialization complete.")



if __name__ == "__main__":
    init_catalog()
