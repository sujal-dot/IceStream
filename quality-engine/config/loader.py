"""Rule configuration loader and validation engine."""

import logging
import os
from typing import Any, Dict, List, Optional, Set
import yaml

from rules.base import QualityRule, Severity
from rules.not_null import NotNullRule
from rules.positive import AmountPositiveRule
from rules.allowed_values import AllowedValuesRule
from rules.timestamp import TimestampValidRule
from detectors.duplicate import DuplicateEventRule, DuplicateOrderRule
from detectors.anomaly import ImpossibleAmountRule, FutureTimestampRule, LateEventRule
from detectors.schema_drift import SchemaDriftRule
from rules.registry import RuleRegistry, default_registry

logger = logging.getLogger("quality_engine.config")

RULE_TYPE_MAP = {
    "not_null": NotNullRule,
    "positive": AmountPositiveRule,
    "allowed_values": AllowedValuesRule,
    "timestamp": TimestampValidRule,
    "duplicate_event": DuplicateEventRule,
    "duplicate_order": DuplicateOrderRule,
    "impossible_amount": ImpossibleAmountRule,
    "future_timestamp": FutureTimestampRule,
    "late_event": LateEventRule,
    "schema_drift": SchemaDriftRule,
}


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

    all_rule_entries: List[Dict[str, Any]] = []
    if "rules" in data and isinstance(data["rules"], list):
        all_rule_entries.extend(data["rules"])
    if "anomaly_rules" in data and isinstance(data["anomaly_rules"], list):
        all_rule_entries.extend(data["anomaly_rules"])

    if not all_rule_entries:
        raise ValueError(f"Configuration in {config_path} must contain a 'rules' or 'anomaly_rules' list")

    seen_rules: Set[str] = set()

    for idx, rule_cfg in enumerate(all_rule_entries):
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

        # Parse enabled status
        enabled = True
        if "enabled" in rule_cfg:
            enabled_val = rule_cfg["enabled"]
            if not isinstance(enabled_val, bool):
                raise ValueError(
                    f"Invalid 'enabled' value for rule '{rule_name}': expected boolean, got {type(enabled_val).__name__}"
                )
            enabled = enabled_val

        # Parse severity
        severity_enum: Optional[Severity] = None
        if "severity" in rule_cfg:
            severity_str = rule_cfg["severity"]
            try:
                severity_enum = Severity(str(severity_str).upper())
            except ValueError:
                valid_severities = [s.value for s in Severity]
                raise ValueError(
                    f"Invalid severity '{severity_str}' for rule '{rule_name}'. Allowed: {valid_severities}"
                )

        rule_type = rule_cfg.get("type")
        if rule_type:
            if rule_type not in RULE_TYPE_MAP:
                raise ValueError(
                    f"Unknown rule type '{rule_type}' for rule '{rule_name}'. Allowed: {list(RULE_TYPE_MAP.keys())}"
                )

            field = rule_cfg.get("field", "event_id" if "event" in rule_name else "amount")

            if rule_type == "not_null":
                instance = NotNullRule(
                    field=field,
                    name=rule_name,
                    severity_override=severity_enum,
                    enabled=enabled,
                )
            elif rule_type == "positive":
                instance = AmountPositiveRule(
                    field=field,
                    name=rule_name,
                    severity_override=severity_enum,
                    enabled=enabled,
                )
            elif rule_type == "allowed_values":
                allowed_vals = rule_cfg.get("allowed_values")
                if not allowed_vals or not isinstance(allowed_vals, list):
                    raise ValueError(
                        f"Rule '{rule_name}' of type 'allowed_values' requires a non-empty 'allowed_values' list"
                    )
                instance = AllowedValuesRule(
                    field=field,
                    allowed_values=allowed_vals,
                    name=rule_name,
                    severity_override=severity_enum,
                    enabled=enabled,
                )
            elif rule_type == "timestamp":
                instance = TimestampValidRule(
                    field=field,
                    name=rule_name,
                    severity_override=severity_enum,
                    enabled=enabled,
                )
            elif rule_type == "duplicate_event":
                window = rule_cfg.get("window_seconds", 300)
                instance = DuplicateEventRule(
                    window_seconds=window,
                    severity_override=severity_enum,
                    enabled=enabled,
                )
            elif rule_type == "duplicate_order":
                window = rule_cfg.get("window_seconds", 300)
                instance = DuplicateOrderRule(
                    window_seconds=window,
                    severity_override=severity_enum,
                    enabled=enabled,
                )
            elif rule_type == "impossible_amount":
                max_val = rule_cfg.get("max_value", 500000)
                instance = ImpossibleAmountRule(
                    max_value=max_val,
                    field=field,
                    severity_override=severity_enum,
                    enabled=enabled,
                )
            elif rule_type == "future_timestamp":
                tolerance = rule_cfg.get("tolerance_seconds", 30)
                instance = FutureTimestampRule(
                    tolerance_seconds=tolerance,
                    field=field,
                    severity_override=severity_enum,
                    enabled=enabled,
                )
            elif rule_type == "late_event":
                lateness = rule_cfg.get("allowed_lateness_seconds", 120)
                instance = LateEventRule(
                    allowed_lateness_seconds=lateness,
                    field=field,
                    severity_override=severity_enum,
                    enabled=enabled,
                )
            elif rule_type == "schema_drift":
                baseline = rule_cfg.get("baseline_version", "v1")
                rename_map = rule_cfg.get("rename_map", {"customer_id": "customer"})
                instance = SchemaDriftRule(
                    baseline_version=baseline,
                    rename_map=rename_map,
                    severity_override=severity_enum,
                    enabled=enabled,
                )
            else:
                raise ValueError(f"Unhandled rule type: {rule_type}")

            target_registry.register(instance, overwrite=True)
        else:
            if not target_registry.exists(rule_name):
                raise KeyError(
                    f"Unknown rule: {rule_name}. Rule must be registered before configuration."
                )

            rule = target_registry.get(rule_name)
            if rule is None:
                raise KeyError(f"Unknown rule: {rule_name}")

            rule.enabled = enabled
            if severity_enum:
                rule.severity = severity_enum

            # Configure specific rule attributes if provided in YAML
            if hasattr(rule, "window_seconds") and "window_seconds" in rule_cfg:
                setattr(rule, "window_seconds", rule_cfg["window_seconds"])
            if hasattr(rule, "max_value") and "max_value" in rule_cfg:
                setattr(rule, "max_value", rule_cfg["max_value"])
            if hasattr(rule, "tolerance_seconds") and "tolerance_seconds" in rule_cfg:
                setattr(rule, "tolerance_seconds", rule_cfg["tolerance_seconds"])
            if hasattr(rule, "allowed_lateness_seconds") and "allowed_lateness_seconds" in rule_cfg:
                setattr(rule, "allowed_lateness_seconds", rule_cfg["allowed_lateness_seconds"])

        logger.debug(
            "Configured rule '%s': enabled=%s, severity=%s",
            rule_name,
            enabled,
            severity_enum.value if severity_enum else "DEFAULT",
        )

    logger.info(
        "Successfully loaded and applied configuration for %d rules from %s",
        len(seen_rules),
        config_path,
    )
    return target_registry
