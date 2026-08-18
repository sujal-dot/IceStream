#!/usr/bin/env bash
# ==============================================================================
# IceStream - Upload Versioned Schemas to MinIO Storage
# ==============================================================================
set -euo pipefail

MINIO_CONTAINER_NAME="${MINIO_CONTAINER_NAME:-icestream-minio}"
MINIO_USER="${MINIO_ROOT_USER:-icestream_minio}"
MINIO_PASS="${MINIO_ROOT_PASSWORD:-icestream_minio_secret}"

docker exec "${MINIO_CONTAINER_NAME}" mc alias set local http://localhost:9000 "${MINIO_USER}" "${MINIO_PASS}" >/dev/null 2>&1

echo "Uploading schemas to MinIO 'schemas' bucket..."

for v in v1.json v2.json v3.json; do
    if [ -f "schema/${v}" ]; then
        docker exec -i "${MINIO_CONTAINER_NAME}" mc put /dev/stdin "local/schemas/${v}" < "schema/${v}" >/dev/null 2>&1
        echo "✓ Uploaded schema/${v} to schemas/${v}"
    fi
done

echo "Schema upload complete."
