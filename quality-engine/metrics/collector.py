"""Metrics collection abstraction and in-memory collector for Quality Engine."""

import threading
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from rules.base import EventStatus, Severity, ValidationResult


class MetricsCollector(ABC):
    """Abstract interface for recording data quality metrics."""

    @abstractmethod
    def record_rule_result(self, result: ValidationResult) -> None:
        """Record the outcome of a single rule validation."""
        pass

    @abstractmethod
    def increment_rule_pass(self, rule_name: str) -> None:
        """Increment pass counter for a rule."""
        pass

    @abstractmethod
    def increment_rule_failure(self, rule_name: str, severity: Severity) -> None:
        """Increment failure counter for a rule."""
        pass

    @abstractmethod
    def increment_event_validation(self, status: EventStatus) -> None:
        """Increment overall event count and health category."""
        pass

    @abstractmethod
    def record_validation_latency(self, latency_ms: float) -> None:
        """Record the execution latency in milliseconds."""
        pass

    @abstractmethod
    def get_metrics(self) -> Dict[str, Any]:
        """Retrieve snapshot of current metrics."""
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset all metric counters."""
        pass


class InMemoryMetricsCollector(MetricsCollector):
    """Thread-safe in-memory metrics collector for development and unit testing."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        """Reset all counters to zero."""
        with getattr(self, "_lock", threading.Lock()):
            self._total_events: int = 0
            self._valid_events: int = 0
            self._invalid_events: int = 0
            self._rule_passes: Dict[str, int] = {}
            self._rule_failures: Dict[str, int] = {}
            self._critical_failures: int = 0
            self._latency_count: int = 0
            self._latency_sum_ms: float = 0.0

    def record_rule_result(self, result: ValidationResult) -> None:
        """Record a ValidationResult."""
        if result.passed:
            self.increment_rule_pass(result.rule_name)
        else:
            self.increment_rule_failure(result.rule_name, result.severity)

    def increment_rule_pass(self, rule_name: str) -> None:
        """Increment rule pass counter."""
        with self._lock:
            self._rule_passes[rule_name] = self._rule_passes.get(rule_name, 0) + 1

    def increment_rule_failure(self, rule_name: str, severity: Severity) -> None:
        """Increment rule failure counter and track critical failures."""
        with self._lock:
            self._rule_failures[rule_name] = self._rule_failures.get(rule_name, 0) + 1
            if severity in (Severity.CRITICAL, Severity.HIGH):
                self._critical_failures += 1

    def increment_event_validation(self, status: EventStatus) -> None:
        """Increment total events and valid/invalid categorization."""
        with self._lock:
            self._total_events += 1
            if status == EventStatus.HEALTHY:
                self._valid_events += 1
            else:
                self._invalid_events += 1

    def record_validation_latency(self, latency_ms: float) -> None:
        """Accumulate validation latency."""
        with self._lock:
            self._latency_count += 1
            self._latency_sum_ms += latency_ms

    def get_metrics(self) -> Dict[str, Any]:
        """Return a copy of the current metrics snapshot."""
        with self._lock:
            error_rate = (
                (self._invalid_events / self._total_events)
                if self._total_events > 0
                else 0.0
            )
            avg_latency_ms = (
                (self._latency_sum_ms / self._latency_count)
                if self._latency_count > 0
                else 0.0
            )
            return {
                "total_events": self._total_events,
                "valid_events": self._valid_events,
                "invalid_events": self._invalid_events,
                "error_rate": error_rate,
                "critical_failures": self._critical_failures,
                "rule_passes": dict(self._rule_passes),
                "rule_failures": dict(self._rule_failures),
                "validation_latency_count": self._latency_count,
                "validation_latency_avg_ms": avg_latency_ms,
            }
