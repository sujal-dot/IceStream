-- Day 9 Flink SQL Catalog Integration Test Script
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

SHOW DATABASES;

USE bronze;

SHOW TABLES;

DESCRIBE checkout_events;

-- Create temporary test table to verify Flink catalog write access (Step 23)
CREATE TABLE IF NOT EXISTS bronze.day9_flink_catalog_test (
    id STRING,
    test_val STRING
);

SHOW TABLES;
