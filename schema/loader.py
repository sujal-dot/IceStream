"""Schema file loader and validation module for IceStream."""

import json
from pathlib import Path
from typing import Any, Dict, Union

from schema.models import EventSchema, FieldSchema, SUPPORTED_TYPES


class SchemaValidationError(Exception):
    """Raised when a schema file fails validation rules."""

    pass


def validate_schema_dict(data: Dict[str, Any], source_name: str = "schema") -> EventSchema:
    """Validate a raw schema dictionary and parse it into an EventSchema instance.

    Raises SchemaValidationError on any malformed or invalid definition.
    """
    if not isinstance(data, dict):
        raise SchemaValidationError(f"Invalid schema in '{source_name}': expected JSON object, got {type(data).__name__}")

    schema_version = data.get("schema_version")
    if not schema_version or not isinstance(schema_version, str):
        raise SchemaValidationError(
            f"Invalid schema in '{source_name}': missing or invalid 'schema_version' string"
        )

    fields_raw = data.get("fields")
    if fields_raw is None or not isinstance(fields_raw, dict):
        raise SchemaValidationError(
            f"Invalid schema in '{source_name}': missing or invalid 'fields' map"
        )

    parsed_fields: Dict[str, FieldSchema] = {}

    for field_name, field_def in fields_raw.items():
        if not isinstance(field_name, str) or not field_name.strip():
            raise SchemaValidationError(
                f"Invalid schema in '{source_name}': field names must be non-empty strings"
            )

        if not isinstance(field_def, dict):
            raise SchemaValidationError(
                f"Invalid schema in '{source_name}': definition for field '{field_name}' must be an object"
            )

        field_type = field_def.get("type")
        if not field_type or not isinstance(field_type, str):
            raise SchemaValidationError(
                f"Invalid schema in '{source_name}': field '{field_name}' missing string 'type'"
            )

        if field_type not in SUPPORTED_TYPES:
            sorted_types = ", ".join(sorted(SUPPORTED_TYPES))
            raise SchemaValidationError(
                f"Invalid schema in '{source_name}': field '{field_name}' has unsupported type '{field_type}'. "
                f"Supported types: {sorted_types}"
            )

        required = field_def.get("required", True)
        if not isinstance(required, bool):
            raise SchemaValidationError(
                f"Invalid schema in '{source_name}': field '{field_name}' 'required' attribute must be boolean"
            )

        enum_vals = field_def.get("enum")
        if enum_vals is not None:
            if not isinstance(enum_vals, list) or not enum_vals:
                raise SchemaValidationError(
                    f"Invalid schema in '{source_name}': field '{field_name}' 'enum' must be a non-empty list"
                )
            for item in enum_vals:
                if not isinstance(item, str):
                    raise SchemaValidationError(
                        f"Invalid schema in '{source_name}': field '{field_name}' enum items must be strings"
                    )

        parsed_fields[field_name] = FieldSchema(
            name=field_name,
            type=field_type,
            required=required,
            enum=enum_vals,
        )

    return EventSchema(
        schema_version=schema_version,
        fields=parsed_fields,
        description=data.get("description"),
    )


def load_schema(file_path: Union[str, Path]) -> EventSchema:
    """Load and validate an EventSchema from a JSON file path.

    Raises FileNotFoundError if file does not exist, or SchemaValidationError if invalid.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Schema file not found: {path.resolve()}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as err:
        raise SchemaValidationError(f"Invalid JSON in schema file '{path}': {err}") from err
    except Exception as err:
        raise SchemaValidationError(f"Failed to read schema file '{path}': {err}") from err

    return validate_schema_dict(data, source_name=str(path))
