"""
IceStream Day 11 — Real-Time Kafka -> Flink -> Iceberg Bronze Pipeline Specification & Runner

Modular PyFlink / Flink SQL pipeline definition for Bronze stream ingestion.
Components:
- KafkaSourceConfig: Kafka source endpoint, topic, and consumer group configuration.
- EventDeserializerConfig: JSON parsing & fault tolerance settings.
- EventMapperConfig: Data type coercion, watermark delay, and ingestion timestamp derivation.
- IcebergSinkConfig: Iceberg catalog URI, warehouse, and table mapping.
- FlinkBronzePipeline: Generates SQL DDL/DML and manages Flink job specifications.
"""

import json
import os
import sys
import time
import urllib.request
import urllib.parse
from dataclasses import dataclass
from typing import Dict, Any, Optional, List


@dataclass
class KafkaSourceConfig:
    bootstrap_servers: str = "kafka:29092"
    topic: str = "checkout-events"
    consumer_group: str = "icestream-flink-bronze"
    startup_mode: str = "latest-offset"


@dataclass
class EventDeserializerConfig:
    format: str = "json"
    fail_on_missing_field: bool = False
    ignore_parse_errors: bool = True


@dataclass
class EventMapperConfig:
    watermark_delay_seconds: int = 5
    source_time_format: str = "yyyy-MM-dd'T'HH:mm:ss"


@dataclass
class IcebergSinkConfig:
    catalog_name: str = "icestream"
    catalog_uri: str = "http://iceberg-rest:8181"
    warehouse: str = "s3://warehouse/"
    target_table: str = "icestream.bronze.checkout_events"
    checkpoint_interval_ms: int = 30000
    checkpoint_dir: str = "s3://checkpoints/flink/bronze/"
    state_backend: str = "filesystem"
    restart_attempts: int = 3
    restart_delay_seconds: int = 10


