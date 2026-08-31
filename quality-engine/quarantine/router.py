"""
IceStream Quarantine Router
Routes invalid events from the Quality Engine to the Iceberg Quarantine persistence layer.
Enforces valid event protection, deterministic error mapping, original event preservation,
deduplication, and operational metrics.
"""
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from rules.base import EventStatus, ValidationResult, ValidationSummary
from schemas.event import QualityEvent
from metrics.collector import InMemoryMetricsCollector, MetricsCollector
from quarantine.error_codes import determine_primary_error
from quarantine.models import QuarantineRecord, QuarantineRouteResult
from quarantine.writer import QuarantineWriter

logger = logging.getLogger("quality_engine.quarantine.router")


def get_default_utc_now() -> str:
    """Generate ISO 8601 UTC timestamp using current clock."""
    return datetime.now(timezone.utc).isoformat()


def serialize_event_payload(event_input: Union[QualityEvent, Dict[str, Any], Any]) -> str:
    """Safely serialize full original event payload to a JSON string without data loss."""
    if isinstance(event_input, QualityEvent):
        data = event_input.to_dict()
    elif isinstance(event_input, dict):
        data = dict(event_input)
    elif hasattr(event_input, "to_dict") and callable(event_input.to_dict):
        data = event_input.to_dict()
    else:
        return str(event_input)

    def json_fallback(obj):
        if hasattr(obj, "isoformat"):
            return obj.isoformat()
        return str(obj)

    return json.dumps(data, default=json_fallback, sort_keys=True)


