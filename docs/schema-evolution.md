# IceStream Schema Evolution & Compatibility Guide

## Overview

In real-time Lakehouse observability pipelines, event schemas evolve over time as new business requirements emerge. Controlling schema evolution ensures downstream streaming engines (Apache Flink), data quality processors (Great Expectations), and storage tables (Apache Iceberg) continue operating without data corruption or silent ingestion failures.

This document details the schema evolution mechanics, compatibility classification rules, and deterministic demonstration of the **IceStream Schema Compatibility Engine**.

---

## Schema Evolution Summary

| Evolution | Schema Changes | Classification | Severity | Impact / Rationale |
| :--- | :--- | :--- | :--- | :--- |
| **V1 → V2** | • Added optional string `coupon_code`<br>• Added optional string `device_model`<br>• Expanded `payment_status` enum with `"REFUNDED"` | **`COMPATIBLE`** | `INFO` | Backward compatible. Existing downstream consumers ignore unknown optional fields and process known status values. |
| **V2 → V3** | • Changed `amount` field type from `float` to `string` | **`BREAKING`** | `BREAKING` | Incompatible type mutation. Downstream analytics expecting numeric operations will crash or fail casting. |

---

## Step-by-Step Evolution Analysis

### Scenario 1: V1 → V2 (Compatible Evolution)

#### V1 Baseline Schema Fragment (`schema/v1.json`)
```json
{
  "schema_version": "v1",
  "fields": {
    "amount": {
      "type": "float",
      "required": true
    },
    "payment_status": {
      "type": "string",
      "required": true,
      "enum": ["SUCCESS", "FAILED", "PENDING"]
    }
  }
}
```

#### V2 Evolved Schema Fragment (`schema/v2.json`)
```json
{
  "schema_version": "v2",
  "fields": {
    "amount": {
      "type": "float",
      "required": true
    },
    "payment_status": {
      "type": "string",
      "required": true,
      "enum": ["SUCCESS", "FAILED", "PENDING", "REFUNDED"]
    },
    "coupon_code": {
      "type": "string",
      "required": false
    },
    "device_model": {
      "type": "string",
      "required": false
    }
  }
}
```

#### Deterministic CLI Check
```bash
python schema/compare.py --old schema/v1.json --new schema/v2.json
```

**Result:**
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

---

### Scenario 2: V2 → V3 (Breaking Evolution)

#### V3 Evolved Schema Fragment (`schema/v3.json`)
```json
{
  "schema_version": "v3",
  "fields": {
    "amount": {
      "type": "string",
      "required": true
    }
  }
}
```

#### Deterministic CLI Check
```bash
python schema/compare.py --old schema/v2.json --new schema/v3.json
```

**Result:**
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

---

## Machine-Readable API & JSON Output

System components (e.g. Flink streaming jobs or circuit breakers) query the compatibility result in structured JSON format:

```bash
python schema/compare.py --old schema/v2.json --new schema/v3.json --json
```

```json
{
  "compatible": false,
  "classification": "BREAKING",
  "old_version": "v2",
  "new_version": "v3",
  "summary": "Schema evolution from v2 to v3 is BREAKING (1 breaking change(s) detected out of 1 total).",
  "changes": [
    {
      "change_type": "FIELD_TYPE_CHANGED",
      "field": "amount",
      "old_value": "float",
      "new_value": "string",
      "classification": "BREAKING",
      "severity": "BREAKING",
      "description": "Incompatible type change for field 'amount' (float -> string)"
    }
  ]
}
```

---

## Classification Rules Reference

1. **Field Addition**:
   - Optional field (`required: false`) → `COMPATIBLE`
   - Required field (`required: true`) → `BREAKING`
2. **Field Removal**:
   - Required or Optional field removed → `BREAKING`
3. **Type Mutations**:
   - Safe numeric promotion (`integer` → `float`) → `COMPATIBLE`
   - Incompatible type change (`float` → `string`, `string` → `float`, etc.) → `BREAKING`
4. **Enum Mutations**:
   - Adding allowed enum values → `COMPATIBLE`
   - Removing allowed enum values → `BREAKING`
5. **Requirement Flags**:
   - Required → Optional → `COMPATIBLE`
   - Optional → Required → `BREAKING`
