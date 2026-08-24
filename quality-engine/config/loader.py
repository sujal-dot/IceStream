"""Rule configuration loader and validation engine."""

import logging
import os
from typing import Any, Dict, List, Optional, Set
import yaml

from rules.base import Severity
from rules.registry import RuleRegistry, default_registry

logger = logging.getLogger("quality_engine.config")


def load_rule_config(
    config_path: str,
    registry: Optional[RuleRegistry] = None,
) -> RuleRegistry:
    """Load and validate rules configuration from a YAML file.
    
    Args:
        config_path: Path to the YAML configuration file.
        registry: RuleRegistry instance to configure (defaults to global default_registry).

    Returns:
        The configured RuleRegistry.

    Raises:
        FileNotFoundError: If the configuration file does not exist.
        ValueError: If configuration syntax or values are invalid, or duplicates exist.
        KeyError: If a configured rule is not registered in the registry.
    """
    target_registry = registry or default_registry

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        raise ValueError(f"Failed to parse YAML file {config_path}: {e}") from e

    if not isinstance(data, dict):
        raise ValueError(f"Invalid configuration root in {config_path}: expected mapping/dict")

    if "rules" not in data or not isinstance(data["rules"], list):
        raise ValueError(f"Configuration in {config_path} must contain a 'rules' list")

    seen_rules: Set[str] = set()

    for idx, rule_cfg in enumerate(data["rules"]):
        if not isinstance(rule_cfg, dict):
            raise ValueError(f"Rule entry #{idx} in {config_path} must be a dictionary")

        rule_name = rule_cfg.get("name")
        if not rule_name or not isinstance(rule_name, str):
            raise ValueError(f"Rule entry #{idx} missing valid 'name' field")

        if rule_name in seen_rules:
            raise ValueError(
                f"Duplicate rule '{rule_name}' declared in configuration {config_path}"
            )
        seen_rules.add(rule_name)

        if not target_registry.exists(rule_name):
            raise KeyError(
                f"Unknown rule: {rule_name}. Rule must be registered before configuration."
            )

        rule = target_registry.get(rule_name)
        if rule is None:
            raise KeyError(f"Unknown rule: {rule_name}")

        # Validate and apply enabled
        if "enabled" in rule_cfg:
            enabled = rule_cfg["enabled"]
            if not isinstance(enabled, bool):
                raise ValueError(
                    f"Invalid 'enabled' value for rule '{rule_name}': expected boolean, got {type(enabled).__name__}"
                )
            rule.enabled = enabled

        # Validate and apply severity override
        if "severity" in rule_cfg:
            severity_str = rule_cfg["severity"]
            try:
                severity_enum = Severity(str(severity_str).upper())
            except ValueError:
                valid_severities = [s.value for s in Severity]
                raise ValueError(
                    f"Invalid severity '{severity_str}' for rule '{rule_name}'. Allowed: {valid_severities}"
                )
            rule.severity = severity_enum

        logger.debug(
            "Configured rule '%s': enabled=%s, severity=%s",
            rule_name,
            rule.enabled,
            rule.severity.value,
        )

    logger.info(
        "Successfully loaded and applied configuration for %d rules from %s",
        len(seen_rules),
        config_path,
    )
    return target_registry
