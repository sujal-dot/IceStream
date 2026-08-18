#!/usr/bin/env bash
# ==============================================================================
# IceStream - Flink -> MinIO S3 Connectivity & Verification Test
# ==============================================================================
set -euo pipefail

FLINK_JOBMANAGER_HOST="${FLINK_JOBMANAGER_HOST:-localhost}"
FLINK_PORT="${FLINK_JOB_MANAGER_PORT:-8081}"
MINIO_CONTAINER_NAME="${MINIO_CONTAINER_NAME:-icestream-minio}"
MINIO_USER="${MINIO_ROOT_USER:-icestream_minio}"
MINIO_PASS="${MINIO_ROOT_PASSWORD:-icestream_minio_secret}"

echo "=================================================="
echo "IceStream Day 8 — Flink -> MinIO Connectivity Test"
echo "=================================================="
echo ""

# 1. Verify JobManager
if curl -sf "http://${FLINK_JOBMANAGER_HOST}:${FLINK_PORT}/v1/overview" >/dev/null 2>&1; then
    printf "%-28s ✓\n" "Flink JobManager"
else
    printf "%-28s ✗\n" "Flink JobManager"
    echo "Error: JobManager is not responding on http://${FLINK_JOBMANAGER_HOST}:${FLINK_PORT}"
    exit 1
fi

# 2. Verify TaskManager
TM_COUNT=$(curl -s "http://${FLINK_JOBMANAGER_HOST}:${FLINK_PORT}/v1/taskmanagers" | grep -o '"taskmanagers":\[[^]]*\]' | grep -o 'id' | wc -l || echo "0")
if [ "${TM_COUNT}" -gt 0 ]; then
    printf "%-28s ✓\n" "Flink TaskManager"
else
    printf "%-28s ✗\n" "Flink TaskManager"
    echo "Error: No active TaskManagers found"
    exit 1
fi

# 3. Verify S3 configuration in Flink container
if docker exec icestream-flink-jobmanager ls /opt/flink/plugins/flink-s3-fs-hadoop-1.18.1/ >/dev/null 2>&1; then
    printf "%-28s ✓\n" "Flink S3 configuration"
else
    printf "%-28s ✗\n" "Flink S3 configuration"
    echo "Error: S3 plugin flink-s3-fs-hadoop not found in plugins folder"
    exit 1
fi

# Set mc alias inside minio container
docker exec "${MINIO_CONTAINER_NAME}" mc alias set local http://localhost:9000 "${MINIO_USER}" "${MINIO_PASS}" >/dev/null 2>&1

# Clean existing test folder in MinIO
docker exec "${MINIO_CONTAINER_NAME}" mc rm -r --force local/warehouse/day8-test/ >/dev/null 2>&1 || true

# 4. Submit Flink SQL job to write object to MinIO via S3
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

docker exec -i icestream-flink-jobmanager /opt/flink/bin/sql-client.sh >/dev/null 2>&1 << EOF
SET 'execution.runtime-mode' = 'batch';

CREATE TABLE minio_conn_test (
    content STRING
) WITH (
    'connector' = 'filesystem',
    'path' = 's3a://warehouse/day8-test/',
    'format' = 'raw'
);

INSERT INTO minio_conn_test VALUES 
    ('IceStream Day 8'),
    ('Flink -> MinIO connectivity test'),
    ('timestamp=${TIMESTAMP}');
EOF

# 5. Wait for Flink job completion and object arrival in MinIO
MAX_RETRIES=15
COUNTER=0
OBJECT_FOUND=false

while [ $COUNTER -lt $MAX_RETRIES ]; do
    OBJECTS=$(docker exec "${MINIO_CONTAINER_NAME}" mc ls local/warehouse/day8-test/ 2>/dev/null || true)
    if echo "${OBJECTS}" | grep -q "part-"; then
        OBJECT_FOUND=true
        break
    fi
    sleep 1
    COUNTER=$((COUNTER + 1))
done

if [ "${OBJECT_FOUND}" = true ]; then
    printf "%-28s ✓\n" "Flink -> MinIO write"
    printf "%-28s ✓\n" "MinIO object exists"
else
    printf "%-28s ✗\n" "Flink -> MinIO write"
    printf "%-28s ✗\n" "MinIO object exists"
    echo "Error: Object was not written to local/warehouse/day8-test/"
    exit 1
fi

# Find written part file
PART_FILE=$(docker exec "${MINIO_CONTAINER_NAME}" mc ls local/warehouse/day8-test/ | awk '{print $NF}' | head -n 1)

# Copy to connection-test.txt for canonical naming compliance
docker exec "${MINIO_CONTAINER_NAME}" mc cp "local/warehouse/day8-test/${PART_FILE}" "local/warehouse/day8-test/connection-test.txt" >/dev/null 2>&1 || true

# 6. Read back and verify content
CONTENT=$(docker exec "${MINIO_CONTAINER_NAME}" mc cat "local/warehouse/day8-test/${PART_FILE}" 2>/dev/null || echo "")

if echo "${CONTENT}" | grep -q "Flink -> MinIO connectivity test"; then
    printf "%-28s ✓\n" "Object read-back"
    echo ""
    echo "Verified Object Content:"
    echo "----------------------------------------"
    echo "${CONTENT}"
    echo "----------------------------------------"
    echo ""
    echo "Flink -> MinIO verification PASSED."
else
    printf "%-28s ✗\n" "Object read-back"
    echo "Error: Object read-back failed or content mismatch."
    exit 1
fi
