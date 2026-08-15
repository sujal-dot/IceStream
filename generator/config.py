"""Configuration settings and CLI argument parsing for the IceStream Event Generator."""

import argparse
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from generator.fault_injection.modes import (
    ALL_FAULT_MODES,
    ALL_SCHEMA_DRIFT_TYPES,
    FaultMode,
)

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
    error_rate: float = 0.0  # Generic Day 4 error rate percentage e.g. 0.5 means 0.5%
    bootstrap_server: str = "localhost:9092"
    topic: str = "checkout-events"
    error_types: List[str] = field(default_factory=lambda: list(ALL_ERROR_TYPES))
    seed: Optional[int] = None
    duration: Optional[float] = None  # Seconds, None or <=0 means run continuously
    log_interval: float = 1.0  # Seconds between statistics log output

    # Day 5 Individual Fault Rates (Percentages: 1.0 = 1%, 0.5 = 0.5%)
    null_rate: Optional[float] = None
    duplicate_rate: Optional[float] = None
    negative_rate: Optional[float] = None
    invalid_enum_rate: Optional[float] = None
    schema_drift_rate: Optional[float] = None
    type_change_rate: Optional[float] = None
    timestamp_drift_rate: Optional[float] = None

    fault_modes: Optional[List[str]] = None
    schema_drift_types: Optional[List[str]] = None

    def __post_init__(self):
        if self.rate <= 0:
            raise ValueError("Target rate must be a positive integer.")
        if self.error_rate < 0.0 or self.error_rate > 100.0:
            raise ValueError("Error rate must be between 0.0 and 100.0 (percentage).")

        # Check for conflict between --error-rate and individual fault rates
        indiv_rates = [
            self.null_rate,
            self.duplicate_rate,
            self.negative_rate,
            self.invalid_enum_rate,
            self.schema_drift_rate,
            self.type_change_rate,
            self.timestamp_drift_rate,
        ]
        has_indiv = any(r is not None for r in indiv_rates)

        if has_indiv and self.error_rate > 0.0:
            raise ValueError(
                "ERROR: --error-rate cannot be combined with individual fault rates. "
                "Use either --error-rate or explicit fault rates."
            )

        # Validate individual rates
        for r_name, r_val in [
            ("null_rate", self.null_rate),
            ("duplicate_rate", self.duplicate_rate),
            ("negative_rate", self.negative_rate),
            ("invalid_enum_rate", self.invalid_enum_rate),
            ("schema_drift_rate", self.schema_drift_rate),
            ("type_change_rate", self.type_change_rate),
            ("timestamp_drift_rate", self.timestamp_drift_rate),
        ]:
            if r_val is not None and (r_val < 0.0 or r_val > 100.0):
                raise ValueError(
                    f"{r_name} must be between 0.0 and 100.0 (percentage)."
                )

        # Validate fault_modes
        if self.fault_modes:
            invalid_modes = [m for m in self.fault_modes if m not in ALL_FAULT_MODES]
            if invalid_modes:
                raise ValueError(
                    f"Unsupported fault modes: {invalid_modes}. Supported modes are: {ALL_FAULT_MODES}"
                )

        # Validate schema_drift_types
        if self.schema_drift_types:
            invalid_drifts = [
                s for s in self.schema_drift_types if s not in ALL_SCHEMA_DRIFT_TYPES
            ]
            if invalid_drifts:
                raise ValueError(
                    f"Unsupported schema drift types: {invalid_drifts}. Supported types are: {ALL_SCHEMA_DRIFT_TYPES}"
                )

        # Validate Day 4 error types if legacy error_rate used
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
        """Returns generic error rate as a probability float between 0.0 and 1.0."""
        return self.error_rate / 100.0

    def get_fault_mode_rates(self) -> Dict[str, float]:
        """Construct dictionary of fault rates (percentages) per FaultMode."""
        indiv_map = {
            FaultMode.NULL.value: self.null_rate,
            FaultMode.DUPLICATE.value: self.duplicate_rate,
            FaultMode.NEGATIVE.value: self.negative_rate,
            FaultMode.INVALID_ENUM.value: self.invalid_enum_rate,
            FaultMode.SCHEMA_DRIFT.value: self.schema_drift_rate,
            FaultMode.TYPE_CHANGE.value: self.type_change_rate,
            FaultMode.TIMESTAMP_DRIFT.value: self.timestamp_drift_rate,
        }

        has_indiv = any(v is not None for v in indiv_map.values())
        rates: Dict[str, float] = {}

        if has_indiv:
            for mode, val in indiv_map.items():
                rates[mode] = val if val is not None else 0.0
        elif self.error_rate > 0.0:
            # Legacy Day 4 mode: distribute error_rate across active/selected modes
            active = self.fault_modes if self.fault_modes else ALL_FAULT_MODES
            per_mode_rate = self.error_rate / len(active)
            for mode in ALL_FAULT_MODES:
                rates[mode] = per_mode_rate if mode in active else 0.0
        else:
            for mode in ALL_FAULT_MODES:
                rates[mode] = 0.0

        return rates


