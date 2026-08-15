"""Core Fault Injection Engine orchestrating fault selection, mutation, and statistics."""

import random
from typing import Any, Dict, List, Optional, Tuple

from generator.fault_injection.modes import (
    ALL_FAULT_MODES,
    ALL_SCHEMA_DRIFT_TYPES,
    FaultMode,
)
from generator.fault_injection.statistics import FaultStatistics
from generator.fault_injection.strategies import (
    DuplicateFaultStrategy,
    InvalidEnumFaultStrategy,
    NegativeFaultStrategy,
    NullFaultStrategy,
    SchemaDriftFaultStrategy,
    TimestampDriftFaultStrategy,
    TypeChangeFaultStrategy,
)


class FaultInjectionEngine:
    """Configurable failure-injection framework for checkout events."""

    def __init__(
        self,
        rates: Optional[Dict[str, float]] = None,
        active_modes: Optional[List[str]] = None,
        schema_drift_types: Optional[List[str]] = None,
        seed: Optional[int] = None,
    ):
        self._rnd = random.Random(seed)
        self.rates: Dict[str, float] = {}

        # Default all fault mode rates to 0.0 if not specified
        for mode in ALL_FAULT_MODES:
            self.rates[mode] = rates.get(mode, 0.0) if rates else 0.0

        # Validate active modes filter if provided
        if active_modes:
            for mode in active_modes:
                if mode not in ALL_FAULT_MODES:
                    raise ValueError(
                        f"Invalid fault mode: '{mode}'. Supported modes are: {ALL_FAULT_MODES}"
                    )
            self.active_modes = list(active_modes)
        else:
            self.active_modes = [
                mode for mode, rate in self.rates.items() if rate > 0.0
            ]
            if not self.active_modes:
                self.active_modes = list(ALL_FAULT_MODES)

        # Initialize strategies
        self.strategies = {
            FaultMode.NULL.value: NullFaultStrategy(),
            FaultMode.DUPLICATE.value: DuplicateFaultStrategy(),
            FaultMode.NEGATIVE.value: NegativeFaultStrategy(),
            FaultMode.INVALID_ENUM.value: InvalidEnumFaultStrategy(),
            FaultMode.SCHEMA_DRIFT.value: SchemaDriftFaultStrategy(
                allowed_drift_types=schema_drift_types
            ),
            FaultMode.TYPE_CHANGE.value: TypeChangeFaultStrategy(),
            FaultMode.TIMESTAMP_DRIFT.value: TimestampDriftFaultStrategy(),
        }

        self.statistics = FaultStatistics(configured_rates=self.rates)

    def record_clean_event(self, event_dict: Dict[str, Any]):
        """Record valid event into history buffer (for duplicate generation)."""
        dup_strat: DuplicateFaultStrategy = self.strategies[FaultMode.DUPLICATE.value]
        dup_strat.record_event(event_dict)

    def select_fault_mode(self) -> Optional[str]:
        """Select a single fault mode based on rates and single-fault-per-event collision handling.

        Returns fault_mode_string if a fault triggered, or None if clean event.
        """
        triggered_modes = []

        for mode in self.active_modes:
            rate_pct = self.rates.get(mode, 0.0)
            if rate_pct > 0.0:
                prob = rate_pct / 100.0
                if self._rnd.random() < prob:
                    triggered_modes.append(mode)

        if not triggered_modes:
            return None

        if len(triggered_modes) == 1:
            return triggered_modes[0]

        # Single fault per event collision resolution:
        # Uniformly pick one among all triggered fault modes for this event
        return self._rnd.choice(triggered_modes)

    def process_event(
        self, event_dict: Dict[str, Any], target_fault_mode: Optional[str] = None
    ) -> Tuple[Dict[str, Any], bool, Optional[str]]:
        """Process event dictionary, applying fault mutation if selected.

        Returns (mutated_event, is_faulty, fault_mode_name).
        """
        # Always record incoming valid event into duplicate history buffer
        self.record_clean_event(event_dict)

        selected_mode = (
            target_fault_mode
            if target_fault_mode is not None
            else self.select_fault_mode()
        )

        if selected_mode is None:
            self.statistics.record_event(fault_mode=None)
            return dict(event_dict), False, None

        if selected_mode not in self.strategies:
            raise ValueError(f"Unsupported fault mode: '{selected_mode}'")

        strategy = self.strategies[selected_mode]
        mutated_event = strategy.mutate(event_dict, self._rnd)

        # Update stats
        self.statistics.record_event(fault_mode=selected_mode)

        return mutated_event, True, selected_mode
