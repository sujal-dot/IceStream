"""Data models for IceStream Schema Versioning & Compatibility Engine."""

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Classification(str, Enum):
    """Schema compatibility classification."""

    COMPATIBLE = "COMPATIBLE"
    WARNING = "WARNING"
    BREAKING = "BREAKING"


class Severity(str, Enum):
    """Severity of a detected schema change."""

    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    BREAKING = "CRITICAL"


class ChangeType(str, Enum):
    """Specific change types detected during schema comparison."""

    MISSING_COLUMN = "MISSING_COLUMN"
    NEW_COLUMN = "NEW_COLUMN"
    TYPE_CHANGE = "TYPE_CHANGE"
    RENAMED_COLUMN = "RENAMED_COLUMN"
    REMOVED_COLUMN = "REMOVED_COLUMN"
    SCHEMA_VERSION_UNKNOWN = "SCHEMA_VERSION_UNKNOWN"
    SCHEMA_VERSION_MISSING = "SCHEMA_VERSION_MISSING"

    # Aliases for backwards compatibility with earlier tests
    FIELD_ADDED = "NEW_COLUMN"
    FIELD_REMOVED = "MISSING_COLUMN"
    FIELD_TYPE_CHANGED = "TYPE_CHANGE"
    FIELD_REQUIRED_CHANGED = "FIELD_REQUIRED_CHANGED"
    ENUM_VALUE_ADDED = "ENUM_VALUE_ADDED"
    ENUM_VALUE_REMOVED = "ENUM_VALUE_REMOVED"
    STRUCTURE_CHANGED = "STRUCTURE_CHANGED"


SUPPORTED_TYPES = {
    "string",
    "integer",
    "float",
    "boolean",
    "timestamp",
    "object",
    "array",
}


@dataclass
class FieldSchema:
    """Definition of an individual field in an event schema."""

    name: str
    type: str
    required: bool = True
    enum: Optional[List[str]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def data_type(self) -> str:
        """Alias for type to conform with normalized schema model."""
        return self.type

    @property
    def nullable(self) -> bool:
        """Derived nullability property (nullable = not required)."""
        return not self.required

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "name": self.name,
            "type": self.type,
            "required": self.required,
            "nullable": self.nullable,
        }
        if self.enum is not None:
            result["enum"] = list(self.enum)
        if self.metadata:
            result["metadata"] = dict(self.metadata)
        return result

    @classmethod
    def from_dict(cls, name: str, d: Dict[str, Any]) -> "FieldSchema":
        return cls(
            name=name,
            type=d.get("type", d.get("data_type", "string")),
            required=d.get("required", not d.get("nullable", False)),
            enum=d.get("enum"),
            metadata=d.get("metadata", {}),
        )


# Alias SchemaField -> FieldSchema for Day 3 schema spec
SchemaField = FieldSchema


@dataclass
class EventSchema:
    """Representation of a full versioned event schema."""

    schema_version: str
    fields: Dict[str, FieldSchema]
    description: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def version(self) -> str:
        """Alias for schema_version."""
        return self.schema_version

    def get_field(self, name: str) -> Optional[FieldSchema]:
        return self.fields.get(name)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "description": self.description,
            "fields": {
                name: field_obj.to_dict() for name, field_obj in self.fields.items()
            },
            "metadata": dict(self.metadata),
        }


# Alias SchemaDefinition -> EventSchema
SchemaDefinition = EventSchema


@dataclass
class SchemaChange:
    """Details of a single change detected between two schema versions."""

    change_type: ChangeType
    field: str
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None
    expected_type: Optional[str] = None
    actual_type: Optional[str] = None
    classification: Classification = Classification.COMPATIBLE
    severity: Severity = Severity.INFO
    description: str = ""
    message: Optional[str] = None

    def __post_init__(self):
        if not self.message:
            self.message = self.description or f"{self.change_type.value} on {self.field}"
        if not self.description:
            self.description = self.message

    def to_dict(self) -> Dict[str, Any]:
        return {
            "change_type": self.change_type.value if isinstance(self.change_type, Enum) else str(self.change_type),
            "field": self.field,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "expected_type": self.expected_type,
            "actual_type": self.actual_type,
            "classification": self.classification.value if isinstance(self.classification, Enum) else str(self.classification),
            "severity": self.severity.value if isinstance(self.severity, Enum) else str(self.severity),
            "description": self.description,
            "message": self.message,
        }


@dataclass
class CompatibilityResult:
    """Overall result of comparing two schema versions."""

    compatible: bool
    classification: Classification
    old_version: str
    new_version: str
    changes: List[SchemaChange] = field(default_factory=list)
    summary: str = ""
    overall_severity: Severity = Severity.INFO

    @property
    def expected_version(self) -> str:
        return self.old_version

    @property
    def actual_version(self) -> str:
        return self.new_version

    def to_dict(self) -> Dict[str, Any]:
        return {
            "compatible": self.compatible,
            "classification": self.classification.value if isinstance(self.classification, Enum) else str(self.classification),
            "expected_version": self.expected_version,
            "actual_version": self.actual_version,
            "old_version": self.old_version,
            "new_version": self.new_version,
            "overall_severity": self.overall_severity.value if isinstance(self.overall_severity, Enum) else str(self.overall_severity),
            "summary": self.summary,
            "changes": [c.to_dict() for c in self.changes],
        }


# Alias SchemaDiff -> CompatibilityResult
SchemaDiff = CompatibilityResult

