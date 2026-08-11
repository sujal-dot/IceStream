# Apache Iceberg Lakehouse Component

## Component Purpose
The `iceberg/` directory manages catalog definitions, table schema evolution specifications, and maintenance scripts for the Apache Iceberg table format built on top of MinIO object storage.

## Planned Responsibility
- Store validated, clean real-time stream data in ACID-compliant open table formats.
- Maintain partitioned historical analytics tables with snapshot management.
- Provide time travel capability for historical auditing and recovery verification.
- Execute table compaction, snapshot expiration, and metadata cleanup maintenance jobs.

## Expected Inputs
- Stream of validated records written via Apache Flink Iceberg connector.

## Expected Outputs
- ACID-compliant Iceberg datasets available for analytical queries and observability backend.
- Metadata logs, snapshots, and manifest files stored in MinIO object storage.

## Future Implementation Phase
- **Implementation Phase**: Phase 3 (Lakehouse Storage & Snapshot Management).
- **Status**: Architecture Target / Planned. No implementation code present on Day 1.
