# IceStream Self-Healing & Recovery Strategy

> **Status Notice**: This document specifies the **Target Self-Healing Architecture & Circuit Breaker Logic** for IceStream. These recovery mechanisms will be implemented in Phases 4 through 6.

---

## 1. Circuit Breaker State Machine

The core resilience mechanism in IceStream is a stateful Circuit Breaker that monitors pipeline error rates and automatically isolates failures to prevent downstream data pollution.

```
       +---------------------------------------------------+
       |                                                   |
       v                                                   |
  +----------+       error rate > 5%         +----------+  |
  |  CLOSED  | ----------------------------> |   OPEN   |  |
  | (Normal) |                               | (Stop)   |  |
  +----------+                               +----------+  |
       ^                                           |       |
       |                                           |       |
       |  validation success                       | test  |
       |  (0% error in sample)                     v       |
       +--------------------------------- +-----------+    | validation failure
                                          | HALF_OPEN | ---+
                                          | (Testing) |
                                          +-----------+
```

### 1.1 State Definitions

1. **CLOSED (Normal Operation)**
   - Ingestion and processing run at full speed.
   - Every event is parsed, validated, and routed (valid -> Iceberg, invalid -> quarantine).
   - Moving error rate is continuously monitored over a sliding 60-second window.

2. **OPEN (Isolated / Paused)**
   - Triggered when the moving error rate exceeds the configured threshold (e.g., > 5% over 100 events).
   - Real-time ingestion into downstream Iceberg tables is paused or isolated.
   - Incident generated in PostgreSQL; urgent Slack alert dispatched to operators.
   - Data streams are diverted into quarantine or held in Kafka topic buffers.

3. **HALF_OPEN (Controlled Recovery Validation)**
   - Initiated automatically after a cooldown period (e.g., 120s) or via manual operator trigger.
   - A limited sample stream (e.g., 50 records) is allowed through the validation engine.
   - If **any** invalid record is detected during validation, the circuit breaker immediately trips back to `OPEN`.
   - If **all** sample records pass validation cleanly, the pipeline transitions back to `CLOSED`.

---

## 2. Comprehensive Recovery Lifecycle

```
[1. Incident Triggered] -> [2. Circuit Breaker OPEN] -> [3. Operator Alerted]
                                                                  |
                                                                  v
[6. Pipeline CLOSED]   <- [5. HALF_OPEN Validation] <- [4. Quarantine Replay]
```

### 2.1 Quarantine Invalid Records
Invalid events are isolated immediately into the `quarantine-events` Kafka topic and written to the `quarantine_records` table in PostgreSQL. The original payload, timestamp, failure reason, and schema version are preserved intact.

### 2.2 Preserve Incident History
Every circuit breaker state change and error rate spike creates an immutable record in PostgreSQL table `incidents`. This provides historical auditing, incident duration tracking, and root cause analysis.

### 2.3 Alert Operators
When a pipeline failure occurs, Slack webhooks and Grafana alerts broadcast the incident ID, error rate percentage, affected topic, and recommended recovery steps.

### 2.4 Validate Source Recovery
Before resuming normal ingestion, the system validates that the upstream event generator or schema registry has returned to a compliant state.

### 2.5 Replay & Reprocess Eligible Records
Once the source or schema rule issue is resolved, operators or automated recovery scripts trigger quarantine replay. Corrected records from the quarantine store are re-published to Kafka for re-validation.

### 2.6 Resume Downstream Processing
Upon successful reprocessing and `HALF_OPEN` verification, downstream Iceberg writes resume seamlessly without manual database intervention.

### 2.7 Audit Trail Maintenance
All recovery operations, manual overrides, replay timestamps, and user actions are logged in the `audit_logs` table for complete compliance visibility.
