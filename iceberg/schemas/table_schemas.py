"""
IceStream Apache Iceberg Table Schemas
"""
from pyiceberg.schema import Schema
from pyiceberg.types import (
    NestedField,
    StringType,
    IntegerType,
    DoubleType,
    DecimalType,
    TimestampType,
)

# ------------------------------------------------------------------------------
# Bronze Layer: Raw events as received from streaming pipeline (Day 10 Contract)
# ------------------------------------------------------------------------------
BRONZE_CHECKOUT_EVENTS_SCHEMA = Schema(
    NestedField(1, "event_id", StringType(), required=False),
    NestedField(2, "event_time", TimestampType(), required=False),
    NestedField(3, "customer_id", StringType(), required=False),
    NestedField(4, "session_id", StringType(), required=False),
    NestedField(5, "order_id", StringType(), required=False),
    NestedField(6, "product_id", StringType(), required=False),
    NestedField(7, "amount", DecimalType(18, 2), required=False),
    NestedField(8, "currency", StringType(), required=False),
    NestedField(9, "payment_method", StringType(), required=False),
    NestedField(10, "payment_status", StringType(), required=False),
    NestedField(11, "device", StringType(), required=False),
    NestedField(12, "country", StringType(), required=False),
    NestedField(13, "source_version", StringType(), required=False),
    NestedField(14, "ingestion_time", TimestampType(), required=False),
)

BRONZE_TABLE_PROPERTIES = {
    "write.format.default": "parquet",
    "format-version": "2",
}


# ------------------------------------------------------------------------------
# Silver Layer: Validated/cleaned events ready for analytics
# ------------------------------------------------------------------------------
SILVER_VALID_CHECKOUT_EVENTS_SCHEMA = Schema(
    NestedField(1, "event_id", StringType(), required=True),
    NestedField(2, "event_time", StringType(), required=True),
    NestedField(3, "event_type", StringType(), required=False),
    NestedField(4, "customer_id", StringType(), required=False),
    NestedField(5, "session_id", StringType(), required=False),
    NestedField(6, "order_id", StringType(), required=False),
    NestedField(7, "product_id", StringType(), required=False),
    NestedField(8, "quantity", IntegerType(), required=False),
    NestedField(9, "unit_price", DoubleType(), required=False),
    NestedField(10, "amount", DoubleType(), required=False),
    NestedField(11, "currency", StringType(), required=False),
    NestedField(12, "payment_method", StringType(), required=False),
    NestedField(13, "payment_status", StringType(), required=False),
    NestedField(14, "device", StringType(), required=False),
    NestedField(15, "country", StringType(), required=False),
    NestedField(16, "source", StringType(), required=False),
    NestedField(17, "source_version", StringType(), required=False),
    NestedField(18, "processed_at", StringType(), required=False),
    NestedField(19, "quality_score", DoubleType(), required=False),
)

# ------------------------------------------------------------------------------
# Quarantine Layer: Invalid or malformed events isolated for investigation
# ------------------------------------------------------------------------------
QUARANTINE_INVALID_CHECKOUT_EVENTS_SCHEMA = Schema(
    NestedField(1, "event_id", StringType(), required=False),
    NestedField(2, "event_time", StringType(), required=False),
    NestedField(3, "raw_payload", StringType(), required=True),
    NestedField(4, "failure_reason", StringType(), required=True),
    NestedField(5, "failure_type", StringType(), required=False),
    NestedField(6, "schema_version", StringType(), required=False),
    NestedField(7, "detected_at", StringType(), required=False),
    NestedField(8, "pipeline_stage", StringType(), required=False),
)

# ------------------------------------------------------------------------------
# Audit Layer: Pipeline quality results, incidents, and operational audit log
# ------------------------------------------------------------------------------
AUDIT_DATA_QUALITY_RESULTS_SCHEMA = Schema(
    NestedField(1, "check_id", StringType(), required=True),
    NestedField(2, "event_id", StringType(), required=False),
    NestedField(3, "check_name", StringType(), required=True),
    NestedField(4, "status", StringType(), required=True),
    NestedField(5, "severity", StringType(), required=False),
    NestedField(6, "failure_reason", StringType(), required=False),
    NestedField(7, "observed_at", StringType(), required=True),
    NestedField(8, "pipeline_stage", StringType(), required=False),
)
