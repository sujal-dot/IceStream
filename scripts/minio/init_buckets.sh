#!/usr/bin/env bash
# ==============================================================================
# IceStream - MinIO Object Storage Bucket Initialization Script
# ==============================================================================
set -euo pipefail

MINIO_CONTAINER_NAME="${MINIO_CONTAINER_NAME:-icestream-minio}"
MINIO_USER="${MINIO_ROOT_USER:-icestream_minio}"
MINIO_PASS="${MINIO_ROOT_PASSWORD:-icestream_minio_secret}"
MINIO_URL="${MINIO_INTERNAL_URL:-http://localhost:9000}"

BUCKETS=("warehouse" "checkpoints" "schemas" "logs")

echo "Initializing IceStream MinIO storage..."
echo ""

# Ensure MinIO container is reachable and set mc alias
if command -v mc &>/dev/null; then
    mc alias set local "${MINIO_HOST_URL:-http://localhost:9000}" "${MINIO_USER}" "${MINIO_PASS}" --api s3v4 >/dev/null 2>&1 || true
    USE_DOCKER=false
else
    docker exec "${MINIO_CONTAINER_NAME}" mc alias set local "${MINIO_URL}" "${MINIO_USER}" "${MINIO_PASS}" >/dev/null 2>&1
    USE_DOCKER=true
fi

for bucket in "${BUCKETS[@]}"; do
    if [ "${USE_DOCKER}" = true ]; then
        docker exec "${MINIO_CONTAINER_NAME}" mc mb --ignore-existing "local/${bucket}" >/dev/null 2>&1
    else
        mc mb --ignore-existing "local/${bucket}" >/dev/null 2>&1
    fi
    echo "✓ ${bucket}"
done

echo ""
echo "MinIO initialization complete."
