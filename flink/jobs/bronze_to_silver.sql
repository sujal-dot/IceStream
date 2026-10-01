-- ==============================================================================
-- IceStream — Flink Bronze → Silver Validation Pipeline
-- Reads committed bronze records, applies quality routing, writes valid events
-- to silver.valid_checkout_events (invalid records are skipped — they were
-- already quarantined by the quality engine via the Python backend).
-- ==============================================================================

-- 1. Re-use the Iceberg REST Catalog (already registered by bronze job; use IF NOT EXISTS)
CREATE CATALOG IF NOT EXISTS icestream WITH (
  'type'='iceberg',
  'catalog-type'='rest',
  'uri'='http://iceberg-rest:8181',
  'warehouse'='s3://warehouse/',
  'io-impl'='org.apache.iceberg.aws.s3.S3FileIO',
  's3.endpoint'='http://minio:9000',
  's3.path-style-access'='true',
  's3.region'='us-east-1',
  'client.region'='us-east-1',
  's3.access-key-id'='${MINIO_ROOT_USER}',
  's3.secret-access-key'='${MINIO_ROOT_PASSWORD}'
);

USE CATALOG icestream;

-- 2. Ensure Silver namespace and table exist
CREATE DATABASE IF NOT EXISTS silver;
USE silver;

CREATE TABLE IF NOT EXISTS valid_checkout_events (
  event_id        STRING,
  event_time      TIMESTAMP(3),
  customer_id     STRING,
  session_id      STRING,
  order_id        STRING,
  product_id      STRING,
  amount          DECIMAL(18, 2),
  currency        STRING,
  payment_method  STRING,
  payment_status  STRING,
  device          STRING,
  country         STRING,
  source_version  STRING,
  ingestion_time  TIMESTAMP(3),
  silver_time     TIMESTAMP(3)
);

-- 3. Streaming settings
SET 'execution.runtime-mode' = 'streaming';
SET 'table.dml-sync' = 'false';
SET 'execution.checkpointing.interval' = '10000ms';
SET 'execution.checkpointing.mode' = 'EXACTLY_ONCE';
SET 'execution.checkpointing.timeout' = '60000ms';
SET 'state.checkpoints.dir' = 's3://checkpoints/flink/silver/';
SET 'state.backend' = 'filesystem';
SET 'restart-strategy.type' = 'fixed-delay';
SET 'restart-strategy.fixed-delay.attempts' = '3';
SET 'restart-strategy.fixed-delay.delay' = '10s';
SET 'table.exec.sink.not-null-enforcer' = 'DROP';

-- 4. Define Kafka source for validated events (checkout-valid topic populated by
--    the quality engine backend when events pass all rules)
USE CATALOG default_catalog;
CREATE DATABASE IF NOT EXISTS default_db;
USE default_db;

CREATE TABLE IF NOT EXISTS kafka_valid_events (
  event_id       STRING,
  event_time     STRING,
  customer_id    STRING,
  session_id     STRING,
  order_id       STRING,
  product_id     STRING,
  amount         DOUBLE,
  currency       STRING,
  payment_method STRING,
  payment_status STRING,
  device         STRING,
  country        STRING,
  source_version STRING,
  event_time_ts AS TO_TIMESTAMP(SUBSTRING(event_time, 1, 19), 'yyyy-MM-dd''T''HH:mm:ss'),
  WATERMARK FOR event_time_ts AS event_time_ts - INTERVAL '10' SECOND
) WITH (
  'connector' = 'kafka',
  'topic' = 'checkout-valid',
  'properties.bootstrap.servers' = 'kafka:29092',
  'properties.group.id' = 'icestream-flink-silver',
  'properties.auto.offset.reset' = 'earliest',
  'properties.enable.auto.commit' = 'true',
  'scan.startup.mode' = 'group-offsets',
  'format' = 'json',
  'json.fail-on-missing-field' = 'false',
  'json.ignore-parse-errors' = 'true'
);

-- 5. Stream validated events from checkout-valid → silver table
INSERT INTO icestream.silver.valid_checkout_events
SELECT
  event_id,
  event_time_ts                  AS event_time,
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
  LOCALTIMESTAMP                 AS ingestion_time,
  LOCALTIMESTAMP                 AS silver_time
FROM default_catalog.default_db.kafka_valid_events
WHERE event_id IS NOT NULL
  AND amount > 0
  AND currency IN ('USD', 'EUR', 'GBP', 'INR', 'JPY', 'CAD', 'AUD')
  AND payment_status IN ('SUCCESS', 'PENDING', 'FAILED', 'REFUNDED');