class FlinkBronzePipeline:
    """Logical representation of the Kafka -> Flink -> Iceberg Bronze Pipeline."""

    def __init__(
        self,
        kafka_config: Optional[KafkaSourceConfig] = None,
        deserializer_config: Optional[EventDeserializerConfig] = None,
        mapper_config: Optional[EventMapperConfig] = None,
        iceberg_config: Optional[IcebergSinkConfig] = None,
    ):
        self.kafka_config = kafka_config or KafkaSourceConfig()
        self.deserializer_config = deserializer_config or EventDeserializerConfig()
        self.mapper_config = mapper_config or EventMapperConfig()
        self.iceberg_config = iceberg_config or IcebergSinkConfig()

    def generate_sql_statement(self) -> str:
        """Generate the complete Flink SQL execution script for the pipeline."""
        sql = f"""-- IceStream Bronze Pipeline Job SQL
CREATE CATALOG {self.iceberg_config.catalog_name} WITH (
  'type'='iceberg',
  'catalog-type'='rest',
  'uri'='{self.iceberg_config.catalog_uri}',
  'warehouse'='{self.iceberg_config.warehouse}',
  'io-impl'='org.apache.iceberg.aws.s3.S3FileIO',
  's3.endpoint'='http://minio:9000',
  's3.path-style-access'='true',
  's3.region'='us-east-1',
  'client.region'='us-east-1',
  's3.access-key-id'='icestream_minio',
  's3.secret-access-key'='icestream_minio_secret'
);

USE CATALOG {self.iceberg_config.catalog_name};
CREATE DATABASE IF NOT EXISTS bronze;
USE bronze;

CREATE TABLE IF NOT EXISTS checkout_events (
  event_id STRING,
  event_time TIMESTAMP(3),
  customer_id STRING,
  session_id STRING,
  order_id STRING,
  product_id STRING,
  amount DECIMAL(18, 2),
  currency STRING,
  payment_method STRING,
  payment_status STRING,
  device STRING,
  country STRING,
  source_version STRING,
  ingestion_time TIMESTAMP(3)
);

SET 'execution.runtime-mode' = 'streaming';
SET 'table.dml-sync' = 'false';
SET 'execution.checkpointing.interval' = '{self.iceberg_config.checkpoint_interval_ms}ms';
SET 'execution.checkpointing.mode' = 'EXACTLY_ONCE';
SET 'execution.checkpointing.timeout' = '60000ms';
SET 'execution.checkpointing.min-pause' = '500ms';
SET 'execution.checkpointing.max-concurrent-checkpoints' = '1';
SET 'state.checkpoints.dir' = '{self.iceberg_config.checkpoint_dir}';
SET 'state.backend' = '{self.iceberg_config.state_backend}';
SET 'restart-strategy.type' = 'fixed-delay';
SET 'restart-strategy.fixed-delay.attempts' = '{self.iceberg_config.restart_attempts}';
SET 'restart-strategy.fixed-delay.delay' = '{self.iceberg_config.restart_delay_seconds}s';
SET 'table.exec.sink.not-null-enforcer' = 'DROP';

-- 4. Define Kafka Source Table in default_catalog
USE CATALOG default_catalog;
CREATE DATABASE IF NOT EXISTS default_db;
USE default_db;

CREATE TABLE IF NOT EXISTS kafka_checkout_events (
  event_id STRING,
  event_time STRING,
  customer_id STRING,
  session_id STRING,
  order_id STRING,
  product_id STRING,
  amount DOUBLE,
  currency STRING,
  payment_method STRING,
  payment_status STRING,
  device STRING,
  country STRING,
  source_version STRING,
  event_time_ts AS TO_TIMESTAMP(SUBSTRING(event_time, 1, 19), '{self.mapper_config.source_time_format}'),
  WATERMARK FOR event_time_ts AS event_time_ts - INTERVAL '{self.mapper_config.watermark_delay_seconds}' SECOND
) WITH (
  'connector' = 'kafka',
  'topic' = '{self.kafka_config.topic}',
  'properties.bootstrap.servers' = '{self.kafka_config.bootstrap_servers}',
  'properties.group.id' = '{self.kafka_config.consumer_group}',
  'scan.startup.mode' = '{self.kafka_config.startup_mode}',
  'format' = '{self.deserializer_config.format}',
  'json.fail-on-missing-field' = '{"true" if self.deserializer_config.fail_on_missing_field else "false"}',
  'json.ignore-parse-errors' = '{"true" if self.deserializer_config.ignore_parse_errors else "false"}'
);

INSERT INTO {self.iceberg_config.target_table}
SELECT
  event_id,
  event_time_ts AS event_time,
  customer_id,
  session_id,
  order_id,
  product_id,
  CAST(amount AS DECIMAL(18, 2)) AS amount,
  currency,
  payment_method,
  payment_status,
  device,
  country,
  source_version,
  LOCALTIMESTAMP AS ingestion_time
FROM default_catalog.default_db.kafka_checkout_events
WHERE event_id IS NOT NULL;
"""
        return sql


def get_active_flink_jobs(flink_url: str = "http://localhost:8081") -> List[Dict[str, Any]]:
    """Retrieve active Flink jobs from the JobManager REST API."""
    try:
        req = urllib.request.urlopen(f"{flink_url}/jobs/overview", timeout=5)
        data = json.loads(req.read().decode("utf-8"))
        return data.get("jobs", [])
    except Exception:
        return []


def get_job_checkpoints(job_id: str, flink_url: str = "http://localhost:8081") -> Dict[str, Any]:
    """Retrieve checkpoint details for a specific Flink job from REST API."""
    try:
        req = urllib.request.urlopen(f"{flink_url}/jobs/{job_id}/checkpoints", timeout=5)
        return json.loads(req.read().decode("utf-8"))
    except Exception:
        return {}


if __name__ == "__main__":
    pipeline = FlinkBronzePipeline()
    print("========================================")
    print("IceStream Bronze Pipeline Spec")
    print("========================================")
    print(f"Topic:          {pipeline.kafka_config.topic}")
    print(f"Consumer Group: {pipeline.kafka_config.consumer_group}")
    print(f"Target Table:   {pipeline.iceberg_config.target_table}")
    print(f"Checkpoint Dir: {pipeline.iceberg_config.checkpoint_dir}")
    print("========================================")
    print("\nGenerated SQL:")
    print(pipeline.generate_sql_statement())
