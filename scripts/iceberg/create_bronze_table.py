#!/usr/bin/env python3
"""
IceStream Bronze Table Creation Script
Creates and validates the production-foundation Iceberg table: icestream.bronze.checkout_events
"""
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from iceberg.config.catalog import get_catalog
from iceberg.schemas.table_schemas import (
    BRONZE_CHECKOUT_EVENTS_SCHEMA,
    BRONZE_TABLE_PROPERTIES,
)


def create_bronze_table():
    print("========================================")
    print("IceStream Bronze Table")
    print("========================================")
    print()

    catalog = get_catalog()
    print(f"Catalog:\nicestream\n")
    print("Namespace:\nbronze\n")
    print("Table:\ncheckout_events\n")

    # 1. Verify / Create bronze namespace
    namespaces = [ns[0] for ns in catalog.list_namespaces() if ns]
    if "bronze" not in namespaces:
        catalog.create_namespace("bronze")

    # 2. Check / Create table
    identifier = "bronze.checkout_events"
    if catalog.table_exists(identifier):
        tbl = catalog.load_table(identifier)
        if len(tbl.schema().fields) != len(BRONZE_CHECKOUT_EVENTS_SCHEMA.fields):
            catalog.drop_table(identifier)
            tbl = catalog.create_table(
                identifier,
                schema=BRONZE_CHECKOUT_EVENTS_SCHEMA,
                properties=BRONZE_TABLE_PROPERTIES,
            )
    else:
        tbl = catalog.create_table(
            identifier,
            schema=BRONZE_CHECKOUT_EVENTS_SCHEMA,
            properties=BRONZE_TABLE_PROPERTIES,
        )

    # 3. Verify schema
    schema_ok = len(tbl.schema().fields) == 14 and all(
        name in [f.name for f in tbl.schema().fields]
        for name in [
            "event_id",
            "event_time",
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
            "ingestion_time",
        ]
    )
    schema_str = "✓" if schema_ok else "✗"
    print(f"Schema:\n{schema_str}\n")

    # 4. Verify format
    write_format = tbl.properties.get("write.format.default", "parquet").upper()
    format_str = f"{write_format} ✓" if write_format == "PARQUET" else f"{write_format} ✗"
    print(f"Format:\n{format_str}\n")

    # 5. Verify location
    location = tbl.location()
    location_ok = location.startswith("s3://warehouse/bronze/checkout_events") or "warehouse" in location
    location_str = "MinIO warehouse ✓" if location_ok else "MinIO warehouse ✗"
    print(f"Location:\n{location_str}\n")

    # Result
    if schema_ok and write_format == "PARQUET" and location_ok:
        print("Result:\nPASS")
    else:
        print("Result:\nFAIL")
        sys.exit(1)


if __name__ == "__main__":
    create_bronze_table()
