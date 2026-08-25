"""Timestamp validity quality rule implementation for IceStream Quality Engine."""

from datetime import datetime, timezone
from typing import Optional
from schemas.event import QualityEvent
from rules.base import QualityRule, Severity, ValidationResult


class TimestampValidRule(QualityRule):
    """Rule verifying that a timestamp field is present, valid ISO-8601, and parseable."""

    def __init__(
        self,
        field: str = "event_time",
        name: Optional[str] = None,
        severity_override: Optional[Severity] = None,
        enabled: bool = True,
    ) -> None:
        super().__init__(severity_override=severity_override, enabled=enabled)
        self.field = field
        self._name = name or f"{field}_valid"

    @property
    def name(self) -> str:
        return self._name

    @property
    def default_severity(self) -> Severity:
        return Severity.HIGH

    def validate(self, event: QualityEvent) -> ValidationResult:
        val = event.get_field(self.field)

        # 1. Null check
        if val is None or (isinstance(val, str) and val.strip() == ""):
            return ValidationResult(
                rule_name=self.name,
                passed=False,
                severity=self.severity,
                message=f"Timestamp field '{self.field}' is null or missing",
                field=self.field,
                event_id=event.event_id,
                metadata={"provided_value": val, "is_null": True},
            )

        # 2. Parse timestamp safely
        if isinstance(val, datetime):
            parsed_dt = val
        elif isinstance(val, str):
            try:
                # Handle standard ISO-8601 with Z suffix or numeric offsets
                clean_val = val.strip().replace("Z", "+00:00")
                parsed_dt = datetime.fromisoformat(clean_val)
            except (ValueError, AttributeError) as e:
                return ValidationResult(
                    rule_name=self.name,
                    passed=False,
                    severity=self.severity,
                    message=f"Timestamp field '{self.field}' value '{val}' is malformed or unparseable ISO-8601",
                    field=self.field,
                    event_id=event.event_id,
                    metadata={"provided_value": val, "error": str(e)},
                )
        else:
            return ValidationResult(
                rule_name=self.name,
                passed=False,
                severity=self.severity,
                message=f"Timestamp field '{self.field}' has invalid non-string type '{type(val).__name__}'",
                field=self.field,
                event_id=event.event_id,
                metadata={"provided_value": str(val), "error": "invalid_type"},
            )

        return ValidationResult(
            rule_name=self.name,
            passed=True,
            severity=self.severity,
            message=f"Timestamp field '{self.field}' is valid ({parsed_dt.isoformat()})",
            field=self.field,
            event_id=event.event_id,
            metadata={"provided_value": val, "parsed_iso": parsed_dt.isoformat()},
        )
