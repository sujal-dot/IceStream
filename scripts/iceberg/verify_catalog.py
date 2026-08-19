#!/usr/bin/env python3
"""
IceStream Iceberg Catalog Verification Script
"""
import sys
import boto3
import requests
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from iceberg.config.catalog import get_catalog, get_catalog_config

EXPECTED_NAMESPACES = {"bronze", "silver", "quarantine", "audit"}
EXPECTED_TABLES = {
    "bronze": ["checkout_events"],
    "silver": ["valid_checkout_events"],
    "quarantine": ["invalid_checkout_events"],
    "audit": ["data_quality_results"],
}


def verify_catalog():
    print("========================================")
    print("IceStream Iceberg Catalog Check")
    print("========================================")
    print()

    all_passed = True

    # 1. Catalog Check
    print("Catalog")
    try:
        catalog = get_catalog()
        catalog_name = catalog.name
        print(f"{catalog_name:<25} ✓")
    except Exception as e:
        print(f"icestream                 ✗ ({e})")
        all_passed = False
        catalog = None
        catalog_name = "icestream"

    print()

    # 2. Namespaces Check
    print("Namespaces")
    existing_namespaces = set()
    if catalog:
        try:
            ns_tuples = catalog.list_namespaces()
            existing_namespaces = {ns[0] for ns in ns_tuples if ns}
        except Exception as e:
            print(f"Error listing namespaces: {e}")
            all_passed = False

    for ns in ["bronze", "silver", "quarantine", "audit"]:
        if ns in existing_namespaces:
            print(f"{ns:<25} ✓")
        else:
            print(f"{ns:<25} ✗")
            all_passed = False

    print()

    # 3. Tables Check
    print("Tables")
    for ns, tables in EXPECTED_TABLES.items():
        for tbl in tables:
            full_tbl_name = f"{ns}.{tbl}"
            table_exists = False
            if catalog:
                try:
                    tables_in_ns = [t[1] for t in catalog.list_tables(ns)]
                    if tbl in tables_in_ns:
                        table_exists = True
                except Exception:
                    pass
            if table_exists:
                print(f"{full_tbl_name:<36} ✓")
            else:
                print(f"{full_tbl_name:<36} ✗")
                all_passed = False

    print()

    # 4. MinIO Storage Check
    config = get_catalog_config(is_internal=False)
    minio_ok = False
    try:
        s3 = boto3.client(
            "s3",
            endpoint_url=config["s3.endpoint"],
            aws_access_key_id=config["s3.access-key-id"],
            aws_secret_access_key=config["s3.secret-access-key"],
            region_name=config["s3.region"],
        )
        resp = s3.list_objects_v2(Bucket="warehouse", Prefix="bronze/checkout_events/metadata/")
        if "Contents" in resp and len(resp["Contents"]) > 0:
            minio_ok = True
    except Exception:
        pass

    if minio_ok:
        print(f"{'MinIO-backed storage':<36} ✓")
    else:
        print(f"{'MinIO-backed storage':<36} ✗")
        all_passed = False

    # 5. Flink Catalog Access Check
    flink_ok = False
    try:
        # Check Flink JobManager reachable and REST catalog endpoint configured
        resp = requests.get("http://localhost:8081/v1/overview", timeout=3)
        if resp.status_code == 200:
            # Also verify REST catalog responds to Flink-accessible endpoint
            cat_resp = requests.get(config["uri"] + "/v1/config", timeout=3)
            if cat_resp.status_code == 200:
                flink_ok = True
    except Exception:
        pass

    if flink_ok:
        print(f"{'Flink catalog access':<36} ✓")
    else:
        print(f"{'Flink catalog access':<36} ✗")
        all_passed = False

    print("========================================")
    if all_passed:
        print("RESULT: PASS")
    else:
        print("RESULT: FAIL")
        sys.exit(1)


if __name__ == "__main__":
    verify_catalog()
