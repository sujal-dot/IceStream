"""IceStream Schema Versioning & Compatibility Package."""

from schema.compatibility import check_compatibility, is_type_compatible
from schema.loader import SchemaValidationError, load_schema, validate_schema_dict
from schema.models import (
    ChangeType,
    Classification,
    CompatibilityResult,
    EventSchema,
    FieldSchema,
    SchemaChange,
    Severity,
)
from schema.registry import SchemaRegistry

__all__ = [
    "EventSchema",
    "FieldSchema",
    "SchemaChange",
    "CompatibilityResult",
    "Classification",
    "Severity",
    "ChangeType",
    "SchemaValidationError",
    "load_schema",
    "validate_schema_dict",
    "check_compatibility",
    "is_type_compatible",
    "SchemaRegistry",
]
