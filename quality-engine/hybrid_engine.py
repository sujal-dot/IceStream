"""Hybrid Quality Engine orchestrator integrating Great Expectations and Custom Rules."""

from dataclasses import dataclass, field as dc_field
import logging
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import pandas as pd

from schemas.event import QualityEvent
from rules.base import EventStatus, Severity, ValidationResult, ValidationSummary
from rules.engine import QualityEngine
from metrics.collector import InMemoryMetricsCollector, MetricsCollector
from ge_adapter.adapter import GEAdapter
from ge_adapter.result_mapper import QualityBatchResult

logger = logging.getLogger("quality_engine.hybrid")


@dataclass
class UnifiedQualityResult:
    """Unified validation summary combining Great Expectations batch checks and Custom streaming rules."""

    batch_id: str
    ge_results: List[ValidationResult]
    custom_results: List[ValidationResult]
    ge_batch_summary: QualityBatchResult
    total_events: int
    invalid_events_count: int
    critical_failures: int
    warning_failures: int
    overall_status: EventStatus
    timestamp: str

    @property
    def all_results(self) -> List[ValidationResult]:
        """All combined validation results."""
        return self.ge_results + self.custom_results

    def to_dict(self) -> Dict[str, Any]:
        """Convert unified quality result to a serializable dictionary."""
        return {
            "batch_id": self.batch_id,
            "overall_status": self.overall_status.value,
            "total_events": self.total_events,
            "invalid_events_count": self.invalid_events_count,
            "critical_failures": self.critical_failures,
            "warning_failures": self.warning_failures,
            "ge_checks": {
                "total": self.ge_batch_summary.total_expectations,
                "passed": self.ge_batch_summary.passed_expectations,
                "failed": self.ge_batch_summary.failed_expectations,
            },
            "custom_checks": {
                "total": len(self.custom_results),
                "passed": sum(1 for r in self.custom_results if r.passed),
                "failed": sum(1 for r in self.custom_results if not r.passed),
            },
            "ge_results": [r.to_dict() for r in self.ge_results],
            "custom_results": [r.to_dict() for r in self.custom_results],
        }


