# Quarantine / Dead Letter Architecture

## Overview

The IceStream Quarantine system provides a durable, persistent Dead Letter Queue (DLQ) for invalid streaming checkout events. Invalid events isolated by the Quality Engine are persisted into an Apache Iceberg table (`quarantine.invalid_checkout_events`) stored as Parquet files on MinIO storage via the IceStream Iceberg REST Catalog.

```
                       Incoming Event
                              │
                              ▼
                       Quality Engine
                              │
                              ▼
                     Validation Results
                              │
                   ┌──────────┴──────────┐
                   │                     │
                 VALID                 INVALID
                   │                     │
                   ▼                     ▼
                Silver             Quarantine Router
                                         │
                                         ▼
                              QuarantineRecord
                                         │
                                         ▼
                                      Iceberg
                                         │
                                         ▼
                                       MinIO
```

---

## Purpose

1. **Original Payload Preservation**: Preserve full raw event payloads for audit, inspection, and future replay without stripping or flattening fields.
2. **Durable Lakehouse Isolation**: Store invalid data directly in Apache Iceberg (`quarantine.invalid_checkout_events`) to enable SQL querying, ACID compliance, and MinIO object storage persistence.
3. **Structured Metadata Enrichment**: Enrich invalid events with primary error classifications (`error_code`), failed rule lists, detection timestamps, pipeline versioning, and source schema versioning.
4. **Validation Engine Decoupling**: Maintain strict architectural separation between validation evaluation (Quality Engine) and persistence routing (Quarantine Router).

---

## Routing Rules & Valid Event Protection

- **Input**: Event payload (`QualityEvent` or `dict`) + Validation results (`ValidationSummary` or list of `ValidationResult`).
- **Valid Event Protection**: The `QuarantineRouter` inspects rule outcomes. If all rules passed (`0` failed rules), the router refuses to quarantine the event, returning `skipped_reason="EVENT_IS_VALID"`. Valid events are routed downstream to the Silver layer.
- **Invalid Event Processing**: Events failing one or more rules are structured into a single `QuarantineRecord`, checked for duplicate quarantine IDs, and appended to Iceberg.

---

## Table Schema (`quarantine.invalid_checkout_events`)

The quarantine table uses PyIceberg with Parquet storage version 2.

| Column | Physical Type | Logical Type | Purpose |
|---|---|---|---|
| `quarantine_id` | `StringType` | String | Unique deterministic record ID (`q_<hash>`) |
| `event_id` | `StringType` | String | Original event identifier (nullable) |
| `event` | `StringType` | String (JSON) | Complete preserved original event payload |
| `error_code` | `StringType` | Enum String | Primary error classification (e.g. `NULL_AMOUNT`) |
| `error_message` | `StringType` | String | Human-readable failure explanation(s) |
| `failed_rules` | `ListType(StringType)` | Array[String] | Deterministic sorted list of all failed rule names |
| `detected_at` | `StringType` | ISO-8601 String | Timestamp when quarantine detection occurred |
| `pipeline_version` | `StringType` | String | Codebase version (e.g. `0.1.0`) |
| `schema_version` | `StringType` | String | Source schema version (e.g. `v3` or `unknown`) |

---

## Error Codes & Deterministic Mapping

Validation rule failures map to standardized, low-cardinality error codes:

| Quality Rule | Primary Error Code | Default Severity |
|---|---|---|
| `amount_not_null` | `NULL_AMOUNT` | `CRITICAL` |
| `amount_positive` | `INVALID_AMOUNT` | `HIGH` |
| `currency_valid` | `INVALID_CURRENCY` | `HIGH` |
| `payment_status_valid` | `INVALID_PAYMENT_STATUS` | `MEDIUM` |
| `event_time_valid` | `INVALID_TIMESTAMP` | `HIGH` |
| `duplicate_event` | `DUPLICATE_EVENT` | `HIGH` |
| `duplicate_order` | `DUPLICATE_ORDER` | `MEDIUM` |
| `impossible_amount` | `IMPOSSIBLE_AMOUNT` | `HIGH` |
| `future_timestamp` | `FUTURE_TIMESTAMP` | `HIGH` |
| `late_event` | `LATE_EVENT` | `MEDIUM` |
| `schema_drift` | `SCHEMA_DRIFT` | `CRITICAL` |
| *(Unmapped rule)* | `DATA_QUALITY_FAILURE` | `WARNING` |

---

## Multiple Failed Rules & Primary Error Selection

When an invalid event breaks multiple rules (e.g. `amount = null` and `currency = 'XYZ'`):

1. **One Quarantine Record**: The system writes exactly **1** quarantine record for the event (not separate records per failed rule).
2. **Primary Error Selection**: The primary `error_code` is selected using rule severity weighting:
   $$\text{Severity Weight: } \text{CRITICAL} (400) > \text{HIGH} (300) > \text{MEDIUM}/\text{WARNING} (200) > \text{LOW}/\text{INFO} (100)$$
   If multiple rules share the highest severity level, alphabetical ordering of the rule name breaks the tie deterministically.
3. **Failed Rules Preservation**: All failed rule names are stored in `failed_rules` ordered by severity weight descending, then rule name alphabetically.

---

## Idempotency & Duplicate Protection

- **Deterministic Quarantine ID**:
  $$\text{quarantine\_id} = \text{"q\_"} + \text{SHA256}(\text{event\_id} \mathbin{\Vert} \text{pipeline\_version} \mathbin{\Vert} \text{failed\_rules} \mathbin{\Vert} \text{detected\_at})[:16]$$
- **In-Context Deduplication**: The `QuarantineRouter` maintains an in-memory deduplication index of processed `quarantine_id`s to prevent writing duplicate records if an event is re-processed within the same execution context.

---

## Storage & Catalog Integration

- **Catalog**: Managed via IceStream Iceberg REST Catalog (`http://localhost:8181`).
- **Warehouse**: Backed by MinIO object storage (`s3://warehouse/quarantine/invalid_checkout_events/`).
- **Format**: Standard Apache Parquet columnar storage with Iceberg v2 table format properties.

---

## Metrics

Operational metrics are tracked via Prometheus-compatible counters:

| Metric Name | Type | Labels | Description |
|---|---|---|---|
| `quarantine_events_total` | Counter | None | Total count of invalid events routed to quarantine |
| `quarantine_write_success_total` | Counter | None | Total records successfully appended to Iceberg |
| `quarantine_write_failure_total` | Counter | None | Total records that failed Iceberg append operations |
| `quarantine_events_by_error_code` | Counter | `error_code` | Quarantine events grouped by primary error code |

> [!IMPORTANT]
> High-cardinality attributes such as `event_id` or `error_message` are NEVER used as Prometheus metric labels.

---

## Failure Handling & No False Success

- Storage append operations are verified by `QuarantineWriter`.
- If an Iceberg append operation fails, `quarantine_write_failure_total` is incremented and the router returns `success=False` with error details.
- The system will **NEVER** report `quarantine_success = True` if table persistence failed.

---

## Future Self-Healing Loop

```
                     Quarantine Table
                            │
                            ▼
                    Recovery Controller (Future Day)
                            │
                            ▼
                     Replay Engine
                            │
                            ▼
                      Quality Engine
                            │
                   ┌────────┴────────┐
                   │                 │
                 VALID             INVALID
                   │                 │
                   ▼                 ▼
                Silver          Re-Quarantine
```

*Note: Automated replay and recovery controllers are reserved for future implementation days. Day 21 focuses strictly on durable bad data preservation.*
