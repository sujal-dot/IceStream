"""Error-Rate Engine for IceStream Quality Engine.

Computes rolling window event error rates, classifies pipeline data health status
(HEALTHY, WARNING, CRITICAL), and enforces metric invariants.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
import threading
from typing import Any, Dict, List, Optional, Union

from rules.base import EventStatus, ValidationSummary
from rules.clock import Clock, SystemClock, parse_iso_timestamp
from metrics.window import WindowAggregator, WindowMetrics

logger = logging.getLogger("quality_engine.metrics.error_rate")


class HealthStatus(str, Enum):
    """Pipeline data health classification categories."""

    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass
class ErrorRateConfig:
    """Configurable threshold definitions for ErrorRateEngine."""

    healthy_max: float = 0.01
    warning_max: float = 0.02

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validate threshold parameters.
        
        Raises:
            ValueError: If configuration values are missing, non-numeric, out-of-bounds,
                       or if healthy_max >= warning_max.
        """
        for param_name, val in [("healthy_max", self.healthy_max), ("warning_max", self.warning_max)]:
            if val is None:
                raise ValueError(f"Configuration threshold '{param_name}' cannot be None")
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                raise ValueError(
                    f"Configuration threshold '{param_name}' must be numeric, got {type(val).__name__}"
                )
            if val < 0.0:
                raise ValueError(f"Configuration threshold '{param_name}' cannot be negative ({val})")
            if val > 1.0:
                raise ValueError(f"Configuration threshold '{param_name}' cannot exceed 1.0 ({val})")

        if float(self.healthy_max) >= float(self.warning_max):
            raise ValueError(
                f"Invalid error rate thresholds: healthy_max ({self.healthy_max}) "
                f"must be strictly less than warning_max ({self.warning_max})"
            )


