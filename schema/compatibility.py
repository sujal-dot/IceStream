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
    # Safe numeric promotions
    ("integer", "long"): True,
    ("integer", "float"): True,
    ("float", "double"): True,
}


def is_type_compatible(old_type: str, new_type: str) -> bool:
    """Determine whether converting old_type to new_type is backward compatible."""
    return TYPE_COMPATIBILITY_MATRIX.get((old_type, new_type), False)


class SchemaComparator:
    """Engine for comparing two SchemaDefinition / EventSchema objects."""

    def __init__(self, rename_map: Optional[Dict[str, str]] = None, policy: Optional[Dict] = None):
        self.rename_map = rename_map or {}
        self.policy = policy or {}

    def compare(
        self,
        expected_schema: EventSchema,
        actual_schema: EventSchema,
        rename_map: Optional[Dict[str, str]] = None,
    ) -> CompatibilityResult:
        """Compare expected_schema and actual_schema to identify all schema drift changes.

        Returns a CompatibilityResult (SchemaDiff) containing all detected SchemaChange items.
        """
        active_rename_map = rename_map if rename_map is not None else self.rename_map
        changes: List[SchemaChange] = []

        expected_fields = expected_schema.fields
        actual_fields = actual_schema.fields

        matched_actual_fields = set()

        # 1. Inspect fields present in expected schema
        for name, expected_field in expected_fields.items():
            mapped_name = active_rename_map.get(name)

            if mapped_name and mapped_name in actual_fields:
                # Renamed column detected via explicit mapping
                actual_field = actual_fields[mapped_name]
                matched_actual_fields.add(mapped_name)

                changes.append(
                    SchemaChange(
                        change_type=ChangeType.RENAMED_COLUMN,
                        field=name,
                        old_value=name,
                        new_value=mapped_name,
                        expected_type=expected_field.type,
                        actual_type=actual_field.type,
                        classification=Classification.WARNING,
                        severity=Severity.WARNING,
                        description=f"Column '{name}' renamed to '{mapped_name}'",
                        message=f"WARNING: column '{name}' renamed to '{mapped_name}'",
                    )
                )

                # Also check type change on renamed column if types differ
                if expected_field.type != actual_field.type:
                    if is_type_compatible(expected_field.type, actual_field.type):
                        changes.append(
                            SchemaChange(
                                change_type=ChangeType.TYPE_CHANGE,
                                field=mapped_name,
                                old_value=expected_field.type,
                                new_value=actual_field.type,
                                expected_type=expected_field.type,
                                actual_type=actual_field.type,
                                classification=Classification.COMPATIBLE,
                                severity=Severity.INFO,
                                description=f"Safe type promotion for '{mapped_name}' ({expected_field.type} -> {actual_field.type})",
                                message=f"INFO: safe type promotion for '{mapped_name}' ({expected_field.type} -> {actual_field.type})",
                            )
                        )
                    else:
                        changes.append(
                            SchemaChange(
                                change_type=ChangeType.TYPE_CHANGE,
                                field=mapped_name,
                                old_value=expected_field.type,
                                new_value=actual_field.type,
                                expected_type=expected_field.type,
                                actual_type=actual_field.type,
                                classification=Classification.BREAKING,
                                severity=Severity.CRITICAL,
                                description=f"CRITICAL SCHEMA DRIFT: {mapped_name} changed from {expected_field.type} to {actual_field.type}",
                                message=f"CRITICAL SCHEMA DRIFT: {mapped_name} changed from {expected_field.type} to {actual_field.type}",
                            )
                        )

            elif name in actual_fields:
                # Field present in both schemas
                matched_actual_fields.add(name)
                actual_field = actual_fields[name]

                # Check type changes
                if expected_field.type != actual_field.type:
                    if is_type_compatible(expected_field.type, actual_field.type):
                        changes.append(
                            SchemaChange(
                                change_type=ChangeType.TYPE_CHANGE,
                                field=name,
                                old_value=expected_field.type,
                                new_value=actual_field.type,
                                expected_type=expected_field.type,
                                actual_type=actual_field.type,
                                classification=Classification.COMPATIBLE,
                                severity=Severity.INFO,
                                description=f"Safe type promotion for field '{name}' ({expected_field.type} -> {actual_field.type})",
                                message=f"INFO: safe type promotion for field '{name}' ({expected_field.type} -> {actual_field.type})",
                            )
                        )
                    else:
                        changes.append(
                            SchemaChange(
                                change_type=ChangeType.TYPE_CHANGE,
                                field=name,
                                old_value=expected_field.type,
                                new_value=actual_field.type,
                                expected_type=expected_field.type,
                                actual_type=actual_field.type,
                                classification=Classification.BREAKING,
                                severity=Severity.CRITICAL,
                                description=f"CRITICAL SCHEMA DRIFT: {name} changed from {expected_field.type} to {actual_field.type}",
                                message=f"CRITICAL SCHEMA DRIFT: {name} changed from {expected_field.type} to {actual_field.type}",
                            )
                        )

                # Check required / nullability changes
                if expected_field.required != actual_field.required:
                    if not expected_field.required and actual_field.required:
                        changes.append(
                            SchemaChange(
                                change_type=ChangeType.FIELD_REQUIRED_CHANGED,
                                field=name,
                                old_value=expected_field.required,
                                new_value=actual_field.required,
                                expected_type=expected_field.type,
                                actual_type=actual_field.type,
                                classification=Classification.BREAKING,
                                severity=Severity.CRITICAL,
                                description=f"Field '{name}' changed from optional to required",
                                message=f"CRITICAL: field '{name}' changed from optional to required",
                            )
                        )
                    elif expected_field.required and not actual_field.required:
                        changes.append(
                            SchemaChange(
                                change_type=ChangeType.FIELD_REQUIRED_CHANGED,
                                field=name,
                                old_value=expected_field.required,
                                new_value=actual_field.required,
                                expected_type=expected_field.type,
                                actual_type=actual_field.type,
                                classification=Classification.COMPATIBLE,
                                severity=Severity.INFO,
                                description=f"Field '{name}' relaxed from required to optional",
                                message=f"INFO: field '{name}' relaxed from required to optional",
                            )
                        )

                # Check enum value compatibility
                if expected_field.enum is not None or actual_field.enum is not None:
                    old_enum = set(expected_field.enum) if expected_field.enum else set()
                    new_enum = set(actual_field.enum) if actual_field.enum else set()

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
                                message=f"INFO: enum field '{name}' expanded with new value(s): {', '.join(added_enum_vals)}",
                            )
                        )

                    if removed_enum_vals:
                        changes.append(
                            SchemaChange(
                                change_type=ChangeType.ENUM_VALUE_REMOVED,
                                field=name,
                                old_value=sorted(list(old_enum)),
                                new_value=sorted(list(new_enum)),
                                classification=Classification.BREAKING,
                                severity=Severity.CRITICAL,
                                description=f"Enum field '{name}' removed value(s): {', '.join(removed_enum_vals)}",
                                message=f"CRITICAL: enum field '{name}' removed value(s): {', '.join(removed_enum_vals)}",
                            )
                        )

            else:
                # Field in expected schema is missing in actual schema
                if expected_field.required:
                    changes.append(
                        SchemaChange(
                            change_type=ChangeType.MISSING_COLUMN,
                            field=name,
                            old_value={"type": expected_field.type, "required": True},
                            new_value=None,
                            expected_type=expected_field.type,
                            actual_type=None,
                            classification=Classification.BREAKING,
                            severity=Severity.CRITICAL,
                            description=f"Required column '{name}' is missing",
                            message=f"CRITICAL SCHEMA DRIFT: required column '{name}' is missing",
                        )
                    )
                else:
                    changes.append(
                        SchemaChange(
                            change_type=ChangeType.REMOVED_COLUMN,
                            field=name,
                            old_value={"type": expected_field.type, "required": False},
                            new_value=None,
                            expected_type=expected_field.type,
                            actual_type=None,
                            classification=Classification.WARNING,
                            severity=Severity.WARNING,
                            description=f"Optional column '{name}' was removed",
                            message=f"WARNING: optional column '{name}' was removed",
                        )
                    )

        # 2. Inspect new fields in actual schema not present in expected schema
        for name, actual_field in actual_fields.items():
            if name not in matched_actual_fields and name not in expected_fields:
                if actual_field.required:
                    changes.append(
                        SchemaChange(
                            change_type=ChangeType.NEW_COLUMN,
                            field=name,
                            old_value=None,
                            new_value={"type": actual_field.type, "required": True},
                            expected_type=None,
                            actual_type=actual_field.type,
                            classification=Classification.BREAKING,
                            severity=Severity.CRITICAL,
                            description=f"New required column '{name}' added",
                            message=f"CRITICAL: new required column '{name}' added without default",
                        )
                    )
                else:
                    changes.append(
                        SchemaChange(
                            change_type=ChangeType.NEW_COLUMN,
                            field=name,
                            old_value=None,
                            new_value={"type": actual_field.type, "required": False},
                            expected_type=None,
                            actual_type=actual_field.type,
                            classification=Classification.COMPATIBLE,
                            severity=Severity.INFO,
                            description=f"New optional column '{name}' added",
                            message=f"INFO: new optional column '{name}' added",
                        )
                    )

        # 3. Determine overall severity and compatibility classification
        if any(c.severity == Severity.CRITICAL for c in changes):
            overall_severity = Severity.CRITICAL
            overall_classification = Classification.BREAKING
            is_compatible = False
        elif any(c.severity in (Severity.WARNING, Severity.BREAKING) for c in changes):
            overall_severity = Severity.WARNING
            overall_classification = Classification.WARNING
            is_compatible = True
        elif any(c.severity == Severity.INFO for c in changes):
            overall_severity = Severity.INFO
            overall_classification = Classification.COMPATIBLE
            is_compatible = True
        else:
            overall_severity = Severity.INFO
            overall_classification = Classification.COMPATIBLE
            is_compatible = True

        if not changes:
            summary = f"Schema {expected_schema.schema_version} and {actual_schema.schema_version} are identical."
        elif is_compatible:
            summary = f"Schema evolution from {expected_schema.schema_version} to {actual_schema.schema_version} is {overall_classification.value} ({len(changes)} change(s) detected)."
        else:
            critical_count = sum(1 for c in changes if c.severity == Severity.CRITICAL)
            summary = f"Schema evolution from {expected_schema.schema_version} to {actual_schema.schema_version} is BREAKING ({critical_count} critical change(s) detected out of {len(changes)} total)."

        return CompatibilityResult(
            compatible=is_compatible,
            classification=overall_classification,
            old_version=expected_schema.schema_version,
            new_version=actual_schema.schema_version,
            changes=changes,
            summary=summary,
            overall_severity=overall_severity,
        )


def check_compatibility(
    old_schema: EventSchema,
    new_schema: EventSchema,
    rename_map: Optional[Dict[str, str]] = None,
) -> CompatibilityResult:
    """Compare an old EventSchema against a new EventSchema and classify compatibility."""
    comparator = SchemaComparator(rename_map=rename_map)
    return comparator.compare(old_schema, new_schema)

