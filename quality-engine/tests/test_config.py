"""Tests for YAML rules configuration loading and validation."""

import os
import tempfile
import pytest
from config.loader import load_rule_config
from rules.base import EventIdNotNullRule, QualityRule, Severity, ValidationResult
from rules.engine import QualityEngine
from rules.registry import RuleRegistry
from schemas.event import QualityEvent


class SecondTestRule(QualityRule):
    @property
    def name(self) -> str:
        return "second_test_rule"

    @property
    def default_severity(self) -> Severity:
        return Severity.LOW

    def validate(self, event: QualityEvent) -> ValidationResult:
        return ValidationResult(
            rule_name=self.name,
            passed=True,
            severity=self.severity,
            message="Second test rule ok",
        )


def test_load_valid_config():
    """Verify loading valid rules configuration and applying severity override."""
    yaml_content = """
rules:
  - name: event_id_not_null
    enabled: true
    severity: HIGH
  - name: second_test_rule
    enabled: false
    severity: MEDIUM
"""
    registry = RuleRegistry()
    registry.register(EventIdNotNullRule())
    registry.register(SecondTestRule())

    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        temp_path = f.name

    try:
        load_rule_config(temp_path, registry=registry)
        r1 = registry.get("event_id_not_null")
        r2 = registry.get("second_test_rule")

        assert r1.enabled is True
        assert r1.severity == Severity.HIGH

        assert r2.enabled is False
        assert r2.severity == Severity.MEDIUM
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_disabled_rule_is_skipped_by_engine():
    """Verify disabled rule is not executed during engine validation."""
    yaml_content = """
rules:
  - name: event_id_not_null
    enabled: false
    severity: CRITICAL
  - name: second_test_rule
    enabled: true
    severity: LOW
"""
    registry = RuleRegistry()
    registry.register(EventIdNotNullRule())
    registry.register(SecondTestRule())

    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        temp_path = f.name

    try:
        load_rule_config(temp_path, registry=registry)
        engine = QualityEngine(registry=registry)

        event = QualityEvent(event_id=None)  # Would fail if event_id_not_null was enabled
        results = engine.validate(event)

        assert len(results) == 1
        assert results[0].rule_name == "second_test_rule"
        assert results[0].passed is True
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_config_rejects_unknown_rule():
    """Verify configuration loading raises KeyError for un-registered rule."""
    yaml_content = """
rules:
  - name: non_existent_rule
    enabled: true
    severity: CRITICAL
"""
    registry = RuleRegistry()

    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        temp_path = f.name

    try:
        with pytest.raises(KeyError, match="Unknown rule: non_existent_rule"):
            load_rule_config(temp_path, registry=registry)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_config_rejects_duplicate_rule_names():
    """Verify duplicate rule names in YAML raise ValueError."""
    yaml_content = """
rules:
  - name: event_id_not_null
    enabled: true
    severity: CRITICAL
  - name: event_id_not_null
    enabled: false
    severity: LOW
"""
    registry = RuleRegistry()
    registry.register(EventIdNotNullRule())

    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        temp_path = f.name

    try:
        with pytest.raises(ValueError, match="Duplicate rule 'event_id_not_null'"):
            load_rule_config(temp_path, registry=registry)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_config_rejects_invalid_severity():
    """Verify invalid severity string in YAML raises ValueError."""
    yaml_content = """
rules:
  - name: event_id_not_null
    enabled: true
    severity: ULTRA_CRITICAL
"""
    registry = RuleRegistry()
    registry.register(EventIdNotNullRule())

    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        temp_path = f.name

    try:
        with pytest.raises(ValueError, match="Invalid severity 'ULTRA_CRITICAL'"):
            load_rule_config(temp_path, registry=registry)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_config_rejects_missing_file():
    """Verify FileNotFoundError when config file does not exist."""
    with pytest.raises(FileNotFoundError):
        load_rule_config("/non/existent/path/rules.yaml")
