-- Day 9 Flink SQL Insert & Read-Back Test
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

SET 'sql-client.execution.result-mode' = 'tableau';

INSERT INTO checkout_events VALUES (
  'evt_day9_test_001',
  '2026-08-19T11:00:00Z',
  'checkout_completed',
  'cust_999',
  'sess_999',
  'ord_999',
  'prod_999',
  2,
  49.99,
  99.98,
  'USD',
  'credit_card',
  'completed',
  'desktop',
  'US',
  'web_store',
  'v1.0.0'
);

SELECT event_id, customer_id, amount, payment_status FROM checkout_events WHERE event_id = 'evt_day9_test_001';
