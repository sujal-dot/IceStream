"""Base abstractions, enums, models, and rule interfaces for IceStream Quality Engine."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field as dc_field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from schemas.event import QualityEvent


class Severity(str, Enum):
    """Severity levels for quality rule failures."""

    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RuleStatus(str, Enum):
    """Execution status of an individual quality rule."""

    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"


class EventStatus(str, Enum):
    """Overall evaluation health status of an event."""

    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    FAILED = "FAILED"


def get_current_utc_timestamp() -> str:
    """Generate ISO-8601 UTC timestamp string."""
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ValidationResult:
    """Standardized validation outcome for a single rule execution."""

    rule_name: str
    passed: bool
    severity: Severity
    message: str
    field: Optional[str] = None
    event_id: Optional[str] = None
    timestamp: str = dc_field(default_factory=get_current_utc_timestamp)
    metadata: Dict[str, Any] = dc_field(default_factory=dict)

    @property
    def status(self) -> RuleStatus:
        """Get the rule execution status."""
        return RuleStatus.PASS if self.passed else RuleStatus.FAIL

    def to_dict(self) -> Dict[str, Any]:
        """Convert validation result to dictionary format."""
        return {
            "event_id": self.event_id,
            "rule": self.rule_name,
            "rule_name": self.rule_name,
            "passed": self.passed,
            "status": self.status.value,
            "severity": self.severity.value if isinstance(self.severity, Enum) else str(self.severity),
            "message": self.message,
            "field": self.field,
            "timestamp": self.timestamp,
            "metadata": dict(self.metadata),
        }


@dataclass
class ValidationSummary:
    """Consolidated summary of all rule validation results for an event."""

    event_id: Optional[str]
    total_rules: int
    passed_rules: int
    failed_rules: int
    critical_failures: int
    overall_status: EventStatus
    results: List[ValidationResult] = dc_field(default_factory=list)
    timestamp: str = dc_field(default_factory=get_current_utc_timestamp)

    def to_dict(self) -> Dict[str, Any]:
        """Convert validation summary to dictionary format."""
        return {
            "event_id": self.event_id,
            "total_rules": self.total_rules,
            "passed_rules": self.passed_rules,
            "failed_rules": self.failed_rules,
            "critical_failures": self.critical_failures,
            "overall_status": self.overall_status.value if isinstance(self.overall_status, Enum) else str(self.overall_status),
            "timestamp": self.timestamp,
            "results": [r.to_dict() for r in self.results],
        }


def compute_validation_summary(
    results: List[ValidationResult], event_id: Optional[str] = None
) -> ValidationSummary:
    """Centralized logic to compute overall health status and summary."""
    total_rules = len(results)
    passed_rules = sum(1 for r in results if r.passed)
    failed_rules = sum(1 for r in results if not r.passed)
    critical_failures = sum(
        1 for r in results if not r.passed and r.severity in (Severity.CRITICAL, Severity.HIGH)
    )

    if failed_rules == 0:
        overall_status = EventStatus.HEALTHY
    elif critical_failures > 0:
        overall_status = EventStatus.FAILED
    else:
        overall_status = EventStatus.WARNING

    return ValidationSummary(
        event_id=event_id,
        total_rules=total_rules,
        passed_rules=passed_rules,
        failed_rules=failed_rules,
        critical_failures=critical_failures,
        overall_status=overall_status,
        results=results,
    )


class QualityRule(ABC):
    """Abstract base class for all IceStream quality rules and detectors."""

    def __init__(
        self,
        severity_override: Optional[Severity] = None,
        enabled: bool = True,
    ) -> None:
        self._severity_override = severity_override
        self._enabled = enabled

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for the quality rule."""
        pass

    @property
    @abstractmethod
    def default_severity(self) -> Severity:
        """Default severity level when the rule fails."""
        pass

    @property
    def severity(self) -> Severity:
        """Current effective severity level (allows configuration override)."""
        if self._severity_override is not None:
            return self._severity_override
        return self.default_severity

    @severity.setter
    def severity(self, value: Severity) -> None:
        """Set a runtime severity override."""
        self._severity_override = value

    @property
    def enabled(self) -> bool:
        """Whether this rule is active for execution."""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        """Set rule enabled status."""
        self._enabled = bool(value)

    @abstractmethod
    def validate(self, event: QualityEvent) -> ValidationResult:
        """Execute validation rule logic against an event.
        
        Args:
            event: The QualityEvent instance to inspect.

        Returns:
            ValidationResult specifying pass/fail status, severity, and message.
        """
        pass


class EventIdNotNullRule(QualityRule):
    """Demonstration rule: Verifies that event_id is present, not null, and not empty."""

    @property
    def name(self) -> str:
        return "event_id_not_null"

    @property
    def default_severity(self) -> Severity:
        return Severity.CRITICAL

    def validate(self, event: QualityEvent) -> ValidationResult:
        event_id = event.event_id

        # Check for None, empty string, or literal "None"
        if event_id is None or str(event_id).strip() == "" or str(event_id).strip().lower() == "none":
            return ValidationResult(
                rule_name=self.name,
                passed=False,
                severity=self.severity,
                message="event_id is null, empty, or unpopulated",
                field="event_id",
                event_id=None,
                metadata={"provided_value": event_id},
            )

        return ValidationResult(
            rule_name=self.name,
            passed=True,
            severity=self.severity,
            message="event_id is present and valid",
            field="event_id",
            event_id=str(event_id),
            metadata={"provided_value": event_id},
        )