def parse_args(args: Optional[List[str]] = None) -> GeneratorConfig:
    """Parse command-line arguments and return a GeneratorConfig object."""
    parser = argparse.ArgumentParser(
        description="IceStream Real-Time Checkout Event Generator & Fault Injection Engine"
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
        help="Generic percentage of events containing injected errors (default: 0.0)",
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
        help="Comma-separated list of Day 4 error types to inject",
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

    # Day 5 Specific CLI Flags
    parser.add_argument(
        "--null-rate",
        type=float,
        default=None,
        help="Percentage of events with NULL values (e.g. 1 for 1%%)",
    )
    parser.add_argument(
        "--duplicate-rate",
        type=float,
        default=None,
        help="Percentage of duplicate events (e.g. 0.5 for 0.5%%)",
    )
    parser.add_argument(
        "--negative-rate",
        type=float,
        default=None,
        help="Percentage of events with negative values (e.g. 0.5 for 0.5%%)",
    )
    parser.add_argument(
        "--invalid-enum-rate",
        type=float,
        default=None,
        help="Percentage of events with invalid enums (e.g. 0.25 for 0.25%%)",
    )
    parser.add_argument(
        "--schema-drift-rate",
        type=float,
        default=None,
        help="Percentage of events with schema drift (e.g. 1 for 1%%)",
    )
    parser.add_argument(
        "--type-change-rate",
        type=float,
        default=None,
        help="Percentage of events with data type changes (e.g. 0.25 for 0.25%%)",
    )
    parser.add_argument(
        "--timestamp-drift-rate",
        type=float,
        default=None,
        help="Percentage of events with timestamp drift (e.g. 0.5 for 0.5%%)",
    )
    parser.add_argument(
        "--fault-modes",
        type=str,
        default=None,
        help="Comma-separated list of active fault modes (e.g. NULL,DUPLICATE,NEGATIVE)",
    )
    parser.add_argument(
        "--schema-drift-types",
        type=str,
        default=None,
        help="Comma-separated list of schema drift types (e.g. ADD_FIELD,REMOVE_FIELD,RENAME_FIELD)",
    )

    parsed = parser.parse_args(args)

    if parsed.error_types:
        types_list = [t.strip() for t in parsed.error_types.split(",") if t.strip()]
    else:
        types_list = list(ALL_ERROR_TYPES)

    fault_modes_list = None
    if parsed.fault_modes:
        fault_modes_list = [
            m.strip().upper() for m in parsed.fault_modes.split(",") if m.strip()
        ]

    schema_drift_types_list = None
    if parsed.schema_drift_types:
        schema_drift_types_list = [
            s.strip().upper()
            for s in parsed.schema_drift_types.split(",")
            if s.strip()
        ]

    # Check command-line raw args for explicit conflict between --error-rate and any individual rate
    # If args passed explicitly (e.g. ['--error-rate', '1', '--null-rate', '1'])
    raw_args = args if args is not None else []
    error_rate_passed = "--error-rate" in raw_args
    indiv_passed = any(
        flag in raw_args
        for flag in [
            "--null-rate",
            "--duplicate-rate",
            "--negative-rate",
            "--invalid-enum-rate",
            "--schema-drift-rate",
            "--type-change-rate",
            "--timestamp-drift-rate",
        ]
    )

    if error_rate_passed and indiv_passed:
        raise ValueError(
            "ERROR: --error-rate cannot be combined with individual fault rates. "
            "Use either --error-rate or explicit fault rates."
        )

    return GeneratorConfig(
        rate=parsed.rate,
        error_rate=parsed.error_rate,
        bootstrap_server=parsed.bootstrap_server,
        topic=parsed.topic,
        error_types=types_list,
        seed=parsed.seed,
        duration=parsed.duration,
        log_interval=parsed.log_interval,
        null_rate=parsed.null_rate,
        duplicate_rate=parsed.duplicate_rate,
        negative_rate=parsed.negative_rate,
        invalid_enum_rate=parsed.invalid_enum_rate,
        schema_drift_rate=parsed.schema_drift_rate,
        type_change_rate=parsed.type_change_rate,
        timestamp_drift_rate=parsed.timestamp_drift_rate,
        fault_modes=fault_modes_list,
        schema_drift_types=schema_drift_types_list,
    )
