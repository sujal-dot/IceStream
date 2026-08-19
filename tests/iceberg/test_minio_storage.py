"""
Integration Tests for MinIO Storage backing Iceberg Tables
"""
import pytest
import boto3
from iceberg.config.catalog import get_catalog_config


def test_minio_warehouse_metadata():
    config = get_catalog_config(is_internal=False)
    s3 = boto3.client(
        "s3",
        endpoint_url=config["s3.endpoint"],
        aws_access_key_id=config["s3.access-key-id"],
        aws_secret_access_key=config["s3.secret-access-key"],
        region_name=config["s3.region"],
    )
    
    resp = s3.list_objects_v2(Bucket="warehouse", Prefix="bronze/checkout_events/metadata/")
    assert "Contents" in resp, "No metadata files found in MinIO warehouse for bronze.checkout_events"
    metadata_files = [obj["Key"] for obj in resp["Contents"] if obj["Key"].endswith(".metadata.json")]
    assert len(metadata_files) > 0, "No .metadata.json file found in bronze table location"
