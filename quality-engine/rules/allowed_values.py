"""Allowed values validation quality rule implementation for IceStream Quality Engine."""

from typing import List, Optional, Set
from schemas.event import QualityEvent
from rules.base import QualityRule, Severity, ValidationResult


class AllowedValuesRule(QualityRule):
    """Generic rule verifying that a field's value belongs to a set of allowed values."""

    def __init__(
        self,
        field: str,
        allowed_values: List[str],
        name: Optional[str] = None,
        severity_override: Optional[Severity] = None,
        enabled: bool = True,
    ) -> None:
        super().__init__(severity_override=severity_override, enabled=enabled)
        self.field = field
        self.allowed_values = list(allowed_values)
        self._allowed_set: Set[str] = set(self.allowed_values)
        self._name = name or f"{field}_valid"

    @property
    def name(self) -> str:
        return self._name

    @property
    def default_severity(self) -> Severity:
        return Severity.HIGH

    def validate(self, event: QualityEvent) -> ValidationResult:
        val = event.get_field(self.field)

        if val is None or (isinstance(val, str) and val.strip() == ""):
            return ValidationResult(
                rule_name=self.name,
                passed=False,
                severity=self.severity,
                message=f"Field '{self.field}' is null or empty, expected one of {self.allowed_values}",
                field=self.field,
                event_id=event.event_id,
                metadata={"provided_value": val, "allowed_values": self.allowed_values, "is_null": True},
            )

        str_val = str(val)
        # Strict validation: case-sensitive exact match
        if str_val in self._allowed_set:
            return ValidationResult(
                rule_name=self.name,
                passed=True,
                severity=self.severity,
                message=f"Field '{self.field}' value '{str_val}' is valid",
                field=self.field,
                event_id=event.event_id,
                metadata={"provided_value": str_val},
            )

        return ValidationResult(
            rule_name=self.name,
            passed=False,
            severity=self.severity,
            message=f"Field '{self.field}' value '{str_val}' is invalid. Allowed values: {self.allowed_values}",
            field=self.field,
            event_id=event.event_id,
            metadata={"provided_value": str_val, "allowed_values": self.allowed_values},
        )


class CurrencyValidRule(AllowedValuesRule):
    """Specific rule for currency validation."""

    def __init__(
        self,
        allowed_values: Optional[List[str]] = None,
        name: str = "currency_valid",
        severity_override: Optional[Severity] = None,
        enabled: bool = True,
    ) -> None:
        values = allowed_values or ["INR", "USD", "EUR"]
        super().__init__(
            field="currency",
            allowed_values=values,
            name=name,
            severity_override=severity_override,
            enabled=enabled,
        )


class PaymentStatusValidRule(AllowedValuesRule):
    """Specific rule for payment status validation."""

    def __init__(
        self,
        allowed_values: Optional[List[str]] = None,
        name: str = "payment_status_valid",
        severity_override: Optional[Severity] = None,
        enabled: bool = True,
    ) -> None:
        values = allowed_values or ["SUCCESS", "FAILED", "PENDING", "CANCELLED"]
        super().__init__(
            field="payment_status",
            allowed_values=values,
            name=name,
            severity_override=severity_override,
            enabled=enabled,
        )
