"""Business anomaly detection rules for IceStream Quality Engine."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Union

from rules.base import QualityRule, Severity, ValidationResult
from rules.clock import Clock, SystemClock, parse_iso_timestamp
from schemas.event import QualityEvent


class ImpossibleAmountRule(QualityRule):
    """Detects transactions exceeding a configured business ceiling limit.
    
    Negative/zero amounts are handled separately by AmountPositiveRule.
    Null/non-numeric values are skipped (handled by NotNullRule).
    """

    def __init__(
        self,
        max_value: float = 500000.0,
        field: str = "amount",
        severity_override: Optional[Severity] = None,
        enabled: bool = True,
    ) -> None:
        super().__init__(severity_override=severity_override, enabled=enabled)
        self._max_value = float(max_value)
        self._field = field

    @property
    def name(self) -> str:
        return "impossible_amount"

    @property
    def default_severity(self) -> Severity:
        return Severity.HIGH

    @property
    def max_value(self) -> float:
        return self._max_value

    @max_value.setter
    def max_value(self, value: float) -> None:
        self._max_value = float(value)

    def validate(self, event: QualityEvent) -> ValidationResult:
        raw_val = event.get_field(self._field)

        if raw_val is None or str(raw_val).strip() == "" or str(raw_val).strip().lower() == "none":
            return ValidationResult(
                rule_name=self.name,
                passed=True,
                severity=self.severity,
                message=f"Skipped impossible_amount check for null {self._field}",
                field=self._field,
                event_id=event.event_id,
                metadata={"skipped": True},
            )

        try:
            amount_val = float(raw_val)
        except (ValueError, TypeError):
            return ValidationResult(
                rule_name=self.name,
                passed=True,
                severity=self.severity,
                message=f"Skipped impossible_amount check for non-numeric {self._field}",
                field=self._field,
                event_id=event.event_id,
                metadata={"skipped": True, "raw_value": raw_val},
            )

        if amount_val > self._max_value:
            return ValidationResult(
                rule_name=self.name,
                passed=False,
                severity=self.severity,
                message=f"amount exceeds maximum business limit ({self._max_value:,.2f})",
                field=self._field,
                event_id=event.event_id,
                metadata={
                    "provided_value": amount_val,
                    "max_value": self._max_value,
                },
            )

        return ValidationResult(
            rule_name=self.name,
            passed=True,
            severity=self.severity,
            message=f"amount is within acceptable business limit ({self._max_value:,.2f})",
            field=self._field,
            event_id=event.event_id,
            metadata={"provided_value": amount_val, "max_value": self._max_value},
        )


class FutureTimestampRule(QualityRule):
    """Detects events with event_time further in the future than allowed clock skew tolerance."""

    def __init__(
        self,
        tolerance_seconds: float = 30.0,
        clock: Optional[Clock] = None,
        field: str = "event_time",
        severity_override: Optional[Severity] = None,
        enabled: bool = True,
    ) -> None:
        super().__init__(severity_override=severity_override, enabled=enabled)
        self._tolerance_seconds = float(tolerance_seconds)
        self._clock = clock or SystemClock()
        self._field = field

    @property
    def name(self) -> str:
        return "future_timestamp"

    @property
    def default_severity(self) -> Severity:
        return Severity.HIGH

    @property
    def tolerance_seconds(self) -> float:
        return self._tolerance_seconds

    @tolerance_seconds.setter
    def tolerance_seconds(self, value: float) -> None:
        self._tolerance_seconds = float(value)

    def validate(self, event: QualityEvent) -> ValidationResult:
        raw_val = event.get_field(self._field)
        event_dt = parse_iso_timestamp(raw_val)

        if event_dt is None:
            return ValidationResult(
                rule_name=self.name,
                passed=True,
                severity=self.severity,
                message=f"Skipped future timestamp check for missing/invalid {self._field}",
                field=self._field,
                event_id=event.event_id,
                metadata={"skipped": True, "raw_value": raw_val},
            )

        ingestion_val = event.get_field("ingestion_time")
        ingestion_dt = parse_iso_timestamp(ingestion_val)
        ref_dt = ingestion_dt or self._clock.now()

        max_allowed = ref_dt + timedelta(seconds=self._tolerance_seconds)

        if event_dt > max_allowed:
            skew_seconds = (event_dt - ref_dt).total_seconds()
            return ValidationResult(
                rule_name=self.name,
                passed=False,
                severity=self.severity,
                message="event_time is beyond allowed clock skew",
                field=self._field,
                event_id=event.event_id,
                metadata={
                    "provided_timestamp": raw_val,
                    "reference_now": ref_dt.isoformat(),
                    "skew_seconds": skew_seconds,
                    "tolerance_seconds": self._tolerance_seconds,
                },
            )

        return ValidationResult(
            rule_name=self.name,
            passed=True,
            severity=self.severity,
            message="event_time is within acceptable clock skew tolerance",
            field=self._field,
            event_id=event.event_id,
            metadata={
                "provided_timestamp": raw_val,
                "reference_now": ref_dt.isoformat(),
                "tolerance_seconds": self._tolerance_seconds,
            },
        )


class LateEventRule(QualityRule):
    """Detects events whose event_time is older than the allowed lateness threshold."""

    def __init__(
        self,
        allowed_lateness_seconds: float = 120.0,
        clock: Optional[Clock] = None,
        field: str = "event_time",
        severity_override: Optional[Severity] = None,
        enabled: bool = True,
    ) -> None:
        super().__init__(severity_override=severity_override, enabled=enabled)
        self._allowed_lateness_seconds = float(allowed_lateness_seconds)
        self._clock = clock or SystemClock()
        self._field = field

    @property
    def name(self) -> str:
        return "late_event"

    @property
    def default_severity(self) -> Severity:
        return Severity.MEDIUM

    @property
    def allowed_lateness_seconds(self) -> float:
        return self._allowed_lateness_seconds

    @allowed_lateness_seconds.setter
    def allowed_lateness_seconds(self, value: float) -> None:
        self._allowed_lateness_seconds = float(value)

    def validate(self, event: QualityEvent) -> ValidationResult:
        raw_val = event.get_field(self._field)
        event_dt = parse_iso_timestamp(raw_val)

        if event_dt is None:
            return ValidationResult(
                rule_name=self.name,
                passed=True,
                severity=self.severity,
                message=f"Skipped late event check for missing/invalid {self._field}",
                field=self._field,
                event_id=event.event_id,
                metadata={"skipped": True, "raw_value": raw_val},
            )

        ingestion_val = event.get_field("ingestion_time")
        ingestion_dt = parse_iso_timestamp(ingestion_val)
        ref_dt = ingestion_dt or self._clock.now()

        event_delay = (ref_dt - event_dt).total_seconds()
        min_allowed = ref_dt - timedelta(seconds=self._allowed_lateness_seconds)

        if event_dt < min_allowed:
            return ValidationResult(
                rule_name=self.name,
                passed=False,
                severity=self.severity,
                message="event arrived later than allowed lateness",
                field=self._field,
                event_id=event.event_id,
                metadata={
                    "provided_timestamp": raw_val,
                    "reference_now": ref_dt.isoformat(),
                    "lateness_seconds": event_delay,
                    "allowed_lateness_seconds": self._allowed_lateness_seconds,
                    "event_delay_seconds": event_delay,
                },
            )

        return ValidationResult(
            rule_name=self.name,
            passed=True,
            severity=self.severity,
            message="event arrived within allowed lateness threshold",
            field=self._field,
            event_id=event.event_id,
            metadata={
                "provided_timestamp": raw_val,
                "reference_now": ref_dt.isoformat(),
                "allowed_lateness_seconds": self._allowed_lateness_seconds,
                "event_delay_seconds": event_delay,
            },
        )
