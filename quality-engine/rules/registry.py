"""Rule Registry for registering, discovering, and instantiating quality rules."""

import inspect
import logging
from typing import Any, Callable, Dict, List, Optional, Type, Union

from .base import EventIdNotNullRule, QualityRule, Severity
from .not_null import NotNullRule
from .positive import AmountPositiveRule
from .allowed_values import AllowedValuesRule, CurrencyValidRule, PaymentStatusValidRule
from .timestamp import TimestampValidRule

logger = logging.getLogger("quality_engine.registry")


class RuleRegistry:
    """Registry managing quality rule instances and factory builders."""

    def __init__(self) -> None:
        self._rules: Dict[str, QualityRule] = {}
        self._rule_classes: Dict[str, Type[QualityRule]] = {}

    def register(
        self,
        rule: Union[QualityRule, Type[QualityRule]],
        overwrite: bool = False,
    ) -> None:
        """Register a QualityRule instance or class.
        
        Args:
            rule: An instance of QualityRule or a QualityRule subclass.
            overwrite: If False, raises ValueError on duplicate rule name.
        """
        if inspect.isclass(rule) and issubclass(rule, QualityRule):
            instance = rule()
            rule_cls = rule
        elif isinstance(rule, QualityRule):
            instance = rule
            rule_cls = rule.__class__
        else:
            raise TypeError(
                f"Expected QualityRule instance or subclass, got {type(rule).__name__}"
            )

        name = instance.name
        if not name or not isinstance(name, str):
            raise ValueError("Rule name must be a non-empty string")

        if name in self._rules and not overwrite:
            raise ValueError(
                f"Rule '{name}' is already registered. Use overwrite=True to replace."
            )

        self._rules[name] = instance
        self._rule_classes[name] = rule_cls
        logger.debug("Registered quality rule: %s (%s)", name, rule_cls.__name__)

    def unregister(self, name: str) -> bool:
        """Unregister a rule by name. Returns True if removed, False otherwise."""
        if name in self._rules:
            del self._rules[name]
            self._rule_classes.pop(name, None)
            logger.debug("Unregistered quality rule: %s", name)
            return True
        return False

    def get(self, name: str) -> Optional[QualityRule]:
        """Retrieve a registered rule instance by name."""
        return self._rules.get(name)

    def get_or_raise(self, name: str) -> QualityRule:
        """Retrieve a registered rule or raise KeyError."""
        rule = self._rules.get(name)
        if rule is None:
            raise KeyError(f"Unknown rule: {name}")
        return rule

    def get_class(self, name: str) -> Optional[Type[QualityRule]]:
        """Retrieve a registered rule class by name."""
        return self._rule_classes.get(name)

    def all(self) -> List[QualityRule]:
        """Return a list of all registered rule instances."""
        return list(self._rules.values())

    def list_rules(self) -> List[str]:
        """Return sorted list of all registered rule names."""
        return sorted(list(self._rules.keys()))

    def exists(self, name: str) -> bool:
        """Check if a rule is registered."""
        return name in self._rules

    def clear(self) -> None:
        """Clear all registered rules."""
        self._rules.clear()
        self._rule_classes.clear()

    def __contains__(self, name: str) -> bool:
        return self.exists(name)

    def __len__(self) -> int:
        return len(self._rules)


