#!/usr/bin/env bash
# ==============================================================================
# IceStream Day 11 Master Checkpoint & Verification Script
# Real-Time Kafka -> Flink -> Iceberg Bronze Streaming Pipeline
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "========================================"
echo "IceStream Day 11 Checkpoint"
echo "========================================"
echo ""

ALL_PASSED=true

# 1. Kafka Check
if docker exec icestream-kafka /opt/kafka/bin/kafka-broker-api-versions.sh --bootstrap-server localhost:9092 >/dev/null 2>&1; then
    printf "%-30s ✓\n" "Kafka"
else
    printf "%-30s ✗\n" "Kafka"
    ALL_PASSED=false
fi

# 2. Flink Check
if curl -sf "http://localhost:8081/v1/overview" >/dev/null 2>&1; then
    printf "%-30s ✓\n" "Flink"
else
    printf "%-30s ✗\n" "Flink"
    ALL_PASSED=false
fi

# 3. MinIO Check
if curl -sf "http://localhost:9000/minio/health/live" >/dev/null 2>&1; then
    printf "%-30s ✓\n" "MinIO"
else
    printf "%-30s ✗\n" "MinIO"
    ALL_PASSED=false
fi

# 4. Iceberg Catalog Check
if curl -sf "http://localhost:8181/v1/config" >/dev/null 2>&1; then
    printf "%-30s ✓\n" "Iceberg Catalog"
else
    printf "%-30s ✗\n" "Iceberg Catalog"
    ALL_PASSED=false
fi

