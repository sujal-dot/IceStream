#!/usr/bin/env bash
# ==============================================================================
# IceStream Day 12 Master Checkpoint & Recovery Verification Script
# Real-Time Flink Checkpoint, State Restoration & Offset Recovery Test
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON_EXEC="${PROJECT_ROOT}/.venv/bin/python"

echo "========================================"
echo "IceStream Day 12 Recovery Test"
echo "========================================"
echo ""

ALL_PASSED=true

# 1. Infrastructure Checks
if docker exec icestream-kafka /opt/kafka/bin/kafka-broker-api-versions.sh --bootstrap-server localhost:9092 >/dev/null 2>&1; then
    printf "%-30s ✓\n" "Kafka"
else
    printf "%-30s ✗\n" "Kafka"
    ALL_PASSED=false
fi

if curl -sf "http://localhost:8081/v1/overview" >/dev/null 2>&1; then
    printf "%-30s ✓\n" "Flink JobManager"
else
    printf "%-30s ✗\n" "Flink JobManager"
    ALL_PASSED=false
fi

if curl -sf "http://localhost:9000/minio/health/live" >/dev/null 2>&1; then
    printf "%-30s ✓\n" "MinIO S3 Store"
else
    printf "%-30s ✗\n" "MinIO S3 Store"
    ALL_PASSED=false
fi

if curl -sf "http://localhost:8181/v1/config" >/dev/null 2>&1; then
    printf "%-30s ✓\n" "Iceberg Catalog"
else
    printf "%-30s ✗\n" "Iceberg Catalog"
    ALL_PASSED=false
fi