def create_default_registry() -> RuleRegistry:
    """Create and populate a standard RuleRegistry with default Day 15 rules."""
    registry = RuleRegistry()

    # Null rules
    registry.register(EventIdNotNullRule())
    not_null_fields = [
        ("customer_id", Severity.HIGH),
        ("session_id", Severity.HIGH),
        ("order_id", Severity.HIGH),
        ("product_id", Severity.HIGH),
        ("amount", Severity.CRITICAL),
        ("currency", Severity.HIGH),
        ("payment_method", Severity.HIGH),
        ("payment_status", Severity.HIGH),
        ("device", Severity.HIGH),
        ("country", Severity.HIGH),
        ("source_version", Severity.HIGH),
        ("event_time", Severity.HIGH),
        ("ingestion_time", Severity.HIGH),
    ]
    for field_name, sev in not_null_fields:
        registry.register(NotNullRule(field=field_name, severity_override=sev))

    # Positive amount rule
    registry.register(AmountPositiveRule(field="amount", severity_override=Severity.HIGH))

    # Allowed values rules
    registry.register(CurrencyValidRule())
    registry.register(PaymentStatusValidRule())

    # Timestamp valid rules
    registry.register(TimestampValidRule(field="event_time", severity_override=Severity.HIGH))
    registry.register(TimestampValidRule(field="ingestion_time", severity_override=Severity.HIGH))

    # Anomaly / Duplicate / Schema Drift rules
    from detectors.duplicate import DuplicateEventRule, DuplicateOrderRule
    from detectors.anomaly import ImpossibleAmountRule, FutureTimestampRule, LateEventRule
    from detectors.schema_drift import SchemaDriftRule

    registry.register(DuplicateEventRule())
    registry.register(DuplicateOrderRule())
    registry.register(ImpossibleAmountRule())
    registry.register(FutureTimestampRule())
    registry.register(LateEventRule())
    registry.register(SchemaDriftRule())

    return registry


_default_registry_instance: Optional[RuleRegistry] = None


def get_default_registry() -> RuleRegistry:
    """Get or create the global default RuleRegistry lazily."""
    global _default_registry_instance
    if _default_registry_instance is None:
        _default_registry_instance = create_default_registry()
    return _default_registry_instance


class _LazyDefaultRegistry:
    """Proxy object that defers default_registry instantiation until first use."""

    def _target(self) -> RuleRegistry:
        return get_default_registry()

    def register(self, *args: Any, **kwargs: Any) -> Any:
        return self._target().register(*args, **kwargs)

    def unregister(self, *args: Any, **kwargs: Any) -> Any:
        return self._target().unregister(*args, **kwargs)

    def get(self, *args: Any, **kwargs: Any) -> Any:
        return self._target().get(*args, **kwargs)

    def get_or_raise(self, *args: Any, **kwargs: Any) -> Any:
        return self._target().get_or_raise(*args, **kwargs)

    def get_class(self, *args: Any, **kwargs: Any) -> Any:
        return self._target().get_class(*args, **kwargs)

    def all(self) -> Any:
        return self._target().all()

    def list_rules(self) -> Any:
        return self._target().list_rules()

    def exists(self, *args: Any, **kwargs: Any) -> Any:
        return self._target().exists(*args, **kwargs)

    def clear(self) -> Any:
        return self._target().clear()

    def __contains__(self, item: Any) -> bool:
        return item in self._target()

    def __len__(self) -> int:
        return len(self._target())

    def __iter__(self) -> Any:
        return iter(self._target().all())


# Global lazy default registry instance
default_registry = _LazyDefaultRegistry()


def register_rule(
    rule_or_registry: Optional[Union[Type[QualityRule], RuleRegistry]] = None,
    *,
    registry: Optional[RuleRegistry] = None,
) -> Union[Type[QualityRule], Callable[[Type[QualityRule]], Type[QualityRule]]]:
    """Decorator to register a QualityRule class dynamically.

    Supports:
        @register_rule
        class MyRule(QualityRule): ...

        @register_rule(custom_registry)
        class MyRule(QualityRule): ...

        @register_rule(registry=custom_registry)
        class MyRule(QualityRule): ...
    """
    if inspect.isclass(rule_or_registry) and issubclass(rule_or_registry, QualityRule):
        target_registry = registry if registry is not None else default_registry
        target_registry.register(rule_or_registry)
        return rule_or_registry

    if isinstance(rule_or_registry, RuleRegistry):
        target_registry = rule_or_registry
    elif registry is not None:
        target_registry = registry
    else:
        target_registry = default_registry

    def decorator(cls: Type[QualityRule]) -> Type[QualityRule]:
        target_registry.register(cls)
        return cls

    return decorator