class HybridQualityEngine:
    """Hybrid orchestrator coordinating Great Expectations (batch checks) and Custom Rules (streaming checks)."""

    def __init__(
        self,
        custom_engine: Optional[QualityEngine] = None,
        ge_adapter: Optional[GEAdapter] = None,
        metrics_collector: Optional[MetricsCollector] = None,
    ) -> None:
        self._metrics = metrics_collector or InMemoryMetricsCollector()
        self._custom_engine = custom_engine or QualityEngine(metrics_collector=self._metrics)
        self._ge_adapter = ge_adapter or GEAdapter(metrics_collector=self._metrics)

        logger.info("HybridQualityEngine initialized with Custom QualityEngine and GEAdapter")

    @property
    def custom_engine(self) -> QualityEngine:
        """Access custom rules engine."""
        return self._custom_engine

    @property
    def ge_adapter(self) -> GEAdapter:
        """Access Great Expectations adapter."""
        return self._ge_adapter

    @property
    def metrics(self) -> MetricsCollector:
        """Access shared metrics collector."""
        return self._metrics

    def validate_event(
        self, event_input: Union[QualityEvent, Dict[str, Any]]
    ) -> Tuple[List[ValidationResult], ValidationSummary]:
        """Delegate event-by-event validation to the custom rules streaming engine."""
        return self._custom_engine.validate_with_summary(event_input)

    def validate_batch(
        self,
        batch_input: Union[pd.DataFrame, List[QualityEvent], List[Dict[str, Any]]],
        batch_id: Optional[str] = None,
    ) -> UnifiedQualityResult:
        """Execute hybrid batch validation: Great Expectations declarative checks + Custom event rules.

        Args:
            batch_input: DataFrame, list of QualityEvents, or list of dicts.
            batch_id: Optional batch identifier string.

        Returns:
            UnifiedQualityResult containing combined outcomes.
        """
        start_time = time.perf_counter()
        bid = batch_id or f"batch_{int(time.time())}"

        # Standardize input list of events
        events: List[QualityEvent] = []
        if isinstance(batch_input, pd.DataFrame):
            dict_records = batch_input.to_dict(orient="records")
            events = [QualityEvent.from_dict(r) for r in dict_records]
        elif isinstance(batch_input, list):
            for item in batch_input:
                if isinstance(item, QualityEvent):
                    events.append(item)
                elif isinstance(item, dict):
                    events.append(QualityEvent.from_dict(item))
                else:
                    raise TypeError(f"Unsupported event item type: {type(item).__name__}")
        else:
            raise TypeError(f"Unsupported batch_input type: {type(batch_input).__name__}")

        total_events = len(events)

        # 1. Run Great Expectations declarative batch checks
        ge_results, ge_batch_summary = self._ge_adapter.validate_with_summary(
            batch_input, batch_id=bid
        )

        # 2. Run Custom Rules against individual streaming events
        custom_results: List[ValidationResult] = []
        failed_event_ids: set = set()

        for idx, event in enumerate(events):
            event_id_str = event.event_id or f"event_idx_{idx}"
            event_res, summary = self._custom_engine.validate_with_summary(event)

            # Mark source as custom
            for r in event_res:
                if "source" not in r.metadata:
                    r.metadata["source"] = "custom"

            custom_results.extend(event_res)

            if summary.overall_status != EventStatus.HEALTHY:
                failed_event_ids.add(event_id_str)

        # Handle GE failures impacting event validity without double-counting
        ge_failed = [r for r in ge_results if not r.passed]
        if ge_failed and total_events > 0:
            pass

        invalid_events_count = len(failed_event_ids)

        # Compute severity statistics across all results
        critical_failures = sum(
            1
            for r in (ge_results + custom_results)
            if not r.passed and r.severity in (Severity.CRITICAL, Severity.HIGH)
        )
        warning_failures = sum(
            1
            for r in (ge_results + custom_results)
            if not r.passed and r.severity in (Severity.WARNING, Severity.MEDIUM, Severity.LOW)
        )

        if (len(ge_failed) == 0) and (len([r for r in custom_results if not r.passed]) == 0):
            overall_status = EventStatus.HEALTHY
        elif critical_failures > 0:
            overall_status = EventStatus.FAILED
        else:
            overall_status = EventStatus.WARNING

        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        unified = UnifiedQualityResult(
            batch_id=bid,
            ge_results=ge_results,
            custom_results=custom_results,
            ge_batch_summary=ge_batch_summary,
            total_events=total_events,
            invalid_events_count=invalid_events_count,
            critical_failures=critical_failures,
            warning_failures=warning_failures,
            overall_status=overall_status,
            timestamp=now_iso,
        )

        logger.info(
            "Hybrid batch validation '%s' complete: events=%d, ge_passed=%d/%d, custom_passed=%d/%d, status=%s, duration=%.2fms",
            bid,
            total_events,
            ge_batch_summary.passed_expectations,
            ge_batch_summary.total_expectations,
            sum(1 for r in custom_results if r.passed),
            len(custom_results),
            overall_status.value,
            (time.perf_counter() - start_time) * 1000.0,
        )

        return unified

    def format_quality_summary(
        self,
        ge_results: List[ValidationResult],
        custom_results: List[ValidationResult],
    ) -> str:
        """Generate the canonical formatted IceStream Quality Summary text report."""
        total_ge = len(ge_results)
        passed_ge = sum(1 for r in ge_results if r.passed)
        failed_ge = sum(1 for r in ge_results if not r.passed)

        total_custom = len(custom_results)
        passed_custom = sum(1 for r in custom_results if r.passed)
        failed_custom = sum(1 for r in custom_results if not r.passed)

        all_results = ge_results + custom_results
        critical_count = sum(
            1 for r in all_results if not r.passed and r.severity in (Severity.CRITICAL, Severity.HIGH)
        )
        warning_count = sum(
            1 for r in all_results if not r.passed and r.severity in (Severity.WARNING, Severity.MEDIUM, Severity.LOW)
        )

        if (failed_ge + failed_custom) == 0:
            overall = "HEALTHY"
        elif critical_count > 0:
            overall = "FAILED"
        else:
            overall = "WARNING"

        summary_lines = [
            "========================================",
            "IceStream Quality Summary",
            "========================================",
            "",
            "GE Checks:",
            f"{total_ge}",
            "",
            "GE Passed:",
            f"{passed_ge}",
            "",
            "GE Failed:",
            f"{failed_ge}",
            "",
            "Custom Checks:",
            f"{total_custom}",
            "",
            "Custom Passed:",
            f"{passed_custom}",
            "",
            "Custom Failed:",
            f"{failed_custom}",
            "",
            "Critical:",
            f"{critical_count}",
            "",
            "Warning:",
            f"{warning_count}",
            "",
            "Overall:",
            f"{overall}",
            "",
            "========================================",
        ]

        return "\n".join(summary_lines)
