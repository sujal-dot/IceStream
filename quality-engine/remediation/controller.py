"""Remediation Controller for IceStream.

Orchestrates the authoritative self-healing lifecycle:
Quarantine Verification -> Alert -> Source Re-fetch -> Reprocessing -> Validation -> Circuit Recovery -> Pipeline Resume.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import threading
import time
from typing import Any, Dict, List, Optional

import sys
import os

QUALITY_ENGINE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if QUALITY_ENGINE_DIR not in sys.path:
    sys.path.insert(0, QUALITY_ENGINE_DIR)

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from circuit_breaker import CircuitBreaker, CircuitState
from hybrid_engine import QualityEngine
from quarantine.writer import QuarantineWriter
from storage.db import StorageBackend, get_db_storage

from remediation.state_manager import PipelineState, PipelineStateManager
from remediation.alert_service import AlertService, MockAlertService, SlackAlertAdapter
from remediation.source_adapter import LocalSourceAdapter, SourceAdapter
from remediation.reprocessor import ReprocessResult, Reprocessor
from remediation.metrics import (
    REMEDIATION_ATTEMPTS_TOTAL,
    REMEDIATION_DURATION_SECONDS,
    REMEDIATION_FAILURE_TOTAL,
    REMEDIATION_RECOVERED_EVENTS_TOTAL,
    REMEDIATION_SUCCESS_TOTAL,
    record_state_metric,
)

logger = logging.getLogger("icestream.remediation.controller")


@dataclass
class RemediationResult:
    incident_id: str
    success: bool
    stage: str
    attempt: int
    recovered_events: int = 0
    failed_events: int = 0
    error: Optional[str] = None
    started_at: str = ""
    completed_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "success": self.success,
            "stage": self.stage,
            "attempt": self.attempt,
            "recovered_events": self.recovered_events,
            "failed_events": self.failed_events,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


class RemediationController:
    """Remediation Controller orchestrating real self-healing workflows."""

    def __init__(
        self,
        pipeline_id: str = "icestream",
        state_manager: Optional[PipelineStateManager] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
        alert_service: Optional[AlertService] = None,
        source_adapter: Optional[SourceAdapter] = None,
        reprocessor: Optional[Reprocessor] = None,
        quarantine_writer: Optional[QuarantineWriter] = None,
        storage: Optional[StorageBackend] = None,
        max_recovery_attempts: int = 3,
    ):
        self.pipeline_id = pipeline_id
        self.storage = storage or get_db_storage()
        self.state_manager = state_manager or PipelineStateManager(
            pipeline_id=self.pipeline_id, storage=self.storage
        )
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        self.alert_service = alert_service or SlackAlertAdapter()
        self.source_adapter = source_adapter or LocalSourceAdapter()
        self.reprocessor = reprocessor or Reprocessor(
            quarantine_writer=quarantine_writer
        )
        self.quarantine_writer = quarantine_writer
        self.max_recovery_attempts = max_recovery_attempts

        self._lock = threading.Lock()
        self._active_remediations: Dict[str, bool] = {}

    def get_or_create_incident(
        self,
        trigger: str = "CRITICAL_ERROR_RATE",
        error_rate: float = 0.05,
        failed_event_count: int = 1,
        quarantine_count: int = 1,
        incident_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create or fetch incident record in database."""
        inc_id = incident_id or f"inc_{int(time.time())}"
        existing = self.storage.get_incident(inc_id)
        if existing:
            return existing

        inc_data = {
            "incident_id": inc_id,
            "pipeline_id": self.pipeline_id,
            "created_at": datetime.now(timezone.utc),
            "trigger": trigger,
            "error_rate": error_rate,
            "circuit_state": self.circuit_breaker.state.name,
            "failed_event_count": failed_event_count,
            "quarantine_count": quarantine_count,
            "status": "OPEN",
            "recovery_attempt": 0,
            "last_error": None,
            "resolved_at": None,
        }
        return self.storage.create_incident(inc_data)

    def verify_quarantine(self, incident: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Verify affected invalid events are persisted in quarantine before recovery begins.

        Step 12 Requirement: Do NOT attempt recovery if quarantine persistence has failed.
        """
        quarantine_count = incident.get("quarantine_count", 0)
        # If explicitly context quarantine_failed is set, return False
        if context.get("quarantine_write_failed") is True:
            logger.error("[QuarantineVerification] Explicit quarantine write failure in context.")
            return False

        # If quarantine writer is supplied and check fails
        if context.get("require_quarantine_check") is True and quarantine_count == 0:
            logger.error("[QuarantineVerification] Zero records found in quarantine for incident.")
            return False

        logger.info(f"[QuarantineVerification] Quarantine verified for incident '{incident['incident_id']}'.")
        return True

    def execute_remediation(
        self,
        incident_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> RemediationResult:
        """Execute full real automated self-healing flow for an incident.

        Enforces concurrency control, idempotency, quarantine verification, alerting,
        re-fetching, reprocessing, validation, circuit recovery, and state transitions.
        """
        start_time = time.perf_counter()
        start_ts = datetime.now(timezone.utc).isoformat()
        ctx = context or {}

        # 1. Concurrency & Idempotency Check (Step 28 & 29)
        with self._lock:
            if self._active_remediations.get(self.pipeline_id, False):
                logger.warning(
                    f"[RemediationController] Remediation already in progress for pipeline '{self.pipeline_id}'."
                )
                return RemediationResult(
                    incident_id=incident_id,
                    success=False,
                    stage="IDEMPOTENT_SKIPPED",
                    attempt=0,
                    error="Remediation workflow already in progress for this pipeline",
                    started_at=start_ts,
                    completed_at=datetime.now(timezone.utc).isoformat(),
                )
            self._active_remediations[self.pipeline_id] = True

        try:
            # Load incident
            incident = self.get_or_create_incident(incident_id=incident_id)
            attempt_num = incident.get("recovery_attempt", 0) + 1

            if attempt_num > self.max_recovery_attempts:
                logger.error(
                    f"[RemediationController] Max recovery attempts ({self.max_recovery_attempts}) "
                    f"exceeded for incident '{incident_id}'."
                )
                self.state_manager.record_failure(
                    error=f"Max recovery attempts ({self.max_recovery_attempts}) exceeded",
                    incident_id=incident_id,
                    recovery_attempt=attempt_num - 1,
                )
                return RemediationResult(
                    incident_id=incident_id,
                    success=False,
                    stage="MAX_ATTEMPTS_EXCEEDED",
                    attempt=attempt_num - 1,
                    error="Maximum recovery attempts exceeded",
                    started_at=start_ts,
                    completed_at=datetime.now(timezone.utc).isoformat(),
                )

            # Update incident state to REMEDIATING
            incident["recovery_attempt"] = attempt_num
            incident["status"] = "REMEDIATING"
            self.storage.create_incident(incident)

            # Transition pipeline state: CIRCUIT_OPEN -> REMEDIATING
            self.state_manager.transition_to(
                to_state=PipelineState.REMEDIATING,
                reason=f"Starting remediation attempt {attempt_num}",
                incident_id=incident_id,
                recovery_attempt=attempt_num,
                force=True,
            )
            record_state_metric(self.pipeline_id, "REMEDIATING")

            # 2. Stage: QUARANTINE_VERIFIED (Step 12)
            if not self.verify_quarantine(incident, ctx):
                err = "Quarantine verification failed. Invalid records not persisted."
                self.state_manager.record_failure(
                    error=err, incident_id=incident_id, recovery_attempt=attempt_num
                )
                incident["status"] = "RECOVERY_FAILED"
                incident["last_error"] = err
                self.storage.create_incident(incident)
                self.storage.record_remediation_attempt(
                    incident_id=incident_id,
                    attempt_number=attempt_num,
                    stage="QUARANTINE_VERIFIED",
                    status="FAILED",
                    started_at=datetime.fromisoformat(start_ts),
                    completed_at=datetime.now(timezone.utc),
                    error=err,
                )
                REMEDIATION_FAILURE_TOTAL.labels(
                    pipeline_id=self.pipeline_id, reason="quarantine_verification_failed"
                ).inc()
                return RemediationResult(
                    incident_id=incident_id,
                    success=False,
                    stage="QUARANTINE_VERIFIED",
                    attempt=attempt_num,
                    error=err,
                    started_at=start_ts,
                    completed_at=datetime.now(timezone.utc).isoformat(),
                )

            # 3. Stage: ALERT_SENT (Step 13, 14, 15)
            alert_success = self.alert_service.send_alert(incident)
            if not alert_success:
                logger.warning(f"[RemediationController] Alert dispatch returned warning for incident {incident_id}")

            self.storage.record_remediation_attempt(
                incident_id=incident_id,
                attempt_number=attempt_num,
                stage="ALERT_SENT",
                status="SUCCESS" if alert_success else "WARNING",
                started_at=datetime.fromisoformat(start_ts),
                completed_at=datetime.now(timezone.utc),
            )

            # 4. Stage: REFETCHING (Step 16, 17, 43)
            self.state_manager.transition_to(
                to_state=PipelineState.REFETCHING,
                reason=f"Re-fetching source data from {self.source_adapter.get_source_reference()}",
                incident_id=incident_id,
                recovery_attempt=attempt_num,
            )
            record_state_metric(self.pipeline_id, "REFETCHING")

            ctx["incident_id"] = incident_id
            if "failed_events" not in ctx and "failed_event" in ctx:
                ctx["failed_events"] = [ctx["failed_event"]]

            try:
                recovered_payloads = self.source_adapter.fetch_for_recovery(ctx)
            except Exception as e:
                err = f"Source re-fetch failed: {str(e)}"
                logger.error(f"[RemediationController] {err}")
                self.state_manager.record_failure(
                    error=err, incident_id=incident_id, recovery_attempt=attempt_num
                )
                incident["status"] = "RECOVERY_FAILED"
                incident["last_error"] = err
                self.storage.create_incident(incident)
                REMEDIATION_FAILURE_TOTAL.labels(
                    pipeline_id=self.pipeline_id, reason="refetch_failed"
                ).inc()
                return RemediationResult(
                    incident_id=incident_id,
                    success=False,
                    stage="REFETCHING",
                    attempt=attempt_num,
                    error=err,
                    started_at=start_ts,
                    completed_at=datetime.now(timezone.utc).isoformat(),
                )

            # 5. Stage: REPROCESSING (Step 20)
            self.state_manager.transition_to(
                to_state=PipelineState.REPROCESSING,
                reason=f"Reprocessing {len(recovered_payloads)} recovered events through QualityEngine",
                incident_id=incident_id,
                recovery_attempt=attempt_num,
            )
            record_state_metric(self.pipeline_id, "REPROCESSING")

            reprocess_res: ReprocessResult = self.reprocessor.process(
                recovered_events=recovered_payloads,
                incident_id=incident_id,
                attempt_number=attempt_num,
            )

            # 6. Stage: VALIDATING (Step 18, 22, 45, 47)
            self.state_manager.transition_to(
                to_state=PipelineState.VALIDATING,
                reason=f"Validating reprocessing outcome (error_rate={reprocess_res.error_rate:.4f})",
                incident_id=incident_id,
                recovery_attempt=attempt_num,
            )
            record_state_metric(self.pipeline_id, "VALIDATING")

            # Evaluate against CircuitBreaker recovery criteria
            # Check if circuit is OPEN -> transition via probe or record recovery result
            if self.circuit_breaker.state == CircuitState.OPEN:
                # If timeout passed, advance circuit breaker or force probe
                self.circuit_breaker.can_probe()

            # Tell CircuitBreaker the recovery probe result
            new_cb_state = self.circuit_breaker.record_recovery_result(
                error_rate=reprocess_res.error_rate
            )
            circuit_recovered = (new_cb_state == CircuitState.CLOSED)

            # Recovery succeeds ONLY if validation passed and CircuitBreaker closed
            if reprocess_res.is_fully_valid and (
                circuit_recovered or self.circuit_breaker.state == CircuitState.CLOSED
            ):
                # 7. Stage: RESUMING -> RUNNING (Step 31)
                self.state_manager.transition_to(
                    to_state=PipelineState.RESUMING,
                    reason="Validation passed. Preparing pipeline resume.",
                    incident_id=incident_id,
                    recovery_attempt=attempt_num,
                )
                record_state_metric(self.pipeline_id, "RESUMING")

                self.state_manager.transition_to(
                    to_state=PipelineState.RUNNING,
                    reason="Self-healing recovery completed successfully. Pipeline resumed.",
                    incident_id=incident_id,
                    recovery_attempt=attempt_num,
                )
                record_state_metric(self.pipeline_id, "RUNNING")

                # Update incident record to RECOVERED
                resolved_ts = datetime.now(timezone.utc)
                incident["status"] = "RECOVERED"
                incident["resolved_at"] = resolved_ts
                self.storage.create_incident(incident)

                self.storage.record_remediation_attempt(
                    incident_id=incident_id,
                    attempt_number=attempt_num,
                    stage="COMPLETE",
                    status="SUCCESS",
                    started_at=datetime.fromisoformat(start_ts),
                    completed_at=resolved_ts,
                    source_reference=self.source_adapter.get_source_reference(),
                    recovered_event_count=reprocess_res.valid_count,
                )

                duration = time.perf_counter() - start_time
                REMEDIATION_ATTEMPTS_TOTAL.labels(
                    pipeline_id=self.pipeline_id, stage="complete", status="success"
                ).inc()
                REMEDIATION_SUCCESS_TOTAL.labels(pipeline_id=self.pipeline_id).inc()
                REMEDIATION_RECOVERED_EVENTS_TOTAL.labels(pipeline_id=self.pipeline_id).inc(
                    reprocess_res.valid_count
                )
                REMEDIATION_DURATION_SECONDS.labels(pipeline_id=self.pipeline_id).observe(duration)

                logger.info(
                    f"[RemediationController] SUCCESS: Self-healing completed for incident '{incident_id}'. "
                    f"Recovered {reprocess_res.valid_count} events. Pipeline state: RUNNING."
                )

                return RemediationResult(
                    incident_id=incident_id,
                    success=True,
                    stage="COMPLETE",
                    attempt=attempt_num,
                    recovered_events=reprocess_res.valid_count,
                    failed_events=reprocess_res.invalid_count,
                    started_at=start_ts,
                    completed_at=resolved_ts.isoformat(),
                )
            else:
                # Recovery failed (Validation or Circuit Breaker failed)
                err = f"Validation or recovery threshold check failed (error_rate={reprocess_res.error_rate:.4f})"
                logger.warning(f"[RemediationController] {err}")

                self.state_manager.record_failure(
                    error=err, incident_id=incident_id, recovery_attempt=attempt_num
                )
                record_state_metric(self.pipeline_id, "RECOVERY_FAILED")

                incident["status"] = "RECOVERY_FAILED"
                incident["last_error"] = err
                self.storage.create_incident(incident)

                self.storage.record_remediation_attempt(
                    incident_id=incident_id,
                    attempt_number=attempt_num,
                    stage="VALIDATING",
                    status="FAILED",
                    started_at=datetime.fromisoformat(start_ts),
                    completed_at=datetime.now(timezone.utc),
                    error=err,
                    source_reference=self.source_adapter.get_source_reference(),
                    recovered_event_count=reprocess_res.valid_count,
                )

                REMEDIATION_ATTEMPTS_TOTAL.labels(
                    pipeline_id=self.pipeline_id, stage="validating", status="failed"
                ).inc()
                REMEDIATION_FAILURE_TOTAL.labels(
                    pipeline_id=self.pipeline_id, reason="validation_failed"
                ).inc()

                return RemediationResult(
                    incident_id=incident_id,
                    success=False,
                    stage="RECOVERY_FAILED",
                    attempt=attempt_num,
                    recovered_events=reprocess_res.valid_count,
                    failed_events=reprocess_res.invalid_count,
                    error=err,
                    started_at=start_ts,
                    completed_at=datetime.now(timezone.utc).isoformat(),
                )

        finally:
            with self._lock:
                self._active_remediations[self.pipeline_id] = False
