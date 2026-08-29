# Error Rate Engine Specification

## Overview
The **Error Rate Engine** computes real-time rolling-window error rates for the IceStream Lakehouse pipeline, classifies pipeline data health into actionable operational states (`HEALTHY`, `WARNING`, `CRITICAL`), and exposes telemetry metrics via a REST API (`GET /metrics`).

---

## Formula
$$\text{error\_rate} = \frac{\text{failed\_events}}{\text{total\_events}}$$

- If $\text{total\_events} = 0$, $\text{error\_rate} = 0.0$ and $\text{data\_available} = \text{false}$.
- Raw ratio (e.g. `0.015`) is stored internally and exposed alongside percentage representation (`error_rate_percent: 1.5`).

---

## Event-Level Semantics

> [!CRITICAL]
> **Mandatory Definition**: A "failed event" means an individual event with at least **ONE** failed enabled quality or anomaly rule. It does NOT mean the total count of failed rules across events.

### Example:
- **Event A**: `amount_not_null` → FAIL, `currency_valid` → FAIL, `future_timestamp` → FAIL (3 rule failures)
- **Event B**: `amount_positive` → FAIL (1 rule failure)
- **Event C**: All rules PASS (0 rule failures)

**Aggregated Metrics**:
- `total_events`: 3
- `valid_events`: 1
- `failed_events`: 2
- `error_rate`: $2 / 3 \approx 0.6667$ ($66.67\%$)
- *(Rule failure counter tracks 4 total rule failures separately).*

---

## Health Classification & Boundary Rules

Health classification maps raw unrounded error rates to categories based on configurable thresholds:

$$\text{Health Status} = \begin{cases} \text{HEALTHY} & \text{if } \text{error\_rate} < \text{healthy\_max} \quad (< 1.0\%) \\ \text{WARNING} & \text{if } \text{healthy\_max} \le \text{error\_rate} \le \text{warning\_max} \quad (1.0\% \text{ to } 2.0\%) \\ \text{CRITICAL} & \text{if } \text{error\_rate} > \text{warning\_max} \quad (> 2.0\%) \end{cases}$$

### Boundary Mapping:
- **0.00%** → `HEALTHY`
- **0.99%** → `HEALTHY`
- **1.00%** → `WARNING`
- **1.99%** → `WARNING`
- **2.00%** → `WARNING`
- **2.01%** → `CRITICAL`

> [!IMPORTANT]
> Precision preservation: Floating-point ratios must be evaluated directly against boundary thresholds before any rounding or formatting occurs. `0.0201` is classified as `CRITICAL`.

---

## Configurable Thresholds

Threshold parameters are managed via `ErrorRateConfig`:

```yaml
error_rate:
  thresholds:
    healthy_max: 0.01
    warning_max: 0.02
```

### Validation Rules:
1. `healthy_max` and `warning_max` must be numeric (`float` or `int`).
2. $0.0 \le \text{healthy\_max} < \text{warning\_max} \le 1.0$.
3. Any negative values, values $> 1.0$, missing parameters, or $\text{healthy\_max} \ge \text{warning\_max}$ trigger immediate validation failure.

---

## Rolling Windows

Metrics are aggregated over rolling time windows:
- **1 Minute** (60 seconds)
- **5 Minutes** (300 seconds)

### Weighted Error Rate:
The 5-minute error rate is computed **directly from event counts across the 5-minute window**:
$$\text{error\_rate}_{5m} = \frac{\sum_{t=0}^{300s} \text{failed\_events}_t}{\sum_{t=0}^{300s} \text{total\_events}_t}$$

It is **NOT** calculated as an unweighted average of 1-minute error rates.

---

## Zero Traffic & Data Availability

When zero events exist in the active window:
- `total_events`: 0
- `valid_events`: 0
- `failed_events`: 0
- `error_rate`: 0.0
- `health`: `HEALTHY`
- `data_available`: `false`

When events exist:
- `data_available`: `true`

This distinguishes "idle pipeline with no traffic" from "active pipeline with 0% error rate."

---

## Telemetry API (`GET /metrics`)

### Endpoint Details
- **Route**: `GET /metrics`
- **Response**: `200 OK` (`application/json`)
- **Safety**: Safe to call repeatedly; does **NOT** mutate event counters or expire window state prematurely.

### Sample Response JSON:
```json
{
  "service": "icestream-quality-engine",
  "status": "ok",
  "timestamp": "2026-08-29T11:00:00Z",
  "windows": {
    "1m": {
      "total_events": 1000,
      "valid_events": 990,
      "failed_events": 10,
      "error_rate": 0.01,
      "error_rate_percent": 1.0,
      "health": "WARNING",
      "data_available": true
    },
    "5m": {
      "total_events": 5000,
      "valid_events": 4950,
      "failed_events": 50,
      "error_rate": 0.01,
      "error_rate_percent": 1.0,
      "health": "WARNING",
      "data_available": true
    }
  }
}
```

---

## Service Health vs. Data Health

- **Service Status** (`status: "ok"`): Indicates that the HTTP backend REST API server is responsive and healthy.
- **Data Health** (`health: "HEALTHY" | "WARNING" | "CRITICAL"`): Reflects the current data quality state of events flowing through the pipeline.
- Example: The API can return `status: "ok"` while `windows["1m"]["health"]` is `"CRITICAL"`.

---

## Architectural Boundary (Day 19 Scope)

The Error Rate Engine is strictly a **SIGNALING layer**. It evaluates data quality and communicates health state.

It does **NOT**:
- Pause Flink stream execution.
- Open circuit breaker states.
- Quarantine events.
- Dispatch alert notifications.
- Restart consumers or services.
