# Great Expectations Integration — Hybrid Quality Architecture

## Why Great Expectations?

Great Expectations (GE) provides industry-standard, declarative data quality expectations for static schema definitions and dataset-level constraints. In IceStream, Great Expectations evaluates structural constraints across batches and micro-batches, ensuring that dataset schema contracts (such as non-null constraints, numerical ranges, and permitted enum value sets) are met before data progresses down the lakehouse pipeline.

## Why Not Use GE For Everything?

While Great Expectations excels at declarative dataset-level expectations, it is not designed to execute per-event validation inside high-throughput real-time streaming engines (1,000+ events/sec). Instantiating GE validators on single streaming events introduces prohibitive overhead. Furthermore, stateful event stream checks—such as event-time deduplication across tumbling/sliding windows, late event arrival detection, future timestamp tolerance, and dynamic schema drift compatibility—require custom event-level rules and stateful window memory.

## Hybrid Architecture

IceStream adopts a **Hybrid Quality Architecture** balancing declarative batch expectations and custom real-time streaming rules:

```
                        Event Stream
                             │
                             ▼
                      Custom Engine
                             │
                 event-by-event rules
                             │
                             ▼
                    Custom Results
                             │
                             │
                             ▼
                       ┌───────────┐
                       │  Unified  │
                       │  Quality  │
                       │  Results  │
                       └─────▲─────┘
                             │
                    batch / micro-batch
                             │
                             ▼
                   Great Expectations
                             │
                    declarative checks
                             │
                             ▼
                         GE Results
```

## GE Responsibilities

Great Expectations owns declarative, batch-level quality expectations:
- `event_id_not_null`: `expect_column_values_to_not_be_null` (column: `event_id`, severity: `CRITICAL`)
- `amount_not_null`: `expect_column_values_to_not_be_null` (column: `amount`, severity: `CRITICAL`)
- `amount_positive`: `expect_column_values_to_be_between` (column: `amount`, min: 0, strict_min: true, severity: `HIGH`)
- `currency_valid`: `expect_column_values_to_be_in_set` (column: `currency`, set: `[INR, USD, EUR]`, severity: `HIGH`)
- `payment_status_valid`: `expect_column_values_to_be_in_set` (column: `payment_status`, set: `[SUCCESS, FAILED, PENDING, CANCELLED]`, severity: `HIGH`)

## Custom Rule Responsibilities

Custom rules own streaming/event-specific and stateful logic:
- `duplicate_event`: Event ID deduplication over rolling time windows (300s).
- `duplicate_order`: Order ID deduplication over rolling time windows (300s).
- `future_timestamp`: Event clock validation against wall-clock tolerance (30s).
- `late_event`: Lateness evaluation against ingestion clock (120s).
- `schema_drift`: Schema version compatibility, type promotion, and field drift detection.
- `rolling_error_rate`: Sliding window health rate calculation.

## Batch vs Streaming

- **Custom Engine**: Runs event-by-event validation at 1,000+ events/sec on low-latency streaming hot paths.
- **Great Expectations**: Runs on batches, micro-batches, or periodic audit intervals, operating on in-memory pandas DataFrames via `GEAdapter`.

## Result Normalization

`GEResultMapper` translates raw Great Expectations result payloads into standardized `ValidationResult` objects:

```json
{
  "event_id": "batch_1724842000",
  "rule": "amount_not_null",
  "rule_name": "amount_not_null",
  "passed": false,
  "status": "FAIL",
  "severity": "CRITICAL",
  "message": "Expectation 'amount_not_null' failed on column 'amount': 1 unexpected values (10.0%)",
  "field": "amount",
  "timestamp": "2026-08-28T10:30:00Z",
  "metadata": {
    "source": "great_expectations",
    "expectation": "expect_column_values_to_not_be_null",
    "element_count": 10,
    "unexpected_count": 1,
    "unexpected_percent": 10.0,
    "batch_id": "batch_1724842000"
  }
}
```

## Severity Mapping

Great Expectations evaluates expectation success/failure (`true`/`false`), while IceStream configuration determines incident severity (`CRITICAL`, `HIGH`, `WARNING`, `INFO`). Changing an expectation severity in `expectations.yaml` changes the normalized `ValidationResult.severity` without altering GE core logic.

## Metrics

`InMemoryMetricsCollector` tracks low-cardinality Great Expectations metrics:
- `ge_validation_runs`: Total batch validation executions.
- `ge_expectations_total`: Cumulative expectations evaluated.
- `ge_expectations_passed`: Cumulative expectations passed.
- `ge_expectations_failed`: Cumulative expectations failed.
- Label: `source="great_expectations"` vs `source="custom"`.

## Performance Considerations

Batch validation benchmark against 10,000 events demonstrates processing speeds exceeding 1,000+ rows/second for GE batch validations combined with Custom streaming rules.
