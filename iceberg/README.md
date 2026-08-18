# Apache Iceberg Lakehouse Component

## Component Purpose
The `iceberg/` directory manages catalog definitions, table schema evolution specifications, and maintenance scripts for the Apache Iceberg table format built on top of MinIO object storage.

## Day 8 Object Storage Foundation
Day 8 establishes the object-storage foundation required by the future Apache Iceberg lakehouse. MinIO buckets (`warehouse`, `checkpoints`, `schemas`, `logs`) and Flink S3 filesystem connectivity are fully configured.

```text
Iceberg tables: NOT IMPLEMENTED YET
Iceberg catalog: NOT IMPLEMENTED YET
```

## Planned Responsibility (Day 9+)
- Store validated, clean real-time stream data in ACID-compliant open table formats.
- Maintain partitioned historical analytics tables with snapshot management.
- Provide time travel capability for historical auditing and recovery verification.
- Execute table compaction, snapshot expiration, and metadata cleanup maintenance jobs.

## Expected Inputs
- Stream of validated records written via Apache Flink Iceberg connector.

## Expected Outputs
- ACID-compliant Iceberg datasets available for analytical queries and observability backend.
- Metadata logs, snapshots, and manifest files stored in MinIO object storage.

## Implementation Roadmap
- **Day 8 Status**: Object Storage Layer (MinIO & Flink S3) ✓
- **Day 9 Target**: Apache Iceberg Tables & REST Catalog Installation
