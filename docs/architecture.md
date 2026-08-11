# IceStream Architecture Specification

> **Status Notice**: This document describes the **Phase 1 Target Architecture** for IceStream. Day 1 provides architecture documentation, repository structure, and configuration placeholders. Runtime components will be implemented in subsequent phases.

---

## 1. Executive Summary

IceStream is a real-time data lakehouse platform designed with built-in observability, automated anomaly detection, quarantine mechanisms, and self-healing recovery logic. Modern enterprise data platforms suffer from silent data degradation, schema drift, and cascading pipeline failures when bad data enters downstream stores. IceStream introduces continuous stream validation, instant circuit breaking, and structured automated recovery to eliminate silent data corruption.

---

## 2. High-Level System Architecture

The overall system architecture follows an event-driven, stream-first design pattern:

```
+------------------------+
| Python Event Simulator |
+------------------------+
            |
            v
   +----------------+
   |  Apache Kafka  |
   +----------------+
            |
            v
   +----------------+
   |  Apache Flink  |
   +----------------+
            |
            v
+-----------------------+
| Validation & Quality  |
+-----------------------+
      |           |
      | (Valid)   | (Invalid)
      v           v
+-----------+   +------------+
|  Apache   |   | Quarantine |
|  Iceberg  |   +------------+
+-----------+         |
      |               v
      v         +------------+
+-----------+   | PostgreSQL |
|   MinIO   |   +------------+
+-----------+         |
      |               v
      +-------> +------------+
                | Observability
                |   FastAPI  |
                +------------+
                      |
                      v
                +------------+
                |   React &  |
                | React Flow |
                +------------+
```

---

## 3. Core Component Responsibilities

### 3.1 Event Generation Engine (Python)
- **Role**: Simulates high-throughput transactional event streams.
- **Responsibility**: Emits JSON event streams representing e-commerce transactions. Supports dynamic injection of failure modes (e.g., negative amounts, missing keys, malformed schemas) to evaluate platform resilience.

### 3.2 Ingestion Backbone (Apache Kafka)
- **Role**: Real-time event broker and decoupling layer.
- **Responsibility**: Receives events from the generator across partitioned topics (`raw-events`, `valid-events`, `quarantine-events`). Guarantees high durability and replayability for downstream stream processors.

### 3.3 Stream Processing & Quality Engine (Apache Flink)
- **Role**: Stateful real-time stream processing engine.
- **Responsibility**: Consumes raw events from Kafka, performs low-latency field parsing, validates schema adherence, and evaluates data quality rules inline. Computes moving error rate metrics over windowed streams.

### 3.4 Data Lakehouse Layer (Apache Iceberg + MinIO)
- **Role**: Long-term storage format and object store.
- **Responsibility**: Valid records are appended to Apache Iceberg tables backed by MinIO object storage. Provides ACID transaction semantics, schema evolution, and time-travel historical queries.

### 3.5 Metadata, Incident & Audit Store (PostgreSQL)
- **Role**: Relational operational database.
- **Responsibility**: Persists structured metadata regarding quarantined events, incident logs, circuit breaker state transitions, and audit records for operator review.

### 3.6 Metrics & Telemetry (Prometheus & Grafana)
- **Role**: System health metrics monitoring.
- **Responsibility**: Scrapes runtime metrics from Flink, Kafka, and quality validators. Grafana dashboards visualize consumer lag, throughput, error rates, and storage latency.

### 3.7 Automated Alerting (Slack Integration)
- **Role**: Operator notification dispatch.
- **Responsibility**: Sends real-time webhook notifications when error rate thresholds are breached or when the pipeline circuit breaker trips to `OPEN`.

### 3.8 Control Plane & Visualization (FastAPI + React / React Flow)
- **Role**: Observability API and operator dashboard.
- **Responsibility**: FastAPI backend serves telemetry via REST and WebSockets. React UI renders an interactive React Flow DAG visualization of pipeline health, active quarantine volumes, and circuit breaker status.

---

## 4. Operational Infrastructure

All services are designed to be orchestrated locally using Docker and Docker Compose, providing a completely reproducible development and testing environment.
