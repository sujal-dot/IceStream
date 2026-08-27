"""Production-Quality Schema Drift Detector for IceStream Quality Engine."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from rules.base import QualityRule, Severity, ValidationResult
from schemas.event import QualityEvent
from schema.compatibility import SchemaComparator
from schema.models import ChangeType, Classification, EventSchema, FieldSchema, SchemaChange, CompatibilityResult
from schema.registry import SchemaRegistry

logger = logging.getLogger("quality_engine.detectors.schema_drift")


def infer_type_from_value(val: Any) -> str:
    """Infer internal schema type string from a runtime Python value."""
    if val is None:
        return "string"
    if isinstance(val, bool):
        return "boolean"
    if isinstance(val, int):
        return "integer"
    if isinstance(val, float):
        return "float"
    if isinstance(val, dict):
        return "object"
    if isinstance(val, list):
        return "array"
    return "string"


class SchemaDriftRule(QualityRule):
    """Quality Engine rule for detecting schema drift between baseline and actual event schema."""

    def __init__(
        self,
        baseline_version: str = "v1",
        schema_registry: Optional[SchemaRegistry] = None,
        rename_map: Optional[Dict[str, str]] = None,
        severity_override: Optional[Severity] = None,
        enabled: bool = True,
    ) -> None:
        super().__init__(severity_override=severity_override, enabled=enabled)
        self._baseline_version = baseline_version
        self._registry = schema_registry or SchemaRegistry()
        self._rename_map = rename_map or {"customer_id": "customer"}
        self._comparator = SchemaComparator(rename_map=self._rename_map)

    @property
    def name(self) -> str:
        return "schema_drift"

    @property
    def default_severity(self) -> Severity:
        return Severity.CRITICAL

    @property
    def baseline_version(self) -> str:
        return self._baseline_version

    @baseline_version.setter
    def baseline_version(self, value: str) -> None:
        self._baseline_version = str(value)

    @property
    def rename_map(self) -> Dict[str, str]:
        return dict(self._rename_map)

    @rename_map.setter
    def rename_map(self, value: Dict[str, str]) -> None:
        self._rename_map = dict(value)
        self._comparator = SchemaComparator(rename_map=self._rename_map)

    def infer_event_schema(self, event: QualityEvent, version_tag: str = "inferred") -> EventSchema:
        """Infer an EventSchema object from an event's payload dictionary."""
        payload = event.to_dict()
        fields: Dict[str, FieldSchema] = {}
        for key, val in payload.items():
            inferred_type = infer_type_from_value(val)
            fields[key] = FieldSchema(
                name=key,
                type=inferred_type,
                required=True,
            )
        return EventSchema(schema_version=version_tag, fields=fields)

    def validate(self, event: QualityEvent) -> ValidationResult:
        """Validate an event against baseline schema to detect schema drift."""
        event_id = event.event_id
        source_version = event.get_field("source_version") or event.source_version

        # 1. Fetch baseline schema from registry
        try:
            expected_schema = self._registry.get(self._baseline_version)
        except KeyError:
            expected_schema = self._registry.get("v1")

        # 2. Determine actual schema
        if source_version is not None:
            source_ver_str = str(source_version).strip()
            if not source_ver_str or source_ver_str.lower() == "none":
                actual_schema = self.infer_event_schema(event, version_tag="missing_version")
                actual_version = "missing_version"
            else:
                try:
                    actual_schema = self._registry.get(source_ver_str)
                    actual_version = source_ver_str
                except KeyError:
                    # Unknown schema version
                    return ValidationResult(
                        rule_name=self.name,
                        passed=False,
                        severity=Severity.CRITICAL,
                        message=f"Unknown schema version: {source_ver_str}",
                        field=None,
                        event_id=event_id,
                        metadata={
                            "error_type": "SCHEMA_VERSION_UNKNOWN",
                            "provided_version": source_ver_str,
                            "change_type": "SCHEMA_VERSION_UNKNOWN",
                            "expected_schema": self._baseline_version,
                            "actual_schema": source_ver_str,
                        },
                    )
        else:
            actual_schema = self.infer_event_schema(event, version_tag="inferred")
            actual_version = "inferred"

        # 3. Compare schemas
        diff = self._comparator.compare(expected_schema, actual_schema)

        if not diff.changes:
            return ValidationResult(
                rule_name=self.name,
                passed=True,
                severity=Severity.INFO,
                message=f"No schema drift detected between {diff.expected_version} and {diff.actual_version}",
                field=None,
                event_id=event_id,
                metadata={
                    "expected_schema": diff.expected_version,
                    "actual_schema": diff.actual_version,
                    "compatibility": diff.classification.value,
                    "changes": [],
                },
            )

        # 4. Find highest severity change
        severity_order = {Severity.INFO: 1, Severity.WARNING: 2, Severity.BREAKING: 3, Severity.CRITICAL: 4}
        sorted_changes = sorted(
            diff.changes,
            key=lambda c: severity_order.get(c.severity, 0),
            reverse=True,
        )
        primary_change = sorted_changes[0]

        # Determine pass/fail status
        # Critical failures cause status FAILED (passed=False)
        passed = (diff.overall_severity == Severity.INFO)

        return ValidationResult(
            rule_name=self.name,
            passed=passed,
            severity=diff.overall_severity,
            message=primary_change.message or primary_change.description,
            field=primary_change.field,
            event_id=event_id,
            metadata={
                "change_type": primary_change.change_type.value if hasattr(primary_change.change_type, "value") else str(primary_change.change_type),
                "field": primary_change.field,
                "expected_type": primary_change.expected_type,
                "actual_type": primary_change.actual_type,
                "expected_schema": diff.expected_version,
                "actual_schema": diff.actual_version,
                "compatibility": diff.classification.value if hasattr(diff.classification, "value") else str(diff.classification),
                "total_changes": len(diff.changes),
                "changes": [c.to_dict() for c in diff.changes],
            },
        )
