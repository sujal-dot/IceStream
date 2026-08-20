"""
Tests for IceStream Bronze Iceberg Table (icestream.bronze.checkout_events)
Covers unit tests (schema & configuration definitions) and integration tests (catalog connection,
MinIO storage, Parquet format, insert, read-back, NULL value handling, and ingestion timestamp).
"""
import pytest
import boto3
import io
import pyarrow.parquet as pq
from datetime import datetime
from decimal import Decimal

from iceberg.schemas.table_schemas import (
    BRONZE_CHECKOUT_EVENTS_SCHEMA,
    BRONZE_TABLE_PROPERTIES,
)
from iceberg.config.catalog import get_catalog, get_catalog_config


# ==============================================================================
# UNIT TESTS (No Docker / Infrastructure Dependency)
# ==============================================================================

def test_unit_bronze_schema_field_count():
    """Verify Bronze schema contains exactly 14 required contract fields."""
    fields = BRONZE_CHECKOUT_EVENTS_SCHEMA.fields
    assert len(fields) == 14


def test_unit_bronze_schema_column_names():
    """Verify Bronze schema field names match the contract."""
    field_names = [f.name for f in BRONZE_CHECKOUT_EVENTS_SCHEMA.fields]
    expected_names = [
        "event_id",
        "event_time",
        "customer_id",
        "session_id",
        "order_id",
        "product_id",
        "amount",
        "currency",
        "payment_method",
        "payment_status",
        "device",
        "country",
        "source_version",
        "ingestion_time",
    ]
    assert field_names == expected_names


def test_unit_bronze_schema_column_types():
    """Verify field types in the schema definition."""
    schema = {f.name: str(f.field_type).lower() for f in BRONZE_CHECKOUT_EVENTS_SCHEMA.fields}
    assert "string" in schema["event_id"]
    assert "timestamp" in schema["event_time"]
    assert "string" in schema["customer_id"]
    assert "decimal(18, 2)" in schema["amount"]
    assert "timestamp" in schema["ingestion_time"]


def test_unit_bronze_schema_nullability():
    """Verify all Bronze fields allow NULL values to support raw ingestion of fault-injected events."""
    for field in BRONZE_CHECKOUT_EVENTS_SCHEMA.fields:
        assert field.required is False, f"Field {field.name} should be optional (nullable) for raw Bronze storage"


def test_unit_bronze_table_properties():
    """Verify default table properties mandate Parquet and format version 2."""
    assert BRONZE_TABLE_PROPERTIES.get("write.format.default") == "parquet"
    assert BRONZE_TABLE_PROPERTIES.get("format-version") == "2"


# ==============================================================================
# INTEGRATION TESTS (Requires Running Infrastructure: MinIO, REST Catalog)
# ==============================================================================

def test_bronze_namespace_exists():
    """Verify 'bronze' namespace exists in the Iceberg catalog."""
    catalog = get_catalog()
    namespaces = [ns[0] for ns in catalog.list_namespaces() if ns]
    assert "bronze" in namespaces


def test_bronze_table_exists():
    """Verify 'bronze.checkout_events' table exists in the Iceberg catalog."""
    catalog = get_catalog()
    tables = [t[1] for t in catalog.list_tables("bronze")]
    assert "checkout_events" in tables


def test_bronze_schema():
    """Verify loaded table schema matches expectation."""
    catalog = get_catalog()
    table = catalog.load_table("bronze.checkout_events")
    field_names = [f.name for f in table.schema().fields]
    assert len(field_names) == 14
    assert "ingestion_time" in field_names


def test_bronze_column_types():
    """Verify loaded table data types."""
    catalog = get_catalog()
    table = catalog.load_table("bronze.checkout_events")
    types = {f.name: str(f.field_type).lower() for f in table.schema().fields}
    assert "decimal(18, 2)" in types["amount"]
    assert "timestamp" in types["event_time"]
    assert "timestamp" in types["ingestion_time"]


def test_bronze_table_format():
    """Verify table property write format is Parquet."""
    catalog = get_catalog()
    table = catalog.load_table("bronze.checkout_events")
    write_format = table.properties.get("write.format.default", "parquet").lower()
    assert write_format == "parquet"


def test_bronze_table_location():
    """Verify table location is managed under MinIO warehouse."""
    catalog = get_catalog()
    table = catalog.load_table("bronze.checkout_events")
    location = table.location()
    assert "warehouse" in location and "bronze/checkout_events" in location


def test_bronze_read():
    """Verify reading back records from bronze.checkout_events."""
    catalog = get_catalog()
    table = catalog.load_table("bronze.checkout_events")
    scan = table.scan()
    arrow_table = scan.to_arrow()
    assert len(arrow_table) > 0, "Expected records in bronze.checkout_events"
    data = arrow_table.to_pydict()
    assert "evt_day10_001" in data["event_id"]


def test_bronze_null_value():
    """Verify Bronze table contains record with NULL value for fault injection compatibility."""
    catalog = get_catalog()
    table = catalog.load_table("bronze.checkout_events")
    arrow_table = table.scan().to_arrow()
    data = arrow_table.to_pydict()
    assert None in data["customer_id"] or None in data["amount"]


def test_bronze_ingestion_time():
    """Verify event_time and ingestion_time are distinct fields in Bronze."""
    catalog = get_catalog()
    table = catalog.load_table("bronze.checkout_events")
    arrow_table = table.scan().to_arrow()
    data = arrow_table.to_pydict()
    for ev_t, ing_t in zip(data["event_time"], data["ingestion_time"]):
        if ev_t and ing_t:
            assert isinstance(ev_t, datetime)
            assert isinstance(ing_t, datetime)


def test_parquet_files_created():
    """Verify physical Parquet files are generated in MinIO storage."""
    config = get_catalog_config(is_internal=False)
    s3 = boto3.client(
        "s3",
        endpoint_url=config["s3.endpoint"],
        aws_access_key_id=config["s3.access-key-id"],
        aws_secret_access_key=config["s3.secret-access-key"],
        region_name=config["s3.region"],
    )
    resp = s3.list_objects_v2(Bucket="warehouse", Prefix="bronze/checkout_events/data/")
    assert "Contents" in resp and len(resp["Contents"]) > 0, "No Parquet data files found in MinIO warehouse"
    parquet_key = resp["Contents"][0]["Key"]
    assert parquet_key.endswith(".parquet")

    # Inspect file format with PyArrow
    obj = s3.get_object(Bucket="warehouse", Key=parquet_key)
    parquet_file = pq.ParquetFile(io.BytesIO(obj["Body"].read()))
    assert parquet_file.metadata.num_rows > 0


def test_iceberg_metadata_created():
    """Verify Iceberg metadata.json files exist in MinIO storage."""
    config = get_catalog_config(is_internal=False)
    s3 = boto3.client(
        "s3",
        endpoint_url=config["s3.endpoint"],
        aws_access_key_id=config["s3.access-key-id"],
        aws_secret_access_key=config["s3.secret-access-key"],
        region_name=config["s3.region"],
    )
    resp = s3.list_objects_v2(Bucket="warehouse", Prefix="bronze/checkout_events/metadata/")
    assert "Contents" in resp and len(resp["Contents"]) > 0, "No Iceberg metadata files found in MinIO"
    keys = [item["Key"] for item in resp["Contents"]]
    has_metadata_json = any(k.endswith(".metadata.json") for k in keys)
    assert has_metadata_json, "Expected .metadata.json in MinIO metadata directory"
