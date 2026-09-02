"""Metrics service layer orchestrating domain metrics providers."""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional

from backend.models.metrics import (
    CircuitBreakerMetricsModel,
    MetricsResponse,
    RemediationMetricsModel,
    WindowMetricsModel,
)

logger = logging.getLogger("icestream.services.metrics")


class MetricsService:
    """Aggregates metrics from ErrorRateEngine, CircuitBreaker, and Remediation state."""

    def __init__(self, error_rate_engine=None, circuit_breaker=None, state_manager=None):
        self.error_rate_engine = error_rate_engine
        self.circuit_breaker = circuit_breaker
        self.state_manager = state_manager

    def get_metrics(self) -> MetricsResponse:
        """Retrieve aggregated metrics snapshot from underlying domain engines."""
        now_iso = datetime.now(timezone.utc).isoformat()
        windows_dict: Dict[str, WindowMetricsModel] = {}

        if self.error_rate_engine:
            snapshot = self.error_rate_engine.get_metrics_snapshot()
            raw_windows = snapshot.get("windows", {})
            for w_name, w_data in raw_windows.items():
                windows_dict[w_name] = WindowMetricsModel(
                    window_seconds=w_data.get("window_seconds", 60 if w_name == "1m" else 300),
                    window_start=w_data.get("window_start"),
                    window_end=w_data.get("window_end"),
                    total_events=w_data.get("total_events", 0),
                    valid_events=w_data.get("valid_events", 0),
                    failed_events=w_data.get("failed_events", 0),
                    error_rate=float(w_data.get("error_rate", 0.0)),
                    error_rate_percent=float(w_data.get("error_rate_percent", 0.0)),
                    health=str(w_data.get("health", "HEALTHY")),
                    data_available=w_data.get("data_available", True),
                )

        if "1m" not in windows_dict:
            windows_dict["1m"] = WindowMetricsModel(window_seconds=60)
        if "5m" not in windows_dict:
            windows_dict["5m"] = WindowMetricsModel(window_seconds=300)

        cb_model = CircuitBreakerMetricsModel()
        if self.circuit_breaker:
            cb_status = self.circuit_breaker.get_status().to_dict()
            cb_model = CircuitBreakerMetricsModel(
                state=str(cb_status.get("state", "CLOSED")),
                enabled=bool(cb_status.get("enabled", True)),
                can_process=bool(cb_status.get("can_process", True)),
                can_probe=bool(cb_status.get("can_probe", False)),
                error_rate=float(cb_status.get("error_rate", 0.0)),
                threshold=float(cb_status.get("threshold", 0.02)),
            )

        rem_model = RemediationMetricsModel()
        pipe_state = None
        if self.state_manager:
            pipe_state = self.state_manager.get_state()

        return MetricsResponse(
            timestamp=now_iso,
            windows=windows_dict,
            circuit_breaker=cb_model,
            remediation=rem_model,
            pipeline_state=pipe_state,
        )
