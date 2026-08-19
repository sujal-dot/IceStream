# Apache Iceberg Catalog and Lakehouse Architecture

## Overview
Apache Iceberg is the open lakehouse table format used in IceStream for store-and-query observability data. Built on top of MinIO object storage, Iceberg brings ACID transactional guarantees, schema evolution, time travel, and efficient columnar layout (Parquet) to real-time streaming data ingestion.

---

## Why Apache Iceberg?
1. **ACID Transactions**: Enables concurrent reads and writes from Apache Flink stream processing jobs without readers encountering partial or uncommitted files.
2. **Schema Evolution**: Supports field additions, renames, and type updates without breaking downstream queries or rewriting historical data files.
3. **Time Travel & Snapshot Isolation**: Retains immutable snapshot histories for audit logs, historical re-processing, and regression testing.
4. **Open Standard**: Native engine integration with Apache Flink, Trino, Spark, and PyIceberg.

---

## Iceberg vs MinIO Responsibilities

> [!IMPORTANT]
> - **MinIO** is the raw S3-compatible object store. It holds physical data files (Parquet) and Iceberg metadata files (`.metadata.json`, manifest files).
> - **Iceberg REST Catalog** is the catalog metadata management service. It manages table pointers, namespace definitions, and schema commits.
> - **Namespaces are NOT MinIO Buckets**. MinIO uses a single `warehouse` bucket (`s3://warehouse/`). Iceberg namespaces (`bronze`, `silver`, `quarantine`, `audit`) are logical catalog groupings stored inside the `s3://warehouse/` bucket prefix tree.

---

## Lakehouse Architecture & Component Data Flow

```text
Kafka (Future Phase)
  ↓
Future Flink Streaming
  ↓
Iceberg REST Catalog (http://iceberg-rest:8181)
  ↓
MinIO Warehouse (s3://warehouse/)
  ├── bronze/
  │   └── checkout_events/
  ├── silver/
  │   └── valid_checkout_events/
  ├── quarantine/
  │   └── invalid_checkout_events/
  └── audit/
      └── data_quality_results/
```

*Note: Kafka → Flink streaming ingestion is marked as **Future Implementation**.*

---

## Lakehouse Namespaces & Purpose

| Namespace | Purpose | Tables |
| :--- | :--- | :--- |
| **`bronze`** | Raw events as received from the streaming pipeline without alteration. | `checkout_events` |
| **`silver`** | Validated, type-coerced, and cleaned events ready for analytics. | `valid_checkout_events` |
| **`quarantine`** | Malformed or policy-violating events isolated for investigation. | `invalid_checkout_events` |
| **`audit`** | Data quality check results, operational logs, and incident metrics. | `data_quality_results` |

---

## Table Schemas

### `bronze.checkout_events`
- `event_id` (String, required)
- `event_time` (String, required)
- `event_type`, `customer_id`, `session_id`, `order_id`, `product_id` (String)
- `quantity` (Integer), `unit_price` (Double), `amount` (Double)
- `currency`, `payment_method`, `payment_status`, `device`, `country`, `source`, `source_version` (String)

### `silver.valid_checkout_events`
- Inherits all Bronze fields
- `processed_at` (String), `quality_score` (Double)

### `quarantine.invalid_checkout_events`
- `event_id`, `event_time` (String)
- `raw_payload` (String, required), `failure_reason` (String, required)
- `failure_type`, `schema_version`, `detected_at`, `pipeline_stage` (String)

### `audit.data_quality_results`
- `check_id` (String, required), `check_name` (String, required), `status` (String, required), `observed_at` (String, required)
- `event_id`, `severity`, `failure_reason`, `pipeline_stage` (String)

---

## Flink Integration & SQL Catalog Registration
Flink connects to the Iceberg REST catalog using the `iceberg-flink-runtime-1.18-1.5.2.jar` and `iceberg-aws-bundle-1.5.2.jar` libraries.

```sql
CREATE CATALOG icestream WITH (
  'type'='iceberg',
  'catalog-type'='rest',
  'uri'='http://iceberg-rest:8181',
  'warehouse'='s3://warehouse/',
  'io-impl'='org.apache.iceberg.aws.s3.S3FileIO',
  's3.endpoint'='http://minio:9000',
  's3.path-style-access'='true',
  's3.region'='us-east-1',
  'client.region'='us-east-1',
  's3.access-key-id'='icestream_minio',
  's3.secret-access-key'='icestream_minio_secret'
);

USE CATALOG icestream;
USE bronze;

SELECT * FROM checkout_events;
```

---

## Restart & Persistence Behavior
- **REST Catalog Service**: State and metadata pointers persist in the REST server backend. Restarting the `iceberg-rest` container preserves all namespaces and table metadata.
- **MinIO Storage**: Physical object files in `icestream_minio_data` volume persist across container restarts. Restarting `minio` leaves metadata and table files fully intact.

---

## Troubleshooting
1. **ClassNotFoundException: org.apache.hadoop.conf.Configuration**
   - Solution: Mount `flink-shaded-hadoop-2-uber-2.8.3-10.0.jar` into `/opt/flink/lib/`.
2. **SdkClientException: Unable to load region from any of the providers in the chain**
   - Solution: Configure `s3.region` and `client.region` in catalog properties, and export `AWS_REGION=us-east-1` in container environment.
3. **Cannot create catalog rest_backend, both type and catalog-impl are set**
   - Solution: Omit `CATALOG_TYPE=rest` from the `iceberg-rest` container's environment variables (it is set by clients connecting to the REST server).
