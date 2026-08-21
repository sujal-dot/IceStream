#!/usr/bin/env bash
# ==============================================================================
# IceStream - Day 11 Bronze Streaming Pipeline Deployment Script
# ==============================================================================
set -euo pipefail

FLINK_JOBMANAGER_HOST="${FLINK_JOBMANAGER_HOST:-localhost}"
FLINK_PORT="${FLINK_PORT:-8081}"
FLINK_URL="http://${FLINK_JOBMANAGER_HOST}:${FLINK_PORT}"
CATALOG_URL="${CATALOG_URL:-http://localhost:8181}"
KAFKA_BOOTSTRAP="${KAFKA_BOOTSTRAP:-localhost:9092}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

echo "========================================"
echo "IceStream Bronze Streaming Job"
echo "========================================"
echo ""

# 1. Verify Kafka reachability
if docker exec icestream-kafka /opt/kafka/bin/kafka-broker-api-versions.sh --bootstrap-server localhost:9092 >/dev/null 2>&1; then
    printf "%-18s ✓\n" "Kafka"
else
    printf "%-18s ✗\n" "Kafka"
    echo "Error: Kafka is not responding."
    exit 1
fi

# 2. Verify Iceberg Catalog reachability
if curl -sf "${CATALOG_URL}/v1/config" >/dev/null 2>&1; then
    printf "%-18s ✓\n" "Iceberg Catalog"
else
    printf "%-18s ✗\n" "Iceberg Catalog"
    echo "Error: Iceberg catalog REST API is not responding on ${CATALOG_URL}"
    exit 1
fi

# 3. Verify Flink JobManager
if curl -sf "${FLINK_URL}/v1/overview" >/dev/null 2>&1; then
    printf "%-18s ✓\n" "Bronze Table"
else
    printf "%-18s ✗\n" "Flink JobManager"
    echo "Error: Flink JobManager is not responding on ${FLINK_URL}"
    exit 1
fi

# 4. Check for existing running Bronze streaming job
ACTIVE_JOB_ID=$(curl -s "${FLINK_URL}/jobs/overview" | python3 -c "
import sys, json
data = json.load(sys.stdin)
jobs = [j for j in data.get('jobs', []) if j.get('state') == 'RUNNING' and ('checkout_events' in j.get('name', '') or 'icestream' in j.get('name', ''))]
if jobs:
    print(jobs[0]['jid'])
" || echo "")

if [ -z "${ACTIVE_JOB_ID}" ]; then
    echo ""
    echo "Submitting Flink job..."
    
    # Submit SQL streaming job to Flink
    docker exec -i icestream-flink-jobmanager /opt/flink/bin/sql-client.sh < "${PROJECT_ROOT}/flink/jobs/kafka_to_iceberg.sql" >/dev/null 2>&1 || true

    # Wait for job submission to register
    sleep 3
    
    ACTIVE_JOB_ID=$(curl -s "${FLINK_URL}/jobs/overview" | python3 -c "
import sys, json
data = json.load(sys.stdin)
jobs = [j for j in data.get('jobs', []) if j.get('state') == 'RUNNING' and ('checkout_events' in j.get('name', '') or 'icestream' in j.get('name', ''))]
if jobs:
    print(jobs[0]['jid'])
" || echo "")
fi

if [ -n "${ACTIVE_JOB_ID}" ]; then
    echo ""
    echo "Job ID:"
    echo "${ACTIVE_JOB_ID}"
    echo ""
    echo "Status:"
    echo "RUNNING"
else
    echo ""
    echo "Error: Failed to submit Flink Bronze job or job exited prematurely."
    exit 1
fi
