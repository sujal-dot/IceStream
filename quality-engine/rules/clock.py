"""Clock abstractions for deterministic time handling in IceStream Quality Engine."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional, Union


def get_utc_now() -> datetime:
    """Get current UTC datetime."""
    return datetime.now(timezone.utc)


def parse_iso_timestamp(ts: Union[str, datetime, int, float, None]) -> Optional[datetime]:
    """Parse an ISO 8601 string or numeric timestamp into a UTC datetime object."""
    if ts is None:
        return None
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            return ts.replace(tzinfo=timezone.utc)
        return ts.astimezone(timezone.utc)
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    if isinstance(ts, str):
        cleaned = ts.strip()
        if not cleaned or cleaned.lower() == "none":
            return None
        # Handle 'Z' suffix for python < 3.11 compatibility
        if cleaned.endswith("Z") or cleaned.endswith("z"):
            cleaned = cleaned[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(cleaned)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except (ValueError, TypeError):
            return None
    return None


class Clock(ABC):
    """Abstract interface for getting the current time."""

    @abstractmethod
    def now(self) -> datetime:
        """Return current datetime in UTC."""
        pass


class SystemClock(Clock):
    """Real system clock implementation returning UTC datetime."""

    def now(self) -> datetime:
        return get_utc_now()


class FixedClock(Clock):
    """Fixed, deterministic clock for testing."""

    def __init__(self, initial_time: Union[str, datetime, None] = None) -> None:
        if initial_time is None:
            self._current_time = datetime(2026, 8, 26, 10, 0, 0, tzinfo=timezone.utc)
        else:
            parsed = parse_iso_timestamp(initial_time)
            if parsed is None:
                raise ValueError(f"Invalid initial_time: {initial_time}")
            self._current_time = parsed

    def now(self) -> datetime:
        return self._current_time

    def set_time(self, new_time: Union[str, datetime]) -> None:
        """Explicitly set current time."""
        parsed = parse_iso_timestamp(new_time)
        if parsed is None:
            raise ValueError(f"Invalid time string: {new_time}")
        self._current_time = parsed

    def advance(self, seconds: float) -> None:
        """Advance clock by N seconds."""
        from datetime import timedelta
        self._current_time += timedelta(seconds=seconds)
