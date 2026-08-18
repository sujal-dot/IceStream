#!/usr/bin/env bash
# ==============================================================================
# IceStream - MinIO Object Storage Verification Script
# ==============================================================================
set -euo pipefail

MINIO_CONTAINER_NAME="${MINIO_CONTAINER_NAME:-icestream-minio}"
MINIO_USER="${MINIO_ROOT_USER:-icestream_minio}"
MINIO_PASS="${MINIO_ROOT_PASSWORD:-icestream_minio_secret}"
MINIO_URL="http://localhost:9000"

# Check MinIO health
if curl -sf "${MINIO_URL}/minio/health/live" >/dev/null 2>&1; then
    printf "%-27s ✓\n" "MinIO Connectivity"
else
    printf "%-27s ✗\n" "MinIO Connectivity"
    exit 1
fi

# Set mc alias inside container
docker exec "${MINIO_CONTAINER_NAME}" mc alias set local http://localhost:9000 "${MINIO_USER}" "${MINIO_PASS}" >/dev/null 2>&1

BUCKETS=("warehouse" "checkpoints" "schemas" "logs")

for bucket in "${BUCKETS[@]}"; do
    if docker exec "${MINIO_CONTAINER_NAME}" mc ls "local/${bucket}" >/dev/null 2>&1; then
        printf "%-27s ✓\n" "${bucket}"
    else
        printf "%-27s ✗\n" "${bucket}"
    fi
done

# Check Flink test object if present
if docker exec "${MINIO_CONTAINER_NAME}" mc ls "local/warehouse/day8-test/connection-test.txt" >/dev/null 2>&1; then
    printf "%-27s ✓\n" "Flink test object"
elif docker exec "${MINIO_CONTAINER_NAME}" mc ls "local/warehouse/day8-test/" >/dev/null 2>&1; then
    printf "%-27s ✓\n" "Flink test object"
else
    printf "%-27s (not found)\n" "Flink test object"
fi
