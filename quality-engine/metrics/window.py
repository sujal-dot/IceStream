"""Rolling-window metrics aggregator for Quality Engine."""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

from rules.clock import Clock, SystemClock, parse_iso_timestamp


@dataclass
class WindowMetrics:
    """Structured container for rolling window validation statistics."""

    window_seconds: int
    window_start: Optional[str]
    window_end: Optional[str]
    total_events: int
    valid_events: int
    invalid_events: int
    error_rate: float

    @property
    def failed_events(self) -> int:
        return self.invalid_events

    @property
    def error_rate_percent(self) -> float:
        return round(self.error_rate * 100.0, 4)

    @property
    def data_available(self) -> bool:
        return self.total_events > 0

    @property
    def health(self) -> str:
        if self.error_rate < 0.01:
            return "HEALTHY"
        elif self.error_rate <= 0.02:
            return "WARNING"
        else:
            return "CRITICAL"

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to standard dictionary representation."""
        return {
            "window_seconds": self.window_seconds,
            "window_start": self.window_start,
            "window_end": self.window_end,
            "total_events": self.total_events,
            "valid_events": self.valid_events,
            "invalid_events": self.invalid_events,
            "failed_events": self.failed_events,
            "error_rate": self.error_rate,
            "error_rate_percent": self.error_rate_percent,
            "health": self.health,
            "data_available": self.data_available,
        }


class WindowAggregator:
    """Rolling window metrics calculator for event validity and error rates.
    
    Stores timestamped event outcomes and automatically evicts entries
    that fall outside the rolling window_seconds range.
    """

    def __init__(
        self,
        window_seconds: int,
        clock: Optional[Clock] = None,
    ) -> None:
        self._window_seconds = int(window_seconds)
        self._clock = clock or SystemClock()
        self._records: deque[Tuple[datetime, bool]] = deque()

    @property
    def window_seconds(self) -> int:
        return self._window_seconds

    def reset(self) -> None:
        """Clear all aggregated window state."""
        self._records.clear()

    def add_event(
        self,
        is_valid: bool,
        timestamp: Optional[Union[datetime, str]] = None,
    ) -> None:
        """Record an event outcome into the window.
        
        Args:
            is_valid: True if event passed all rules, False if any rule failed.
            timestamp: Event timestamp or None (defaults to current clock time).
        """
        event_dt = parse_iso_timestamp(timestamp)
        if event_dt is None:
            event_dt = self._clock.now()

        self._records.append((event_dt, is_valid))

    def _evict_expired(self, ref_time: datetime) -> None:
        """Evict records older than window_seconds relative to ref_time."""
        cutoff = ref_time - timedelta(seconds=self._window_seconds)
        while self._records and self._records[0][0] < cutoff:
            self._records.popleft()

    def get_metrics(
        self,
        ref_time: Optional[Union[datetime, str]] = None,
    ) -> WindowMetrics:
        """Compute rolling window metrics as of ref_time.
        
        Args:
            ref_time: Current time baseline or None (defaults to clock.now()).

        Returns:
            WindowMetrics instance.
        """
        if ref_time is None:
            now_dt = self._clock.now()
        else:
            now_dt = parse_iso_timestamp(ref_time) or self._clock.now()

        self._evict_expired(now_dt)

        total_events = len(self._records)
        valid_events = sum(1 for _, valid in self._records if valid)
        invalid_events = total_events - valid_events

        error_rate = (
            (invalid_events / total_events) if total_events > 0 else 0.0
        )

        window_start_dt = (
            self._records[0][0]
            if total_events > 0
            else (now_dt - timedelta(seconds=self._window_seconds))
        )
        window_end_dt = now_dt

        return WindowMetrics(
            window_seconds=self._window_seconds,
            window_start=window_start_dt.isoformat(),
            window_end=window_end_dt.isoformat(),
            total_events=total_events,
            valid_events=valid_events,
            invalid_events=invalid_events,
            error_rate=error_rate,
        )
