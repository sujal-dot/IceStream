# IceStream Schema Versioning & Compatibility Engine

## Overview

In real-time streaming architectures (Lakehouse / Delta Lake / Iceberg), schema drift from event producers can lead to downstream data corruption, broken analytical pipelines, and failed database ingestion.

The **IceStream Schema Versioning & Compatibility Engine** maintains versioned machine-readable JSON schema contracts, validates schema integrity, and evaluates whether a schema change between two versions is **`COMPATIBLE`** or **`BREAKING`**.

This standalone engine provides foundational capabilities for future real-time observability, quarantine processing, and circuit-breaker mechanisms.

---

## Schema Files & Source of Truth

The machine-readable JSON files in `schema/` serve as the single source of truth for event structures:

- **`schema/v1.json`**: Initial baseline checkout event schema (17 required fields, standard enum values).
- **`schema/v2.json`**: Compatible evolution (adds optional `coupon_code` and `device_model` fields, expands `payment_status` enum with `"REFUNDED"`).
- **`schema/v3.json`**: Breaking evolution (changes field type of `amount` from `float` to `string`).
- **`schema/registry.json`**: Local manifest tracking available schema versions and active production schema version (`v2`).

### Schema Structure Format

```json
{
  "schema_version": "v1",
  "description": "Original IceStream Checkout Event Schema",
  "fields": {
    "amount": {
      "type": "float",
      "required": true
    },
    "payment_method": {
      "type": "string",
      "required": true,
      "enum": [
        "UPI",
        "CREDIT_CARD",
        "DEBIT_CARD",
        "NET_BANKING",
        "WALLET",
        "COD"
      ]
    }
  }
}
```

---

## Compatibility Rules & Policies

| Rule Category | Evolution Scenario | Classification | Severity | Rationale / Policy |
| :--- | :--- | :--- | :--- | :--- |
| **Optional Field Added** | `+ coupon_code: optional string` | `COMPATIBLE` | `INFO` | Downstream consumers ignoring unknown fields or handling nulls remain unbroken. |
| **Required Field Added** | `+ tax_id: required string` | `BREAKING` | `BREAKING` | Existing event producers do not supply this required field. |
| **Field Removed** | `- customer_id` | `BREAKING` | `BREAKING` | Existing consumers expecting this field will fail. |
| **Incompatible Type Change** | `amount: float → string` | `BREAKING` | `BREAKING` | Downstream consumers expecting numeric values will encounter parse/type errors. |
| **Safe Type Promotion** | `quantity: integer → float` | `COMPATIBLE` | `INFO` | Numeric widening preserves analytical precision. |
| **Optional → Required** | `coupon_code: optional → required` | `BREAKING` | `BREAKING` | Old messages lacking this field will fail validation. |
| **Required → Optional** | `customer_id: required → optional` | `COMPATIBLE` | `INFO` | Relaxing constraints does not break existing valid payloads. |
| **Enum Expansion** | `payment_status: + REFUNDED` | `COMPATIBLE` | `INFO` | Adding allowed enum values is compatible. |
| **Enum Reduction** | `payment_status: - FAILED` | `BREAKING` | `BREAKING` | Removing valid enum values breaks existing producers. |

---

## Type Compatibility Matrix

| Old Type | New Type | Result | Notes |
| :--- | :--- | :--- | :--- |
| `string` | `string` | `COMPATIBLE` | Identical primitive |
| `integer` | `integer` | `COMPATIBLE` | Identical primitive |
| `float` | `float` | `COMPATIBLE` | Identical primitive |
| `boolean` | `boolean` | `COMPATIBLE` | Identical primitive |
| `timestamp` | `timestamp` | `COMPATIBLE` | Identical primitive |
| `integer` | `float` | `COMPATIBLE` | Safe numeric widening promotion |
| `float` | `string` | `BREAKING` | Numeric to string conversion breaks consumers |
| `string` | `float` | `BREAKING` | String to float conversion breaks non-numeric strings |
| `integer` | `string` | `BREAKING` | Integer to string conversion |
| `string` | `object` | `BREAKING` | Primitive to object conversion |
| `object` | `string` | `BREAKING` | Object to primitive conversion |

---

## Schema Registry Abstraction

The Python `SchemaRegistry` class (`schema/registry.py`) provides a lightweight local registry interface:

```python
from schema import SchemaRegistry

registry = SchemaRegistry()

# List available versions
versions = registry.list_versions()  # ['v1', 'v2', 'v3']

# Retrieve a specific schema version
v1_schema = registry.get("v1")

# Get active current production schema
current = registry.current()  # v2 schema

# Compare two versions programmatically
result = registry.compare_versions("v1", "v2")
print(result.classification)  # Classification.COMPATIBLE
```

---

## CLI Usage

Use `schema/compare.py` to compare schema JSON files or version tags:

### Compatible Comparison (V1 → V2)

```bash
python schema/compare.py --old schema/v1.json --new schema/v2.json
```

**Output:**
```text
Schema Compatibility Check
==========================

Old schema: v1
New schema: v2

Changes:
+ device_model: optional string
+ coupon_code: optional string
+ payment_status (enum value added)
  Enum field 'payment_status' expanded with new value(s): REFUNDED

Classification:
COMPATIBLE ✓
```

### Breaking Comparison (V2 → V3)

```bash
python schema/compare.py --old schema/v2.json --new schema/v3.json
```

**Output:**
```text
Schema Compatibility Check
==========================

Old schema: v2
New schema: v3

Changes:
~ amount
  float → string

Classification:
BREAKING ✗

Reason:
- Incompatible type change for field 'amount' (float -> string)
```

### Machine-Readable JSON Mode

```bash
python schema/compare.py --old schema/v1.json --new schema/v2.json --json
```

---

## Future Integration

The Schema Versioning and Compatibility Engine is designed to integrate seamlessly into:
- **Flink Streaming Processor**: Real-time schema drift validation against active schema.
- **Data Quality Engine**: Automated rule generation based on schema field contracts.
- **Circuit Breaker / Quarantine**: Immediate routing of breaking schema drifts to quarantine topics.
