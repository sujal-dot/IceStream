# IceStream Fault Injection Engine Documentation

The **IceStream Fault Injection Engine** provides a controlled, configurable failure-injection framework that intentionally mutates high-throughput e-commerce checkout events published to Apache Kafka.

It enables realistic data quality failure simulation for streaming lakehouse observability and self-healing pipeline demonstrations.

---

## Architecture & Flow

```text
                 ┌─────────────────────┐
                 │ Valid Event         │
                 │ Generator           │
                 └──────────┬──────────┘
                            │
                            ▼
                 ┌─────────────────────┐
                 │ Fault Injection     │
                 │ Engine              │
                 └──────────┬──────────┘
                            │
                  ┌─────────┴─────────┐
                  │                   │
                CLEAN               FAULTY
                  │                   │
                  └─────────┬─────────┘
                            ▼
                       Kafka
                  checkout-events
```

All generated events (clean or faulty) enter the single Kafka topic: `checkout-events`. No separate Kafka topics are created per fault type.

---

## Supported Fault Modes & Failure Semantics

### 1. NULL Fault

- **Fault Name**: `NULL`
- **CLI Option**: `--null-rate <percentage>` (e.g. `--null-rate 1` for 1%)
- **Meaning**: Injects `null` values into required checkout event fields.
- **Affected Fields**: `customer_id`, `session_id`, `order_id`, `product_id`, `amount`, `currency`, `payment_method`, `payment_status`.
- **Example Valid Event**:
  ```json
  {
    "event_id": "evt_a1b2c3d4e5f67890",
    "customer_id": "CUS000123",
    "amount": 1499.00
  }
  ```
- **Example Faulty Event**:
  ```json
  {
    "event_id": "evt_a1b2c3d4e5f67890",
    "customer_id": null,
    "amount": 1499.00
  }
  ```
- **Expected Future Detection**: `not_null` data-quality rules in Flink / Great Expectations.

---

### 2. DUPLICATE Fault

- **Fault Name**: `DUPLICATE`
- **CLI Option**: `--duplicate-rate <percentage>` (e.g. `--duplicate-rate 0.5` for 0.5%)
- **Meaning**: Re-uses exact past event identity (`event_id` and payload) to simulate stream duplicate delivery.
- **Affected Fields**: Entire payload / `event_id`.
- **Example Valid Event**:
  ```json
  {
    "event_id": "evt_88f91a2b3c4d5e6f",
    "order_id": "ORD5544332",
    "amount": 2990.00
  }
  ```
- **Example Faulty Event (re-sent later in stream)**:
  ```json
  {
    "event_id": "evt_88f91a2b3c4d5e6f",
    "order_id": "ORD5544332",
    "amount": 2990.00
  }
  ```
- **Expected Future Detection**: Stream deduplication window / stateful primary key uniqueness check.

---

### 3. NEGATIVE Fault

- **Fault Name**: `NEGATIVE`
- **CLI Option**: `--negative-rate <percentage>` (e.g. `--negative-rate 1` for 1%)
- **Meaning**: Generates logically impossible negative transactional values.
- **Affected Fields**: `amount`, `unit_price`, `quantity`.
- **Example Valid Event**:
  ```json
  {
    "quantity": 2,
    "unit_price": 749.50,
    "amount": 1499.00
  }
  ```
- **Example Faulty Event**:
  ```json
  {
    "quantity": 2,
    "unit_price": 749.50,
    "amount": -1499.00
  }
  ```
- **Expected Future Detection**: Range / non-negative numeric constraint check (`amount > 0`).

---

### 4. INVALID_ENUM Fault

- **Fault Name**: `INVALID_ENUM`
- **CLI Option**: `--invalid-enum-rate <percentage>` (e.g. `--invalid-enum-rate 0.5` for 0.5%)
- **Meaning**: Generates field values outside permitted enumeration sets.
- **Affected Fields**: `payment_method`, `payment_status`.
- **Example Valid Event**:
  ```json
  {
    "payment_method": "UPI",
    "payment_status": "SUCCESS"
  }
  ```
