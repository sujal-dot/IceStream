# MinIO Object Storage & S3 Filesystem Architecture

## Overview
MinIO serves as the S3-compatible object storage layer for **IceStream**. It provides scalable, high-performance object storage for lakehouse data tables, Flink execution state checkpoints, versioned event schemas, and pipeline audit logs.

## Storage Architecture & Bucket Layout

MinIO uses flat S3 buckets rather than nested directory structures:

```text
MinIO Object Storage
│
├── warehouse/           (Lakehouse data tables - Bronze / Silver / Gold)
├── checkpoints/         (Flink streaming state checkpoints & savepoints)
├── schemas/             (Versioned JSON schema definitions v1, v2, v3)
└── logs/                (Pipeline telemetry & audit log artifacts)
```

| Bucket | Purpose | Access Pattern |
| :--- | :--- | :--- |
| `warehouse` | Apache Iceberg data tables and Parquet data files | Read/Write by Flink & Iceberg |
| `checkpoints` | Flink state backend streaming checkpoints and savepoints | Write by Flink TaskManager |
| `schemas` | Versioned event schemas (`v1.json`, `v2.json`, `v3.json`) | Read by Schema Registry & Flink |
| `logs` | Pipeline operational telemetry, failure logs, and audits | Write by pipeline audit workers |

## Docker Endpoint vs. Host Endpoint

Understanding network isolation in local development:

- **Docker Internal Endpoint**: `http://minio:9000`
  Used by containerized services (`flink-jobmanager`, `flink-taskmanager`, `postgres`) running inside the `icestream-network` bridge network.
- **Host Endpoint**: `http://localhost:9000`
  Used by host CLI tools (`mc`), Python pytest scripts, and developer tools.
- **MinIO Console UI**: `http://localhost:9001`
  Web interface for viewing bucket contents and managing storage objects.

## S3 Compatible Credentials & Security Policy

For local development:
- `MINIO_ROOT_USER`: Configured via `.env` (default: `icestream_minio`)
- `MINIO_ROOT_PASSWORD`: Configured via `.env` (default: `icestream_minio_secret`)
- Anonymous write access is strictly disabled.
- Credentials are managed via environment variables and excluded from source control.

## Flink S3 Filesystem Integration

Flink integrates with MinIO using the built-in `flink-s3-fs-hadoop-1.18.1.jar` plugin (`fs.s3a.` / `s3.` scheme).

### Container Configuration (`docker-compose.yml`)
```yaml
environment:
  ENABLE_BUILT_IN_PLUGINS: "flink-s3-fs-hadoop-1.18.1.jar"
  FLINK_PROPERTIES: |
    jobmanager.rpc.address: flink-jobmanager
    s3.endpoint: http://minio:9000
    s3.path.style.access: true
    s3.access-key: icestream_minio
    s3.secret-key: icestream_minio_secret
    s3.ssl.enabled: false
    s3.region: us-east-1
```

## Day 8 Verification & Connectivity Test

Verification consists of:
1. `scripts/minio/init_buckets.sh`: Idempotent script creating `warehouse`, `checkpoints`, `schemas`, and `logs`.
2. `scripts/flink/test_minio.sh`: Executes a batch Flink SQL statement that writes test data to `s3a://warehouse/day8-test/` and verifies read-back.
3. `scripts/minio/verify_storage.sh`: Health check verifying bucket existence and object persistence.
4. `tests/minio/test_minio_storage.py`: Pytest suite for automated CI/CD assertion.

## Future Apache Iceberg Integration Target

In Phase 3 (Day 9+), Apache Iceberg tables will be stored inside the `warehouse` bucket under logical layer prefixes:

```text
s3://warehouse/
├── bronze/         (Raw event ingestion table)
├── silver/         (Validated & enriched event table)
└── gold/           (Aggregated metric analytics table)
```

> [!NOTE]
> **Day 8 Status**: Object storage foundation is active. Apache Iceberg catalog and tables will be introduced in Day 9.

## Troubleshooting

- **Bucket initialization failure**: Ensure MinIO container is running and healthy (`docker compose ps`).
- **Flink S3 Connection Refused**: Verify Flink is using `http://minio:9000` rather than `http://localhost:9000`.
- **Plugin Missing Error**: Verify `ENABLE_BUILT_IN_PLUGINS: "flink-s3-fs-hadoop-1.18.1.jar"` is set in `docker-compose.yml`.
