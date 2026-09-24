"""
Stream Quality Validator for IceStream.

Authoritative stream quality evaluation engine. Consumes event payloads,
validates against QualityEngine rules, records rolling error rates in ErrorRateEngine,
routes invalid events to Iceberg quarantine persistence, and triggers automated
circuit breaker tripping and incident management when thresholds are breached.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import os
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Union

# Ensure quality-engine root is in path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
QUALITY_ENGINE_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if QUALITY_ENGINE_ROOT not in sys.path:
    sys.path.insert(0, QUALITY_ENGINE_ROOT)

BACKEND_ROOT = os.path.abspath(os.path.join(QUALITY_ENGINE_ROOT, "..", "backend"))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from prometheus_client import Counter

from rules.base import (
    EventStatus,
    RuleStatus,
    Severity,
    ValidationResult,
    ValidationSummary,
    compute_validation_summary,
)
from rules.engine import QualityEngine
from rules.registry import create_default_registry
from schemas.event import QualityEvent
from quarantine.models import QuarantineRouteResult
from quarantine.router import QuarantineRouter
from metrics.error_rate import ErrorRateEngine
from circuit_breaker.breaker import CircuitBreaker
from circuit_breaker.state import CircuitState
from remediation.state_manager import PipelineState, PipelineStateManager
from remediation.controller import RemediationController

logger = logging.getLogger("icestream.quality_engine.streaming")

# Prometheus Metrics
try:
    STREAM_EVENTS_VALIDATED_TOTAL = Counter(
        "icestream_stream_events_validated_total",
        "Total events evaluated by stream quality validator",
        labelnames=["status", "pipeline_id"],
    )
except ValueError:
    from prometheus_client import REGISTRY
    STREAM_EVENTS_VALIDATED_TOTAL = REGISTRY._names_to_collectors.get("icestream_stream_events_validated_total")

try:
    STREAM_QUARANTINE_ROUTED_TOTAL = Counter(
        "icestream_stream_quarantine_routed_total",
        "Total events routed to quarantine from stream",
        labelnames=["error_code", "pipeline_id"],
    )
except ValueError:
    from prometheus_client import REGISTRY
    STREAM_QUARANTINE_ROUTED_TOTAL = REGISTRY._names_to_collectors.get("icestream_stream_quarantine_routed_total")

try:
    STREAM_CIRCUIT_TRIPPED_TOTAL = Counter(
        "icestream_stream_circuit_tripped_total",
        "Total occurrences of stream circuit breaker tripping to OPEN",
        labelnames=["pipeline_id"],
    )
except ValueError:
    from prometheus_client import REGISTRY
    STREAM_CIRCUIT_TRIPPED_TOTAL = REGISTRY._names_to_collectors.get("icestream_stream_circuit_tripped_total")


@dataclass
class ValidationOutcome:
    """Consolidated outcome of evaluating a stream event."""

    event_id: Optional[str]
    is_valid: bool
    summary: Optional[ValidationSummary]
    quarantine_result: Optional[QuarantineRouteResult] = None
    circuit_state: str = "CLOSED"
    incident_id: Optional[str] = None
    error_rate: float = 0.0


class StreamQualityValidator:
    """Validates real-time streaming events, routes to quarantine, and monitors circuit breaker."""

    def __init__(
        self,
        quality_engine: Optional[QualityEngine] = None,
        quarantine_router: Optional[QuarantineRouter] = None,
        error_rate_engine: Optional[ErrorRateEngine] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
        state_manager: Optional[PipelineStateManager] = None,
        remediation_controller: Optional[RemediationController] = None,
        pipeline_id: str = "icestream",
        auto_quarantine: bool = True,
        auto_trip_circuit: bool = True,
        auto_remediate: bool = False,
        circuit_window_seconds: int = 60,
    ) -> None:
        self.pipeline_id = pipeline_id
        self.quality_engine = quality_engine or QualityEngine(registry=create_default_registry())
        self.quarantine_router = quarantine_router or QuarantineRouter()
        self.error_rate_engine = error_rate_engine or ErrorRateEngine()
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        self.state_manager = state_manager
        self.remediation_controller = remediation_controller
        self.auto_quarantine = auto_quarantine
        self.auto_trip_circuit = auto_trip_circuit
        self.auto_remediate = auto_remediate
        self.circuit_window_seconds = circuit_window_seconds
        self._lock = threading.Lock()

    def validate_event(
        self,
        payload: Union[Dict[str, Any], str, bytes, QualityEvent],
    ) -> ValidationOutcome:
        """Validate a single incoming stream event payload.

        Handles:
        1. Raw bytes/string JSON deserialization (capturing malformed payloads).
        2. Rule execution through QualityEngine.
        3. Updating ErrorRateEngine metrics.
        4. Routing failing events to QuarantineRouter (Iceberg persistence).
        5. Checking circuit breaker error rate thresholds and updating pipeline state.
        """
        raw_event_dict: Optional[Dict[str, Any]] = None
        event_id: Optional[str] = None

        # 1. Safe deserialization
        if isinstance(payload, bytes):
            try:
                decoded_str = payload.decode("utf-8")
                raw_event_dict = json.loads(decoded_str)
            except Exception as e:
                return self._handle_malformed_payload(payload_str=str(payload), error_msg=str(e))
        elif isinstance(payload, str):
            try:
                raw_event_dict = json.loads(payload)
            except Exception as e:
                return self._handle_malformed_payload(payload_str=payload, error_msg=str(e))
        elif isinstance(payload, dict):
            raw_event_dict = payload
        elif isinstance(payload, QualityEvent):
            raw_event_dict = payload.to_dict()
        else:
            return self._handle_malformed_payload(
                payload_str=str(payload),
                error_msg=f"Unsupported payload type: {type(payload).__name__}",
            )

        if raw_event_dict is not None:
            event_id = raw_event_dict.get("event_id")
            # Raw events from Kafka represent application-layer payloads and do not
            # carry lakehouse platform ingestion metadata. Assign ingestion_time upon stream consumption.
            if "ingestion_time" not in raw_event_dict:
                raw_event_dict["ingestion_time"] = datetime.now(timezone.utc).isoformat()

        # 2. Rule evaluation via QualityEngine
        try:
            results, summary = self.quality_engine.validate_with_summary(raw_event_dict)
        except Exception as ex:
            logger.error("Unexpected exception during QualityEngine evaluation: %s", ex)
            return self._handle_malformed_payload(
                payload_str=json.dumps(raw_event_dict),
                error_msg=f"QualityEngine evaluation failure: {str(ex)}",
            )

        is_valid = summary.overall_status in (EventStatus.HEALTHY, EventStatus.WARNING)
        now_ts = datetime.now(timezone.utc).isoformat()

        # 3. Update ErrorRateEngine
        self.error_rate_engine.record_event(summary, timestamp=now_ts)

        quarantine_result: Optional[QuarantineRouteResult] = None
        incident_id: Optional[str] = None

        if is_valid:
            if STREAM_EVENTS_VALIDATED_TOTAL is not None:
                STREAM_EVENTS_VALIDATED_TOTAL.labels(status="valid", pipeline_id=self.pipeline_id).inc()
            return ValidationOutcome(
                event_id=event_id,
                is_valid=True,
                summary=summary,
                quarantine_result=None,
                circuit_state=self.circuit_breaker.state.name,
                incident_id=None,
                error_rate=self.error_rate_engine.calculate(self.circuit_window_seconds).error_rate,
            )

        # 4. Handle Invalid Event
        if STREAM_EVENTS_VALIDATED_TOTAL is not None:
            STREAM_EVENTS_VALIDATED_TOTAL.labels(status="invalid", pipeline_id=self.pipeline_id).inc()

        if self.auto_quarantine and self.quarantine_router:
            try:
                quarantine_result = self.quarantine_router.route_invalid_event(raw_event_dict, summary)
                if (
                    quarantine_result
                    and quarantine_result.quarantine_record
                    and STREAM_QUARANTINE_ROUTED_TOTAL is not None
                ):
                    STREAM_QUARANTINE_ROUTED_TOTAL.labels(
                        error_code=quarantine_result.quarantine_record.error_code,
                        pipeline_id=self.pipeline_id,
                    ).inc()
            except Exception as q_err:
                logger.error("Failed to route invalid event %s to quarantine: %s", event_id, q_err)

        # 5. Circuit Breaker & Incident Evaluation
        current_metrics = self.error_rate_engine.calculate(window_seconds=self.circuit_window_seconds)
        current_error_rate = current_metrics.error_rate

        if self.auto_trip_circuit and self.circuit_breaker:
            old_circuit_state = self.circuit_breaker.state
            new_circuit_state = self.circuit_breaker.evaluate(current_error_rate)

            # Auto-close from HALF_OPEN when error rate returns below threshold with adequate sample
            if (
                old_circuit_state == CircuitState.HALF_OPEN
                and current_metrics.total_events >= 10
                and current_error_rate <= self.circuit_breaker.config.error_threshold
            ):
                try:
                    self.circuit_breaker.record_recovery_result(error_rate=current_error_rate, success=True)
                except Exception as rec_err:
                    logger.debug("Could not record recovery result: %s", rec_err)

            # Tripped from CLOSED/HALF_OPEN to OPEN
            elif new_circuit_state == CircuitState.OPEN and old_circuit_state != CircuitState.OPEN:
                if STREAM_CIRCUIT_TRIPPED_TOTAL is not None:
                    STREAM_CIRCUIT_TRIPPED_TOTAL.labels(pipeline_id=self.pipeline_id).inc()

                logger.warning(
                    "[StreamQualityValidator] Circuit breaker tripped to OPEN! "
                    "Rolling error rate: %.4f (threshold: %.4f)",
                    current_error_rate,
                    self.circuit_breaker.config.error_threshold,
                )

                # Open an Incident
                if self.remediation_controller is not None:
                    try:
                        incident = self.remediation_controller.get_or_create_incident(
                            trigger="STREAM_QUALITY_DEGRADATION",
                            error_rate=current_error_rate,
                            failed_event_count=current_metrics.failed_events,
                            quarantine_count=current_metrics.failed_events,
                        )
                        incident_id = incident.get("incident_id")
                        logger.info(
                            "[StreamQualityValidator] Created self-healing incident '%s' for error rate spike.",
                            incident_id,
                        )

                        if self.auto_remediate and incident_id:
                            threading.Thread(
                                target=self.remediation_controller.execute_remediation,
                                args=(incident_id,),
                                daemon=True,
                                name=f"AutoRemediation-{incident_id}",
                            ).start()
                    except Exception as rc_err:
                        logger.error("Failed to trigger incident creation on circuit trip: %s", rc_err)

                # Transition pipeline state manager
                if self.state_manager is not None:
                    try:
                        self.state_manager.transition_to(
                            to_state=PipelineState.CIRCUIT_OPEN,
                            reason=f"Streaming error rate {current_metrics.error_rate_percent:.2f}% exceeded threshold",
                            incident_id=incident_id,
                        )
                    except Exception as sm_err:
                        logger.error("Failed to transition pipeline state to CIRCUIT_OPEN: %s", sm_err)

        return ValidationOutcome(
            event_id=event_id,
            is_valid=False,
            summary=summary,
            quarantine_result=quarantine_result,
            circuit_state=self.circuit_breaker.state.name,
            incident_id=incident_id,
            error_rate=current_error_rate,
        )

    def _handle_malformed_payload(self, payload_str: str, error_msg: str) -> ValidationOutcome:
        """Handle severely malformed or unparseable payload string."""
        now_ts = datetime.now(timezone.utc).isoformat()
        res = ValidationResult(
            rule_name="malformed_json",
            passed=False,
            severity=Severity.CRITICAL,
            message=error_msg,
            field="payload",
            timestamp=now_ts,
        )
        summary = compute_validation_summary([res], event_id=None)

        self.error_rate_engine.record_event_outcome(is_valid=False, timestamp=now_ts)
        if STREAM_EVENTS_VALIDATED_TOTAL is not None:
            STREAM_EVENTS_VALIDATED_TOTAL.labels(status="invalid", pipeline_id=self.pipeline_id).inc()

        quarantine_result: Optional[QuarantineRouteResult] = None
        if self.auto_quarantine and self.quarantine_router:
            synth_dict = {"event_id": "malformed_event", "raw_payload": payload_str}
            quarantine_result = self.quarantine_router.route_invalid_event(synth_dict, summary)
            if (
                quarantine_result
                and quarantine_result.quarantine_record
                and STREAM_QUARANTINE_ROUTED_TOTAL is not None
            ):
                STREAM_QUARANTINE_ROUTED_TOTAL.labels(
                    error_code=quarantine_result.quarantine_record.error_code,
                    pipeline_id=self.pipeline_id,
                ).inc()

        current_metrics = self.error_rate_engine.calculate(window_seconds=self.circuit_window_seconds)
        return ValidationOutcome(
            event_id=None,
            is_valid=False,
            summary=summary,
            quarantine_result=quarantine_result,
            circuit_state=self.circuit_breaker.state.name,
            error_rate=current_metrics.error_rate,
        )

    def process_batch(
        self,
        events: List[Any],
        flush_quarantine: bool = True,
    ) -> List[ValidationOutcome]:
        """Validate a collection of events and flush quarantine persistence at end of batch."""
        outcomes = [self.validate_event(evt) for evt in events]
        if flush_quarantine and self.quarantine_router and self.quarantine_router.writer:
            self.quarantine_router.writer.flush()
        return outcomes

    def consume_stream(
        self,
        consumer: Any,
        stop_event: Optional[threading.Event] = None,
        max_messages: Optional[int] = None,
        poll_timeout: float = 1.0,
    ) -> int:
        """Continuous stream consumption loop.

        Args:
            consumer: Confluent-Kafka or mock consumer with poll(timeout) interface.
            stop_event: Optional threading event to signal loop termination.
            max_messages: Optional limit on total processed messages (for testing/batch).
            poll_timeout: Poll timeout in seconds.

        Returns:
            Total messages processed.
        """
        processed_count = 0
        logger.info("[StreamQualityValidator] Starting stream consumption loop...")

        try:
            while True:
                if stop_event is not None and stop_event.is_set():
                    break
                if max_messages is not None and processed_count >= max_messages:
                    break

                msg = consumer.poll(timeout=poll_timeout)
                if msg is None:
                    continue

                if hasattr(msg, "error") and callable(msg.error) and msg.error():
                    # Handle Kafka partition EOF or errors
                    err = msg.error()
                    err_code = getattr(err, "code", lambda: None)()
                    if err_code != -191:  # KafkaError._PARTITION_EOF
                        logger.warning("Kafka consumer error: %s", err)
                    continue

                val = msg.value() if hasattr(msg, "value") and callable(msg.value) else msg
                self.validate_event(val)
                processed_count += 1

                # Periodic flush check
                if processed_count % 50 == 0 and self.quarantine_router and self.quarantine_router.writer:
                    self.quarantine_router.writer.flush()

        finally:
            if self.quarantine_router and self.quarantine_router.writer:
                self.quarantine_router.writer.flush()
            logger.info("[StreamQualityValidator] Stream consumption loop stopped. Processed %d messages.", processed_count)

        return processed_count
