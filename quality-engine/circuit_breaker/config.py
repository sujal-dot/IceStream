"""Circuit Breaker configuration management and validation for IceStream Quality Engine."""

from dataclasses import dataclass
import os
from typing import Any, Dict, Optional
import yaml


@dataclass
class CircuitBreakerConfig:
    """Configurable threshold and behavior settings for CircuitBreaker."""

    enabled: bool = True
    error_threshold: float = 0.02
    recovery_timeout_seconds: float = 60.0
    half_open_success_threshold: int = 1
    half_open_failure_threshold: int = 1
    max_history: int = 100

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validate configuration thresholds and parameters.
        
        Raises:
            ValueError: If parameters are missing, invalid types, or out of bounds.
        """
        # Validate enabled
        if self.enabled is None or not isinstance(self.enabled, bool):
            raise ValueError(f"Configuration parameter 'enabled' must be boolean, got {type(self.enabled).__name__}")

        # Validate error_threshold: must be numeric and 0.0 <= error_threshold <= 1.0
        if self.error_threshold is None:
            raise ValueError("Configuration parameter 'error_threshold' cannot be None")
        if isinstance(self.error_threshold, bool) or not isinstance(self.error_threshold, (int, float)):
            raise ValueError(f"Configuration parameter 'error_threshold' must be numeric, got {type(self.error_threshold).__name__}")
        float_threshold = float(self.error_threshold)
        if float_threshold < 0.0 or float_threshold > 1.0:
            raise ValueError(f"Configuration parameter 'error_threshold' must be between 0.0 and 1.0, got {self.error_threshold}")

        # Validate recovery_timeout_seconds: must be numeric and > 0
        if self.recovery_timeout_seconds is None:
            raise ValueError("Configuration parameter 'recovery_timeout_seconds' cannot be None")
        if isinstance(self.recovery_timeout_seconds, bool) or not isinstance(self.recovery_timeout_seconds, (int, float)):
            raise ValueError(f"Configuration parameter 'recovery_timeout_seconds' must be numeric, got {type(self.recovery_timeout_seconds).__name__}")
        if float(self.recovery_timeout_seconds) <= 0:
            raise ValueError(f"Configuration parameter 'recovery_timeout_seconds' must be strictly positive (>0), got {self.recovery_timeout_seconds}")

        # Validate half_open_success_threshold: must be int and >= 1
        if self.half_open_success_threshold is None:
            raise ValueError("Configuration parameter 'half_open_success_threshold' cannot be None")
        if isinstance(self.half_open_success_threshold, bool) or not isinstance(self.half_open_success_threshold, int):
            raise ValueError(f"Configuration parameter 'half_open_success_threshold' must be an integer, got {type(self.half_open_success_threshold).__name__}")
        if self.half_open_success_threshold < 1:
            raise ValueError(f"Configuration parameter 'half_open_success_threshold' must be at least 1, got {self.half_open_success_threshold}")

        # Validate half_open_failure_threshold: must be int and >= 1
        if self.half_open_failure_threshold is None:
            raise ValueError("Configuration parameter 'half_open_failure_threshold' cannot be None")
        if isinstance(self.half_open_failure_threshold, bool) or not isinstance(self.half_open_failure_threshold, int):
            raise ValueError(f"Configuration parameter 'half_open_failure_threshold' must be an integer, got {type(self.half_open_failure_threshold).__name__}")
        if self.half_open_failure_threshold < 1:
            raise ValueError(f"Configuration parameter 'half_open_failure_threshold' must be at least 1, got {self.half_open_failure_threshold}")

        # Validate max_history: must be int and >= 1
        if self.max_history is None:
            raise ValueError("Configuration parameter 'max_history' cannot be None")
        if isinstance(self.max_history, bool) or not isinstance(self.max_history, int):
            raise ValueError(f"Configuration parameter 'max_history' must be an integer, got {type(self.max_history).__name__}")
        if self.max_history < 1:
            raise ValueError(f"Configuration parameter 'max_history' must be at least 1, got {self.max_history}")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CircuitBreakerConfig":
        """Construct CircuitBreakerConfig from a configuration mapping."""
        cb_dict = data.get("circuit_breaker", data)
        return cls(
            enabled=cb_dict.get("enabled", True),
            error_threshold=float(cb_dict.get("error_threshold", 0.02)),
            recovery_timeout_seconds=float(cb_dict.get("recovery_timeout_seconds", 60.0)),
            half_open_success_threshold=int(cb_dict.get("half_open_success_threshold", 1)),
            half_open_failure_threshold=int(cb_dict.get("half_open_failure_threshold", 1)),
            max_history=int(cb_dict.get("max_history", 100)),
        )

    @classmethod
    def from_yaml(cls, yaml_path: str) -> "CircuitBreakerConfig":
        """Load CircuitBreakerConfig from a YAML file."""
        if not os.path.exists(yaml_path):
            raise FileNotFoundError(f"Circuit breaker config file not found: {yaml_path}")
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise ValueError(f"Invalid YAML configuration in {yaml_path}: expected mapping")
        return cls.from_dict(data)