class QuarantineRouter:
    """Orchestrates routing, metadata enrichment, deduplication, and persistence of invalid events."""

    def __init__(
        self,
        writer: Optional[QuarantineWriter] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        clock_fn: Optional[Callable[[], str]] = None,
        pipeline_version: Optional[str] = None,
    ) -> None:
        self._writer = writer or QuarantineWriter(metrics_collector=metrics_collector)
        self._metrics = metrics_collector or InMemoryMetricsCollector()
        self._clock_fn = clock_fn or get_default_utc_now
        self._pipeline_version = pipeline_version or os.getenv("ICESTREAM_PIPELINE_VERSION", "0.1.0")
        self._seen_quarantine_ids: Set[str] = set()

    @property
    def writer(self) -> QuarantineWriter:
        """Access underlying quarantine writer."""
        return self._writer

    @property
    def metrics(self) -> MetricsCollector:
        """Access metrics collector."""
        return self._metrics

    def route_invalid_event(
        self,
        event_input: Union[QualityEvent, Dict[str, Any]],
        validation_results: Union[List[ValidationResult], ValidationSummary],
    ) -> QuarantineRouteResult:
        """Route an invalid event to quarantine.

        Args:
            event_input: Original event payload (QualityEvent or dict).
            validation_results: List of ValidationResult objects or a ValidationSummary.

        Returns:
            QuarantineRouteResult describing the persistence outcome.
        """
        # Extract validation results
        results_list: List[ValidationResult] = []
        if isinstance(validation_results, ValidationSummary):
            results_list = validation_results.results
        elif isinstance(validation_results, list):
            results_list = validation_results

        failed_results = [r for r in results_list if not r.passed]

        # Valid Event Protection: Router must refuse valid events
        if not failed_results:
            logger.debug("Refusing to quarantine valid event; 0 rule failures present.")
            return QuarantineRouteResult(
                quarantine_record=None,
                success=False,
                skipped_reason="EVENT_IS_VALID",
            )

        # 1. Determine primary error, error message, and sorted failed rules
        primary_error_code, error_message, sorted_failed_rules = determine_primary_error(failed_results)

        # 2. Extract event metadata
        event_dict: Dict[str, Any] = {}
        if isinstance(event_input, QualityEvent):
            event_dict = event_input.to_dict()
            event_id = event_input.event_id
        elif isinstance(event_input, dict):
            event_dict = event_input
            event_id = event_dict.get("event_id")
        else:
            event_id = None

        # 3. Extract source schema_version
        schema_version = (
            event_dict.get("source_version")
            or event_dict.get("schema_version")
            or "unknown"
        )

        # 4. Capture detected_at using clock function
        detected_at = self._clock_fn()

        # 5. Preserve original event payload as string
        raw_event_str = serialize_event_payload(event_input)

        # 6. Compute deterministic quarantine_id
        dedup_seed = f"{event_id or 'none'}:{self._pipeline_version}:{','.join(sorted_failed_rules)}:{detected_at}"
        hash_digest = hashlib.sha256(dedup_seed.encode("utf-8")).hexdigest()[:16]
        quarantine_id = f"q_{hash_digest}"

        record = QuarantineRecord(
            quarantine_id=quarantine_id,
            event_id=event_id,
            event=raw_event_str,
            error_code=primary_error_code,
            error_message=error_message,
            failed_rules=sorted_failed_rules,
            detected_at=detected_at,
            pipeline_version=self._pipeline_version,
            schema_version=schema_version,
        )

        # 7. Deduplication Check
        if quarantine_id in self._seen_quarantine_ids:
            logger.info("Skipping duplicate quarantine write for quarantine_id '%s'", quarantine_id)
            return QuarantineRouteResult(
                quarantine_record=record,
                success=True,
                skipped_reason="DUPLICATE_QUARANTINE_SKIPPED",
            )

        # 8. Persist to Iceberg table
        write_success = self._writer.write_record(record)

        if write_success:
            self._seen_quarantine_ids.add(quarantine_id)
            self._metrics.increment_counter("quarantine_events_total")
            self._metrics.increment_counter("quarantine_events_by_error_code", labels={"error_code": primary_error_code})
            logger.info("Event '%s' successfully quarantined as '%s' [quarantine_id=%s]", event_id, primary_error_code, quarantine_id)
            return QuarantineRouteResult(quarantine_record=record, success=True)
        else:
            logger.error("Failed to persist quarantine record for event '%s' [quarantine_id=%s]", event_id, quarantine_id)
            return QuarantineRouteResult(
                quarantine_record=record,
                success=False,
                error="Iceberg write failure",
            )

    def route_batch(
        self,
        events_and_results: List[Tuple[Union[QualityEvent, Dict[str, Any]], Union[List[ValidationResult], ValidationSummary]]],
    ) -> List[QuarantineRouteResult]:
        """Route a batch of events to quarantine.

        Collects all invalid events, builds records, and issues a single batch append operation
        to Iceberg for maximum performance.
        """
        records_to_write: List[QuarantineRecord] = []
        route_results: List[QuarantineRouteResult] = []

        for event_input, val_results in events_and_results:
            results_list = val_results.results if isinstance(val_results, ValidationSummary) else val_results
            failed_results = [r for r in results_list if not r.passed]

            if not failed_results:
                route_results.append(
                    QuarantineRouteResult(quarantine_record=None, success=False, skipped_reason="EVENT_IS_VALID")
                )
                continue

            primary_code, err_msg, failed_rules = determine_primary_error(failed_results)

            if isinstance(event_input, QualityEvent):
                event_dict = event_input.to_dict()
                event_id = event_input.event_id
            elif isinstance(event_input, dict):
                event_dict = event_input
                event_id = event_dict.get("event_id")
            else:
                event_dict = {}
                event_id = None

            schema_ver = event_dict.get("source_version") or event_dict.get("schema_version") or "unknown"
            detected_at = self._clock_fn()
            raw_str = serialize_event_payload(event_input)

            dedup_seed = f"{event_id or 'none'}:{self._pipeline_version}:{','.join(failed_rules)}:{detected_at}"
            hash_digest = hashlib.sha256(dedup_seed.encode("utf-8")).hexdigest()[:16]
            quarantine_id = f"q_{hash_digest}"

            record = QuarantineRecord(
                quarantine_id=quarantine_id,
                event_id=event_id,
                event=raw_str,
                error_code=primary_code,
                error_message=err_msg,
                failed_rules=failed_rules,
                detected_at=detected_at,
                pipeline_version=self._pipeline_version,
                schema_version=schema_ver,
            )

            if quarantine_id in self._seen_quarantine_ids:
                route_results.append(
                    QuarantineRouteResult(quarantine_record=record, success=True, skipped_reason="DUPLICATE_QUARANTINE_SKIPPED")
                )
                continue

            records_to_write.append(record)
            # Placeholder result to be updated after batch write
            route_results.append(QuarantineRouteResult(quarantine_record=record, success=False))

        if records_to_write:
            written_count, batch_success = self._writer.write_batch(records_to_write)
            if batch_success:
                for rec in records_to_write:
                    self._seen_quarantine_ids.add(rec.quarantine_id)
                    self._metrics.increment_counter("quarantine_events_total")
                    self._metrics.increment_counter("quarantine_events_by_error_code", labels={"error_code": rec.error_code})
                for res in route_results:
                    if res.quarantine_record in records_to_write:
                        res.success = True
            else:
                for res in route_results:
                    if res.quarantine_record in records_to_write:
                        res.success = False
                        res.error = "Batch Iceberg write failure"

        return route_results
