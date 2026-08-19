# IceStream Installed Component Versions

This document records the exact versions of core infrastructure components, runtimes, and libraries used in the IceStream platform as of Day 9.

| Component | Version | Compatibility / Notes |
| :--- | :--- | :--- |
| **Apache Flink** | `1.18.1` | Scala 2.12 edition; base image `flink:1.18.1-scala_2.12-java11` |
| **Apache Iceberg** | `1.5.2` | REST Catalog specification; `iceberg-flink-runtime-1.18:1.5.2` |
| **PyIceberg** | `0.8.1` | Python Iceberg client library (`pyiceberg[s3fs,sql-postgres]`) |
| **Java** | `11.0.26` | OpenJDK 11 (Temurin-11.0.26+4) inside Flink runtime container |
| **Apache Kafka** | `3.7.0` | KRaft mode broker (`apache/kafka:3.7.0`) |
| **MinIO** | `RELEASE.2024-03-21T23-13-43Z` | S3-compatible object storage server |
| **PostgreSQL** | `16-alpine` | Metadata & incident database |
| **Python** | `3.10.13` | Platform runtime environment |

## Compatibility Matrix Note
- Flink 1.18.1 is fully compatible with Iceberg Flink connector version 1.5.2 (`iceberg-flink-runtime-1.18-1.5.2.jar`).
- PyIceberg 0.8.1 supports Iceberg REST catalog specification v1 and S3 filesystem access via `pyiceberg[s3fs]`.
