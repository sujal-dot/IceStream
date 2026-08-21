# Real-Time Kafka → Flink → Iceberg Bronze Pipeline Documentation

**Date:** August 21, 2026  
**Phase:** Phase 3 — Lakehouse (Day 11)

---

## 1. End-to-End Architecture

```text
                    ┌─────────────────────┐
                    │ Python Event        │
                    │ Generator           │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │       Kafka         │
                    │  checkout-events    │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │       Flink         │
                    │                     │
                    │ Kafka Source        │
                    │ JSON Parsing        │
                    │ Basic Mapping       │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Apache Iceberg      │
                    │ bronze.checkout_    │
                    │ events              │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │       MinIO         │
                    │ Parquet + Metadata  │
                    └─────────────────────┘
```

The Day 11 real-time streaming pipeline continuously ingests JSON events published to Kafka, deserializes and maps them in Apache Flink, and commits Parquet data files and Iceberg snapshot metadata to MinIO object storage.

---

## 2. Kafka Source & Consumer Group

- **Topic Name:** `checkout-events`
- **Partitions:** 3
- **Bootstrap Servers:** `kafka:29092` (internal Docker listener), `localhost:9092` (host listener)
- **Consumer Group:** `icestream-flink-bronze`
- **Starting Offset:** `latest-offset` (configurable to `earliest-offset`)

---

## 3. Flink Stream Processing & Deserialization Strategy

- **Job Manager:** `icestream-flink-jobmanager:8081`
- **Task Manager:** `icestream-flink-taskmanager`
- **Deserializer Format:** JSON (`json.fail-on-missing-field = false`, `json.ignore-parse-errors = true`)
- **Watermark Strategy:** Bounded out-of-orderness delay of 5 seconds (`WATERMARK FOR event_time_ts AS event_time_ts - INTERVAL '5' SECOND`).
- **Timestamp Handling:**
  - `event_time`: Extracted from ISO 8601 string in payload (`yyyy-MM-dd'T'HH:mm:ss`).
  - `ingestion_time`: Populated at ingestion time by Flink using `LOCALTIMESTAMP`.

---

## 4. Iceberg Catalog & Sink Mapping

- **Catalog:** Apache Iceberg REST Catalog (`http://iceberg-rest:8181`)
- **Namespace:** `bronze`
- **Target Table:** `icestream.bronze.checkout_events`
- **Storage Format:** PARQUET (Format version 2)
- **MinIO Location:** `s3://warehouse/bronze/checkout_events/`

### Bronze Table Schema
| Field Name | Type | Description |
|---|---|---|
| `event_id` | STRING | Unique event identifier |
| `event_time` | TIMESTAMP | Event occurrence timestamp (UTC) |
| `customer_id` | STRING | Customer ID |
| `session_id` | STRING | User session ID |
| `order_id` | STRING | Order ID |
| `product_id` | STRING | Product ID |
| `amount` | DECIMAL(18,2) | Transaction amount |
| `currency` | STRING | Currency code (INR) |
| `payment_method` | STRING | Payment mechanism (UPI, CREDIT_CARD, etc.) |
| `payment_status` | STRING | Status (SUCCESS, FAILED, PENDING) |
| `device` | STRING | Client device (mobile, desktop, tablet) |
| `country` | STRING | Country code |
| `source_version` | STRING | Schema version string |
| `ingestion_time` | TIMESTAMP | Actual Flink ingestion processing timestamp |

---

## 5. Checkpointing & Exactly-Once Semantics

- **Checkpoint Interval:** 30 seconds (`FLINK_CHECKPOINT_INTERVAL_MS=30000`)
- **Checkpoint Mode:** `EXACTLY_ONCE`
- **Checkpoint Storage:** MinIO `s3://checkpoints/flink/bronze/`
- **Timeout:** 60 seconds

Iceberg streaming commits occur synchronously on Flink checkpoint completion.

---

## 6. Continuous Count Verification & Operations

Run the pipeline deployment script:
```bash
./scripts/flink/run_bronze_pipeline.sh
```

Monitor streaming record count growth:
```bash
PYTHONPATH=. .venv/bin/python scripts/iceberg/watch_bronze_count.py --interval 5 --duration 30
```

Execute master Day 11 end-to-end verification:
```bash
./scripts/day11_checkpoint.sh
```

---

## 7. Known Limitations & Future Work

- **Duplicates:** Duplicate events are accepted into the Bronze layer as raw history. Deduplication occurs in subsequent Silver transformations.
- **Data Quality:** Validation, quarantine routing, and error rate tracking will be implemented in Silver/Quality engine phases.
