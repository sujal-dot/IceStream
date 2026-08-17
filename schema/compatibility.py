"""Schema Compatibility & Breaking Change Detection Engine for IceStream."""

from typing import Dict, List, Optional, Tuple

from schema.models import (
    ChangeType,
    Classification,
    CompatibilityResult,
    EventSchema,
    FieldSchema,
    SchemaChange,
    Severity,
)

# Type compatibility matrix for (old_type, new_type) -> is_compatible
TYPE_COMPATIBILITY_MATRIX: Dict[Tuple[str, str], bool] = {
    ("string", "string"): True,
    ("integer", "integer"): True,
    ("float", "float"): True,
    ("boolean", "boolean"): True,
    ("timestamp", "timestamp"): True,
    ("object", "object"): True,
    ("array", "array"): True,
    # Safe numeric promotion: integer -> float is compatible
    ("integer", "float"): True,
}


def is_type_compatible(old_type: str, new_type: str) -> bool:
    """Determine whether converting old_type to new_type is backward compatible."""
    return TYPE_COMPATIBILITY_MATRIX.get((old_type, new_type), False)


def check_compatibility(
    old_schema: EventSchema,
    new_schema: EventSchema,
) -> CompatibilityResult:
    """Compare an old EventSchema against a new EventSchema and classify compatibility.

    Returns a CompatibilityResult with detailed schema changes, individual change severity,
    and an overall COMPATIBLE or BREAKING classification.
    """
    changes: List[SchemaChange] = []
    has_breaking_change = False

    old_fields = old_schema.fields
    new_fields = new_schema.fields

    # 1. Check for removed fields (present in old, absent in new)
    for name, old_field in old_fields.items():
        if name not in new_fields:
            has_breaking_change = True
            req_str = "required" if old_field.required else "optional"
            changes.append(
                SchemaChange(
                    change_type=ChangeType.FIELD_REMOVED,
                    field=name,
                    old_value={"type": old_field.type, "required": old_field.required},
                    new_value=None,
                    classification=Classification.BREAKING,
                    severity=Severity.BREAKING,
                    description=f"Removed {req_str} field '{name}'",
                )
            )

    # 2. Check for added fields (absent in old, present in new)
    for name, new_field in new_fields.items():
        if name not in old_fields:
            if new_field.required:
                has_breaking_change = True
                changes.append(
                    SchemaChange(
                        change_type=ChangeType.FIELD_ADDED,
                        field=name,
                        old_value=None,
                        new_value={"type": new_field.type, "required": True},
                        classification=Classification.BREAKING,
                        severity=Severity.BREAKING,
                        description=f"Added required field '{name}' without default",
                    )
                )
            else:
                changes.append(
                    SchemaChange(
                        change_type=ChangeType.FIELD_ADDED,
                        field=name,
                        old_value=None,
                        new_value={"type": new_field.type, "required": False},
                        classification=Classification.COMPATIBLE,
                        severity=Severity.INFO,
                        description=f"Added optional field '{name}'",
                    )
                )

    # 3. Check existing fields present in both schemas
    for name, old_field in old_fields.items():
        if name in new_fields:
            new_field = new_fields[name]

            # Check type changes
            if old_field.type != new_field.type:
                compatible_type = is_type_compatible(old_field.type, new_field.type)
                if compatible_type:
                    changes.append(
                        SchemaChange(
                            change_type=ChangeType.FIELD_TYPE_CHANGED,
                            field=name,
                            old_value=old_field.type,
                            new_value=new_field.type,
                            classification=Classification.COMPATIBLE,
                            severity=Severity.INFO,
                            description=f"Safe type promotion for field '{name}' ({old_field.type} -> {new_field.type})",
                        )
                    )
                else:
                    has_breaking_change = True
                    changes.append(
                        SchemaChange(
                            change_type=ChangeType.FIELD_TYPE_CHANGED,
                            field=name,
                            old_value=old_field.type,
                            new_value=new_field.type,
                            classification=Classification.BREAKING,
                            severity=Severity.BREAKING,
                            description=f"Incompatible type change for field '{name}' ({old_field.type} -> {new_field.type})",
                        )
                    )

            # Check required flag changes
            if old_field.required != new_field.required:
                if not old_field.required and new_field.required:
                    # Optional -> Required (BREAKING)
                    has_breaking_change = True
                    changes.append(
                        SchemaChange(
                            change_type=ChangeType.FIELD_REQUIRED_CHANGED,
                            field=name,
                            old_value=old_field.required,
                            new_value=new_field.required,
                            classification=Classification.BREAKING,
                            severity=Severity.BREAKING,
                            description=f"Field '{name}' changed from optional to required",
                        )
                    )
                elif old_field.required and not new_field.required:
                    # Required -> Optional (COMPATIBLE)
                    changes.append(
                        SchemaChange(
                            change_type=ChangeType.FIELD_REQUIRED_CHANGED,
                            field=name,
                            old_value=old_field.required,
                            new_value=new_field.required,
                            classification=Classification.COMPATIBLE,
                            severity=Severity.INFO,
                            description=f"Field '{name}' relaxed from required to optional",
                        )
                    )

            # Check enum value compatibility
            if old_field.enum is not None or new_field.enum is not None:
                old_enum = set(old_field.enum) if old_field.enum else set()
                new_enum = set(new_field.enum) if new_field.enum else set()

                added_enum_vals = sorted(list(new_enum - old_enum))
                removed_enum_vals = sorted(list(old_enum - new_enum))

                if added_enum_vals:
                    changes.append(
                        SchemaChange(
                            change_type=ChangeType.ENUM_VALUE_ADDED,
                            field=name,
                            old_value=sorted(list(old_enum)),
                            new_value=sorted(list(new_enum)),
                            classification=Classification.COMPATIBLE,
                            severity=Severity.INFO,
                            description=f"Enum field '{name}' expanded with new value(s): {', '.join(added_enum_vals)}",
                        )
                    )

                if removed_enum_vals:
                    has_breaking_change = True
                    changes.append(
                        SchemaChange(
                            change_type=ChangeType.ENUM_VALUE_REMOVED,
                            field=name,
                            old_value=sorted(list(old_enum)),
                            new_value=sorted(list(new_enum)),
                            classification=Classification.BREAKING,
                            severity=Severity.BREAKING,
                            description=f"Enum field '{name}' removed value(s): {', '.join(removed_enum_vals)}",
                        )
                    )

    overall_classification = (
        Classification.BREAKING if has_breaking_change else Classification.COMPATIBLE
    )
    is_compatible = not has_breaking_change

    if not changes:
        summary = f"Schema {old_schema.schema_version} and {new_schema.schema_version} are identical."
    elif is_compatible:
        summary = f"Schema evolution from {old_schema.schema_version} to {new_schema.schema_version} is COMPATIBLE ({len(changes)} change(s) detected)."
    else:
        breaking_count = sum(1 for c in changes if c.classification == Classification.BREAKING)
        summary = f"Schema evolution from {old_schema.schema_version} to {new_schema.schema_version} is BREAKING ({breaking_count} breaking change(s) detected out of {len(changes)} total)."

    return CompatibilityResult(
        compatible=is_compatible,
        classification=overall_classification,
        old_version=old_schema.schema_version,
        new_version=new_schema.schema_version,
        changes=changes,
        summary=summary,
    )
