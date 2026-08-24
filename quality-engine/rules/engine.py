"""Quality Engine orchestrator for executing quality rules against events."""

import logging
import time
import traceback
from typing import Any, Dict, List, Optional, Tuple, Union

from metrics.collector import InMemoryMetricsCollector, MetricsCollector
from schemas.event import QualityEvent
from rules.base import (
    EventStatus,
    QualityRule,
    Severity,
    ValidationResult,
    ValidationSummary,
    compute_validation_summary,
)
from rules.registry import RuleRegistry, default_registry

logger = logging.getLogger("quality_engine.engine")


class QualityEngine:
    """Core evaluation engine that validates events against configured quality rules."""

    def __init__(
        self,
        registry: Optional[Union[RuleRegistry, List[QualityRule]]] = None,
        metrics_collector: Optional[MetricsCollector] = None,
    ) -> None:
        if registry is None:
            self._registry = default_registry
        elif isinstance(registry, RuleRegistry):
            self._registry = registry
        elif isinstance(registry, list):
            self._registry = RuleRegistry()
            for r in registry:
                self._registry.register(r)
        else:
            raise TypeError(
                f"Expected RuleRegistry or List[QualityRule], got {type(registry).__name__}"
            )

        self._metrics = metrics_collector or InMemoryMetricsCollector()
        logger.info(
            "QualityEngine initialized with %d registered rules",
            len(self._registry),
        )

    @property
    def registry(self) -> RuleRegistry:
        """Access the underlying rule registry."""
        return self._registry

    @property
    def metrics(self) -> MetricsCollector:
        """Access the metrics collector."""
        return self._metrics

    def get_active_rules(self) -> List[QualityRule]:
        """Return list of currently enabled rules."""
        return [r for r in self._registry.all() if r.enabled]

    def validate(
        self, event_input: Union[QualityEvent, Dict[str, Any]]
    ) -> List[ValidationResult]:
        """Validate a single event against all active quality rules.
        
        Args:
            event_input: A QualityEvent instance or a raw payload dictionary.

        Returns:
            List of ValidationResult objects for all executed rules.
        """
        results, _ = self.validate_with_summary(event_input)
        return results

    def validate_with_summary(
        self, event_input: Union[QualityEvent, Dict[str, Any]]
    ) -> Tuple[List[ValidationResult], ValidationSummary]:
        """Validate an event and return both the individual results and summary.
        
        Args:
            event_input: A QualityEvent or dictionary.

        Returns:
            Tuple of (List[ValidationResult], ValidationSummary).
        """
        start_time = time.perf_counter()

        # Parse event representation
        if isinstance(event_input, QualityEvent):
            event = event_input
        elif isinstance(event_input, dict):
            event = QualityEvent.from_dict(event_input)
        else:
            raise TypeError(
                f"Expected QualityEvent or dict, got {type(event_input).__name__}"
            )

        event_id = event.event_id
        active_rules = self.get_active_rules()
        results: List[ValidationResult] = []

        for rule in active_rules:
            try:
                result = rule.validate(event)
                if not isinstance(result, ValidationResult):
                    raise TypeError(
                        f"Rule {rule.name} returned {type(result).__name__}, expected ValidationResult"
                    )
            except Exception as e:
                # Capture exception without crashing the engine (rule isolation)
                tb_str = traceback.format_exc()
                logger.error(
                    "Unexpected exception executing rule '%s' on event '%s': %s",
                    rule.name,
                    event_id,
                    str(e),
                    exc_info=True,
                )
                result = ValidationResult(
                    rule_name=rule.name,
                    passed=False,
                    severity=Severity.CRITICAL,
                    message=f"Rule execution failure: {type(e).__name__}: {str(e)}",
                    field=None,
                    event_id=event_id,
                    metadata={
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "traceback": tb_str,
                    },
                )

            results.append(result)
            self._metrics.record_rule_result(result)

        # Compute summary
        summary = compute_validation_summary(results, event_id=event_id)
        self._metrics.increment_event_validation(summary.overall_status)

        latency_ms = (time.perf_counter() - start_time) * 1000.0
        self._metrics.record_validation_latency(latency_ms)

        logger.debug(
            "Validated event %s: status=%s, rules_executed=%d, failed=%d, latency=%.2fms",
            event_id,
            summary.overall_status.value,
            summary.total_rules,
            summary.failed_rules,
            latency_ms,
        )

        return results, summary
