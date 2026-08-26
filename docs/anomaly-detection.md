# IceStream Anomaly & Duplicate Detection Engine — Day 16

## Overview

Day 16 extends the IceStream Quality Engine with stateful duplicate event/order detection, business anomaly rules, deterministic clock abstractions, and rolling-window metrics aggregation (1-minute and 5-minute windows).

## Architectural Flow

```
                    Incoming Events
                          │
                          ▼
                  ┌───────────────┐
                  │ Quality Engine│
                  └───────┬───────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
      Duplicate       Anomaly          Validity
       Rules           Rules             Rules
          │               │               │
          └───────────────┼───────────────┘
                          ▼
                  Validation Results
                          │
                          ▼
                 Event-level Status
                          │
                ┌─────────┴─────────┐
                ▼                   ▼
           1-minute              5-minute
             window                window
                │                   │
                └─────────┬─────────┘
                          ▼
                    Error Rate
```

---

## Detection Rules

### 1. Duplicate Event Detection (`DuplicateEventRule`)
- **Rule Name:** `duplicate_event`
- **Severity:** `CRITICAL`
- **Definition:** Flags events sharing the same `event_id` within a rolling window (`window_seconds: 300`).
- **Null Handling:** `None`, empty strings, or unpopulated `event_id` fields skip duplicate detection (handled separately by `EventIdNotNullRule`).
- **State Management:** In-memory bounded tracking state with automatic expiration of IDs older than `window_seconds`.

### 2. Duplicate Order Detection (`DuplicateOrderRule`)
- **Rule Name:** `duplicate_order`
- **Severity:** `HIGH`
- **Definition:** Flags repeated `order_id` occurrences within a rolling window (`window_seconds: 300`).
- **Purpose:** Signals potential duplicate submissions or retry anomalies. Independent of `event_id` duplicates.

### 3. Impossible Amount Detection (`ImpossibleAmountRule`)
- **Rule Name:** `impossible_amount`
- **Severity:** `HIGH`
- **Definition:** Flags transactions exceeding a business limit (`max_value: 500000`).
- **Separation:** Negative or zero amounts are checked by `AmountPositiveRule`. Impossible amount focuses strictly on upper ceiling anomalies.

### 4. Future Timestamp Detection (`FutureTimestampRule`)
- **Rule Name:** `future_timestamp`
- **Severity:** `HIGH`
- **Definition:** Flags events where `event_time` is further in the future than allowed clock skew tolerance (`tolerance_seconds: 30`).

### 5. Late Event Detection (`LateEventRule`)
- **Rule Name:** `late_event`
- **Severity:** `MEDIUM`
- **Definition:** Flags events arriving older than allowed lateness (`allowed_lateness_seconds: 120`). Diagnoses arrival delay via `event_delay = ingestion_time - event_time`.

---

## Difference Between Future vs Late Timestamps

| Metric | Condition | Formula |
| :--- | :--- | :--- |
| **Future Timestamp** | Event time is in the future beyond tolerance | `event_time > reference_time + tolerance_seconds` |
| **Late Event** | Event time is older than allowed lateness | `reference_time - event_time > allowed_lateness_seconds` |
| **Acceptable Window** | Event time is normal | `reference_time - allowed_lateness <= event_time <= reference_time + tolerance` |

---

## State Management & Expiration

Duplicate detection state is managed strictly in memory without database queries:
- **State Bounding:** Timestamped deque/dictionary evicts entries when reference time advances past `window_seconds`.
- **Instance Isolation:** Each rule/engine instance owns its state. No global sets shared between tests.
- **Clock Abstraction:** Supports `SystemClock` (wall clock) and `FixedClock` (injectable, advanceable time for deterministic testing).

---

## Rolling-Window Metrics Engine

`WindowAggregator` provides sliding rolling-window statistics for 1-minute (60s) and 5-minute (300s) durations.

### Formatted Output Model (`WindowMetrics`)
```json
{
  "window_seconds": 60,
  "window_start": "2026-08-26T10:00:00+00:00",
  "window_end": "2026-08-26T10:01:00+00:00",
  "total_events": 100,
  "valid_events": 95,
  "invalid_events": 5,
  "error_rate": 0.05
}
```

### Error Rate Calculation
$$\text{error\_rate} = \frac{\text{invalid\_events}}{\text{total\_events}}$$

*Zero-Event Handling:* When `total_events == 0`, `error_rate` defaults to `0.0`.

---

## CRITICAL DISTINCTION: Rule Failures vs Invalid Events

- **Valid Event:** An event where **0** enabled rules fail (`overall_status == HEALTHY`).
- **Invalid Event:** An event where **at least 1** enabled rule fails.

> [!IMPORTANT]
> **RULE FAILURES $\neq$ INVALID EVENTS**
> An event that fails 3 rules (e.g. `duplicate_event`, `impossible_amount`, `future_timestamp`) counts as **ONE** invalid event (`invalid_events += 1`), NOT three!
> 
> Individual rule failures are tracked separately under `rule_failures` metrics counters.
