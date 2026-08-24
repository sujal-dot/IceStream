"""Tests for RuleRegistry and dynamic rule registration."""

import pytest
from rules.base import EventIdNotNullRule, QualityRule, Severity, ValidationResult
from rules.registry import RuleRegistry, default_registry, register_rule
from schemas.event import QualityEvent


class SampleDummyRule(QualityRule):
    @property
    def name(self) -> str:
        return "sample_dummy_rule"

    @property
    def default_severity(self) -> Severity:
        return Severity.LOW

    def validate(self, event: QualityEvent) -> ValidationResult:
        return ValidationResult(
            rule_name=self.name,
            passed=True,
            severity=self.severity,
            message="all ok",
        )


def test_registry_registration_and_get():
    """Verify registering rule instances and retrieving them."""
    registry = RuleRegistry()
    rule = SampleDummyRule()
    registry.register(rule)

    assert registry.exists("sample_dummy_rule")
    assert registry.get("sample_dummy_rule") is rule
    assert registry.get_or_raise("sample_dummy_rule") is rule
    assert len(registry) == 1
    assert "sample_dummy_rule" in registry.list_rules()


def test_registry_register_by_class():
    """Verify registering a QualityRule subclass directly."""
    registry = RuleRegistry()
    registry.register(SampleDummyRule)

    assert registry.exists("sample_dummy_rule")
    assert isinstance(registry.get("sample_dummy_rule"), SampleDummyRule)


def test_registry_rejects_duplicate_rule_names():
    """Verify duplicate registration raises ValueError by default."""
    registry = RuleRegistry()
    rule1 = SampleDummyRule()
    rule2 = SampleDummyRule()

    registry.register(rule1)
    with pytest.raises(ValueError, match="already registered"):
        registry.register(rule2)


def test_registry_allows_duplicate_with_overwrite():
    """Verify duplicate registration succeeds when overwrite=True."""
    registry = RuleRegistry()
    rule1 = SampleDummyRule()
    rule2 = SampleDummyRule()

    registry.register(rule1)
    registry.register(rule2, overwrite=True)
    assert registry.get("sample_dummy_rule") is rule2


def test_registry_unknown_rule():
    """Verify unknown rule retrieval returns None or raises KeyError."""
    registry = RuleRegistry()
    assert registry.get("non_existent") is None

    with pytest.raises(KeyError, match="Unknown rule: non_existent"):
        registry.get_or_raise("non_existent")


def test_registry_unregister_and_clear():
    """Verify unregistering a rule and clearing the registry."""
    registry = RuleRegistry()
    registry.register(SampleDummyRule())
    assert registry.exists("sample_dummy_rule")

    assert registry.unregister("sample_dummy_rule") is True
    assert not registry.exists("sample_dummy_rule")
    assert registry.unregister("sample_dummy_rule") is False

    registry.register(SampleDummyRule())
    registry.clear()
    assert len(registry) == 0


def test_register_rule_decorator():
    """Verify @register_rule decorator dynamically registers into registry."""
    custom_reg = RuleRegistry()

    @register_rule(registry=custom_reg)
    class DecoratedRule(QualityRule):
        @property
        def name(self) -> str:
            return "decorated_rule"

        @property
        def default_severity(self) -> Severity:
            return Severity.MEDIUM

        def validate(self, event: QualityEvent) -> ValidationResult:
            return ValidationResult(
                rule_name=self.name,
                passed=True,
                severity=self.severity,
                message="ok",
            )

    assert custom_reg.exists("decorated_rule")
    assert isinstance(custom_reg.get("decorated_rule"), DecoratedRule)


def test_default_registry_has_event_id_rule():
    """Verify global default_registry contains EventIdNotNullRule."""
    assert default_registry.exists("event_id_not_null")
    rule = default_registry.get("event_id_not_null")
    assert isinstance(rule, EventIdNotNullRule)
