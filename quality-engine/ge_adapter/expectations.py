"""Expectation configuration parsing, validation, and registry for Great Expectations integration."""

from dataclasses import dataclass, field as dc_field
import logging
import os
from typing import Any, Dict, List, Optional, Set, Union
import yaml

from rules.base import Severity

logger = logging.getLogger("quality_engine.ge_adapter.expectations")

# Canonical set of supported Great Expectations declarative expectations
SUPPORTED_EXPECTATIONS = {
    "expect_column_values_to_not_be_null",
    "expect_column_values_to_be_between",
    "expect_column_values_to_be_in_set",
    "expect_column_to_exist",
    "expect_column_values_to_be_of_type",
}


@dataclass
class ExpectationConfig:
    """Strongly typed representation of an IceStream GE expectation declaration."""

    name: str
    expectation: str
    column: str
    severity: Severity = Severity.HIGH
    enabled: bool = True
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    strict_min: Optional[bool] = None
    strict_max: Optional[bool] = None
    value_set: Optional[List[Any]] = None
    kwargs: Dict[str, Any] = dc_field(default_factory=dict)

    def to_ge_kwargs(self) -> Dict[str, Any]:
        """Build dictionary of kwargs passed directly to Great Expectations dataset validator."""
        kw = {"column": self.column}
        if self.min_value is not None:
            kw["min_value"] = self.min_value
        if self.max_value is not None:
            kw["max_value"] = self.max_value
        if self.strict_min is not None:
            kw["strict_min"] = self.strict_min
        if self.strict_max is not None:
            kw["strict_max"] = self.strict_max
        if self.value_set is not None:
            kw["value_set"] = self.value_set
        kw.update(self.kwargs)
        return kw


class GEExpectationRegistry:
    """Registry and validator for Great Expectations declarative expectations."""

    def __init__(self) -> None:
        self._expectations: Dict[str, ExpectationConfig] = {}

    def register(self, config: ExpectationConfig) -> None:
        """Register and validate an ExpectationConfig."""
        self._validate_config(config)
        self._expectations[config.name] = config
        logger.debug("Registered GE expectation '%s' (%s on '%s')", config.name, config.expectation, config.column)

    def get(self, name: str) -> Optional[ExpectationConfig]:
        """Get an expectation by name."""
        return self._expectations.get(name)

    def all(self) -> List[ExpectationConfig]:
        """Get all registered expectations."""
        return list(self._expectations.values())

    def active(self) -> List[ExpectationConfig]:
        """Get enabled expectations only."""
        return [e for e in self._expectations.values() if e.enabled]

    def _validate_config(self, config: ExpectationConfig) -> None:
        """Enforce strict configuration validation rules."""
        if not config.name or not isinstance(config.name, str):
            raise ValueError("GE Expectation requires a non-empty string 'name'")
        if not config.column or not isinstance(config.column, str):
            raise ValueError(f"Expectation '{config.name}' requires a valid 'column' name")

        if config.expectation not in SUPPORTED_EXPECTATIONS:
            raise ValueError(
                f"Unknown expectation '{config.expectation}' for '{config.name}'. "
                f"Allowed expectations: {sorted(list(SUPPORTED_EXPECTATIONS))}"
            )

        # Validate expectation-specific parameters
        if config.expectation == "expect_column_values_to_be_between":
            if config.min_value is None and config.max_value is None:
                raise ValueError(
                    f"Expectation '{config.name}' (expect_column_values_to_be_between) requires at least min_value or max_value"
                )
            if (
                config.min_value is not None
                and config.max_value is not None
                and config.min_value > config.max_value
            ):
                raise ValueError(
                    f"Expectation '{config.name}': min_value ({config.min_value}) cannot be greater than max_value ({config.max_value})"
                )

        if config.expectation == "expect_column_values_to_be_in_set":
            if not config.value_set or not isinstance(config.value_set, list):
                raise ValueError(
                    f"Expectation '{config.name}' (expect_column_values_to_be_in_set) requires a non-empty 'value_set' list"
                )

    @classmethod
    def load_from_yaml(cls, yaml_path: str) -> "GEExpectationRegistry":
        """Load and validate expectations from a YAML configuration file."""
        if not os.path.exists(yaml_path):
            raise FileNotFoundError(f"GE Expectation config file not found: {yaml_path}")

        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict) or "expectations" not in data:
            raise ValueError(f"Invalid YAML format in {yaml_path}: missing top-level 'expectations' list")

        registry = cls()
        seen_names: Set[str] = set()

        for idx, entry in enumerate(data["expectations"]):
            if not isinstance(entry, dict):
                raise ValueError(f"Expectation entry #{idx} in {yaml_path} must be a dict")

            name = entry.get("name")
            if not name:
                raise ValueError(f"Expectation entry #{idx} missing 'name'")

            if name in seen_names:
                raise ValueError(f"Duplicate GE expectation name '{name}' in {yaml_path}")
            seen_names.add(name)

            expectation = entry.get("expectation")
            column = entry.get("column")
            enabled = bool(entry.get("enabled", True))

            severity_str = str(entry.get("severity", "HIGH")).upper()
            try:
                severity = Severity(severity_str)
            except ValueError:
                valid_sevs = [s.value for s in Severity]
                raise ValueError(f"Invalid severity '{severity_str}' in expectation '{name}'. Allowed: {valid_sevs}")

            cfg = ExpectationConfig(
                name=name,
                expectation=expectation,
                column=column,
                severity=severity,
                enabled=enabled,
                min_value=entry.get("min_value"),
                max_value=entry.get("max_value"),
                strict_min=entry.get("strict_min"),
                strict_max=entry.get("strict_max"),
                value_set=entry.get("value_set"),
                kwargs=entry.get("kwargs", {}),
            )
            registry.register(cfg)

        logger.info("Loaded %d GE expectations from %s", len(registry.all()), yaml_path)
        return registry
