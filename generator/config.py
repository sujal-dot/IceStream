"""Configuration settings and CLI argument parsing for the IceStream Event Generator."""

import argparse
from dataclasses import dataclass, field
from typing import List, Optional

ALL_ERROR_TYPES = [
    "null_amount",
    "null_customer_id",
    "negative_amount",
    "duplicate_event_id",
    "invalid_currency",
    "missing_required_field",
    "wrong_data_type",
    "future_timestamp",
]


@dataclass
class GeneratorConfig:
    rate: int = 1000
    error_rate: float = 0.0  # Percentage e.g. 0.5 means 0.5%
    bootstrap_server: str = "localhost:9092"
    topic: str = "checkout-events"
    error_types: List[str] = field(default_factory=lambda: list(ALL_ERROR_TYPES))
    seed: Optional[int] = None
    duration: Optional[float] = None  # Seconds, None or <=0 means run continuously
    log_interval: float = 1.0  # Seconds between statistics log output

    def __post_init__(self):
        if self.rate <= 0:
            raise ValueError("Target rate must be a positive integer.")
        if self.error_rate < 0.0 or self.error_rate > 100.0:
            raise ValueError("Error rate must be between 0.0 and 100.0 (percentage).")
        if not self.error_types:
            self.error_types = list(ALL_ERROR_TYPES)
        else:
            invalid_types = [t for t in self.error_types if t not in ALL_ERROR_TYPES]
            if invalid_types:
                raise ValueError(
                    f"Unsupported error types: {invalid_types}. Supported types are: {ALL_ERROR_TYPES}"
                )

    @property
    def error_probability(self) -> float:
        """Returns error rate as a probability float between 0.0 and 1.0."""
        return self.error_rate / 100.0


def parse_args(args: Optional[List[str]] = None) -> GeneratorConfig:
    """Parse command-line arguments and return a GeneratorConfig object."""
    parser = argparse.ArgumentParser(
        description="IceStream Real-Time Checkout Event Generator"
    )

    parser.add_argument(
        "--rate",
        type=int,
        default=1000,
        help="Target event generation rate in events/second (default: 1000)",
    )
    parser.add_argument(
        "--error-rate",
        type=float,
        default=0.0,
        help="Percentage of events that contain injected errors (e.g. 0.5 for 0.5%%, default: 0.0)",
    )
    parser.add_argument(
        "--bootstrap-server",
        type=str,
        default="localhost:9092",
        help="Kafka bootstrap server(s) (default: localhost:9092)",
    )
    parser.add_argument(
        "--topic",
        type=str,
        default="checkout-events",
        help="Target Kafka topic (default: checkout-events)",
    )
    parser.add_argument(
        "--error-types",
        type=str,
        default=None,
        help="Comma-separated list of error types to inject (default: all supported error types)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducible event generation (default: None)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Duration in seconds to run generator (default: None for continuous execution)",
    )
    parser.add_argument(
        "--log-interval",
        type=float,
        default=1.0,
        help="Interval in seconds between throughput statistics logs (default: 1.0)",
    )

    parsed = parser.parse_args(args)

    if parsed.error_types:
        types_list = [t.strip() for t in parsed.error_types.split(",") if t.strip()]
    else:
        types_list = list(ALL_ERROR_TYPES)

    return GeneratorConfig(
        rate=parsed.rate,
        error_rate=parsed.error_rate,
        bootstrap_server=parsed.bootstrap_server,
        topic=parsed.topic,
        error_types=types_list,
        seed=parsed.seed,
        duration=parsed.duration,
        log_interval=parsed.log_interval,
    )
