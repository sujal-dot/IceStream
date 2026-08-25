# IceStream Quality Rules & Validity Detection Engine (Day 15)

## Overview

The IceStream Quality Engine Day 15 extends the foundational quality architecture with production-grade data validity rules:
1. **NOT NULL** (Field Presence & Unpopulated Check)
2. **POSITIVE AMOUNT** (Financial & Quantity Value Bounds)
3. **VALID CURRENCY** (Supported Currency Codes)
4. **VALID PAYMENT STATUS** (Allowed Transaction Statuses)
5. **VALID TIMESTAMP** (ISO-8601 Structure & UTC Parsing)

---

## Architecture Diagram

```
                    Event
                      │
                      ▼
               QualityEngine
                      │
          ┌───────────┼────────────┐
          ▼           ▼            ▼
     NotNullRule   PositiveRule  AllowedValues
          │           │            │
          └───────────┼────────────┘
                      ▼
              TimestampRule
                      │
                      ▼
             ValidationResult[]
                      │
                      ▼
                Metrics
```

---

## Quality Rules Reference

### 1. NotNullRule (`not_null`)

- **Purpose**: Verifies that a target event field is populated, non-null, non-empty, and not literal `"none"`.
- **Fields**: `event_id`, `customer_id`, `session_id`, `order_id`, `product_id`, `amount`, `currency`, `payment_method`, `payment_status`, `device`, `country`, `source_version`, `event_time`, `ingestion_time`.
- **Condition**: `field_value is not None` and string values are non-empty after trimming.
- **Null Definition**: `None`, `""`, `"   "`, `"none"` (case-insensitive string). Note: `0`, `0.0`, and `False` are treated as valid non-null values.
- **Severity**: `CRITICAL` for core identity/financial fields (`event_id`, `amount`), `HIGH` for metadata/timestamp fields.
- **Example PASS**: `"evt_123"`, `1499.00`, `0`, `False`
- **Example FAIL**: `None`, `""`, `"none"`

---

### 2. AmountPositiveRule (`positive`)

- **Purpose**: Ensures financial amounts and numeric measurements are strictly greater than zero.
- **Fields**: `amount` (or quantity).
- **Condition**: `amount > 0`
- **Severity**: `HIGH`
- **Example PASS**: `1499.00`, `0.01`
- **Example FAIL**: `0`, `-50.00`, `None`, `"abc"`

---

### 3. AllowedValuesRule (`allowed_values`) / CurrencyValidRule / PaymentStatusValidRule

- **Purpose**: Verifies that enum-like text fields belong strictly to a configured set of valid domain values.
- **Fields**: `currency`, `payment_status`.
- **Condition**: Strict case-sensitive match against `allowed_values`.

#### Currency (`currency_valid`)
- **Allowed Values**: `["INR", "USD", "EUR"]`
- **Severity**: `HIGH`
- **Example PASS**: `"INR"`, `"USD"`
- **Example FAIL**: `"GBP"`, `"inr"`, `None`

#### Payment Status (`payment_status_valid`)
- **Allowed Values**: `["SUCCESS", "FAILED", "PENDING", "CANCELLED"]`
- **Severity**: `HIGH`
- **Example PASS**: `"SUCCESS"`, `"PENDING"`
- **Example FAIL**: `"UNKNOWN"`, `"processing"`, `None`

---

### 4. TimestampValidRule (`timestamp`)

- **Purpose**: Validates ISO-8601 string formatting, parseability, and timezone consistency for temporal fields.
- **Fields**: `event_time`, `ingestion_time`.
- **Condition**: Valid ISO-8601 timestamp string parseable by standard datetime parsers.
- **Severity**: `HIGH`
- **Example PASS**: `"2026-08-25T10:30:22.431Z"`, `"2026-08-25T10:30:22+05:30"`
- **Example FAIL**: `"invalid-date"`, `123456789`, `None`

---

## Result Model & Serialization

Every rule returns a standardized `ValidationResult`:

```json
{
  "event_id": "evt_day15_bad",
  "rule": "amount_positive",
  "rule_name": "amount_positive",
  "passed": false,
  "status": "FAIL",
  "severity": "HIGH",
  "message": "Field 'amount' must be greater than 0, got -500.0",
  "field": "amount",
  "timestamp": "2026-08-25T10:38:00+00:00",
  "metadata": {
    "provided_value": -500.0
  }
}
```

---

## Rule Registry & YAML Configuration

Rules are configured declaratively in `quality-engine/config/rules.yaml`:

```yaml
rules:
  - name: event_id_not_null
    enabled: true
    type: not_null
    field: event_id
    severity: CRITICAL

  - name: amount_positive
    enabled: true
    type: positive
    field: amount
    severity: HIGH

  - name: currency_valid
    enabled: true
    type: allowed_values
    field: currency
    severity: HIGH
    allowed_values:
      - INR
      - USD
      - EUR

  - name: event_time_valid
    enabled: true
    type: timestamp
    field: event_time
    severity: HIGH
```
