# React Flow Lineage Dashboard

## Overview & Purpose

The **React Flow Lineage Dashboard** provides interactive, real-time visualization of the end-to-end data engineering pipeline topology in **IceStream**. Located at route `/lineage` in the single-page React frontend application, the dashboard renders both the primary data processing flow and the quarantine failure path.

```text
Kafka
  ↓
Flink
  ↓
Quality Engine
  ├──→ Iceberg Bronze → Iceberg Silver → Analytics
  └──→ Quarantine → DLQ
```

---

## Architecture & Integration

The frontend lineage dashboard is built using **React 18**, **TypeScript**, and **React Flow (`@xyflow/react`)**. Graph structure and health status are dynamically fetched from the Day 23 FastAPI backend (`GET /lineage`).

```text
FastAPI Telemetry Backend
           ↓
     GET /lineage
           ↓
   lineageApi.ts Client
           ↓
  LineagePage Component
           ↓
 React Flow Lineage Canvas
```

---

## Component Topology & Nodes

The graph visualizes 8 core data pipeline components along with system observability controllers:

### 1. Main Processing Flow
* **Kafka (`kafka`)**: `checkout-events` topic ingesting raw e-commerce event streams.
* **Flink (`flink`)**: Apache Flink streaming engine performing parsing, validation, and anomaly detection.
* **Quality Engine (`quality-engine`)**: Hybrid validation engine combining Great Expectations and 14 active quality rules.
* **Iceberg Bronze (`iceberg-bronze`)**: Raw storage layer stored as Parquet on MinIO object storage (`bronze.checkout_events`).
* **Iceberg Silver (`iceberg-silver`)**: Validated, clean analytical layer (`silver.valid_checkout_events`).
* **Analytics (`analytics`)**: Downstream consumption layer (Trino / Spark SQL queries).

### 2. Failure Branch
* **Quarantine (`quarantine`)**: Dead letter Iceberg table storing invalid schema and rule-violating events (`quarantine.invalid_checkout_events`).
* **DLQ (`dlq`)**: Kafka Dead Letter Queue topic (`checkout-dlq`) for unrecoverable messages.

### 3. System Observability & Control
* **Error-Rate Engine (`error-rate-engine`)**: Real-time error rate metric calculator over 1m/5m windows.
* **Circuit Breaker (`circuit-breaker`)**: Authoritative state machine monitoring pipeline thresholds.
* **Remediation Controller (`remediation-controller`)**: Automated self-healing remediation runner.

---

## Node & Edge Data Model

Backend JSON schema returned by `GET /lineage`:

```json
{
  "nodes": [
    {
      "id": "kafka",
      "type": "source",
      "label": "Kafka",
      "status": "HEALTHY",
      "details": {
        "resource": "checkout-events",
        "description": "Event ingestion stream"
      }
    }
  ],
  "edges": [
    {
      "id": "kafka-to-flink",
      "source": "kafka",
      "target": "flink",
      "label": "events",
      "animated": true
    }
  ]
}
```

---

## Runtime Status Integration

Node statuses are mapped from live backend state:

| Status | Semantic Treatment | Border / Badge Color | Description |
| :--- | :--- | :--- | :--- |
| `HEALTHY` | Positive | Emerald (`#10B981`) | Normal operation |
| `WARNING` | Warning | Amber (`#F59E0B`) | Minor anomaly or validation warning |
| `DEGRADED` | Warning | Amber (`#F59E0B`) | Degraded streaming throughput |
| `CRITICAL` | Critical | Rose (`#EF4444`) | Severe failure or threshold breach |
| `CIRCUIT_OPEN` | Critical | Rose (`#EF4444`) | Circuit breaker OPEN |
| `IDLE` | Neutral | Slate (`#6B7280`) | Inactive / standby failure branch |
| `ACTIVE` | Active Branch | Blue / Amber | Failure branch actively receiving bad records |

---

## Interactive Features

* **Node Details Drawer**: Clicking any node opens a right-hand inspection drawer displaying component specs, topic/table names, configuration parameters, upstream sources, and downstream targets.
* **Toolbar Controls**:
  * **Fit View**: Auto-fits graph within the viewport (`fitView`).
  * **Reset Layout**: Recovers default viewport layout.
  * **Refresh**: Triggers real-time refetching of `/lineage` backend API.
* **Canvas Interactivity**: Smooth zoom (0.3x - 1.8x), pan, drag nodes, minimap, and background dot grid.
* **Error & Retry Handling**: Clear API connection fallback state with a working `[Retry]` button when backend is unreachable.

---

## Development & Testing

Run frontend unit test suite:
```bash
cd frontend && npm run test
```

Build production bundle:
```bash
cd frontend && npm run build
```
