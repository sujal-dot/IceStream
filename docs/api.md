# IceStream Observability Backend API Specification

This document provides complete documentation for the IceStream FastAPI Observability Telemetry and Pipeline Control REST API.

The backend acts as an API and transport layer over authoritative domain components (`ErrorRateEngine`, `CircuitBreaker`, `PipelineStateManager`, `RemediationController`, `QualityEngine`, `SchemaDriftDetector`, and `StorageBackend`).

---

## Base URL

`http://localhost:8000`

Interactive OpenAPI Docs: `http://localhost:8000/docs`
OpenAPI JSON Schema: `http://localhost:8000/openapi.json`

---

## Table of Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | API & Dependency Health Status |
| `GET` | `/pipeline/status` | Authoritative Pipeline State & Active Incident |
| `POST` | `/pipeline/pause` | Manually Pause Pipeline Operations |
| `POST` | `/pipeline/resume` | Manually Resume Pipeline Operations (Safety Protected) |
| `POST` | `/pipeline/recover` | Trigger Self-Healing Remediation Workflow |
| `GET` | `/metrics` | Real-Time Telemetry & Rolling Window Metrics |
| `GET` | `/incidents` | List Persisted Pipeline Incidents (Paginated) |
| `GET` | `/incidents/{id}` | Detailed Incident Record & Recovery Attempts History |
| `GET` | `/lineage` | React Flow Compatible End-to-End Data Lineage Graph |
| `GET` | `/quality` | Data Quality Engine Status & Severity Breakdown |
| `GET` | `/schema/drift` | Schema Drift Detection Status & Version Changes |
| `GET` | `/events` | Sanitized Read-Only Event Metadata Inspection |

---

## Endpoint Details

### 1. GET /health

**Purpose**: Verifies backend HTTP service availability and non-sensitive dependency health (`postgres`, `quality_engine`, `iceberg_catalog`).

**Response Model**: `HealthResponse`

**Sample Response (`200 OK`)**:
```json
{
  "status": "ok",
  "service": "icestream-backend",
  "version": "0.23.0",
  "timestamp": "2026-09-02T10:00:00Z",
  "dependencies": {
    "postgres": "ok",
    "quality_engine": "ok",
    "iceberg_catalog": "ok"
  }
}
```

---

### 2. GET /pipeline/status

**Purpose**: Returns the authoritative backend-owned pipeline state from `PipelineStateManager`.

**Response Model**: `PipelineStatusResponse`

**Sample Response (`200 OK`)**:
```json
{
  "pipeline_id": "icestream",
  "state": "RUNNING",
  "previous_state": "RESUMING",
  "reason": "Validation passed. Pipeline resumed.",
  "incident_id": null,
  "recovery_attempt": 0,
  "stage": "RUNNING",
  "last_error": null,
  "updated_at": "2026-09-02T10:00:00Z"
}
```

---

### 3. POST /pipeline/pause

**Purpose**: Manually pauses pipeline operations using authoritative state transitions.

**Request Body (Optional)**:
```json
{
  "reason": "Operator initiated maintenance"
}
```

**Sample Response (`200 OK`)**:
```json
{
  "pipeline_id": "icestream",
  "state": "PAUSED",
  "previous_state": "RUNNING",
  "message": "Pipeline paused successfully.",
  "updated_at": "2026-09-02T10:00:00Z"
}
```

---

### 4. POST /pipeline/resume

**Purpose**: Resumes pipeline operations. If the authoritative CircuitBreaker is `OPEN`, manual resume is blocked to protect data integrity.

**Error Response (`409 Conflict`)**:
```json
{
  "error": "PIPELINE_PROTECTED",
  "message": "Pipeline cannot resume while circuit breaker is OPEN."
}
```

---

### 5. POST /pipeline/recover

**Purpose**: Triggers the existing `RemediationController` self-healing workflow.

**Request Body (Optional)**:
```json
{
  "incident_id": "inc_123"
}
```

**Sample Response (`200 OK`)**:
```json
{
  "incident_id": "inc_123",
  "status": "STARTED",
  "pipeline_state": "REMEDIATING",
  "recovery_attempt": 1,
  "message": "Remediation executed successfully."
}
```

---

### 6. GET /metrics

**Purpose**: Retrieves real-time rolling window metrics snapshot from `ErrorRateEngine` and `CircuitBreaker`.

**Sample Response (`200 OK`)**:
```json
{
  "service": "icestream-quality-engine",
  "status": "ok",
  "timestamp": "2026-09-02T10:00:00Z",
  "windows": {
    "1m": {
      "window_seconds": 60,
      "total_events": 1000,
      "valid_events": 990,
      "failed_events": 10,
      "error_rate": 0.01,
      "error_rate_percent": 1.0,
      "health": "WARNING"
    },
    "5m": {
      "window_seconds": 300,
      "total_events": 5000,
      "valid_events": 4950,
      "failed_events": 50,
      "error_rate": 0.01,
      "error_rate_percent": 1.0,
      "health": "WARNING"
    }
  },
  "circuit_breaker": {
    "state": "CLOSED",
    "enabled": true,
    "can_process": true,
    "can_probe": false,
    "error_rate": 0.01,
    "threshold": 0.02
  },
  "remediation": {
    "attempts": 0,
    "successes": 0,
    "failures": 0,
    "recovered_events": 0
  }
}
```

---

### 7. GET /incidents

**Purpose**: Retrieves paginated list of persisted pipeline incidents from database storage.

**Query Parameters**:
- `status`: Optional status filter (`OPEN`, `RECOVERED`, `RECOVERY_FAILED`).
- `limit`: Integer (1 to 100, default 50).
- `offset`: Integer (ge 0, default 0).

---

### 8. GET /incidents/{id}

**Purpose**: Retrieves full detailed record, circuit status, remediation stage, and attempts history for a specific incident.

**Error Response (`404 Not Found`)**:
```json
{
  "detail": "Incident 'inc_999' not found"
}
```

---

### 9. GET /lineage

**Purpose**: Supplies node and edge structure compatible with React Flow representing end-to-end IceStream data lineage.

---

### 10. GET /quality

**Purpose**: Returns current quality status, failed rules count, and severity summary.

---

### 11. GET /schema/drift

**Purpose**: Exposes schema drift detection status, version comparison, and detected field changes.
