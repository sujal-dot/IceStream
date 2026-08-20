#!/usr/bin/env python3
"""
IceStream Bronze Table Verification Script
Validates the table catalog, namespace, table columns, data types, table format, location,
Iceberg metadata, and Parquet data files on MinIO.
"""
import sys
import boto3
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from iceberg.config.catalog import get_catalog, get_catalog_config


EXPECTED_FIELDS = [
    ("event_id", "string"),
    ("event_time", "timestamp"),
    ("customer_id", "string"),
    ("session_id", "string"),
    ("order_id", "string"),
    ("product_id", "string"),
    ("amount", "decimal"),
    ("currency", "string"),
    ("payment_method", "string"),
    ("payment_status", "string"),
    ("device", "string"),
    ("country", "string"),
    ("source_version", "string"),
    ("ingestion_time", "timestamp"),
]


def verify_bronze_table():
    print("========================================")
    print("IceStream Bronze Table Verification")
    print("========================================")
    print()

    all_passed = True

    # 1. Catalog Check
    print("Catalog:")
    try:
        catalog = get_catalog()
        print(f"icestream                 ✓")
    except Exception as e:
        print(f"icestream                 ✗ ({e})")
        return False

    # 2. Namespace Check
    print("\nNamespace:")
    namespaces = [ns[0] for ns in catalog.list_namespaces() if ns]
    if "bronze" in namespaces:
        print(f"bronze                    ✓")
    else:
        print(f"bronze                    ✗")
        all_passed = False

    # 3. Table Check
    print("\nTable:")
    tables_in_ns = [t[1] for t in catalog.list_tables("bronze")]
    if "checkout_events" in tables_in_ns:
        print(f"bronze.checkout_events    ✓")
        tbl = catalog.load_table("bronze.checkout_events")
    else:
        print(f"bronze.checkout_events    ✗")
        return False

    # 4. Columns & Data Types Check
    print("\nColumns & Types:")
    schema_fields = {f.name: str(f.field_type).lower() for f in tbl.schema().fields}
    for field_name, expected_type in EXPECTED_FIELDS:
        actual_type = schema_fields.get(field_name, "missing")
        type_display = expected_type.upper()
        if expected_type in actual_type:
            print(f"{field_name:<17} {type_display:<12} ✓")
        else:
            print(f"{field_name:<17} {type_display:<12} ✗ (got {actual_type})")
            all_passed = False

    # 5. Table Format Check
    print("\nTable Format:")
    write_format = tbl.properties.get("write.format.default", "parquet").upper()
    if write_format == "PARQUET":
        print(f"PARQUET                   ✓")
    else:
        print(f"PARQUET                   ✗ (got {write_format})")
        all_passed = False

    # 6. Table Location Check
    print("\nTable Location:")
    location = tbl.location()
    if "warehouse" in location and "bronze" in location and "checkout_events" in location:
        print(f"s3://warehouse/bronze/checkout_events ✓")
    else:
        print(f"{location} ✗")
        all_passed = False

    # 7. MinIO Iceberg Metadata & Parquet Files Check
    print("\nMinIO Storage & Metadata:")
    config = get_catalog_config(is_internal=False)
    metadata_ok = False
    data_files_ok = False
    try:
        s3 = boto3.client(
            "s3",
            endpoint_url=config["s3.endpoint"],
            aws_access_key_id=config["s3.access-key-id"],
            aws_secret_access_key=config["s3.secret-access-key"],
            region_name=config["s3.region"],
        )
        meta_resp = s3.list_objects_v2(Bucket="warehouse", Prefix="bronze/checkout_events/metadata/")
        if "Contents" in meta_resp and len(meta_resp["Contents"]) > 0:
            metadata_ok = True

        data_resp = s3.list_objects_v2(Bucket="warehouse", Prefix="bronze/checkout_events/data/")
        if "Contents" in data_resp and len(data_resp["Contents"]) > 0:
            data_files_ok = True
    except Exception as e:
        print(f"MinIO check error: {e}")

    if metadata_ok:
        print(f"Iceberg Metadata          ✓")
    else:
        print(f"Iceberg Metadata          ✗")
        all_passed = False

    if data_files_ok:
        print(f"Parquet Data Files        ✓")
    else:
        print(f"Parquet Data Files        ✗")
        all_passed = False

    print("\n========================================")
    if all_passed:
        print("RESULT: PASS")
    else:
        print("RESULT: FAIL")
        sys.exit(1)


if __name__ == "__main__":
    verify_bronze_table()
