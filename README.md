# IceStream — Real-Time Lakehouse Observability & Self-Healing Data Pipeline

[![Project Status: Phase 1 Architecture](https://img.shields.io/badge/Project_Status-Phase_1:_Architecture_%26_Environment-blue.svg)](#project-status)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 1. Project Description

**IceStream** is a enterprise-grade real-time streaming data platform architecture designed to ingest high-velocity event streams, detect data corruption in real time, isolate malformed records, calculate dynamic error rates, and execute automated self-healing recovery workflows.

By combining stream processing with lakehouse table formats, real-time circuit breakers, and interactive lineage visualization, IceStream eliminates silent data corruption and prevents bad data from polluting downstream analytics stores.

---

## 2. Project Status

> **CURRENT STATUS**: **Phase 5 — Self-Healing Pipeline**

- **Phase 1 — Architecture & Environment**
  - **Day 1 — Architecture** ✓
  - **Day 2 — Docker Infrastructure** ✓
  - **Day 3 — Kafka Architecture** ✓
  - **Day 4 — Event Generator** ✓
  - **Day 5 — Fault Injection Engine** ✓
  - **Day 6 — Schema Versioning** ✓
  - **Day 7 — Kafka Testing + Week 1 Checkpoint** ✓
- **Phase 3 — LAKEHOUSE**
  - **Day 8 — MinIO Object Storage** ✓
  - **Day 9 — Iceberg Catalog** ✓
  - **Day 10 — Bronze Iceberg Table** ✓
  - **Day 11 — Flink → Iceberg Streaming** ✓
  - **Day 12 — Streaming Reliability** ✓
  - **Day 13 — Apache Iceberg ACID Audit** ✓
- **Phase 4 — OBSERVABILITY ENGINE**
  - **Day 14 — Quality Engine Architecture** ✓
  - **Day 15 — Null + Validity Detection Engine** ✓
  - **Day 16 — Duplicate + Anomaly Detection** ✓
  - **Day 17 — Schema Drift Detector** ✓
  - **Day 18 — Great Expectations Integration** ✓
- **Phase 5 — SELF-HEALING PIPELINE**
  - **Day 19 — Error-Rate Engine & /metrics Endpoint** ✓
  - **Day 20 — Circuit Breaker** ✓
  - **Day 21 — Quarantine / Dead Letter Queue** ✓
  - **Day 22 — Automated Remediation / Self-Healing Pipeline** ✓

- **Implemented on Day 1**: Project architecture specifications, repository directory layout, component documentation, failure resilience matrices, recovery workflow specifications, configuration placeholders, and system diagrams.
- **Implemented on Day 2**: Local Docker Compose infrastructure orchestrating Kafka (KRaft), MinIO, PostgreSQL, Flink (JobManager & TaskManager), Prometheus, and Grafana with native container health checks.
- **Implemented on Day 3**: Kafka messaging architecture, 6 core topics (`checkout-events`, `checkout-valid`, `checkout-invalid`, `checkout-dlq`, `pipeline-control`, `schema-events`), partition/retention rules, management scripts (`create_topics.sh`, `verify_topics.sh`), and end-to-end Python producer/consumer verification test suite.
- **Implemented on Day 4**: Python e-commerce checkout event generator (`generator/`), configurable high-throughput producer (1,000+ events/sec target), 8 controlled schema anomaly injection types (`null_amount`, `null_customer_id`, `negative_amount`, `duplicate_event_id`, `invalid_currency`, `missing_required_field`, `wrong_data_type`, `future_timestamp`), CLI interface, rate limiter, stats tracker, unit tests, and Kafka integration tests.
- **Implemented on Day 5**: Controlled Fault Injection Engine (`generator/fault_injection/`), supporting 7 distinct failure modes (`NULL`, `DUPLICATE`, `NEGATIVE`, `INVALID_ENUM`, `SCHEMA_DRIFT`, `TYPE_CHANGE`, `TIMESTAMP_DRIFT`), individual rate CLI flags, fault mode selection, collision handling, runtime statistics tracking, documentation (`docs/fault-injection.md`), and unit/integration tests.
  *Note: IceStream can now intentionally inject realistic data failures into the Kafka event stream for observability and recovery demonstrations.*
- **Implemented on Day 6**: Schema Versioning & Schema Compatibility Engine (`schema/`), versioned JSON schema contracts (`v1.json`, `v2.json`, `v3.json`), schema loader & validation engine (`loader.py`), schema registry abstraction (`registry.py`), compatibility classification engine (`compatibility.py`), CLI comparison utility (`schema/compare.py`), documentation (`schema/README.md`, `docs/schema-evolution.md`), and unit test suite (`tests/schema/`).
  *Note: Evaluates schema evolutions as COMPATIBLE or BREAKING with granular severity and reason breakdowns.*
- **Implemented on Day 7 (Week 1 Checkpoint)**: Kafka streaming observability and dedicated benchmark consumer (`scripts/kafka/performance_consumer.py`), real-time throughput tracking, end-to-end latency measurement (p50, p95, p99), real Kafka consumer lag per partition, Prometheus metrics exporter integration (ports 8000 & 8001), automated Grafana dashboard provisioning (`IceStream — Week 1 Streaming Overview`), automated checkpoint validation runner (`scripts/week1_checkpoint.py`), performance report (`docs/week1-performance-report.md`), and demo documentation (`docs/week1-demo.md`).
- **Implemented on Day 8**: MinIO S3-compatible object storage infrastructure setup, bucket initialization (`warehouse`, `checkpoints`, `schemas`, `logs`), Flink S3 filesystem plugin configuration (`flink-s3-fs-hadoop`), Flink → MinIO end-to-end object write & read-back verification test (`scripts/flink/test_minio.sh`), bucket management & verification scripts (`scripts/minio/init_buckets.sh`, `scripts/minio/verify_storage.sh`, `scripts/minio/upload_schemas.sh`), storage architecture documentation (`docs/minio-storage.md`), and Pytest test suite (`tests/minio/test_minio_storage.py`).
- **Implemented on Day 9**: Apache Iceberg REST Catalog (`tabulario/iceberg-rest`), MinIO-backed lakehouse storage (`s3://warehouse/`), 4 core Iceberg catalog namespaces (`bronze`, `silver`, `quarantine`, `audit`), representative Iceberg table definitions (`bronze.checkout_events`, `silver.valid_checkout_events`, `quarantine.invalid_checkout_events`, `audit.data_quality_results`), Flink Iceberg runtime & AWS bundle JAR integration (`iceberg-flink-runtime-1.18-1.5.2.jar`, `iceberg-aws-bundle-1.5.2.jar`), Flink SQL catalog connectivity, Flink table write & read-back proof, catalog/MinIO restart persistence verification, initialization and verification scripts (`scripts/iceberg/init_catalog.py`, `scripts/iceberg/verify_catalog.py`), documentation (`docs/iceberg-catalog.md`), and Pytest test suite (`tests/iceberg/`).
- **Implemented on Day 10**: Production foundation Bronze Iceberg table (`icestream.bronze.checkout_events`), 14-field production schema contract (`DECIMAL(18,2)`, `TIMESTAMP`, `source_version`, `ingestion_time`), Parquet physical storage format (`write.format.default = parquet`), Iceberg format version 2 (`format-version = 2`), MinIO-backed warehouse storage (`s3://warehouse/bronze/checkout_events`), Flink SQL insert & read-back verification, raw event preservation with nullable fields for fault injection capture, reproducibile creation script (`scripts/iceberg/create_bronze_table.py`), inspection & verification script (`scripts/iceberg/verify_bronze_table.py`), Day 10 checkpoint script (`scripts/day10_checkpoint.sh`), technical documentation (`docs/bronze-table.md`), and Pytest integration suite (`tests/iceberg/test_bronze_table.py`).
- **Implemented on Day 11**: Real-time Kafka → Flink → Iceberg Bronze streaming pipeline, Flink JSON deserialization, field mapping, event timestamp & watermark strategy, ingestion timestamp generation, checkpointing to MinIO (`s3://checkpoints/flink/bronze/`), Flink SQL streaming DDL/DML definition (`flink/jobs/kafka_to_iceberg.sql`), deployment automation (`scripts/flink/run_bronze_pipeline.sh`), continuous count monitor (`scripts/iceberg/watch_bronze_count.py`), master Day 11 checkpoint runner (`scripts/day11_checkpoint.sh`), documentation (`docs/kafka-flink-iceberg.md`), and streaming integration tests (`tests/streaming/test_kafka_to_iceberg.py`).
- **Implemented on Day 12**: Streaming reliability infrastructure, Flink `EXACTLY_ONCE` checkpointing (30s interval, `s3://checkpoints/flink/bronze/`), fixed-delay task restart strategy (3 attempts, 10s delay), Kafka consumer offset state recovery (`icestream-flink-bronze`), automated TaskManager failure and recovery test script (`scripts/day12_recovery_test.sh`), technical documentation (`docs/flink-reliability.md`), Grafana Flink Reliability panel monitoring, and Pytest reliability test suite (`tests/streaming/test_reliability.py`).
- **Implemented on Day 13**: Apache Iceberg ACID Concurrency & Durability Audit (`scripts/day13_acid_audit.py`, `tests/acid/`), empirical validation of Atomicity (500/500 records all-or-nothing), Consistency (schema & manifest fidelity), Snapshot Isolation (Reader C continuous query without locks or failures), and Optimistic Concurrency Control (Writer A & B concurrent append with collision backoff/retry), catalog restart durability proof, technical documentation (`docs/acid-audit.md`), execution results report (`docs/reports/day13-acid-results.md`), and Pytest concurrency suite (`tests/acid/test_acid_audit.py`).
- **Implemented on Day 14**: Quality Engine Architecture & Rule Interface (`quality-engine/`), standardized event model (`QualityEvent`), `QualityRule` abstract contract (`validate(event)`), uniform `ValidationResult` and `ValidationSummary` models, controlled severity (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `INFO`) and status enums (`HEALTHY`, `WARNING`, `FAILED`), dynamic `RuleRegistry` with `@register_rule` decorator, `QualityEngine` rule orchestrator with complete failure isolation and exception handling, declarative YAML configuration loader (`rules.yaml`), demonstration rule (`EventIdNotNullRule`), `MetricsCollector` abstraction, CLI runner (`quality-engine/main.py`), documentation (`docs/quality-engine.md`, `quality-engine/README.md`), and 35 unit tests (`quality-engine/tests/`).
- **Implemented on Day 15**: Real Data-Quality Rules & Null + Validity Detection Engine (`quality-engine/rules/`), reusable `NotNullRule`, `AmountPositiveRule`, `AllowedValuesRule` (`CurrencyValidRule`, `PaymentStatusValidRule`), `TimestampValidRule`, expanded YAML configuration (`rules.yaml`), generic rule type loader (`config/loader.py`), rule pass/fail result serialization, metrics tracking with low-cardinality rule labels, unit test suite (`quality-engine/tests/test_validity_rules.py`), engine integration suite (`quality-engine/tests/test_quality_engine_day15.py`), and quality rules documentation (`docs/quality-rules.md`).
- **Implemented on Day 16**: Duplicate & Anomaly Detection + Rolling-Window Metrics (`quality-engine/detectors/`, `quality-engine/metrics/`), duplicate event (`DuplicateEventRule`) and duplicate order (`DuplicateOrderRule`) detection with bounded state and window expiration, impossible amount limit (`ImpossibleAmountRule`), future timestamp tolerance (`FutureTimestampRule`), late event lateness detection (`LateEventRule`), deterministic time handling with injectable `Clock` (`SystemClock`, `FixedClock`), 1-minute and 5-minute rolling window metrics aggregation (`WindowAggregator`), structured `WindowMetrics` model, event-level error rate calculation (`invalid_events / total_events`), 10,000-event performance benchmark (`test_performance.py`), technical documentation (`docs/anomaly-detection.md`), and 79 unit tests (`quality-engine/tests/`).
- **Implemented on Day 17**: Production-quality Schema Drift Detector (`quality-engine/detectors/schema_drift.py`), dynamic schema comparison engine (`schema/compatibility.py`, `SchemaComparator`), ChangeType classification (`MISSING_COLUMN`, `NEW_COLUMN`, `TYPE_CHANGE`, `RENAMED_COLUMN`, `REMOVED_COLUMN`), severity model (`INFO`, `WARNING`, `CRITICAL`), compatibility classification (`COMPATIBLE`, `WARNING`, `BREAKING`), explicit schema rename mapping, unknown version detection (`SCHEMA_VERSION_UNKNOWN`), zero-I/O in-memory schema definition caching, low-cardinality schema drift metrics tracking, quality engine integration (`QualityEngine`), performance benchmark (`benchmarks/bench_schema_drift.py`), technical documentation (`docs/schema-drift.md`), and 152 Pytest unit/integration tests (`tests/quality-engine/test_schema_drift.py`).
- **Implemented on Day 18**: Hybrid Quality Engine Architecture (`quality-engine/ge_adapter/`, `quality-engine/hybrid_engine.py`), Great Expectations (GE v0.18.19) adapter integration, declarative expectation configuration (`config/expectations.yaml`), Expectation Registry (`GEExpectationRegistry`), raw GE result normalization to standardized `ValidationResult` schema (`GEResultMapper`), `QualityBatchResult` summary model, `HybridQualityEngine` orchestrator combining Great Expectations (batch/micro-batch declarative checks) with Custom Rules Engine (event-by-event streaming checks), deduplicated event invalidity tracking, formatted `IceStream Quality Summary` report generator, low-cardinality GE Prometheus metrics collector integration (`ge_validation_runs`, `ge_expectations_total`, `ge_expectations_passed`, `ge_expectations_failed`), 10,000-event performance benchmark, technical documentation (`docs/great-expectations-integration.md`), and 132 Pytest unit/integration tests.
- **Implemented on Day 19**: Error-Rate Engine (`quality-engine/metrics/error_rate.py`) calculating `error_rate = failed_events / total_events`, 1-minute and 5-minute rolling windows, health classification thresholds (`< 1% HEALTHY`, `1–2% WARNING`, `> 2% CRITICAL`), configurable threshold validation, event-level failure aggregation (multiple failed rules per event = 1 failed event), zero-traffic `data_available` status, FastAPI observability backend service (`backend/app.py`) exposing `GET /metrics` and `GET /health` REST endpoints, technical documentation (`docs/error-rate-engine.md`), unit test suite (`tests/test_error_rate_engine.py`), API test suite (`tests/test_metrics_api.py`), integration test suite (`tests/test_day19_error_rate_integration.py`), and performance benchmark (`benchmarks/bench_error_rate_engine.py`). *Note: Signaling layer only; circuit breaker and automated recovery actions are strictly reserved for subsequent days.*
- **Implemented on Day 20**: Authoritative Circuit Breaker state machine (`quality-engine/circuit_breaker/`), 3 primary states (`CLOSED`, `OPEN`, `HALF_OPEN`), strict state transition validation, configurable 2% critical threshold (`quality-engine/config/circuit_breaker.yaml`), recovery timeout (default 60s), controlled single-probe recovery mechanism (`begin_recovery_probe()`), thread-safe transition execution (`threading.Lock`), injectable deterministic clock (`Clock`, `SystemClock`, `FixedClock`), bounded transition history (`max_history`), low-cardinality monitoring metrics (`circuit_breaker_state`, recovery counters), read-only REST status API (`GET /circuit-breaker`), updated `/metrics` response integration, technical documentation (`docs/circuit-breaker.md`), and comprehensive Pytest test suite (`tests/test_circuit_breaker.py`). *Note: The circuit breaker currently makes recovery decisions but does not yet execute external recovery actions.*
- **Implemented on Day 21**: Durable Apache Iceberg Quarantine / Dead Letter Queue (`quarantine.invalid_checkout_events`), Parquet file format on MinIO storage via Iceberg REST Catalog (`http://localhost:8181`), complete raw payload preservation (`event`), deterministic error code mapping (`NULL_AMOUNT`, `INVALID_AMOUNT`, `INVALID_CURRENCY`, `INVALID_PAYMENT_STATUS`, `INVALID_TIMESTAMP`, `DUPLICATE_EVENT`, `DUPLICATE_ORDER`, `IMPOSSIBLE_AMOUNT`, `FUTURE_TIMESTAMP`, `LATE_EVENT`, `SCHEMA_DRIFT`), severity-based primary error selection (`CRITICAL` > `HIGH` > `MEDIUM` > `LOW`), deterministic failed-rule ordering, valid event protection in `QuarantineRouter` (refuses valid events), `QuarantineWriter` atomic batch appends, deterministic quarantine record deduplication (`quarantine_id = q_<hash>`), low-cardinality Prometheus quarantine metrics (`quarantine_events_total`, `quarantine_write_success_total`, `quarantine_write_failure_total`, `quarantine_events_by_error_code`), zero-false-success failure handling, repeatable table setup script (`scripts/create_quarantine_table.py`), 1,000-event performance benchmark (`benchmarks/benchmark_quarantine.py`), technical architecture documentation (`docs/quarantine.md`), and Pytest test suite (`quality-engine/tests/test_quarantine.py`).
- **Implemented on Day 22**: Real Automated Remediation & Self-Healing Pipeline (`quality-engine/remediation/`, `backend/storage/`), stateful `PipelineStateManager` enforcing 11 state transitions (`RUNNING`, `DEGRADED`, `QUARANTINING`, `CIRCUIT_OPEN`, `REMEDIATING`, `REFETCHING`, `REPROCESSING`, `VALIDATING`, `RESUMING`, `RECOVERY_FAILED`, `RECOVERED`), PostgreSQL persistence with SQLite fallback (`pipeline_state`, `pipeline_state_history`, `pipeline_incidents`, `remediation_attempts`), `LocalSourceAdapter` for deterministic source re-fetching with audit provenance tracking, `Reprocessor` executing real `QualityEngine` re-validation and quarantining invalid re-fetched events, `AlertService` with `SlackAlertAdapter` webhooks, `RemediationController` orchestrating quarantine verification, alert dispatch, re-fetch, reprocess, validation, circuit breaker `HALF_OPEN` -> `CLOSED` recovery, max attempts enforcement (3 limit), exponential backoff, and concurrency/idempotency locking, updated REST API endpoints (`GET /pipeline/status`, `GET /incidents/{incident_id}`, `POST /pipeline/remediate`), Prometheus remediation metrics exporter, comprehensive technical documentation (`docs/automated-remediation.md`), and 21 integration tests (`tests/test_day22_self_healing.py`).

---

## Week 1 Achievement

IceStream can generate high-volume realistic e-commerce checkout events, publish them to Kafka, measure streaming performance, end-to-end latency, and consumer lag, display real-time metrics in Grafana, and intentionally inject controlled data failures into the event stream.

---

*Note: Downstream processing component references in this document reflect planned architecture targets.*


---

## Current Infrastructure

The local containerized development environment is fully operational and verified via Docker Compose:

| Infrastructure Service | Container Name | Version / Image | Exposed Port | Health Status |
| :--- | :--- | :--- | :--- | :---: |
| **Apache Kafka** | `icestream-kafka` | `apache/kafka:3.7.0` (KRaft Mode) | `localhost:9092` | `healthy` ✓ |
| **MinIO** | `icestream-minio` | `minio/minio:RELEASE.2024-03-21` | `localhost:9000` / `9001` | `healthy` ✓ |
| **Iceberg REST Catalog** | `icestream-iceberg-rest` | `tabulario/iceberg-rest:0.1.0` | `localhost:8181` | `healthy` ✓ |
| **PostgreSQL** | `icestream-postgres` | `postgres:16-alpine` | `localhost:5432` | `healthy` ✓ |
| **Flink JobManager** | `icestream-flink-jobmanager` | `flink:1.18.1-scala_2.12-java11` | `localhost:8081` | `healthy` ✓ |
| **Flink TaskManager** | `icestream-flink-taskmanager` | `flink:1.18.1-scala_2.12-java11` | Internal (`icestream-network`) | `healthy` ✓ |
| **Prometheus** | `icestream-prometheus` | `prom/prometheus:v2.51.0` | `localhost:9090` | `healthy` ✓ |
| **Grafana** | `icestream-grafana` | `grafana/grafana:10.4.1` | `localhost:3000` | `healthy` ✓ |

All infrastructure specifications and operations procedures are documented in [`docs/infrastructure.md`](docs/infrastructure.md).

---

## 3. Problem Statement

Modern data platforms ingest millions of continuous events per second across distributed pipelines. However, production streaming pipelines frequently suffer from critical operational defects:

- **Schema Drift**: Unannounced upstream payload changes breaking downstream parsers.
- **Null & Missing Values**: Required identifier or timestamp keys omitted from event bodies.
- **Invalid Field Values**: Negative currency amounts, out-of-bound values, or corrupted types.
- **Duplicate Records**: Network retries causing repeated event ingestion.
- **Malformed Events**: Invalid JSON payloads or corrupted string encodings.
- **Silent Data Degradation**: Bad data passing silently into production analytical tables.
- **Sudden Error-Rate Spikes**: Unnoticed source system bugs corrupting large volumes of data.
- **Cascading Failures**: Errors propagating to downstream BI dashboards and ML models.
- **Delayed Incident Detection**: Outages identified hours or days after occurrence.
- **Lack of Data Lineage**: Inability to trace corrupted datasets back to source origins.
- **Lack of Automated Recovery**: Manual database queries required to isolate and reprocess bad data.

### Why Traditional Solutions Fail
Traditional data pipelines typically choose between two bad outcomes:
1. **Crash & Fail**: Pipeline halts completely on any malformed record, creating massive consumer lag and blocking valid business data.
2. **Ignorant Ingestion**: Pipeline ignores errors and writes corrupted events directly to storage, polluting business reports and corrupting data lakehouses.

### The IceStream Solution
IceStream unifies **Real-Time Validation + Observability + Quarantine + Incident Detection + Circuit Breaking + Automated Recovery**. Invalid events are isolated into a quarantine catalog instantly while valid records continue flowing into Apache Iceberg tables without interruption.

---

## 4. Project Objectives

1. Build a real-time event streaming architecture.
2. Process events using Apache Kafka and Apache Flink.
3. Store data in an Apache Iceberg lakehouse.
4. Detect data-quality problems.
5. Detect schema drift.
6. Quarantine invalid records.
7. Calculate real-time error rates.
8. Implement a circuit breaker.
9. Generate incidents and alerts.
10. Provide data lineage visualization.
11. Provide engineering metrics.
12. Demonstrate Iceberg time travel.
13. Demonstrate automated recovery.
14. Provide reproducible local deployment using Docker.

---

## 5. High-Level Architecture Target

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
                             /           \
                     (Valid)/             \(Invalid)
                           v               v
                +-------------------+   +--------------------+
                |  Apache Iceberg   |   | Quarantine Catalog |
                | (MinIO S3 Storage)|   |    (PostgreSQL)    |
                +-------------------+   +--------------------+
                          |                       |
                          v                       v
                +-------------------+   +--------------------+
                | Observability API |   |  Circuit Breaker   |
                |     (FastAPI)     |   |   (Self-Healing)   |
                +-------------------+   +--------------------+
                          |                       |
                          v                       v
                +-------------------+   +--------------------+
                |  React Lineage UI |   |  Prometheus /      |
                |   (React Flow)    |   |  Grafana / Slack   |
                +-------------------+   +--------------------+
```

Detailed technical specifications are documented in [`docs/architecture.md`](docs/architecture.md).

---

## 6. Technology Stack (Planned)

The planned technology stack and intended responsibilities are detailed below:

| Technology | Intended Responsibility | Implementation Status |
| :--- | :--- | :--- |
| **Python** | Event simulation engine, failure triggers, utility automation scripts | Planned (Day 2+) |
| **Apache Kafka** | Real-time event broker for raw, valid, and quarantine streams | Planned (Day 2+) |
| **Apache Flink** | Stateful stream processing, windowed error rate calculation, parsing | Planned (Day 3+) |
| **Apache Iceberg** | Open table format for ACID lakehouse storage & time travel queries | Planned (Day 3+) |
| **MinIO** | S3-compatible object storage for Apache Iceberg Parquet data | Planned (Day 2+) |
| **PostgreSQL** | Relational metadata store for incidents, quarantine logs, & audit trails | Planned (Day 2+) |
| **FastAPI** | Telemetry REST API & WebSocket server for real-time observability | Planned (Day 5+) |
| **React** | Web dashboard framework for platform monitoring | Planned (Day 5+) |
| **TypeScript** | Type-safe frontend application code | Planned (Day 5+) |
| **React Flow** | Interactive data lineage DAG visualization | Planned (Day 5+) |
| **Prometheus** | Metric collection for consumer lag, throughput, and error rates | Planned (Day 4+) |
| **Grafana** | Visual telemetry dashboards and operational graphs | Planned (Day 4+) |
| **Slack** | Automated incident alert notification webhooks | Planned (Day 4+) |
| **Docker / Compose** | Containerized reproducible local development environment | Architecture Placeholder (Day 1) |
| **Pytest** | Testing framework for quality rules and end-to-end failure injection | Planned (Day 6+) |
| **GitHub Actions** | CI/CD pipeline automation for testing and validation | Planned (Day 6+) |

---

## 7. Data Flow (15-Stage Lifecycle Target)

1. **Event Generated**: Python simulator constructs transaction JSON payload.
2. **Event Published**: Payload sent to Kafka `raw-events` topic.
3. **Flink Consumes**: Apache Flink reads stream record with offset tracking.
4. **Event Parsed**: Bytes deserialized and validated structurally.
5. **Schema Validated**: Field presence, data types, and versions checked.
6. **Data-Quality Rules Evaluated**: Domain constraints checked (e.g., amount > 0).
7. **Anomaly Detection**: Statistical volume and value range checks executed.
8. **Valid Records Continue**: Clean events forwarded to Apache Iceberg sink.
9. **Invalid Records Quarantined**: Failed events diverted to quarantine storage with error context.
10. **Error Rate Calculated**: Flink window aggregators compute moving failure percentage.
11. **Circuit Breaker Evaluates**: Pipeline health checked against error rate threshold.
12. **Incidents Generated**: Incident log created in PostgreSQL if threshold breached.
13. **Alerts Sent**: Notifications dispatched to Slack and Grafana.
14. **Recovery Attempted**: Circuit breaker moves to `HALF_OPEN`; source fix & quarantine replay tested.
15. **Pipeline Resumes**: Ingestion returns to `CLOSED` normal operation after successful validation.

Detailed lifecycle documentation is available in [`docs/data-flow.md`](docs/data-flow.md).

---

## 8. Failure Scenarios & Resilience

IceStream is designed to handle 15 distinct failure scenarios including:
- Null values in required fields
- Negative transaction amounts
- Duplicate event identifiers
- Missing mandatory keys & unexpected extra fields
- Invalid data types and currency codes
- Future and stale event timestamps
- Schema version mismatches & sudden error-rate spikes
- Broker, TaskManager, or object storage connectivity drops

Full failure scenario specifications are available in [`docs/failure-scenarios.md`](docs/failure-scenarios.md).

---

## 9. Recovery Strategy & Circuit Breaker

The self-healing architecture employs a 3-state Circuit Breaker:

```
[ CLOSED ] --(Error Rate > 5%)--> [ OPEN ] --(Cooldown / Reset)--> [ HALF_OPEN ] --(Validation Pass)--> [ CLOSED ]
```

- **CLOSED**: Normal processing state.
- **OPEN**: Error threshold exceeded; ingestion isolated, incident logged, alerts dispatched.
- **HALF_OPEN**: Controlled sample stream re-tested; successful validation resets breaker to `CLOSED`.

Full recovery strategy specifications are available in [`docs/recovery-strategy.md`](docs/recovery-strategy.md).

---

## 10. Repository Structure

```
icestream/
│
├── README.md                 # Main project overview & architecture specification
├── LICENSE                   # MIT License (2026 IceStream Contributors)
├── .gitignore                # Comprehensive environment & artifact ignore rules
├── .env.example              # Configuration variable placeholders (No credentials)
├── docker-compose.yml        # Architecture placeholder Docker Compose spec
│
├── generator/                # [Planned Phase 2] Python event simulation engine
│   └── README.md             # Component specification & inputs/outputs
│
├── kafka/                    # [Planned Phase 2] Kafka topic & schema registry specs
│   └── README.md             # Component specification & inputs/outputs
│
├── flink/                    # [Planned Phase 3] Flink streaming jobs & windowing logic
│   └── README.md             # Component specification & inputs/outputs
│
├── iceberg/                  # [Planned Phase 3] Iceberg catalog & schema evolution
│   └── README.md             # Component specification & inputs/outputs
│
├── quality-engine/           # [Planned Phase 4] Quality rules & circuit breaker state
│   └── README.md             # Component specification & inputs/outputs
│
├── backend/                  # [Planned Phase 5] FastAPI REST & WebSockets server
│   └── README.md             # Component specification & inputs/outputs
│
├── frontend/                 # [Planned Phase 5] React + React Flow dashboard UI
│   └── README.md             # Component specification & inputs/outputs
│
├── monitoring/               # [Planned Phase 4] Prometheus metrics & Grafana dashboards
│   └── README.md             # Component specification & inputs/outputs
│
├── tests/                    # [Planned Phase 6] Pytest suite & failure injection tests
│   └── README.md             # Component specification & inputs/outputs
│
├── docs/                     # Comprehensive project documentation
│   ├── architecture.md       # Target architecture & component breakdown
│   ├── data-flow.md          # 15-stage data lifecycle specification
│   ├── failure-scenarios.md  # 15 failure scenarios & resilience matrix
│   ├── recovery-strategy.md  # Circuit breaker state machine & self-healing logic
│   └── diagrams/             # Visual Mermaid diagram sources
│       ├── architecture.mmd  # Architecture Mermaid diagram source
│       └── data-flow.mmd     # Data flow sequence Mermaid diagram source
│
└── scripts/                  # [Planned Phase 2-6] Automation & setup scripts
    └── README.md             # Component specification & inputs/outputs
```

---

## 11. Planned Observability Capabilities

- **Real-Time Error Telemetry**: Dynamic error rate calculation over sliding time windows.
- **Interactive Lineage DAG**: React Flow UI rendering pipeline nodes, consumer lag, and state.
- **Quarantine Inspection**: Catalog UI to inspect failed payloads and failure root causes.
- **Incident Audit Trail**: Immutable PostgreSQL incident logs tracking duration and resolution.
- **Grafana & Slack Alerting**: Automated metrics graphing and instant Slack webhook alerts.

---

## 12. Planned Testing Strategy

- **Unit Testing**: Pytest suite validating quality rules and schema enforcement.
- **Integration Testing**: Kafka-Flink-Iceberg local container test pipeline.
- **Failure Injection**: Automated scripts simulating bad events, broker stops, and rate spikes.
- **Self-Healing Verification**: End-to-end test verifying automatic circuit breaker trip and recovery.

---

## 13. Development Roadmap & Implementation Phases

- [x] **Phase 1 — Architecture & Environment**:
  - [x] Day 1: Architecture specification, repository design, docs, diagrams, and placeholders.
  - [x] Day 2: Local Docker infrastructure (Kafka KRaft, MinIO, PostgreSQL, Flink, Prometheus, Grafana).
  - [x] Day 3: Kafka architecture, 6 topics, partition/retention rules, management scripts, and end-to-end Python verification tests.
- [ ] **Phase 2 — Streaming Backbone & Ingestion**: Event generator, MinIO bucket setup, PostgreSQL metadata schema.
- [ ] **Phase 3 — Stream Processing & Lakehouse Storage**: Flink validation job, Iceberg catalog tables, time travel.
- [ ] **Phase 4 — Quality Engine & Observability**: Error rate windowing, circuit breaker state machine, Prometheus/Grafana monitoring, Slack alerts.
- [ ] **Phase 5 — Control Plane & UI**: FastAPI telemetry backend, React + React Flow lineage visualizer.
- [ ] **Phase 6 — Testing & Automation**: End-to-end failure injection, automated self-healing verification, documentation polish.

---

## 14. How to Clone the Repository

```bash
# Clone the repository
git clone https://github.com/your-username/icestream.git

# Navigate to the project root
cd icestream
```

---

## 15. Initial Setup Instructions (Phase 1)

1. **Verify Environment Variables**:
   Copy `.env.example` to `.env` to view planned configuration variables:
   ```bash
   cp .env.example .env
   ```

2. **Inspect Documentation**:
   Review architecture documents and diagrams:
   - Architecture: [`docs/architecture.md`](docs/architecture.md)
   - Data Lifecycle: [`docs/data-flow.md`](docs/data-flow.md)
   - Failure Scenarios: [`docs/failure-scenarios.md`](docs/failure-scenarios.md)
   - Recovery Strategy: [`docs/recovery-strategy.md`](docs/recovery-strategy.md)

---

## 16. License

This project is released under the [MIT License](LICENSE).
Copyright (c) 2026 IceStream Contributors.
