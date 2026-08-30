"""Authoritative Circuit Breaker State Machine for IceStream Quality Engine."""

from collections import deque
from datetime import datetime, timezone
from enum import Enum
import logging
import threading
from typing import Any, Dict, List, Optional, Union

from rules.clock import Clock, SystemClock
from circuit_breaker.config import CircuitBreakerConfig
from circuit_breaker.state import (
    CircuitBreakerStatus,
    CircuitState,
    InvalidStateTransitionError,
    StateTransition,
)

logger = logging.getLogger("quality_engine.circuit_breaker")

# Numeric state mappings for monitoring & metrics
STATE_METRIC_MAP = {
    CircuitState.CLOSED: 0,
    CircuitState.OPEN: 1,
    CircuitState.HALF_OPEN: 2,
}


class CircuitBreaker:
    """Authoritative state machine component managing pipeline processing permissions.
    
    States:
        CLOSED: Normal pipeline operations. (can_process=True, can_probe=False)
        OPEN: Critical error rate detected; processing suspended. (can_process=False, can_probe=False)
        HALF_OPEN: Recovery timeout elapsed; testing pipeline recovery. (can_process=False, can_probe=True)
    """

    VALID_TRANSITIONS = {
        (CircuitState.CLOSED, CircuitState.OPEN),
        (CircuitState.OPEN, CircuitState.HALF_OPEN),
        (CircuitState.HALF_OPEN, CircuitState.CLOSED),
        (CircuitState.HALF_OPEN, CircuitState.OPEN),
    }

    def __init__(
        self,
        config: Optional[CircuitBreakerConfig] = None,
        clock: Optional[Clock] = None,
    ) -> None:
        self._config = config or CircuitBreakerConfig()
        self._config.validate()
        self._clock = clock or SystemClock()
        self._lock = threading.Lock()

        self._state: CircuitState = CircuitState.CLOSED
        self._opened_at_dt: Optional[datetime] = None
        self._last_state_change_dt: datetime = self._clock.now()

        self._probe_active: bool = False
        self._last_error_rate: float = 0.0

        self._recovery_attempts: int = 0
        self._successful_recoveries: int = 0
        self._failed_recoveries: int = 0

        self._open_total_count: int = 0
        self._history: deque = deque(maxlen=self._config.max_history)

        logger.info(
            "[CIRCUIT BREAKER] Initialized: state=%s, enabled=%s, threshold=%.4f, recovery_timeout=%.1fs",
            self._state.value,
            self._config.enabled,
            self._config.error_threshold,
            self._config.recovery_timeout_seconds,
        )

    @property
    def config(self) -> CircuitBreakerConfig:
        return self._config

    @property
    def clock(self) -> Clock:
        return self._clock

    def current_state(self) -> CircuitState:
        """Retrieve current circuit state, checking and executing timeout transitions if OPEN."""
        with self._lock:
            self._check_timeout_transition_locked()
            return self._state

    @property
    def state(self) -> CircuitState:
        """Property wrapper for current_state."""
        return self.current_state()

    def _check_timeout_transition_locked(self) -> None:
        """Internal helper to check and apply OPEN -> HALF_OPEN timeout transition under lock."""
        if not self._config.enabled:
            return

        if self._state == CircuitState.OPEN and self._opened_at_dt is not None:
            now_dt = self._clock.now()
            elapsed = (now_dt - self._opened_at_dt).total_seconds()
            if elapsed >= self._config.recovery_timeout_seconds:
                self._execute_transition_locked(
                    new_state=CircuitState.HALF_OPEN,
                    reason="recovery_timeout_elapsed",
                    metadata={"elapsed_seconds": round(elapsed, 2)},
                )

    def can_process(self) -> bool:
        """Check whether the pipeline is permitted to process events."""
        with self._lock:
            if not self._config.enabled:
                return True
            self._check_timeout_transition_locked()
            return self._state == CircuitState.CLOSED

    def can_probe(self) -> bool:
        """Check whether a recovery probe attempt is permitted."""
        with self._lock:
            if not self._config.enabled:
                return False
            self._check_timeout_transition_locked()
            return self._state == CircuitState.HALF_OPEN and not self._probe_active

    def evaluate(self, error_rate: float) -> CircuitState:
        """Evaluate current error rate against circuit breaker thresholds.
        
        Args:
            error_rate: The pipeline error rate ratio (0.0 to 1.0).

        Returns:
            Current CircuitState after evaluation.
        """
        with self._lock:
            self._last_error_rate = error_rate
            if not self._config.enabled:
                return CircuitState.CLOSED

            self._check_timeout_transition_locked()

            if self._state == CircuitState.CLOSED:
                # Boundary rule: strictly > error_threshold triggers OPEN
                if error_rate > self._config.error_threshold:
                    self._execute_transition_locked(
                        new_state=CircuitState.OPEN,
                        reason="error_rate_above_threshold",
                        error_rate=error_rate,
                    )

            return self._state

    def evaluate_engine(self, engine: Any, window_seconds: int = 60) -> CircuitState:
        """Evaluate error rate directly from an ErrorRateEngine instance."""
        metrics = engine.calculate(window_seconds=window_seconds)
        return self.evaluate(metrics.error_rate)

    def transition_to(
        self,
        new_state: Union[CircuitState, str],
        reason: str = "manual",
        error_rate: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Explicitly perform a state transition with validation."""
        target_state = new_state if isinstance(new_state, CircuitState) else CircuitState(str(new_state))
        with self._lock:
            self._execute_transition_locked(
                new_state=target_state,
                reason=reason,
                error_rate=error_rate,
                metadata=metadata,
            )

    def _execute_transition_locked(
        self,
        new_state: CircuitState,
        reason: str,
        error_rate: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Internal atomic state transition execution under lock."""
        old_state = self._state

        # Same state transition is a no-op
        if old_state == new_state:
            return

        # Validate transition pair
        if (old_state, new_state) not in self.VALID_TRANSITIONS:
            raise InvalidStateTransitionError(
                f"Invalid state transition: cannot transition directly from {old_state.value} to {new_state.value}"
            )

        now_dt = self._clock.now()
        now_iso = now_dt.isoformat()

        # Update state timestamps & counters
        self._state = new_state
        self._last_state_change_dt = now_dt

        if new_state == CircuitState.OPEN:
            self._opened_at_dt = now_dt
            self._open_total_count += 1
            self._probe_active = False
        elif new_state == CircuitState.CLOSED:
            self._opened_at_dt = None
            self._probe_active = False

        # Record transition history
        transition_record = StateTransition(
            from_state=old_state.value,
            to_state=new_state.value,
            timestamp=now_iso,
            reason=reason,
            error_rate=error_rate if error_rate is not None else self._last_error_rate,
            metadata=metadata or {},
        )
        self._history.append(transition_record)

        # Log transition cleanly
        rate_str = (
            f" (error_rate={error_rate * 100.0:.2f}%)"
            if error_rate is not None
            else f" (error_rate={self._last_error_rate * 100.0:.2f}%)"
        )
        logger.info(
            "[CIRCUIT BREAKER] %s -> %s | reason: %s%s",
            old_state.value,
            new_state.value,
            reason,
            rate_str,
        )

    def begin_recovery_probe(self) -> bool:
        """Attempt to initiate a single concurrent recovery probe in HALF_OPEN state.
        
        Returns:
            True if permission granted (probe permitted); False if denied.
        """
        with self._lock:
            if not self._config.enabled:
                return False

            self._check_timeout_transition_locked()

            if self._state != CircuitState.HALF_OPEN:
                logger.debug(
                    "[CIRCUIT BREAKER] Recovery probe denied: current_state=%s (requires HALF_OPEN)",
                    self._state.value,
                )
                return False

            if self._probe_active:
                logger.debug("[CIRCUIT BREAKER] Recovery probe denied: probe already in progress")
                return False

            self._probe_active = True
            self._recovery_attempts += 1
            logger.info("[CIRCUIT BREAKER] Recovery probe permitted (attempt #%d)", self._recovery_attempts)
            return True

    def begin_recovery(self) -> bool:
        """Alias for begin_recovery_probe."""
        return self.begin_recovery_probe()

    def record_recovery_result(
        self,
        error_rate: float,
        success: Optional[bool] = None,
    ) -> CircuitState:
        """Record the outcome of a recovery probe and transition state.
        
        Args:
            error_rate: The observed recovery sample error rate.
            success: Optional explicit boolean pass/fail flag.

        Returns:
            The resulting CircuitState after recording probe outcome.
        """
        with self._lock:
            self._last_error_rate = error_rate

            if self._state != CircuitState.HALF_OPEN:
                raise InvalidStateTransitionError(
                    f"Cannot record recovery result when circuit is in {self._state.value} state"
                )

            is_pass = (
                success
                if success is not None
                else (error_rate <= self._config.error_threshold)
            )

            self._probe_active = False

            if is_pass:
                self._successful_recoveries += 1
                self._execute_transition_locked(
                    new_state=CircuitState.CLOSED,
                    reason="recovery_pass",
                    error_rate=error_rate,
                    metadata={"probe_success": True},
                )
            else:
                self._failed_recoveries += 1
                self._execute_transition_locked(
                    new_state=CircuitState.OPEN,
                    reason="recovery_fail",
                    error_rate=error_rate,
                    metadata={"probe_success": False},
                )

            return self._state

    def get_history(self) -> List[Dict[str, Any]]:
        """Retrieve bounded state transition history."""
        with self._lock:
            return [t.to_dict() for t in self._history]

    def get_status(self) -> CircuitBreakerStatus:
        """Construct structured CircuitBreakerStatus model."""
        with self._lock:
            self._check_timeout_transition_locked()
            can_proc = True if not self._config.enabled else (self._state == CircuitState.CLOSED)
            can_prb = False if not self._config.enabled else (self._state == CircuitState.HALF_OPEN and not self._probe_active)

            opened_at_str = self._opened_at_dt.isoformat() if self._opened_at_dt else None
            last_change_str = self._last_state_change_dt.isoformat()

            return CircuitBreakerStatus(
                state=self._state,
                enabled=self._config.enabled,
                error_rate=self._last_error_rate,
                threshold=self._config.error_threshold,
                can_process=can_proc,
                can_probe=can_prb,
                last_state_change=last_change_str,
                opened_at=opened_at_str,
                recovery_attempts=self._recovery_attempts,
                successful_recoveries=self._successful_recoveries,
                failed_recoveries=self._failed_recoveries,
            )

    def get_metrics(self) -> Dict[str, Any]:
        """Get circuit breaker metrics map for telemetry dashboards."""
        with self._lock:
            self._check_timeout_transition_locked()
            return {
                "circuit_breaker_state": STATE_METRIC_MAP[self._state],
                "circuit_breaker_open_total": self._open_total_count,
                "circuit_breaker_recovery_attempts_total": self._recovery_attempts,
                "circuit_breaker_recovery_success_total": self._successful_recoveries,
                "circuit_breaker_recovery_failure_total": self._failed_recoveries,
            }
