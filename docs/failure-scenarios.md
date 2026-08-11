# IceStream Failure Scenarios & Resilience Matrix

> **Status Notice**: This document details the **Planned 15 Failure Scenarios** that IceStream will detect, quarantine, and recover from in upcoming phases.

---

## Failure Scenario Specifications

### Scenario 1: Null Values in Mandatory Fields
- **Example Failure**: Payload receives `{"event_id": "evt_101", "user_id": null, "amount": 49.99}` where `user_id` is mandatory.
- **Detection Mechanism**: Flink schema validator inspects mandatory non-null constraints.
- **Expected Response**: Event is rejected from valid stream and routed to quarantine with reason `NULL_REQUIRED_FIELD`.
- **Expected Recovery**: Automated quarantine logging; upstream generator config corrected during replay testing.

### Scenario 2: Negative Transaction Amount
- **Example Failure**: Payload receives `{"event_id": "evt_102", "user_id": "usr_5", "amount": -150.00}`.
- **Detection Mechanism**: Quality engine evaluates domain bounds (`amount > 0`).
- **Expected Response**: Event quarantined under `INVALID_DOMAIN_BOUNDS`; error metric counter incremented.
- **Expected Recovery**: Quarantine event audited; payload fixed or filtered during batch reprocessing.

### Scenario 3: Duplicate Event ID
- **Example Failure**: Event ID `evt_1001` is received twice within the deduplication window.
- **Detection Mechanism**: Flink stateful deduplication filter using RocksDB state backend.
- **Expected Response**: Duplicate instance is flagged, logged as `DUPLICATE_EVENT_ID`, and routed to quarantine.
- **Expected Recovery**: Unique record landed in Iceberg; duplicate suppressed without stopping the stream.

### Scenario 4: Missing Required Field
- **Example Failure**: Payload receives `{"amount": 99.99, "currency": "USD"}` missing `event_id` and `timestamp`.
- **Detection Mechanism**: JSON Schema validator checks required keys `[event_id, timestamp, user_id]`.
- **Expected Response**: Structural validation error raised; event routed to `quarantine-events` topic.
- **Expected Recovery**: Incident logged; pipeline remains `CLOSED` if error rate remains below threshold.

### Scenario 5: Unexpected Extra Field (Schema Strictness)
- **Example Failure**: Payload receives `{"event_id": "evt_105", "unknown_field_xyz": "corrupt_data"}`.
- **Detection Mechanism**: Strict schema mode validation against target schema definition.
- **Expected Response**: Event flagged for schema non-compliance and quarantined.
- **Expected Recovery**: Schema evolution approved or extra fields stripped via schema registry update.

### Scenario 6: Invalid Data Type
- **Example Failure**: Payload receives `{"amount": "ONE_HUNDRED"}` instead of float `100.00`.
- **Detection Mechanism**: Flink type parser fails to coerce string to numeric float.
- **Expected Response**: Serialization/parsing exception caught; event diverted to quarantine.
- **Expected Recovery**: Parsing metric incremented; malformed record stored for manual operator inspection.

### Scenario 7: Invalid Currency Code
- **Example Failure**: Payload receives `{"currency": "ZZZ"}` which is not in ISO 4217 set.
- **Detection Mechanism**: Reference lookup validation against allowed currency code set `[USD, EUR, GBP, JPY]`.
- **Expected Response**: Domain validation failure logged; event quarantined.
- **Expected Recovery**: Currency lookup table updated or payload rejected.

### Scenario 8: Invalid Payment Status
- **Example Failure**: Payload receives `{"status": "PENDING_UNKNOWN_STATE"}` outside enum `[COMPLETED, PENDING, FAILED, REFUNDED]`.
- **Detection Mechanism**: Enum constraint check in quality validation rules.
- **Expected Response**: Event routed to quarantine; warning metric recorded.
- **Expected Recovery**: Enum definitions updated in backend schema registry if valid new state.

### Scenario 9: Future Timestamp
- **Example Failure**: Payload timestamp is 24 hours in the future (`2028-01-01T00:00:00Z`).
- **Detection Mechanism**: Time boundary check against `system_time + max_skew_tolerance (5 minutes)`.
- **Expected Response**: Event flagged as `FUTURE_TIMESTAMP_ANOMALY` and diverted to quarantine.
- **Expected Recovery**: Generator clock drift calibrated; quarantine record re-timestamped if necessary.

### Scenario 10: Stale / Out-of-Order Timestamp
- **Example Failure**: Payload timestamp is 30 days old, exceeding watermark threshold.
- **Detection Mechanism**: Flink watermark evaluator detects late-arriving event past allowed lateness bound.
- **Expected Response**: Event emitted to late data side-output stream and sent to quarantine storage.
- **Expected Recovery**: Late data analyzed in quarantine lakehouse partition without polluting real-time window computations.

### Scenario 11: Schema Version Change / Mismatch
- **Example Failure**: Payload contains `schema_version: 3` when processor supports `v1` and `v2`.
- **Detection Mechanism**: Schema Registry version resolution check.
- **Expected Response**: Record rejected; incident created for `UNSUPPORTED_SCHEMA_VERSION`.
- **Expected Recovery**: Flink job updated with new schema handler; unparsed events replayed from Kafka offset.

### Scenario 12: Sudden Error-Rate Spike
- **Example Failure**: Generator injects 25% corrupt payloads in a 60-second window.
- **Detection Mechanism**: Flink windowed error rate aggregator exceeds 5% threshold.
- **Expected Response**: Circuit breaker transitions from `CLOSED` to `OPEN`. Stream ingestion paused/isolated. Incident created; Slack alert sent.
- **Expected Recovery**: Source isolated, root cause resolved, circuit breaker transitioned to `HALF_OPEN` for validation, then `CLOSED`.

### Scenario 13: Kafka Broker Interruption
- **Example Failure**: Kafka broker becomes unreachable or partition leader disappears.
- **Detection Mechanism**: Flink Kafka consumer driver connectivity error & retry exhaustion.
- **Expected Response**: Flink job triggers checkpoint fallback; health monitor reports ingestion connection failure.
- **Expected Recovery**: Kafka connection restored; Flink resumes reading from last successful checkpoint without data loss.

### Scenario 14: Flink Processing Task Failure
- **Example Failure**: Flink TaskManager node crashes due to OutOfMemory error.
- **Detection Mechanism**: Flink JobManager heartbeat timeout.
- **Expected Response**: JobManager restarts TaskManager; processing resumes from latest consistent checkpoint.
- **Expected Recovery**: Automatic state restoration via Flink checkpointing mechanism; pipeline resumes.

### Scenario 15: Apache Iceberg Write Failure
- **Example Failure**: MinIO object storage connection drop during Iceberg commit.
- **Detection Mechanism**: Iceberg catalog commit exception in Flink sink writer.
- **Expected Response**: Iceberg transaction rolls back cleanly preserving ACID state; sink retries commit.
- **Expected Recovery**: Storage connection restored; uncommitted batch retried and committed snapshot finalized.