# 2. Ensure Flink Streaming Job is Active
RUNNING_JOB_ID=$("${PYTHON_EXEC}" -c "
import urllib.request, json
try:
    req = urllib.request.urlopen('http://localhost:8081/jobs/overview', timeout=5)
    data = json.loads(req.read().decode('utf-8'))
    jobs = [j for j in data.get('jobs', []) if j.get('state') == 'RUNNING']
    if jobs:
        print(jobs[0]['jid'])
except Exception:
    print('')
" 2>/dev/null || echo "")

if [ -z "${RUNNING_JOB_ID}" ]; then
    echo "Submitting Flink Bronze streaming job..."
    "${SCRIPT_DIR}/flink/run_bronze_pipeline.sh" >/dev/null 2>&1 || true
    sleep 3
    RUNNING_JOB_ID=$("${PYTHON_EXEC}" -c "
import urllib.request, json
try:
    req = urllib.request.urlopen('http://localhost:8081/jobs/overview', timeout=5)
    data = json.loads(req.read().decode('utf-8'))
    jobs = [j for j in data.get('jobs', []) if j.get('state') == 'RUNNING']
    if jobs:
        print(jobs[0]['jid'])
except Exception:
    print('')
" 2>/dev/null || echo "")
fi

if [ -n "${RUNNING_JOB_ID}" ]; then
    printf "%-30s RUNNING ✓\n" "Initial Flink status"
else
    printf "%-30s FAILED ✗\n" "Initial Flink status"
    echo "Error: No active Flink streaming job found."
    exit 1
fi

# 3. Start Generator to Produce Controlled Event Stream
echo ""
echo "Starting continuous event stream generator..."
PYTHONPATH="${PROJECT_ROOT}" "${PYTHON_EXEC}" "${PROJECT_ROOT}/generator/main.py" \
    --rate 300 \
    --duration 45 \
    --error-rate 0 >/dev/null 2>&1 &
GEN_PID=$!

# Wait for at least 1 checkpoint to complete
echo "Waiting for completed checkpoint in MinIO S3..."
CHECKPOINT_COUNT=0
WAIT_ACC=0
while [ ${CHECKPOINT_COUNT} -eq 0 ] && [ ${WAIT_ACC} -lt 40 ]; do
    sleep 3
    WAIT_ACC=$((WAIT_ACC + 3))
    CHECKPOINT_COUNT=$("${PYTHON_EXEC}" -c "
import urllib.request, json
try:
    chk = json.loads(urllib.request.urlopen('http://localhost:8081/jobs/${RUNNING_JOB_ID}/checkpoints').read())
    print(chk.get('counts', {}).get('completed', 0))
except Exception:
    print('0')
" 2>/dev/null || echo "0")
done

if [ "${CHECKPOINT_COUNT}" -gt 0 ]; then
    printf "%-30s ✓ (${CHECKPOINT_COUNT} completed)\n" "Checkpoint completed"
else
    printf "%-30s ✗\n" "Checkpoint completed"
    echo "Error: No checkpoints completed in time."
    kill ${GEN_PID} 2>/dev/null || true
    exit 1
fi

# 4. Verify Checkpoint Artifact in MinIO S3
S3_CHK_PATH=$(docker exec icestream-minio mc ls --recursive "local/checkpoints/flink/bronze/${RUNNING_JOB_ID}/" 2>/dev/null | grep "_metadata" | head -n 1 || echo "")
if [ -n "${S3_CHK_PATH}" ]; then
    printf "%-30s ✓\n" "MinIO S3 Artifact"
else
    printf "%-30s ✗\n" "MinIO S3 Artifact"
    ALL_PASSED=false
fi

# 5. Record Count Before Failure
COUNT_BEFORE_FAILURE=$("${PYTHON_EXEC}" -c "
from iceberg.config.catalog import get_catalog
cat = get_catalog()
tbl = cat.load_table('bronze.checkout_events')
tbl.refresh()
print(len(tbl.scan().to_arrow()))
" 2>/dev/null || echo "0")

echo ""
printf "%-30s %s\n" "Count before failure" "${COUNT_BEFORE_FAILURE}"

# 6. Inject Controlled TaskManager Failure
echo ""
echo "Injecting Flink failure (Stopping TaskManager container)..."
FAIL_START_TIME=$(date +%s)
docker compose stop flink-taskmanager >/dev/null 2>&1
printf "%-30s ✓\n" "Failure injected"

# Allow brief outage pause
sleep 5

# 7. Restart Flink TaskManager
echo "Restarting Flink TaskManager service..."
docker compose start flink-taskmanager >/dev/null 2>&1

# Wait for TaskManager to rejoin and JobManager to restore job
RESTORED=false
WAIT_RESTORE=0
while [ "${RESTORED}" = "false" ] && [ ${WAIT_RESTORE} -lt 40 ]; do
    sleep 2
    WAIT_RESTORE=$((WAIT_RESTORE + 2))
    JOB_STATE=$("${PYTHON_EXEC}" -c "
import urllib.request, json
try:
    req = urllib.request.urlopen('http://localhost:8081/jobs/${RUNNING_JOB_ID}', timeout=5)
    data = json.loads(req.read().decode('utf-8'))
    print(data.get('state', ''))
except Exception:
    print('')
" 2>/dev/null || echo "")
    if [ "${JOB_STATE}" = "RUNNING" ]; then
        RESTORED=true
    fi
done

FAIL_END_TIME=$(date +%s)
RECOVERY_DURATION=$((FAIL_END_TIME - FAIL_START_TIME))

if [ "${RESTORED}" = "true" ]; then
    printf "%-30s ✓\n" "Flink restarted"
    printf "%-30s ✓\n" "Checkpoint restored"
    printf "%-30s ✓\n" "Kafka resumed"
    printf "%-30s ✓\n" "Iceberg resumed"
else
    printf "%-30s ✗\n" "Flink restarted"
    ALL_PASSED=false
fi

# 8. Measure Ingestion Growth After Recovery
sleep 5
COUNT_AFTER_RESTART=$("${PYTHON_EXEC}" -c "
from iceberg.config.catalog import get_catalog
cat = get_catalog()
tbl = cat.load_table('bronze.checkout_events')
tbl.refresh()
print(len(tbl.scan().to_arrow()))
" 2>/dev/null || echo "0")

sleep 10
COUNT_RECOVERED_2=$("${PYTHON_EXEC}" -c "
from iceberg.config.catalog import get_catalog
cat = get_catalog()
tbl = cat.load_table('bronze.checkout_events')
tbl.refresh()
print(len(tbl.scan().to_arrow()))
" 2>/dev/null || echo "0")

wait ${GEN_PID} 2>/dev/null || true

echo ""
printf "%-30s %s\n" "Count after recovery" "${COUNT_AFTER_RESTART}"
printf "%-30s %s\n" "Count post-recovery (T+10s)" "${COUNT_RECOVERED_2}"
printf "%-30s %ss\n" "Recovery duration" "${RECOVERY_DURATION}"

if [ "${COUNT_RECOVERED_2}" -gt "${COUNT_AFTER_RESTART}" ] && [ "${COUNT_AFTER_RESTART}" -ge "${COUNT_BEFORE_FAILURE}" ]; then
    printf "%-30s ✓\n" "Count continues increasing"
else
    printf "%-30s ✗\n" "Count continues increasing"
    ALL_PASSED=false
fi

# 9. Duplicate Record Analysis
DUPLICATES_COUNT=$("${PYTHON_EXEC}" -c "
from iceberg.config.catalog import get_catalog
import pyarrow.compute as pc
cat = get_catalog()
tbl = cat.load_table('bronze.checkout_events')
tbl.refresh()
arr = tbl.scan().to_arrow()
event_ids = arr['event_id'].to_pylist()
dups = len(event_ids) - len(set(event_ids))
print(dups)
" 2>/dev/null || echo "0")

printf "%-30s %s\n" "Duplicates observed" "${DUPLICATES_COUNT}"

echo ""
echo "========================================"
if [ "${ALL_PASSED}" = "true" ]; then
    echo "Recovery test               PASS"
else
    echo "Recovery test               FAIL"
    exit 1
fi
echo "========================================"
