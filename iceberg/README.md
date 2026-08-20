# Apache Iceberg Lakehouse Component

## Component Purpose
The `iceberg/` directory manages catalog definitions, table schema evolution specifications, and maintenance scripts for the Apache Iceberg table format built on top of MinIO object storage.

## Lakehouse Structure

```text
icestream (Catalog)
│
├── bronze
│   └── checkout_events (Production raw event foundation)
│
├── silver
│   └── valid_checkout_events (Upcoming)
│
├── quarantine
│   └── invalid_checkout_events (Upcoming)
│
└── audit
    └── data_quality_results (Upcoming)
```

## Implemented Layers

### Day 8 — Object Storage Foundation ✓
- MinIO object storage (`warehouse`, `checkpoints`, `schemas`, `logs`)
- Flink S3 filesystem plugin (`flink-s3-fs-hadoop`)

### Day 9 — Iceberg Catalog Service ✓
- Iceberg REST Catalog (`tabulario/iceberg-rest`)
- Namespaces: `bronze`, `silver`, `quarantine`, `audit`

### Day 10 — Bronze Iceberg Table ✓
- `icestream.bronze.checkout_events`
- 14-field production schema (`DECIMAL(18,2)`, `TIMESTAMP`, `source_version`, `ingestion_time`)
- Parquet physical format (`write.format.default = parquet`)
- Iceberg format version 2 (`format-version = 2`)
- Flink SQL write & read-back verification
- MinIO metadata and Parquet data file validation

## Maintenance & Verification Scripts

- `scripts/iceberg/init_catalog.py`: Initialize catalog namespaces and tables
- `scripts/iceberg/create_bronze_table.py`: Create/update Bronze table definition
- `scripts/iceberg/verify_bronze_table.py`: Verify Bronze table schema, Parquet format, and metadata
- `scripts/iceberg/test_flink_write_read.sql`: Flink SQL write and read-back test
