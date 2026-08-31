#!/usr/bin/env python3
"""
IceStream Script: Repeatable & Idempotent Quarantine Table Creation
Ensures the 'quarantine' namespace and 'quarantine.invalid_checkout_events' Iceberg table exist.
"""
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pyiceberg.exceptions import NamespaceAlreadyExistsError, TableAlreadyExistsError
from iceberg.config.catalog import get_catalog
from iceberg.schemas.table_schemas import QUARANTINE_INVALID_CHECKOUT_EVENTS_SCHEMA

NAMESPACE = "quarantine"
TABLE_NAME = "invalid_checkout_events"
FULL_TABLE_NAME = f"{NAMESPACE}.{TABLE_NAME}"


def create_quarantine_table():
    print("========================================")
    print("IceStream Quarantine Table Initialization")
    print("========================================")
    print()

    catalog = get_catalog()
    print(f"Catalog: {catalog.name}\n")

    # 1. Ensure Namespace Exists
    try:
        catalog.create_namespace(NAMESPACE)
        print(f"Namespace '{NAMESPACE}': Created ✓")
    except NamespaceAlreadyExistsError:
        print(f"Namespace '{NAMESPACE}': Already exists ✓")
    except Exception as e:
        print(f"Namespace '{NAMESPACE}': Error ({e})")
        sys.exit(1)

    # 2. Ensure Table Exists
    try:
        if catalog.table_exists(FULL_TABLE_NAME):
            tbl = catalog.load_table(FULL_TABLE_NAME)
            fields = [f.name for f in tbl.schema().fields]
            if "quarantine_id" not in fields or len(fields) != len(QUARANTINE_INVALID_CHECKOUT_EVENTS_SCHEMA.fields):
                print(f"Table '{FULL_TABLE_NAME}' schema outdated. Updating table...")
                catalog.drop_table(FULL_TABLE_NAME)
                tbl = catalog.create_table(
                    FULL_TABLE_NAME,
                    schema=QUARANTINE_INVALID_CHECKOUT_EVENTS_SCHEMA,
                    properties={"write.format.default": "parquet", "format-version": "2"},
                )
                print(f"Table '{FULL_TABLE_NAME}': Recreated with Day 21 schema ✓")
            else:
                print(f"Table '{FULL_TABLE_NAME}': Already exists with current schema ✓")
        else:
            tbl = catalog.create_table(
                FULL_TABLE_NAME,
                schema=QUARANTINE_INVALID_CHECKOUT_EVENTS_SCHEMA,
                properties={"write.format.default": "parquet", "format-version": "2"},
            )
            print(f"Table '{FULL_TABLE_NAME}': Created ✓")
    except Exception as e:
        print(f"Table '{FULL_TABLE_NAME}': Error ({e})")
        sys.exit(1)

    print("\nQuarantine table initialization complete.")


if __name__ == "__main__":
    create_quarantine_table()