# 5. Bronze Table Check
BRONZE_EXISTS=$(PYTHONPATH="${PROJECT_ROOT}" "${PROJECT_ROOT}/.venv/bin/python" -c "
from iceberg.config.catalog import get_catalog
try:
    cat = get_catalog()
    tbl = cat.load_table('bronze.checkout_events')
    print('TRUE')
except Exception:
    print('FALSE')
" 2>/dev/null || echo "FALSE")

if [ "${BRONZE_EXISTS}" = "TRUE" ]; then
    printf "%-30s ✓\n" "Bronze Table"
else
    printf "%-30s ✗\n" "Bronze Table"
    ALL_PASSED=false
fi

# 6. Ensure Flink Job is Running
RUNNING_JOB_ID=$(curl -s "http://localhost:8081/jobs/overview" | python3 -c "
import sys, json
data = json.load(sys.stdin)
jobs = [j for j in data.get('jobs', []) if j.get('state') == 'RUNNING' and ('checkout_events' in j.get('name', '') or 'icestream' in j.get('name', ''))]
if jobs:
    print(jobs[0]['jid'])
" || echo "")

if [ -z "${RUNNING_JOB_ID}" ]; then
    # Auto-submit if not active
    "${PROJECT_ROOT}/scripts/flink/run_bronze_pipeline.sh" >/dev/null 2>&1 || true
    sleep 3
    RUNNING_JOB_ID=$(curl -s "http://localhost:8081/jobs/overview" | python3 -c "
import sys, json
data = json.load(sys.stdin)
jobs = [j for j in data.get('jobs', []) if j.get('state') == 'RUNNING' and ('checkout_events' in j.get('name', '') or 'icestream' in j.get('name', ''))]
if jobs:
    print(jobs[0]['jid'])
" || echo "")
fi

if [ -n "${RUNNING_JOB_ID}" ]; then
    printf "\n%-30s ✓\n" "Kafka → Flink"
    printf "%-30s ✓\n" "Flink → Iceberg"
else
    printf "\n%-30s ✗\n" "Kafka → Flink"
    printf "%-30s ✗\n" "Flink → Iceberg"
    ALL_PASSED=false
fi

# 7. Start Generator for Continuous Ingestion Verification
PYTHONPATH="${PROJECT_ROOT}" "${PROJECT_ROOT}/.venv/bin/python" "${PROJECT_ROOT}/generator/main.py" --rate 250 --duration 12 >/dev/null 2>&1 &
GEN_PID=$!

sleep 1

# Measure Initial Count (T1)
COUNT_1=$(PYTHONPATH="${PROJECT_ROOT}" "${PROJECT_ROOT}/.venv/bin/python" -c "
from iceberg.config.catalog import get_catalog
cat = get_catalog()
tbl = cat.load_table('bronze.checkout_events')
tbl.refresh()
print(len(tbl.scan().to_arrow()))
" 2>/dev/null || echo "0")

sleep 5

# Measure Count at T2
COUNT_2=$(PYTHONPATH="${PROJECT_ROOT}" "${PROJECT_ROOT}/.venv/bin/python" -c "
from iceberg.config.catalog import get_catalog
cat = get_catalog()
tbl = cat.load_table('bronze.checkout_events')
tbl.refresh()
print(len(tbl.scan().to_arrow()))
" 2>/dev/null || echo "0")

sleep 5

# Measure Count at T3
COUNT_3=$(PYTHONPATH="${PROJECT_ROOT}" "${PROJECT_ROOT}/.venv/bin/python" -c "
from iceberg.config.catalog import get_catalog
cat = get_catalog()
tbl = cat.load_table('bronze.checkout_events')
tbl.refresh()
print(len(tbl.scan().to_arrow()))
" 2>/dev/null || echo "0")

wait ${GEN_PID} 2>/dev/null || true

# Give Flink checkpoint commit time to process pending buffer
sleep 3

COUNT_FINAL=$(PYTHONPATH="${PROJECT_ROOT}" "${PROJECT_ROOT}/.venv/bin/python" -c "
from iceberg.config.catalog import get_catalog
cat = get_catalog()
tbl = cat.load_table('bronze.checkout_events')
tbl.refresh()
print(len(tbl.scan().to_arrow()))
" 2>/dev/null || echo "0")

echo ""
printf "%-30s %s\n" "Initial Count" "${COUNT_1}"
printf "%-30s %s\n" "After 5 sec" "${COUNT_2}"
printf "%-30s %s\n" "After 10 sec" "${COUNT_3}"
printf "%-30s %s\n" "Final Count" "${COUNT_FINAL}"
echo ""

if [ "${COUNT_FINAL}" -gt "${COUNT_1}" ]; then
    printf "%-30s ✓\n" "Continuous Growth"
else
    printf "%-30s ✗\n" "Continuous Growth"
    ALL_PASSED=false
fi

# 8. Check Parquet files in MinIO
PARQUET_FILES=$(docker exec icestream-minio mc ls local/warehouse/bronze/checkout_events/data/ 2>/dev/null | grep -c "\.parquet" || echo "0")
if [ "${PARQUET_FILES}" -gt 0 ]; then
    printf "%-30s ✓\n" "Parquet Files"
else
    printf "%-30s ✗\n" "Parquet Files"
    ALL_PASSED=false
fi

# 9. Check Iceberg Snapshots
SNAPSHOTS_COUNT=$(PYTHONPATH="${PROJECT_ROOT}" "${PROJECT_ROOT}/.venv/bin/python" -c "
from iceberg.config.catalog import get_catalog
cat = get_catalog()
tbl = cat.load_table('bronze.checkout_events')
print(len(tbl.snapshots()))
" 2>/dev/null || echo "0")

if [ "${SNAPSHOTS_COUNT}" -gt 0 ]; then
    printf "%-30s ✓\n" "Iceberg Snapshots"
else
    printf "%-30s ✗\n" "Iceberg Snapshots"
    ALL_PASSED=false
fi

# 10. Check Flink Checkpoints
COMPLETED_CHECKPOINTS=$(python3 -c "
import urllib.request, json
try:
    chk = json.loads(urllib.request.urlopen('http://localhost:8081/jobs/${RUNNING_JOB_ID}/checkpoints').read())
    print(chk.get('counts', {}).get('completed', 0))
except Exception:
    print('0')
" 2>/dev/null || echo "0")

if [ "${COMPLETED_CHECKPOINTS}" -gt 0 ]; then
    printf "%-30s ✓\n" "Flink Checkpoints"
else
    printf "%-30s ✗\n" "Flink Checkpoints"
    ALL_PASSED=false
fi

echo ""
echo "========================================"
if [ "${ALL_PASSED}" = "true" ]; then
    echo "RESULT: DAY 11 PASS"
else
    echo "RESULT: DAY 11 FAIL"
    exit 1
fi
echo "========================================"
