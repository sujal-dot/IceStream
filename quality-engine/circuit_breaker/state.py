"""Circuit Breaker state enum, exception, and status models for IceStream Quality Engine."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class CircuitState(str, Enum):
    """Primary states for the Circuit Breaker state machine."""

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class InvalidStateTransitionError(ValueError):
    """Raised when an invalid state transition is attempted."""

    pass


@dataclass
class StateTransition:
    """Record of a circuit breaker state transition."""

    from_state: str
    to_state: str
    timestamp: str
    reason: str
    error_rate: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize state transition to a dictionary."""
        res: Dict[str, Any] = {
            "from": self.from_state,
            "to": self.to_state,
            "timestamp": self.timestamp,
            "reason": self.reason,
        }
        if self.error_rate is not None:
            res["error_rate"] = self.error_rate
        for k, v in self.metadata.items():
            if k not in res:
                res[k] = v
        return res


@dataclass
class CircuitBreakerStatus:
    """Structured status summary for CircuitBreaker."""

    state: CircuitState
    enabled: bool
    error_rate: float
    threshold: float
    can_process: bool
    can_probe: bool
    last_state_change: Optional[str]
    opened_at: Optional[str]
    recovery_attempts: int
    successful_recoveries: int
    failed_recoveries: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert status model to JSON-serializable dictionary."""
        return {
            "state": self.state.value if isinstance(self.state, Enum) else str(self.state),
            "enabled": self.enabled,
            "error_rate": round(self.error_rate, 4),
            "threshold": self.threshold,
            "can_process": self.can_process,
            "can_probe": self.can_probe,
            "last_state_change": self.last_state_change,
            "opened_at": self.opened_at,
            "recovery_attempts": self.recovery_attempts,
            "successful_recoveries": self.successful_recoveries,
            "failed_recoveries": self.failed_recoveries,
        }
