# IceStream — Incident Management & Slack Alerting Architecture (Day 24)

## Architecture Overview

IceStream implements production-grade backend incident management and alerting. **PostgreSQL** serves as the authoritative source of truth for incidents, while **Slack** functions as a resilient, best-effort notification transport layer.

```text
Bad Data
   ↓
Quality Engine (Validation & Error Rate Engine)
   ↓
Error Rate > Threshold (2%)
   ↓
Circuit Breaker OPEN & Pipeline State -> CIRCUIT_OPEN
   ↓
Incident Service (PostgreSQL Persistence & Deduplication)
   │
   ├──────────────► Commit PostgreSQL DB Record (INC-YYYY-MMDD-XXXX)
   │
   ▼
Slack Service Dispatch Alert Notification (3x Exponential Backoff Retries)
   │
   ▼
Slack Incoming Webhook (Alert Delivery Status Recorded)
```

---

## 1. Incident Model & Database Persistence

All incidents are persisted in the `pipeline_incidents` PostgreSQL table (with in-memory SQLite fallback for unit testing).

### Database Schema (`pipeline_incidents`)

| Field | Type | Description |
|---|---|---|
| `incident_id` | `VARCHAR(64)` PRIMARY KEY | Deterministic unique incident identifier (e.g. `INC-2026-0903-0001`) |
| `pipeline_name` | `VARCHAR(64)` | Name of affected stream (`checkout-stream`) |
| `status` | `VARCHAR(64)` | Incident lifecycle state (`OPEN`, `ACKNOWLEDGED`, `RESOLVED`) |
| `severity` | `VARCHAR(32)` | Health severity (`CRITICAL` > 2%, `WARNING` 1–2%, `HEALTHY` < 1%) |
| `error_rate` | `DOUBLE PRECISION` | Observed error rate ratio (e.g., `0.0372` = `3.72%`) |
| `threshold` | `DOUBLE PRECISION` | Configured error rate threshold (default `0.02` = `2%`) |
| `failed_records` | `BIGINT` | Total failed/quarantined record count |
| `total_records` | `BIGINT` | Total evaluated record count |
| `detected_at` | `TIMESTAMP` | Initial breach detection timestamp |
| `created_at` | `TIMESTAMP` | DB record creation timestamp |
| `updated_at` | `TIMESTAMP` | Last status/metrics update timestamp |
| `resolved_at` | `TIMESTAMP` NULL | Resolution timestamp when pipeline recovers |
| `trigger_type` | `VARCHAR(64)` | Incident trigger classification (`CRITICAL_ERROR_RATE`) |
| `action_taken` | `TEXT` | Automated action executed by system (`Downstream pipeline paused.`) |
| `slack_sent` | `BOOLEAN` | Notification delivery flag |
| `slack_sent_at` | `TIMESTAMP` NULL | Timestamp of successful Slack HTTP delivery |
| `slack_error` | `TEXT` NULL | Exception/error detail if Slack delivery fails |

---

## 2. Deterministic Incident ID Format

Incident IDs are generated deterministically by the backend using date-based sequence formatting:

```text
INC-YYYY-MMDD-XXXX
```

* `YYYY-MMDD`: Current UTC date (e.g. `2026-0903`)
* `XXXX`: 4-digit zero-padded daily sequence counter (`0001`, `0002`, ...)

---

## 3. Incident Deduplication

To prevent alert storms and duplicate DB rows during ongoing pipeline outages, `IncidentService` implements strict thread-safe deduplication:

1. **Active Check**: Before creating a new incident, the system queries for an active incident (`status IN ('OPEN', 'ACKNOWLEDGED')`) for the pipeline.
2. **Metric Update**: If an active incident exists, the system updates `error_rate`, `failed_records`, `total_records`, and `updated_at` on the existing incident.
3. **Alert Suppression**: The system suppresses repeated Slack alerts for the active outage, ensuring operators receive exactly **one** primary alert per incident lifecycle.

---

## 4. Slack Alerting & Resilience

Slack webhooks are integrated safely without risking pipeline stability or DB transaction rollbacks.

### Notification Workflow
1. PostgreSQL transaction is **committed first**.
2. `SlackService` dispatches structured payload via HTTP POST to `SLACK_WEBHOOK_URL`.
3. If Slack fails (network error, timeout, HTTP 5xx), `SlackService` retries up to **3 times** with exponential backoff (`0.5s`, `1.0s`, `2.0s`).
4. If all retries fail, `slack_sent` is set to `False` and `slack_error` is logged. **The pipeline and DB incident remain intact.**

### Incident Alert Format
```text
*🚨 ICESTREAM INCIDENT*

*Pipeline:* checkout-stream
*Status:* OPEN
*Severity:* CRITICAL

*Error rate:* 3.72%
*Threshold:* 2%
*Failed records:* 372

*Detected:* 10:31:05

*Action:*
Downstream pipeline paused.

*Incident ID:*
INC-2026-0903-0001
```

### Resolution Alert Format
```text
*✅ ICESTREAM INCIDENT RESOLVED*

*Pipeline:* checkout-stream

*Status:* RESOLVED

*Error rate:* 0.42%

*Recovered at:* 10:38:21

*Incident ID:*
INC-2026-0903-0001
```

---

## 5. Incident Lifecycle & API Endpoints

```text
       OPEN
        │
        ├──► POST /incidents/{id}/acknowledge
        ▼
   ACKNOWLEDGED
        │
        ├──► POST /incidents/{id}/resolve (or Automated Remediation Recovery)
        ▼
     RESOLVED
```

### REST API Endpoints

* `GET /incidents`: Query paginated incidents with optional `status` or `severity` filter.
* `GET /incidents/{id}`: Fetch detailed incident record and remediation attempt history.
* `POST /incidents/{id}/acknowledge`: Transition incident from `OPEN` to `ACKNOWLEDGED` (idempotent).
* `POST /incidents/{id}/resolve`: Transition incident to `RESOLVED`, record `resolved_at`, and dispatch Slack resolution alert.

---

## 6. Testing & Manual Verification

Run automated test suite:
```bash
.venv/bin/pytest -v tests/test_day24_slack_incidents.py
```

Run CLI manual Slack alert test script:
```bash
# Mock mode (local console output):
python scripts/test_slack_alert.py --mock

# Real webhook mode:
SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..." python scripts/test_slack_alert.py
```
