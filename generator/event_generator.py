"""Event Generator Engine orchestrating data generation, error injection, and Kafka publishing."""

import random
from typing import Optional

from generator.config import GeneratorConfig
from generator.data_generator import DataGenerator
from generator.error_injector import ErrorInjector
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
        self.error_injector = ErrorInjector(
            seed=config.seed, error_types=config.error_types
        )
        self.producer = producer
        self._rnd = random.Random(config.seed)

    def generate_single_event(self) -> tuple[dict, bool, Optional[str]]:
        """Generate a single event dictionary, applying error injection if selected.

        Returns (event_payload, is_corrupted, error_type_or_none).
        """
        valid_event = self.data_gen.generate_valid_event()

        # Decide whether to corrupt based on error_probability
        should_corrupt = (
            self.config.error_probability > 0
            and self._rnd.random() < self.config.error_probability
        )

        if should_corrupt:
            corrupted_event, error_type = self.error_injector.inject_error(
                valid_event
            )
            return corrupted_event, True, error_type
        else:
            # Record valid ID for potential duplicate injection
            self.error_injector.record_valid_event_id(valid_event["event_id"])
            return valid_event, False, None

    def produce_next_event(self) -> tuple[dict, bool, Optional[str]]:
        """Generate next event and transmit via Kafka producer if configured."""
        event_dict, is_corrupted, error_type = self.generate_single_event()
        if self.producer:
            self.producer.send_event(
                topic=self.config.topic,
                event_payload=event_dict,
                is_corrupted=is_corrupted,
            )
        return event_dict, is_corrupted, error_type
