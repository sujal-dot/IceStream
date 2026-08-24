"""Validator orchestration abstractions for IceStream Quality Engine.

Architectural Separation:
- `QualityRule`: Represents an atomic, single-responsibility assertion on an event (e.g., `EventIdNotNullRule`, `AmountPositiveRule`).
- `EventValidator`: Represents an orchestrating entity that executes a collection of quality rules against events and aggregates their validation results.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Union

from rules.base import QualityRule, ValidationResult, ValidationSummary
from rules.registry import RuleRegistry, default_registry
from schemas.event import QualityEvent


class BaseValidator(ABC):
    """Abstract interface for event validators."""

    @abstractmethod
    def validate_event(
        self, event: Union[QualityEvent, Dict[str, Any]]
    ) -> List[ValidationResult]:
        """Validate a single event and return rule execution results."""
        pass

    @abstractmethod
    def validate_batch(
        self, events: List[Union[QualityEvent, Dict[str, Any]]]
    ) -> List[ValidationSummary]:
        """Validate a collection of events and return summaries."""
        pass


class EventValidator(BaseValidator):
    """Default validator that executes configured rules from a registry."""

    def __init__(
        self,
        registry: Optional[RuleRegistry] = None,
    ) -> None:
        self._registry = registry or default_registry

    @property
    def registry(self) -> RuleRegistry:
        return self._registry

    def validate_event(
        self, event: Union[QualityEvent, Dict[str, Any]]
    ) -> List[ValidationResult]:
        """Validate a single event against all active rules in the registry."""
        from rules.engine import QualityEngine

        engine = QualityEngine(registry=self._registry)
        return engine.validate(event)

    def validate_batch(
        self, events: List[Union[QualityEvent, Dict[str, Any]]]
    ) -> List[ValidationSummary]:
        """Validate a batch of events and return validation summaries."""
        from rules.engine import QualityEngine

        engine = QualityEngine(registry=self._registry)
        summaries: List[ValidationSummary] = []
        for evt in events:
            _, summary = engine.validate_with_summary(evt)
            summaries.append(summary)
        return summaries
