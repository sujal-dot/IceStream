# IceStream Local Docker Infrastructure Specification

> **Status Notice**: This document describes the **Day 2 Local Docker Infrastructure** for IceStream. All core infrastructure services (Kafka, MinIO, PostgreSQL, Flink JobManager/TaskManager, Prometheus, Grafana) are configured, orchestrated, health-checked, and verified via Docker Compose.

---

## 1. Prerequisites

Before starting the IceStream local infrastructure, ensure your local system meets the following requirements:
- **Docker Engine**: Version 24.0+ (Tested on v29.6.1)
- **Docker Compose**: Version 2.20+ (Tested on v5.3.0)
- **Resources**: Minimum 4 CPU cores and 4 GB allocated RAM to Docker Desktop.

---

## 2. Docker Compose Architecture

The local infrastructure operates within an isolated container network (`icestream-network`) with health-based startup order dependencies:

```
                      +-------------------+
                      | icestream-network |
                      +---------+---------+
                                |
      +-------------------------+-------------------------+
      |                         |                         |
+-----+-----+             +-----+-----+             +-----+-----+
|   Kafka   |             |   MinIO   |             | PostgreSQL|
|  (KRaft)  |             |  (S3 API) |             | (Metadata)|
+-----------+             +-----------+             +-----------+
      |                         |                         |
      +-------------------------+-------------------------+
                                |
      +-------------------------+-------------------------+
      |                                                   |
+-----+-----+                                       +-----+-----+
|Prometheus | <-------- health dependency --------- |  Grafana  |
+-----------+                                       +-----------+
      |
+-----+-----+
|   Flink   |
| JobManager|
+-----+-----+
      ^
      | health dependency
+-----+-----+
|   Flink   |
|TaskManager|
+-----------+
```

---

## 3. Infrastructure Services Summary

| Service Name | Container Name | Image | Purpose | Port Mapping | Health Check Command |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `kafka` | `icestream-kafka` | `apache/kafka:3.7.0` | Event broker (KRaft mode) | `9092:9092` | `/opt/kafka/bin/kafka-broker-api-versions.sh --bootstrap-server localhost:9092` |
| `minio` | `icestream-minio` | `minio/minio:RELEASE.2024-03-21T23-13-43Z` | S3-compatible object storage | `9000:9000`, `9001:9001` | `mc ready local \|\| curl -f http://localhost:9000/minio/health/live` |
| `postgres` | `icestream-postgres` | `postgres:16-alpine` | Metadata & incident database | `5432:5432` | `pg_isready -U icestream_user -d icestream_db` |
| `flink-jobmanager` | `icestream-flink-jobmanager` | `flink:1.18.1-scala_2.12-java11` | Stream job coordinator | `8081:8081` | `curl -f http://localhost:8081/v1/overview` |
| `flink-taskmanager` | `icestream-flink-taskmanager` | `flink:1.18.1-scala_2.12-java11` | Stream execution worker | N/A (Internal) | `curl -s http://flink-jobmanager:8081/v1/taskmanagers \| grep -q 'taskmanagers'` |
| `prometheus` | `icestream-prometheus` | `prom/prometheus:v2.51.0` | Metrics telemetry collector | `9090:9090` | `wget -q --spider http://localhost:9090/-/healthy` |
| `grafana` | `icestream-grafana` | `grafana/grafana:10.4.1` | Telemetry visual dashboard | `3000:3000` | `curl -f http://localhost:3000/api/health` |

---

## 4. Exposed Localhost Ports

| Port | Service | Description | Access URL |
| :--- | :--- | :--- | :--- |
| `9092` | Kafka | Localhost KRaft Kafka broker endpoint | `localhost:9092` |
| `9000` | MinIO | MinIO S3 API Endpoint | `http://localhost:9000` |
| `9001` | MinIO | MinIO Console Web UI | `http://localhost:9001` |
| `5432` | PostgreSQL | Operational database connection | `localhost:5432` |
| `8081` | Flink | Flink Dashboard Web UI | `http://localhost:8081` |
| `9090` | Prometheus | Prometheus Metrics Web UI | `http://localhost:9090` |
| `3000` | Grafana | Grafana Telemetry Web UI | `http://localhost:3000` |

---

## 5. Docker Volumes

State persistence is maintained using named Docker volumes:
- `icestream_kafka_data`: Persists Kafka topic logs and offsets.
- `icestream_minio_data`: Persists S3 objects and data buckets.
- `icestream_postgres_data`: Persists PostgreSQL relational database tables.
- `icestream_prometheus_data`: Persists time-series metrics data.
- `icestream_grafana_data`: Persists Grafana dashboards and user settings.

---

## 6. Docker Networks

All containers attach to a dedicated bridge network:
- **Network Name**: `icestream-network`
- **Inter-container Communication**: Containers reference each other via Docker service names (`kafka:29092`, `postgres:5432`, `flink-jobmanager:8081`, `prometheus:9090`).

---

## 7. Environment Variables

Configuration parameters are managed via `.env` (copied from `.env.example`). Key infrastructure parameters include:
- `KAFKA_BROKER_ID`: `1`
- `KAFKA_CLUSTER_ID`: `4L6g3nShT-eMCtK--X86sw`
- `MINIO_ROOT_USER`: `icestream_minio`
- `MINIO_ROOT_PASSWORD`: `icestream_minio_secret`
- `POSTGRES_DB`: `icestream_db`
- `POSTGRES_USER`: `icestream_user`
- `POSTGRES_PASSWORD`: `icestream_password`
- `GRAFANA_ADMIN_USER`: `admin`
- `GRAFANA_ADMIN_PASSWORD`: `admin`

---

## 8. Service Health Checks

Every service defines explicit health verification:
- **Kafka**: Invokes `/opt/kafka/bin/kafka-broker-api-versions.sh` against broker endpoint.
- **MinIO**: Queries `/minio/health/live` HTTP status.
- **PostgreSQL**: Runs `pg_isready` utility for database responsiveness.
- **Flink JobManager**: Queries HTTP REST API `/v1/overview`.
- **Flink TaskManager**: Verifies TaskManager slot registration via JobManager REST API.
- **Prometheus**: Checks HTTP `/ - /healthy` endpoint.
- **Grafana**: Queries HTTP `/api/health` status endpoint.

---

## 9. Operations Guide

### How to Start the Infrastructure
```bash
docker compose up -d
```

### How to Check Service Status
```bash
docker compose ps
```

### How to Inspect Container Logs
```bash
# View logs for all services
docker compose logs -f

# View logs for a specific service
docker compose logs -f kafka
docker compose logs -f postgres
docker compose logs -f flink-jobmanager
docker compose logs -f minio
```

### How to Stop the Infrastructure (Preserving Data Volumes)
```bash
docker compose down
```

### How to Restart the Infrastructure
```bash
docker compose down && docker compose up -d
```

### How to Completely Remove the Environment (Including Data Volumes)
> **WARNING**: The `-v` flag deletes all persistent Docker volumes (`icestream_*_data`), erasing all local stored data.

```bash
docker compose down -v
```
