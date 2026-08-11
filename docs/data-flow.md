# IceStream Data Flow Lifecycle

> **Status Notice**: This document details the **Planned 15-Stage Data Lifecycle** for IceStream. This represents the target processing flow to be built across future phases.

---

## 1. Overview of Data Flow

The IceStream platform processes event streams through a 15-stage end-to-end lifecycle. Every record passing through the system is continuously evaluated for schema integrity, domain validity, and statistical normality before landing in the lakehouse.

---

## 2. The 15-Stage Lifecycle

```
[1. Event Generated] ---> [2. Published to Kafka] ---> [3. Flink Consumes]
                                                               |
                                                               v
[6. Quality Rules]  <--- [5. Schema Validated]   <--- [4. Event Parsed]
        |
        v
[7. Anomaly Detection]
        |
        +-----------------------------------+
        |                                   |
        v (Valid)                           v (Invalid)
[8. Valid Records Continue]         [9. Records Quarantined]
        |                                   |
        v                                   v
[Iceberg Lakehouse Write]           [10. Calculate Error Rate]
                                            |
                                            v
                                    [11. Circuit Breaker]
                                            |
                                            v
                                    [12. Incidents Generated]
                                            |
                                            v
                                    [13. Alerts Sent]
                                            |
                                            v
                                    [14. Recovery Attempted]
                                            |
                                            v
                                    [15. Pipeline Resumes]
```

### Stage 1: Event Generation
The Python Event Simulator constructs structured JSON event payloads representing transactional activity (e.g., user ID, amount, timestamp, currency, payment status).

### Stage 2: Kafka Publishing
Events are published to the Apache Kafka `raw-events` topic using configured partitioning strategies for parallel consumption.

### Stage 3: Flink Ingestion
Apache Flink stream processing workers consume event records from Kafka with managed offset tracking.

### Stage 4: Record Parsing
Flink jobs deserialize JSON payloads into internal state objects, flagging malformed or unparseable byte streams.

### Stage 5: Schema Validation
Field structures, mandatory key presence, data types, and schema version numbers are checked against defined JSON schemas.

### Stage 6: Data-Quality Rule Evaluation
Business logic validation rules are applied (e.g., transaction amount > 0, currency in allowed ISO codes, timestamp within plausible time window).

### Stage 7: Anomaly Detection
Statistical anomaly detection algorithms evaluate stream patterns for sudden volume spikes or out-of-range value distributions.

### Stage 8: Valid Record Routing
Records passing all schema, quality, and anomaly checks are forwarded to the Apache Iceberg sink.

### Stage 9: Record Quarantine
Failed or malformed records are diverted to the `quarantine-events` Kafka topic and logged into PostgreSQL with full error context.

### Stage 10: Moving Error Rate Calculation
Flink window aggregators compute real-time error rates (failed events / total events) over sliding 60-second windows.

### Stage 11: Circuit Breaker Evaluation
The quality engine evaluates current error rates against defined threshold limits (e.g., 5% error rate). If breached, the circuit breaker state transitions to `OPEN`.

### Stage 12: Incident Generation
Structured incident records are created in PostgreSQL detailing failure triggers, error counts, affected schema versions, and timestamps.

### Stage 13: Automated Alert Dispatch
Alert notifications containing incident summaries are pushed to operators via Slack webhooks and Grafana alert channels.

### Stage 14: Recovery Validation & Testing
The system enters `HALF_OPEN` state, pausing ingestion from bad sources or attempting controlled replay of corrected quarantine data.

### Stage 15: Pipeline Resumption
Upon successful validation of stream health, the circuit breaker resets to `CLOSED`, and normal ingestion resumes.
