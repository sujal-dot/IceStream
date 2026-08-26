"""Duplicate event and order detection rules with bounded state expiration."""

from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Union

from rules.base import QualityRule, Severity, ValidationResult
from rules.clock import Clock, SystemClock, parse_iso_timestamp
from schemas.event import QualityEvent


class DuplicateEventRule(QualityRule):
    """Detects duplicate event_ids within a rolling time window.
    
    State is bounded and expires after window_seconds.
    Null/empty event_ids are skipped (handled by NotNullRule).
    """

    def __init__(
        self,
        window_seconds: int = 300,
        clock: Optional[Clock] = None,
        severity_override: Optional[Severity] = None,
        enabled: bool = True,
    ) -> None:
        super().__init__(severity_override=severity_override, enabled=enabled)
        self._window_seconds = window_seconds
        self._clock = clock or SystemClock()
        self._seen_events: Dict[str, datetime] = {}

    @property
    def name(self) -> str:
        return "duplicate_event"

    @property
    def default_severity(self) -> Severity:
        return Severity.CRITICAL

    @property
    def window_seconds(self) -> int:
        return self._window_seconds

    @window_seconds.setter
    def window_seconds(self, value: int) -> None:
        self._window_seconds = int(value)

    def reset(self) -> None:
        """Clear internal duplicate tracking state."""
        self._seen_events.clear()

    def _purge_expired(self, ref_time: datetime) -> None:
        """Remove state entries older than window_seconds relative to ref_time."""
        cutoff = ref_time - timedelta(seconds=self._window_seconds)
        expired = [eid for eid, seen_time in self._seen_events.items() if seen_time < cutoff]
        for eid in expired:
            del self._seen_events[eid]

    def validate(self, event: QualityEvent) -> ValidationResult:
        event_id = event.event_id

        # Skip null or empty event_id (handled by event_id_not_null)
        if event_id is None or str(event_id).strip() == "" or str(event_id).strip().lower() == "none":
            return ValidationResult(
                rule_name=self.name,
                passed=True,
                severity=self.severity,
                message="Skipped duplicate check for null/empty event_id",
                field="event_id",
                event_id=None,
                metadata={"skipped": True},
            )

        event_id_str = str(event_id)
        now_dt = self._clock.now()

        # Purge state before evaluation
        self._purge_expired(now_dt)

        if event_id_str in self._seen_events:
            first_seen = self._seen_events[event_id_str].isoformat()
            return ValidationResult(
                rule_name=self.name,
                passed=False,
                severity=self.severity,
                message="duplicate event_id detected",
                field="event_id",
                event_id=event_id_str,
                metadata={
                    "provided_value": event_id_str,
                    "first_seen": first_seen,
                    "window_seconds": self._window_seconds,
                },
            )

        self._seen_events[event_id_str] = now_dt
        return ValidationResult(
            rule_name=self.name,
            passed=True,
            severity=self.severity,
            message="event_id is unique in active window",
            field="event_id",
            event_id=event_id_str,
            metadata={"provided_value": event_id_str},
        )


class DuplicateOrderRule(QualityRule):
    """Detects duplicate order_ids within a rolling time window.
    
    Repeated order_id in window is flagged with HIGH severity as a quality/anomaly signal.
    State is bounded and expires after window_seconds.
    Null/empty order_ids are skipped (handled by NotNullRule).
    """

    def __init__(
        self,
        window_seconds: int = 300,
        clock: Optional[Clock] = None,
        severity_override: Optional[Severity] = None,
        enabled: bool = True,
    ) -> None:
        super().__init__(severity_override=severity_override, enabled=enabled)
        self._window_seconds = window_seconds
        self._clock = clock or SystemClock()
        self._seen_orders: Dict[str, datetime] = {}

    @property
    def name(self) -> str:
        return "duplicate_order"

    @property
    def default_severity(self) -> Severity:
        return Severity.HIGH

    @property
    def window_seconds(self) -> int:
        return self._window_seconds

    @window_seconds.setter
    def window_seconds(self, value: int) -> None:
        self._window_seconds = int(value)

    def reset(self) -> None:
        """Clear internal tracking state."""
        self._seen_orders.clear()

    def _purge_expired(self, ref_time: datetime) -> None:
        """Remove state entries older than window_seconds relative to ref_time."""
        cutoff = ref_time - timedelta(seconds=self._window_seconds)
        expired = [oid for oid, seen_time in self._seen_orders.items() if seen_time < cutoff]
        for oid in expired:
            del self._seen_orders[oid]

    def validate(self, event: QualityEvent) -> ValidationResult:
        order_id = event.order_id

        # Skip null or empty order_id
        if order_id is None or str(order_id).strip() == "" or str(order_id).strip().lower() == "none":
            return ValidationResult(
                rule_name=self.name,
                passed=True,
                severity=self.severity,
                message="Skipped duplicate check for null/empty order_id",
                field="order_id",
                event_id=event.event_id,
                metadata={"skipped": True},
            )

        order_id_str = str(order_id)
        now_dt = self._clock.now()

        # Purge state before evaluation
        self._purge_expired(now_dt)

        if order_id_str in self._seen_orders:
            first_seen = self._seen_orders[order_id_str].isoformat()
            return ValidationResult(
                rule_name=self.name,
                passed=False,
                severity=self.severity,
                message="duplicate order_id detected",
                field="order_id",
                event_id=event.event_id,
                metadata={
                    "provided_value": order_id_str,
                    "first_seen": first_seen,
                    "window_seconds": self._window_seconds,
                },
            )

        self._seen_orders[order_id_str] = now_dt
        return ValidationResult(
            rule_name=self.name,
            passed=True,
            severity=self.severity,
            message="order_id is unique in active window",
            field="order_id",
            event_id=event.event_id,
            metadata={"provided_value": order_id_str},
        )
