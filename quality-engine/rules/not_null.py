"""Not-null quality rule implementation for IceStream Quality Engine."""

from typing import Any, Optional
from schemas.event import QualityEvent
from rules.base import QualityRule, Severity, ValidationResult


class NotNullRule(QualityRule):
    """Reusable rule verifying that a specified event field is present and non-null."""

    def __init__(
        self,
        field: str,
        name: Optional[str] = None,
        severity_override: Optional[Severity] = None,
        enabled: bool = True,
    ) -> None:
        super().__init__(severity_override=severity_override, enabled=enabled)
        self.field = field
        self._name = name or f"{field}_not_null"

    @property
    def name(self) -> str:
        return self._name

    @property
    def default_severity(self) -> Severity:
        if self.field in ("event_id", "amount"):
            return Severity.CRITICAL
        return Severity.HIGH

    def validate(self, event: QualityEvent) -> ValidationResult:
        val = event.get_field(self.field)

        # Null check logic:
        # None is NULL.
        # Empty string or string "none" (case-insensitive) is treated as null/unpopulated for string fields.
        # Numeric 0 or 0.0 or False are NOT null.
        is_null = False
        if val is None:
            is_null = True
        elif isinstance(val, str) and (val.strip() == "" or val.strip().lower() == "none"):
            is_null = True

        if is_null:
            return ValidationResult(
                rule_name=self.name,
                passed=False,
                severity=self.severity,
                message=f"Field '{self.field}' is null or unpopulated",
                field=self.field,
                event_id=event.event_id,
                metadata={"provided_value": val, "is_null": True},
            )

        return ValidationResult(
            rule_name=self.name,
            passed=True,
            severity=self.severity,
            message=f"Field '{self.field}' is present and valid",
            field=self.field,
            event_id=event.event_id,
            metadata={"provided_value": val},
        )
