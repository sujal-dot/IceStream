# Circuit Breaker

## Purpose

The Circuit Breaker is an authoritative state machine component that protects downstream lakehouse storage, Iceberg tables, and real-time data consumers from critical pipeline corruption. When pipeline error rates surpass configured safety thresholds (> 2%), the circuit breaker trips to `OPEN`, providing a decision signal for downstream components to suspend processing until system health is verified.

---

## States

### CLOSED
- **Description**: Normal pipeline operations.
- `can_process()`: `True`
- `can_probe()`: `False`
- **Transition Rule**: If evaluated error rate strictly exceeds the threshold (`error_rate > 0.02`), the state machine transitions `CLOSED -> OPEN`.

### OPEN
- **Description**: Critical data quality error rate detected. Stream ingestion and downstream processing are suspended.
- `can_process()`: `False`
- `can_probe()`: `False`
- **Transition Rule**: Remains in `OPEN` state until the recovery timeout (`recovery_timeout_seconds`, default 60s) has elapsed. Once elapsed, it automatically transitions `OPEN -> HALF_OPEN`.

### HALF_OPEN
- **Description**: Recovery testing window. Permits a controlled recovery probe to evaluate whether pipeline health has recovered.
- `can_process()`: `False`
- `can_probe()`: `True` (strictly capped at one concurrent probe).
- **Transition Rule**:
  - Recovery probe PASS (`error_rate <= 0.02`): `HALF_OPEN -> CLOSED`.
  - Recovery probe FAIL (`error_rate > 0.02`): `HALF_OPEN -> OPEN` (resets recovery timeout).

---

## State Transition Diagram

```
                 error_rate > 2%
          ┌────────────────────────┐
          │                        ▼
      ┌────────┐              ┌────────┐
      │ CLOSED │              │  OPEN  │
      └───┬────┘              └───┬────┘
          │                       │
          │ normal                │ timeout
          │                       ▼
          │                  ┌───────────┐
          │                  │ HALF_OPEN │
          │                  └─────┬─────┘
          │                        │
          │               ┌────────┴────────┐
          │               ▼                 ▼
          │             PASS              FAIL
          │               │                 │
          └───────────────┘                 │
                                            │
                                            ▼
                                           OPEN
```

---

## Error Threshold

- `error_threshold`: `0.02` (2.0%)
- **Boundary Semantics**:
  - `0.0199` -> `CLOSED`
  - `0.0200` -> `CLOSED` (exactly 2.00% is the upper WARNING boundary and does NOT trip the circuit)
  - `0.0201` -> `OPEN` (strictly > 2.00% required to trip)

---

## Recovery Timeout

- Configured via `recovery_timeout_seconds` (default: 60 seconds).
- Utilizes an injectable `Clock` abstraction (`SystemClock`, `FixedClock`) for deterministic testing without sleeping in real time (`time.sleep`).

---

## Recovery Probe

- Controlled via `begin_recovery_probe()` / `begin_recovery()`.
- Synchronized with `threading.Lock` to guarantee **only ONE** recovery probe can run concurrently during `HALF_OPEN`.

---

## State History

- Bounded state transition log backed by `deque(maxlen=max_history)` (default: 100 entries).
- Captures transition details: `from`, `to`, `timestamp`, `reason`, `error_rate`, and custom metadata.

---

## Metrics

Low-cardinality monitoring metrics:
- `circuit_breaker_state`: Numeric state gauge (`CLOSED: 0`, `OPEN: 1`, `HALF_OPEN: 2`)
- `circuit_breaker_open_total`: Cumulative counter of transitions to `OPEN`
- `circuit_breaker_recovery_attempts_total`: Cumulative counter of recovery probes initiated
- `circuit_breaker_recovery_success_total`: Cumulative counter of successful probes
- `circuit_breaker_recovery_failure_total`: Cumulative counter of failed probes

---

## API

- `GET /circuit-breaker`: Read-only REST endpoint exposing current state machine status, thresholds, and transition counters.
- `GET /metrics`: Telemetry endpoint integrating `circuit_breaker` state alongside 1-minute and 5-minute rolling window error rates.

---

## Concurrency

- Thread-safe state machine operations protected by re-entrant locking primitives.
- Rejects racing concurrent recovery probes and guarantees atomic state transitions.

---

## Why Circuit Breaker Is Separate From Recovery

The Circuit Breaker is strictly a **decision engine** answering `SHOULD THE PIPELINE CONTINUE?`. It does not directly call infrastructure commands (such as restarting Docker containers, cancelling Flink jobs, or sending Slack notifications). Decoupling the decision signal from execution enables future self-healing orchestrators to act upon circuit state cleanly and safely.
