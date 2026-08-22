-- ==============================================================================
-- IceStream Day 11 — Real-Time Kafka -> Flink -> Iceberg Bronze Pipeline Job
-- ==============================================================================

-- 1. Configure Iceberg REST Catalog
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
CREATE DATABASE IF NOT EXISTS bronze;
USE bronze;

-- 2. Ensure Bronze Target Table Definition in Iceberg Catalog
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

-- 3. Configure Streaming Runtime, Checkpointing & Restart Strategy Settings
SET 'execution.runtime-mode' = 'streaming';
SET 'table.dml-sync' = 'false';
SET 'execution.checkpointing.interval' = '30000ms';
SET 'execution.checkpointing.mode' = 'EXACTLY_ONCE';
SET 'execution.checkpointing.timeout' = '60000ms';
SET 'execution.checkpointing.min-pause' = '500ms';
SET 'execution.checkpointing.max-concurrent-checkpoints' = '1';
SET 'state.checkpoints.dir' = 's3://checkpoints/flink/bronze/';
SET 'state.backend' = 'filesystem';
SET 'restart-strategy.type' = 'fixed-delay';
SET 'restart-strategy.fixed-delay.attempts' = '3';
SET 'restart-strategy.fixed-delay.delay' = '10s';
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
  event_time_ts AS TO_TIMESTAMP(SUBSTRING(event_time, 1, 19), 'yyyy-MM-dd''T''HH:mm:ss'),
  WATERMARK FOR event_time_ts AS event_time_ts - INTERVAL '5' SECOND
) WITH (
  'connector' = 'kafka',
  'topic' = 'checkout-events',
  'properties.bootstrap.servers' = 'kafka:29092',
  'properties.group.id' = 'icestream-flink-bronze',
  'scan.startup.mode' = 'latest-offset',
  'format' = 'json',
  'json.fail-on-missing-field' = 'false',
  'json.ignore-parse-errors' = 'true'
);

-- 5. Execute Continuous Streaming Ingestion into Iceberg Bronze Table
INSERT INTO icestream.bronze.checkout_events
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
