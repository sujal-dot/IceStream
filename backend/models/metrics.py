"""Metrics API response models."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class WindowMetricsModel(BaseModel):
    """Metrics for a single time window (1m or 5m)."""

    window_seconds: int
    window_start: Optional[str] = None
    window_end: Optional[str] = None
    total_events: int = 0
    valid_events: int = 0
    failed_events: int = 0
    error_rate: float = 0.0
    error_rate_percent: float = 0.0
    health: str = "HEALTHY"
    data_available: bool = True


class CircuitBreakerMetricsModel(BaseModel):
    """Circuit breaker status snapshot in metrics."""

    state: str = "CLOSED"
    enabled: bool = True
    can_process: bool = True
    can_probe: bool = False
    error_rate: float = 0.0
    threshold: float = 0.02


class RemediationMetricsModel(BaseModel):
    """Remediation metrics snapshot."""

    attempts: int = 0
    successes: int = 0
    failures: int = 0
    recovered_events: int = 0


class MetricsResponse(BaseModel):
    """Overall metrics endpoint response model."""

    service: str = Field(default="icestream-quality-engine", example="icestream-quality-engine")
    status: str = Field(default="ok", example="ok")
    timestamp: str
    windows: Dict[str, WindowMetricsModel]
    circuit_breaker: CircuitBreakerMetricsModel
    remediation: RemediationMetricsModel
    pipeline_state: Optional[Dict[str, Any]] = None
    history: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
