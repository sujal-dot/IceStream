-- Day 10 Flink SQL Insert & Read-Back Test for icestream.bronze.checkout_events
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

SET 'execution.runtime-mode' = 'batch';
SET 'sql-client.execution.result-mode' = 'tableau';

INSERT INTO checkout_events VALUES 
  ('evt_day10_001', TIMESTAMP '2026-08-20 10:30:21', 'CUS10001', 'SES10001', 'ORD10001', 'PROD001', 1499.00, 'INR', 'UPI', 'SUCCESS', 'mobile', 'IN', 'v1', TIMESTAMP '2026-08-20 10:30:23'),
  ('evt_day10_002', TIMESTAMP '2026-08-20 10:31:00', 'CUS10002', 'SES10002', 'ORD10002', 'PROD002', 2999.50, 'INR', 'CREDIT_CARD', 'SUCCESS', 'desktop', 'IN', 'v1', TIMESTAMP '2026-08-20 10:31:02'),
  ('evt_day10_003', TIMESTAMP '2026-08-20 10:32:00', CAST(NULL AS STRING), 'SES10003', 'ORD10003', 'PROD003', CAST(NULL AS DECIMAL(18,2)), 'INR', 'UPI', 'FAILED', 'mobile', 'IN', 'v1', TIMESTAMP '2026-08-20 10:32:02'),
  ('evt_day10_001', TIMESTAMP '2026-08-20 10:30:21', 'CUS10001', 'SES10001', 'ORD10001', 'PROD001', 1499.00, 'INR', 'UPI', 'SUCCESS', 'mobile', 'IN', 'v1', TIMESTAMP '2026-08-20 10:30:25');

SELECT COUNT(*) AS total_events FROM checkout_events;

SELECT * FROM checkout_events LIMIT 10;

SELECT 
    COUNT(*) AS total_events,
    COUNT(event_id) AS event_ids,
    COUNT(event_time) AS event_times,
    COUNT(customer_id) AS customer_ids,
    COUNT(amount) AS amounts
FROM checkout_events;