@dataclass
class ErrorRateMetrics:
    """Structured container for error rate calculations and health classification."""

    window_seconds: int
    window_start: Optional[str]
    window_end: Optional[str]
    total_events: int
    valid_events: int
    failed_events: int
    error_rate: float
    error_rate_percent: float
    health_status: HealthStatus
    data_available: bool
    calculated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary format matching API specifications."""
        return {
            "window_seconds": self.window_seconds,
            "window_start": self.window_start,
            "window_end": self.window_end,
            "total_events": self.total_events,
            "valid_events": self.valid_events,
            "failed_events": self.failed_events,
            "error_rate": self.error_rate,
            "error_rate_percent": round(self.error_rate_percent, 4),
            "health": self.health_status.value if isinstance(self.health_status, Enum) else str(self.health_status),
            "data_available": self.data_available,
            "calculated_at": self.calculated_at,
        }


class ErrorRateEngine:
    """Engine for computing pipeline error rates and health status.
    
    Formula:
        error_rate = failed_events / total_events
        (0.0 when total_events == 0)

    Health Categories:
        < 1%       ( < healthy_max )  -> HEALTHY
        1-2%  ( healthy_max <= rate <= warning_max ) -> WARNING
        > 2%       ( > warning_max )  -> CRITICAL
    """

    def __init__(
        self,
        config: Optional[ErrorRateConfig] = None,
        windows: Optional[List[int]] = None,
        clock: Optional[Clock] = None,
    ) -> None:
        self._config = config or ErrorRateConfig()
        self._config.validate()
        self._window_sizes = windows or [60, 300]
        self._clock = clock or SystemClock()
        self._lock = threading.Lock()
        self._last_health_state: Dict[int, HealthStatus] = {}

        self._window_aggregators: Dict[int, WindowAggregator] = {
            w: WindowAggregator(window_seconds=w, clock=self._clock)
            for w in self._window_sizes
        }

    @property
    def config(self) -> ErrorRateConfig:
        return self._config

    def reset(self) -> None:
        """Reset all internal window state."""
        with self._lock:
            for agg in self._window_aggregators.values():
                agg.reset()
            self._last_health_state.clear()

    def record_event_outcome(
        self,
        is_valid: bool,
        timestamp: Optional[Union[datetime, str]] = None,
    ) -> None:
        """Record a single event validation outcome into rolling windows."""
        with self._lock:
            for agg in self._window_aggregators.values():
                agg.add_event(is_valid=is_valid, timestamp=timestamp)

    def record_event(
        self,
        summary: ValidationSummary,
        timestamp: Optional[Union[datetime, str]] = None,
    ) -> None:
        """Record an event validation summary outcome into rolling windows.
        
        Event validity rule:
            summary.overall_status == EventStatus.HEALTHY -> valid event (is_valid=True)
            summary.overall_status != EventStatus.HEALTHY -> failed event (is_valid=False)
        """
        is_valid = (summary.overall_status == EventStatus.HEALTHY)
        self.record_event_outcome(is_valid=is_valid, timestamp=timestamp)

    def classify(self, error_rate: float) -> HealthStatus:
        """Classify pipeline health based on raw error rate ratio.
        
        Boundary rules:
            error_rate < healthy_max                  -> HEALTHY
            healthy_max <= error_rate <= warning_max -> WARNING
            error_rate > warning_max                  -> CRITICAL
        """
        if error_rate < self._config.healthy_max:
            return HealthStatus.HEALTHY
        elif error_rate <= self._config.warning_max:
            return HealthStatus.WARNING
        else:
            return HealthStatus.CRITICAL

    def calculate(
        self,
        window_seconds: int = 60,
        ref_time: Optional[Union[datetime, str]] = None,
    ) -> ErrorRateMetrics:
        """Calculate error rate metrics for a given rolling window duration.
        
        Args:
            window_seconds: Window size in seconds (e.g. 60 or 300).
            ref_time: Evaluation baseline timestamp (defaults to current clock time).

        Returns:
            ErrorRateMetrics instance.
        """
        with self._lock:
            agg = self._window_aggregators.get(window_seconds)
            if agg is None:
                agg = WindowAggregator(window_seconds=window_seconds, clock=self._clock)
                self._window_aggregators[window_seconds] = agg

            win_metrics = agg.get_metrics(ref_time=ref_time)

        total_events = win_metrics.total_events
        valid_events = win_metrics.valid_events
        failed_events = win_metrics.invalid_events  # failed events

        # Invariant checks
        if total_events < 0 or valid_events < 0 or failed_events < 0:
            raise ValueError(f"Invariant violation: negative event counts ({win_metrics})")
        if valid_events + failed_events != total_events:
            raise ValueError(f"Invariant violation: valid ({valid_events}) + failed ({failed_events}) != total ({total_events})")
        if failed_events > total_events:
            raise ValueError(f"Invariant violation: failed_events ({failed_events}) > total_events ({total_events})")

        if total_events > 0:
            error_rate = failed_events / total_events
            data_available = True
        else:
            error_rate = 0.0
            data_available = False

        if not (0.0 <= error_rate <= 1.0):
            raise ValueError(f"Invariant violation: error_rate out of range [0.0, 1.0]: {error_rate}")

        error_rate_percent = error_rate * 100.0
        health = self.classify(error_rate)

        # Log health transition if status changed
        with self._lock:
            prev_health = self._last_health_state.get(window_seconds)
            if prev_health is not None and prev_health != health:
                logger.info(
                    "ERROR RATE STATUS CHANGE [%ds window]: previous=%s, current=%s, error_rate=%.2f%%",
                    window_seconds,
                    prev_health.value,
                    health.value,
                    error_rate_percent,
                )
            self._last_health_state[window_seconds] = health

        calc_time = (
            parse_iso_timestamp(ref_time).isoformat()
            if ref_time and parse_iso_timestamp(ref_time)
            else self._clock.now().isoformat()
        )

        return ErrorRateMetrics(
            window_seconds=window_seconds,
            window_start=win_metrics.window_start,
            window_end=win_metrics.window_end,
            total_events=total_events,
            valid_events=valid_events,
            failed_events=failed_events,
            error_rate=error_rate,
            error_rate_percent=error_rate_percent,
            health_status=health,
            data_available=data_available,
            calculated_at=calc_time,
        )

    def get_metrics_snapshot(
        self,
        ref_time: Optional[Union[datetime, str]] = None,
    ) -> Dict[str, Any]:
        """Generate full metrics snapshot dictionary for all configured windows."""
        now_dt = parse_iso_timestamp(ref_time) or self._clock.now()
        now_iso = now_dt.isoformat()

        m1 = self.calculate(window_seconds=60, ref_time=now_dt)
        m5 = self.calculate(window_seconds=300, ref_time=now_dt)

        return {
            "service": "icestream-quality-engine",
            "status": "ok",
            "timestamp": now_iso,
            "windows": {
                "1m": m1.to_dict(),
                "5m": m5.to_dict(),
            },
        }
