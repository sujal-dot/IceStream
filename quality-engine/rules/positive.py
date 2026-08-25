"""Positive numeric quality rule implementation for IceStream Quality Engine."""

from decimal import Decimal, InvalidOperation
from typing import Optional, Union
from schemas.event import QualityEvent
from rules.base import QualityRule, Severity, ValidationResult


class AmountPositiveRule(QualityRule):
    """Rule verifying that amount (or another numeric field) is strictly greater than 0."""

    def __init__(
        self,
        field: str = "amount",
        name: Optional[str] = None,
        severity_override: Optional[Severity] = None,
        enabled: bool = True,
    ) -> None:
        super().__init__(severity_override=severity_override, enabled=enabled)
        self.field = field
        self._name = name or f"{field}_positive"

    @property
    def name(self) -> str:
        return self._name

    @property
    def default_severity(self) -> Severity:
        return Severity.HIGH

    def validate(self, event: QualityEvent) -> ValidationResult:
        val = event.get_field(self.field)

        # 1. Null check: if null, fail with clear message and metadata
        if val is None:
            return ValidationResult(
                rule_name=self.name,
                passed=False,
                severity=self.severity,
                message=f"Field '{self.field}' is null, must be greater than 0",
                field=self.field,
                event_id=event.event_id,
                metadata={"provided_value": None, "is_null": True},
            )

        # 2. Type parsing and evaluation
        num_val: Optional[Union[float, Decimal]] = None

        if isinstance(val, bool):
            # Boolean is not a valid numeric amount
            return ValidationResult(
                rule_name=self.name,
                passed=False,
                severity=self.severity,
                message=f"Field '{self.field}' has invalid boolean type",
                field=self.field,
                event_id=event.event_id,
                metadata={"provided_value": str(val), "error": "invalid_boolean_type"},
            )

        if isinstance(val, (int, float)):
            num_val = float(val)
        elif isinstance(val, Decimal):
            num_val = val
        elif isinstance(val, str):
            try:
                num_val = Decimal(val.strip())
            except (InvalidOperation, ValueError):
                return ValidationResult(
                    rule_name=self.name,
                    passed=False,
                    severity=self.severity,
                    message=f"Field '{self.field}' value '{val}' has invalid non-numeric format",
                    field=self.field,
                    event_id=event.event_id,
                    metadata={"provided_value": val, "error": "invalid_numeric_type"},
                )
        else:
            return ValidationResult(
                rule_name=self.name,
                passed=False,
                severity=self.severity,
                message=f"Field '{self.field}' has unsupported type '{type(val).__name__}'",
                field=self.field,
                event_id=event.event_id,
                metadata={"provided_value": str(val), "error": "unsupported_type"},
            )

        # Check positivity: num_val > 0
        if num_val > 0:
            return ValidationResult(
                rule_name=self.name,
                passed=True,
                severity=self.severity,
                message=f"Field '{self.field}' is positive ({val})",
                field=self.field,
                event_id=event.event_id,
                metadata={"provided_value": float(num_val) if isinstance(num_val, Decimal) else num_val},
            )
        else:
            return ValidationResult(
                rule_name=self.name,
                passed=False,
                severity=self.severity,
                message=f"Field '{self.field}' must be greater than 0, got {val}",
                field=self.field,
                event_id=event.event_id,
                metadata={"provided_value": float(num_val) if isinstance(num_val, Decimal) else num_val},
            )
