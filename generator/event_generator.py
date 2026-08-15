"""Event Generator Engine orchestrating data generation, fault injection, and Kafka publishing."""

import random
from typing import Optional, Tuple

from generator.config import GeneratorConfig
from generator.data_generator import DataGenerator
from generator.error_injector import ErrorInjector
from generator.fault_injection.engine import FaultInjectionEngine
from generator.producer import EventProducer


class EventGeneratorEngine:
    """Core generator orchestration engine."""

    def __init__(

        self,
        config: GeneratorConfig,
        producer: Optional[EventProducer] = None,
    ):
        self.config = config
        self.data_gen = DataGenerator(seed=config.seed)

        # Initialize Fault Injection Engine for Day 5 failure injection
        rates = config.get_fault_mode_rates()
        self.fault_engine = FaultInjectionEngine(
            rates=rates,
            active_modes=config.fault_modes,
            schema_drift_types=config.schema_drift_types,
            seed=config.seed,
        )

        # Legacy Day 4 ErrorInjector kept for backwards compatibility if needed
        self.error_injector = ErrorInjector(
            seed=config.seed, error_types=config.error_types
        )
        self.producer = producer
        self._rnd = random.Random(config.seed)

    def generate_single_event(self) -> Tuple[dict, bool, Optional[str]]:
        """Generate a single event dictionary, applying fault injection if selected.

        Returns (event_payload, is_corrupted, fault_mode_or_error_type).
        """
        valid_event = self.data_gen.generate_valid_event()

        # Check if Day 5 Fault Injection Engine has active configured rates
        rates = self.config.get_fault_mode_rates()
        has_active_faults = any(r > 0.0 for r in rates.values())

        if has_active_faults or self.config.fault_modes:
            event_dict, is_faulty, fault_mode = self.fault_engine.process_event(valid_event)
            return event_dict, is_faulty, fault_mode
        elif self.config.error_probability > 0:
            # Fallback to Day 4 legacy error injector if only generic --error-rate is set
            should_corrupt = self._rnd.random() < self.config.error_probability
            if should_corrupt:
                corrupted_event, error_type = self.error_injector.inject_error(valid_event)
                return corrupted_event, True, error_type
            else:
                self.error_injector.record_valid_event_id(valid_event["event_id"])
                return valid_event, False, None
        else:
            self.fault_engine.record_clean_event(valid_event)
            return valid_event, False, None

    def produce_next_event(self) -> Tuple[dict, bool, Optional[str]]:
        """Generate next event and transmit via Kafka producer if configured."""
        event_dict, is_corrupted, fault_type = self.generate_single_event()
        if self.producer:
            self.producer.send_event(
                topic=self.config.topic,
                event_payload=event_dict,
                is_corrupted=is_corrupted,
            )
        return event_dict, is_corrupted, fault_type
