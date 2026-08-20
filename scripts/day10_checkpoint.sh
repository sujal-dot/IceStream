#!/usr/bin/env bash
# ==============================================================================
# IceStream — Day 10 Checkpoint Verification Script
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_PYTHON="${PROJECT_ROOT}/.venv/bin/python3"

echo "========================================"
echo "IceStream Day 10 Checkpoint"
echo "========================================"
echo ""

# Execute python-based checkpoint verifier
"${VENV_PYTHON}" - << 'EOF'
import sys
import boto3
import requests

from iceberg.config.catalog import get_catalog, get_catalog_config

all_passed = True

# 1. MinIO Check
try:
    resp = requests.get("http://localhost:9000/minio/health/live", timeout=3)
    if resp.status_code == 200:
        print(f"{'MinIO':<30} ✓")
    else:
        print(f"{'MinIO':<30} ✗")
        all_passed = False
except Exception:
    print(f"{'MinIO':<30} ✗")
    all_passed = False

# 2. Iceberg Catalog Service Check
try:
    resp = requests.get("http://localhost:8181/v1/config", timeout=3)
    if resp.status_code == 200:
        print(f"{'Iceberg Catalog':<30} ✓")
    else:
        print(f"{'Iceberg Catalog':<30} ✗")
        all_passed = False
except Exception:
    print(f"{'Iceberg Catalog':<30} ✗")
    all_passed = False

catalog = None
try:
    catalog = get_catalog()
except Exception:
    pass

# 3. bronze namespace Check
if catalog:
    namespaces = [ns[0] for ns in catalog.list_namespaces() if ns]
    if "bronze" in namespaces:
        print(f"{'bronze namespace':<30} ✓")
    else:
        print(f"{'bronze namespace':<30} ✗")
        all_passed = False
else:
    print(f"{'bronze namespace':<30} ✗")
    all_passed = False

# 4. bronze.checkout_events Table Check
tbl = None
if catalog:
    tables = [t[1] for t in catalog.list_tables("bronze")]
    if "checkout_events" in tables:
        print(f"{'bronze.checkout_events':<30} ✓")
        tbl = catalog.load_table("bronze.checkout_events")
    else:
        print(f"{'bronze.checkout_events':<30} ✗")
        all_passed = False
else:
    print(f"{'bronze.checkout_events':<30} ✗")
    all_passed = False

print()

# 5. Schema Check
if tbl and len(tbl.schema().fields) == 14:
    print(f"{'Schema':<30} ✓")
else:
    print(f"{'Schema':<30} ✗")
    all_passed = False

# 6. Parquet Configuration Check
if tbl and tbl.properties.get("write.format.default", "parquet").lower() == "parquet":
    print(f"{'Parquet':<30} ✓")
else:
    print(f"{'Parquet':<30} ✗")
    all_passed = False

# 7. MinIO Metadata & Data Files Check
config = get_catalog_config(is_internal=False)
s3 = boto3.client(
    "s3",
    endpoint_url=config["s3.endpoint"],
    aws_access_key_id=config["s3.access-key-id"],
    aws_secret_access_key=config["s3.secret-access-key"],
    region_name=config["s3.region"],
)

metadata_exists = False
data_exists = False

try:
    meta_resp = s3.list_objects_v2(Bucket="warehouse", Prefix="bronze/checkout_events/metadata/")
    if "Contents" in meta_resp and len(meta_resp["Contents"]) > 0:
        metadata_exists = True

    data_resp = s3.list_objects_v2(Bucket="warehouse", Prefix="bronze/checkout_events/data/")
    if "Contents" in data_resp and len(data_resp["Contents"]) > 0:
        data_exists = True
except Exception:
    pass

# 8. Flink Write Check
if data_exists:
    print(f"{'Flink write':<30} ✓")
else:
    print(f"{'Flink write':<30} ✗")
    all_passed = False

# 9. Iceberg Metadata Check
if metadata_exists:
    print(f"{'Iceberg metadata':<30} ✓")
else:
    print(f"{'Iceberg metadata':<30} ✗")
    all_passed = False

# 10. Parquet Data File Check
if data_exists:
    print(f"{'Parquet data file':<30} ✓")
else:
    print(f"{'Parquet data file':<30} ✗")
    all_passed = False

# 11. Read-back Check
readback_ok = False
if tbl:
    try:
        arrow_table = tbl.scan().to_arrow()
        if len(arrow_table) > 0:
            readback_ok = True
    except Exception:
        pass

if readback_ok:
    print(f"{'Read-back':<30} ✓")
else:
    print(f"{'Read-back':<30} ✗")
    all_passed = False

print()
print("========================================")
if all_passed:
    print("RESULT: DAY 10 PASS")
    print("========================================")
else:
    print("RESULT: DAY 10 FAIL")
    print("========================================")
    sys.exit(1)
EOF
