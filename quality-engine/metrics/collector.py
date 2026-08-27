"""Metrics collection abstraction and in-memory collector for Quality Engine."""

import threading
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union

from rules.base import EventStatus, Severity, ValidationResult, ValidationSummary
from rules.clock import Clock, SystemClock
from metrics.window import WindowAggregator, WindowMetrics


class MetricsCollector(ABC):
    """Abstract interface for recording data quality metrics and window statistics."""

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
    def record_event_summary(
        self,
        summary: ValidationSummary,
        timestamp: Optional[Union[Any, str]] = None,
    ) -> None:
        """Record event-level validation summary into rolling window aggregators."""
        pass

    @abstractmethod
    def record_validation_latency(self, latency_ms: float) -> None:
        """Record the execution latency in milliseconds."""
        pass

    @abstractmethod
    def get_window_metrics(self, window_seconds: int) -> Optional[WindowMetrics]:
        """Retrieve rolling window metrics for a specific window duration."""
        pass

    @abstractmethod
    def get_metrics(self) -> Dict[str, Any]:
        """Retrieve snapshot of current metrics."""
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset all metric counters and window aggregators."""
        pass


class InMemoryMetricsCollector(MetricsCollector):
    """Thread-safe in-memory metrics collector with rolling window aggregations."""

    def __init__(
        self,
        windows: Optional[List[int]] = None,
        clock: Optional[Clock] = None,
    ) -> None:
        self._lock = threading.Lock()
        self._window_sizes = windows or [60, 300]
        self._clock = clock or SystemClock()
        self.reset()

    def reset(self) -> None:
        """Reset all counters and rolling windows to zero."""
        with getattr(self, "_lock", threading.Lock()):
            self._total_events: int = 0
            self._valid_events: int = 0
            self._invalid_events: int = 0
            self._rule_passes: Dict[str, int] = {}
            self._rule_failures: Dict[str, int] = {}
            self._critical_failures: int = 0
            self._latency_count: int = 0
            self._latency_sum_ms: float = 0.0
            self._schema_drift_total: int = 0
            self._schema_drift_info: int = 0
            self._schema_drift_warning: int = 0
            self._schema_drift_critical: int = 0
            self._schema_type_change_total: int = 0
            self._schema_missing_column_total: int = 0
            self._schema_new_column_total: int = 0
            self._schema_rename_total: int = 0
            self._window_aggregators: Dict[int, WindowAggregator] = {
                w: WindowAggregator(window_seconds=w, clock=self._clock)
                for w in self._window_sizes
            }

    def record_rule_result(self, result: ValidationResult) -> None:
        """Record a ValidationResult."""
        if result.passed:
            self.increment_rule_pass(result.rule_name)
        else:
            self.increment_rule_failure(result.rule_name, result.severity)

        if result.rule_name == "schema_drift" or "change_type" in result.metadata:
            with self._lock:
                self._schema_drift_total += 1
                sev = getattr(result.severity, "value", str(result.severity)).upper()
                if sev == "INFO":
                    self._schema_drift_info += 1
                elif sev == "WARNING":
                    self._schema_drift_warning += 1
                elif sev in ("CRITICAL", "HIGH", "BREAKING"):
                    self._schema_drift_critical += 1

                change_type = str(result.metadata.get("change_type", "")).upper()
                if "TYPE_CHANGE" in change_type:
                    self._schema_type_change_total += 1
                elif "MISSING_COLUMN" in change_type:
                    self._schema_missing_column_total += 1
                elif "NEW_COLUMN" in change_type:
                    self._schema_new_column_total += 1
                elif "RENAME" in change_type:
                    self._schema_rename_total += 1

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

    def record_event_summary(
        self,
        summary: ValidationSummary,
        timestamp: Optional[Union[Any, str]] = None,
    ) -> None:
        """Record event-level summary outcome into all active rolling windows."""
        is_valid = (summary.overall_status == EventStatus.HEALTHY)
        with self._lock:
            for agg in self._window_aggregators.values():
                agg.add_event(is_valid=is_valid, timestamp=timestamp)

    def record_validation_latency(self, latency_ms: float) -> None:
        """Accumulate validation latency."""
        with self._lock:
            self._latency_count += 1
            self._latency_sum_ms += latency_ms

    def get_window_metrics(self, window_seconds: int) -> Optional[WindowMetrics]:
        """Retrieve window metrics for specified duration."""
        with self._lock:
            agg = self._window_aggregators.get(window_seconds)
            if agg is None:
                # Dynamically create if requested
                agg = WindowAggregator(window_seconds=window_seconds, clock=self._clock)
                self._window_aggregators[window_seconds] = agg
            return agg.get_metrics()

    def get_metrics(self) -> Dict[str, Any]:
        """Return a copy of current metrics snapshot including rolling windows."""
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
            window_dict = {
                w: agg.get_metrics().to_dict()
                for w, agg in self._window_aggregators.items()
            }
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
                "schema_drift_total": self._schema_drift_total,
                "schema_drift_info": self._schema_drift_info,
                "schema_drift_warning": self._schema_drift_warning,
                "schema_drift_critical": self._schema_drift_critical,
                "schema_type_change_total": self._schema_type_change_total,
                "schema_missing_column_total": self._schema_missing_column_total,
                "schema_new_column_total": self._schema_new_column_total,
                "schema_rename_total": self._schema_rename_total,
                "windows": window_dict,
            }