- **Example Faulty Event**:
  ```json
  {
    "payment_method": "CRYPTO_UNKNOWN",
    "payment_status": "UNKNOWN_STATUS_X"
  }
  ```
- **Expected Future Detection**: Allowed-set enum validation check.

---

### 5. SCHEMA_DRIFT Fault

- **Fault Name**: `SCHEMA_DRIFT`
- **CLI Option**: `--schema-drift-rate <percentage>` (e.g. `--schema-drift-rate 1` for 1%)
- **Meaning**: Simulates an unannounced producer schema change (`ADD_FIELD`, `REMOVE_FIELD`, `RENAME_FIELD`).
- **Affected Fields**: Dynamic structural payload changes.
- **Example Valid Event**:
  ```json
  {
    "customer_id": "CUS001",
    "payment_status": "SUCCESS",
    "source_version": "v1"
  }
  ```
- **Example Faulty Event (RENAME_FIELD scenario)**:
  ```json
  {
    "client_id": "CUS001",
    "payment_status": "SUCCESS",
    "source_version": "v2"
  }
  ```
- **Expected Future Detection**: Automated schema registry / dynamic schema evolution monitoring.

---

### 6. TYPE_CHANGE Fault

- **Fault Name**: `TYPE_CHANGE`
- **CLI Option**: `--type-change-rate <percentage>` (e.g. `--type-change-rate 0.5` for 0.5%)
- **Meaning**: Alters the data type of an event field (e.g. numeric to string).
- **Affected Fields**: `quantity`, `amount`, `customer_id`.
- **Example Valid Event**:
  ```json
  {
    "quantity": 2,
    "amount": 1499.00
  }
  ```
- **Example Faulty Event**:
  ```json
  {
    "quantity": "2",
    "amount": "1499.00"
  }
  ```
- **Expected Future Detection**: Strict data type conformance validation.

---

### 7. TIMESTAMP_DRIFT Fault

- **Fault Name**: `TIMESTAMP_DRIFT`
- **CLI Option**: `--timestamp-drift-rate <percentage>` (e.g. `--timestamp-drift-rate 0.5` for 0.5%)
- **Meaning**: Generates out-of-order, stale, or future event timestamps (`FUTURE_TIMESTAMP`, `STALE_TIMESTAMP`, `CLOCK_SKEW`).
- **Affected Fields**: `event_time`.
- **Example Valid Event**:
  ```json
  {
    "event_time": "2026-08-15T11:00:00.000Z"
  }
  ```
- **Example Faulty Event (FUTURE_TIMESTAMP variant)**:
  ```json
  {
    "event_time": "2026-08-15T13:00:00.000Z"
  }
  ```
- **Expected Future Detection**: Watermark & event-time freshness threshold check.

---

## Ready-to-Run Demonstration Commands

### Demo 1 — Clean Stream

```bash
python generator/main.py \
  --rate 1000 \
  --error-rate 0
```

### Demo 2 — Null Spike

```bash
python generator/main.py \
  --rate 1000 \
  --null-rate 5
```

### Demo 3 — Duplicate Spike

```bash
python generator/main.py \
  --rate 1000 \
  --duplicate-rate 3
```

### Demo 4 — Schema Drift

```bash
python generator/main.py \
  --rate 1000 \
  --schema-drift-rate 2
```

### Demo 5 — Multiple Controlled Failures

```bash
python generator/main.py \
  --rate 1000 \
  --null-rate 1 \
  --duplicate-rate 0.5 \
  --negative-rate 0.5 \
  --invalid-enum-rate 0.5 \
  --schema-drift-rate 0.2 \
  --type-change-rate 0.5 \
  --timestamp-drift-rate 0.5
```

> [!NOTE]
> When running with multiple fault rates, single-fault-per-event collision handling guarantees each faulty event receives exactly one fault mutation, making detection metrics clear and deterministic.
