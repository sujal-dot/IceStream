# Automated Remediation & Self-Healing Pipeline Documentation

## 1. Overview & Problem Statement

In real-time Lakehouse data ingestion (Apache Iceberg, Apache Flink, Kafka), data corruptions and schema violations can drive elevated error rates that trigger Circuit Breakers to suspend streaming processing. Traditional pipeline architectures rely on manual human intervention or basic retry loops, leading to:
- Extended operational downtime
- Stale downstream analytics in the Lakehouse
- Risk of duplicate event processing or silent data loss

**IceStream Self-Healing Automation** introduces a real, stateful, automated remediation engine that orchestrates end-to-end recovery:

```
[Bad Data Detected] → [Quarantine (Iceberg)] → [Circuit Breaker (OPEN)] → [Alert (Slack/Webhook)]
          ↓
[Source Re-Fetch] → [QualityEngine Reprocess] → [Validation PASS] → [Circuit Breaker (CLOSED)] → [Resume Pipeline (RUNNING)]
```

This workflow is **authoritative**—the backend maintains persistent pipeline state in PostgreSQL (`pipeline_state`, `pipeline_incidents`, `remediation_attempts`) with SQLite fallback for isolated testing environments.

---

## 2. Remediation Lifecycle & State Machine

The pipeline transitions deterministically through 11 states:

```
                     ┌─────────────────────────────────────────────────────────┐
                     │                         RUNNING                         │
                     └────────────────────────────┬────────────────────────────┘
                                                  │ Error Rate > 2%
                                                  ▼
                                            CIRCUIT_OPEN
                                                  │
                                                  ▼
                                            REMEDIATING
                                                  │
                                                  ▼
                                            REFETCHING
                                                  │
                                                  ▼
                                           REPROCESSING
                                                  │
                                                  ▼
                                            VALIDATING
                                                  │
                                     ┌────────────┴────────────┐
                         Validation PASS                   Validation FAIL
                                     │                         │
                                     ▼                         ▼
                                  RESUMING              RECOVERY_FAILED
                                     │                         │
                                     ▼                         ▼
                                  RUNNING                 CIRCUIT_OPEN
```

| State | Description |
|---|---|
| `RUNNING` | Normal pipeline execution; events pass quality validation and ingestion into Silver/Gold layers. |
| `DEGRADED` | Error rate is elevated (>1%) but below critical threshold. Warnings logged. |
| `QUARANTINING` | Invalid events are being persisted to Apache Iceberg quarantine layer. |
| `CIRCUIT_OPEN` | Critical error rate exceeded (>2%); circuit opens and event ingestion is suspended. |
| `REMEDIATING` | Automated remediation workflow initiated for an active incident. |
| `REFETCHING` | `SourceAdapter` re-fetches corrected raw source records. |
| `REPROCESSING` | `Reprocessor` passes re-fetched records through real `QualityEngine` rules. |
| `VALIDATING` | Remediation controller validates reprocess outcomes and checks recovery thresholds. |
| `RESUMING` | `CircuitBreaker` transitions `HALF_OPEN` -> `CLOSED`. |
| `RECOVERED` | Incident resolved, pipeline fully restored to `RUNNING`. |
| `RECOVERY_FAILED` | Re-fetched data failed validation or max attempts exceeded (limit: 3); circuit remains `OPEN`. |

---

## 3. Core Architecture Components

### 3.1. `PipelineStateManager` (`quality-engine/remediation/state_manager.py`)
- Authoritative state machine maintaining current state and full state transition audit trail.
- Persists states to PostgreSQL/SQLite storage backend.
- Prevents invalid state transitions with thread safety.

### 3.2. `SourceAdapter` (`quality-engine/remediation/source_adapter.py`)
- Abstract base class for fetching corrected source data.
- `LocalSourceAdapter` provides deterministic re-fetching with `source_reference` audit tracking.

### 3.3. `Reprocessor` (`quality-engine/remediation/reprocessor.py`)
- Executes real `QualityEngine` validation against re-fetched payloads without mocking.
- Routes valid events to output array and quarantines invalid re-fetched events via `QuarantineWriter`.

### 3.4. `AlertService` (`quality-engine/remediation/alert_service.py`)
- Abstract alert interface with `SlackAlertAdapter` (sending HTTP webhooks) and `MockAlertService` for testing.

### 3.5. `RemediationController` (`quality-engine/remediation/controller.py`)
- Master orchestrator coordinating quarantine verification, alert dispatch, re-fetch, reprocess, validation, circuit breaker `HALF_OPEN` -> `CLOSED` recovery, max attempts enforcement (3 limit), exponential backoff, and concurrency/idempotency locking.

---

## 4. Operational API & Monitoring Endpoints

### 4.1. `GET /pipeline/status`
Returns authoritative backend pipeline state, current incident, recovery attempt, and transition history.
```json
{
  "pipeline_id": "icestream_checkout_pipeline",
  "state": "RUNNING",
  "circuit_state": "CLOSED",
  "active_incident_id": null,
  "recovery_attempt": 0,
  "last_updated": "2026-09-01T10:20:00.000000Z"
}
```

### 4.2. `POST /pipeline/remediate`
Triggers automated remediation for an active incident.
```json
{
  "incident_id": "inc_982341",
  "force": false
}
```
Response:
```json
{
  "incident_id": "inc_982341",
  "success": true,
  "stage": "COMPLETE",
  "attempt": 1,
  "recovered_events": 1,
  "failed_events": 0
}
```

### 4.3. Prometheus Metrics (`GET /metrics`)
- `icestream_remediation_attempts_total`: Total remediation attempts.
- `icestream_remediation_success_total`: Successful recovery count.
- `icestream_remediation_failure_total`: Failed recovery count.
- `icestream_remediation_recovered_events_total`: Total events recovered and processed.
- `icestream_remediation_duration_seconds`: Histogram of remediation execution duration.
- `icestream_pipeline_state`: Gauge mapping current pipeline state (0=RUNNING, 1=DEGRADED, 2=CIRCUIT_OPEN, 3=REMEDIATING, etc.).

---

## 5. Verification & Testing

To run the complete Day 22 Self-Healing Pipeline test suite:
```bash
.venv/bin/pytest -v tests/test_day22_self_healing.py
```

All 21 test scenarios verify state transitions, quarantine persistence, source re-fetching, real QualityEngine re-validation, circuit breaker recovery, max attempts limits (3), idempotency, and full end-to-end self-healing flow.
