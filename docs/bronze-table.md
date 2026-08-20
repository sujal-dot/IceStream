# IceStream Bronze Table Specification — `icestream.bronze.checkout_events`

## 1. Overview & Purpose

The **Bronze Table** (`icestream.bronze.checkout_events`) serves as the production-foundation raw ingestion layer of the IceStream Lakehouse architecture.

> [!IMPORTANT]
> **Bronze Ingestion Principle**: Bronze is intentionally close to the raw source event. Validation, deduplication, quality score calculation, and enrichment occur downstream (in Silver and Quarantine). Bronze allows nullable fields so malformed or fault-injected events are captured rather than rejected before observability systems can inspect them.

## 2. Table Metadata & Storage Location

- **Catalog**: `icestream` (Iceberg REST Catalog)
- **Namespace**: `bronze`
- **Table Name**: `checkout_events`
- **Full Identifier**: `icestream.bronze.checkout_events`
- **Storage Backend**: MinIO (S3-compatible Object Storage)
- **Logical Warehouse Path**: `s3://warehouse/bronze/checkout_events`
- **Physical Data Format**: `Parquet` (`write.format.default = parquet`)
- **Iceberg Format Version**: `2` (`format-version = 2`)

## 3. Production Schema Contract

| Column Name | Data Type | Nullable | Description |
| :--- | :--- | :--- | :--- |
| `event_id` | `STRING` | Yes | Unique logical event identifier |
| `event_time` | `TIMESTAMP` | Yes | Original business event timestamp (UTC) |
| `customer_id` | `STRING` | Yes | Identifier of purchasing customer |
| `session_id` | `STRING` | Yes | User browsing session identifier |
| `order_id` | `STRING` | Yes | E-commerce order transaction identifier |
| `product_id` | `STRING` | Yes | Purchased product item identifier |
| `amount` | `DECIMAL(18,2)` | Yes | Financial transaction amount (precise decimal representation) |
| `currency` | `STRING` | Yes | ISO currency code (e.g., `INR`, `USD`) |
| `payment_method` | `STRING` | Yes | Payment mode (`UPI`, `CREDIT_CARD`, `DEBIT_CARD`, etc.) |
| `payment_status` | `STRING` | Yes | Transaction status (`SUCCESS`, `FAILED`, `PENDING`) |
| `device` | `STRING` | Yes | Client device type (`mobile`, `desktop`, `tablet`) |
| `country` | `STRING` | Yes | Two-letter ISO country code (`IN`, `US`) |
| `source_version` | `STRING` | Yes | Schema/producer version (`v1`, `v2`, `v3`) |
| `ingestion_time` | `TIMESTAMP` | Yes | Storage timestamp when event entered Bronze layer |

## 4. Architectural & Design Decisions

### 4.1 `event_time` vs `ingestion_time`
- **`event_time`**: The timestamp when the user performed the checkout action in the upstream application source.
- **`ingestion_time`**: The timestamp when the event was committed into the IceStream Bronze table.
- Comparing `ingestion_time - event_time` provides real-time visibility into ingestion delay and streaming pipeline latency.

### 4.2 Financial Precision (`DECIMAL(18,2)`)
To avoid binary floating-point rounding errors typical of `FLOAT` / `DOUBLE`, financial transactional values are strictly typed as `DECIMAL(18,2)`.

### 4.3 Schema Versioning (`source_version`)
`source_version` captures the schema version published by the event producer. This enables downstream schema-evolution handlers and compatibility checkers to recognize producer schema drifts (`v1` vs `v2` vs `v3`).

### 4.4 Duplicate & Null Handling
- Primary keys are **not** declared at the storage layer because Iceberg does not enforce relational unique constraints on append-heavy Bronze streams.
- If multiple events arrive with identical `event_id`, Bronze preserves all raw records.
- Deduplication and quarantine isolation are performed downstream during Silver transformations.

### 4.5 Partitioning Strategy
- Small dev writes are unpartitioned to avoid excessive tiny partitions.
- For high-volume production streaming, date-based partitioning (`days(event_time)`) is recommended.

## 5. Flink & PyIceberg Integration

- **Write Integration**: Apache Flink SQL / Stream execution engine writes directly into `icestream.bronze.checkout_events` via Iceberg REST Catalog.
- **Read Integration**: PyIceberg, PyArrow, or Flink SQL can read back table snapshots transactionally.

## 6. Small File & Compaction Awareness

Development test workloads commit small batches of records. In production streaming workloads, appropriate Iceberg commit intervals and periodic `rewrite_data_files` compaction jobs will maintain optimal Parquet file sizes.
