"""Data models for IceStream Schema Versioning & Compatibility Engine."""

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Classification(str, Enum):
    """Schema compatibility classification."""

    COMPATIBLE = "COMPATIBLE"
    BREAKING = "BREAKING"


class Severity(str, Enum):
    """Severity of a detected schema change."""

    INFO = "INFO"
    WARNING = "WARNING"
    BREAKING = "BREAKING"
    CRITICAL = "CRITICAL"


class ChangeType(str, Enum):
    """Specific change types detected during schema comparison."""

    FIELD_ADDED = "FIELD_ADDED"
    FIELD_REMOVED = "FIELD_REMOVED"
    FIELD_TYPE_CHANGED = "FIELD_TYPE_CHANGED"
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

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "name": self.name,
            "type": self.type,
            "required": self.required,
        }
        if self.enum is not None:
            result["enum"] = list(self.enum)
        return result

    @classmethod
    def from_dict(cls, name: str, d: Dict[str, Any]) -> "FieldSchema":
        return cls(
            name=name,
            type=d.get("type", "string"),
            required=d.get("required", True),
            enum=d.get("enum"),
        )


@dataclass
class EventSchema:
    """Representation of a full versioned event schema."""

    schema_version: str
    fields: Dict[str, FieldSchema]
    description: Optional[str] = None

    def get_field(self, name: str) -> Optional[FieldSchema]:
        return self.fields.get(name)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "description": self.description,
            "fields": {
                name: field_obj.to_dict() for name, field_obj in self.fields.items()
            },
        }


@dataclass
class SchemaChange:
    """Details of a single change detected between two schema versions."""

    change_type: ChangeType
    field: str
    old_value: Optional[Any]
    new_value: Optional[Any]
    classification: Classification
    severity: Severity
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "change_type": self.change_type.value if isinstance(self.change_type, Enum) else str(self.change_type),
            "field": self.field,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "classification": self.classification.value if isinstance(self.classification, Enum) else str(self.classification),
            "severity": self.severity.value if isinstance(self.severity, Enum) else str(self.severity),
            "description": self.description,
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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "compatible": self.compatible,
            "classification": self.classification.value if isinstance(self.classification, Enum) else str(self.classification),
            "old_version": self.old_version,
            "new_version": self.new_version,
            "summary": self.summary,
            "changes": [c.to_dict() for c in self.changes],
        }
