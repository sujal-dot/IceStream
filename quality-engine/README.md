# IceStream Quality Engine

The **Quality Engine** is an extensible, modular Python evaluation component that inspects streaming events flowing through the IceStream pipeline against configurable data-quality rules, isolates execution failures, computes event health status, and tracks quality metrics.

---

## 1. Architectural Role & Boundary

The Quality Engine is responsible for:
```
Event  ──>  Rule Evaluation  ──>  Validation Results  ──>  Metrics
```

It is **decoupled** from transport, storage, and notification layers:
- **Upstream**: Kafka and Flink feed events into the engine.
- **Engine**: Applies registered quality rules and generates standardized `ValidationResult` objects.
- **Downstream**: Metrics, future quarantine routing, and circuit breakers consume the results.

```
       Kafka / Flink / Upstream
                  │
                  ▼
                Event
                  │
                  ▼
          ┌───────────────┐
          │ QualityEngine │
          └───────┬───────┘
                  │
                  ▼
            Rule Registry
                  │
        ┌─────────┼─────────┐
        ▼         ▼         ▼
      Rule A    Rule B    Rule C
        │         │         │
        └─────────┼─────────┘
                  ▼
         ValidationResult[]
                  │
          ┌───────┴───────┐
          ▼               ▼
       Metrics         Summary
```

---

## 2. Directory Structure

```
quality-engine/
│
├── rules/
│   ├── __init__.py          # Rule exports & status definitions
│   ├── base.py              # QualityRule interface, Severity, ValidationResult, EventIdNotNullRule
│   ├── engine.py            # QualityEngine execution & isolation orchestrator
│   └── registry.py          # RuleRegistry & dynamic @register_rule decorator
│
├── validators/
│   ├── __init__.py
│   └── base.py              # BaseValidator & EventValidator orchestration
│
├── detectors/
│   └── __init__.py          # Anomaly & drift detector placeholders (future)
│
├── metrics/
│   ├── __init__.py
│   └── collector.py         # MetricsCollector interface & InMemoryMetricsCollector
│
├── schemas/
│   ├── __init__.py
│   └── event.py             # QualityEvent dataclass model
│
├── config/
│   ├── __init__.py
│   ├── loader.py            # YAML configuration parser & validator
│   └── rules.yaml           # Declarative rule enablement & severity overrides
│
├── tests/
│   ├── __init__.py
│   ├── test_rule_interface.py
│   ├── test_registry.py
│   ├── test_quality_result.py
│   ├── test_engine.py
│   ├── test_config.py
│   └── test_metrics.py
│
├── main.py                  # CLI runner & demonstration entry point
├── requirements.txt
└── README.md
```

---

## 3. Core Contract: `validate(event)`

Every quality rule must subclass `QualityRule` and implement the `validate(event)` method:

```python
from rules.base import QualityRule, Severity, ValidationResult
from schemas.event import QualityEvent

class AmountPositiveRule(QualityRule):
    @property
    def name(self) -> str:
        return "amount_positive"

    @property
    def default_severity(self) -> Severity:
        return Severity.HIGH

    def validate(self, event: QualityEvent) -> ValidationResult:
        amt = event.amount
        if amt is None or amt <= 0:
            return ValidationResult(
                rule_name=self.name,
                passed=False,
                severity=self.severity,
                message=f"amount must be strictly positive, got {amt}",
                field="amount",
                event_id=event.event_id,
            )
        return ValidationResult(
            rule_name=self.name,
            passed=True,
            severity=self.severity,
            message="amount is positive",
            field="amount",
            event_id=event.event_id,
        )
```

---

## 4. Rule Registry & Extensibility

Rules are registered dynamically without modifying the engine source code:

```python
from rules.registry import RuleRegistry, default_registry, register_rule
from rules.engine import QualityEngine

# Method 1: Explicit instance registration
registry = RuleRegistry()
registry.register(AmountPositiveRule())

# Method 2: Dynamic class decorator
@register_rule(registry=registry)
class CustomCheckRule(QualityRule):
    ...

# Instantiate engine and validate
engine = QualityEngine(registry=registry)
results, summary = engine.validate_with_summary(event)
```

---

## 5. Declarative YAML Configuration

Rule enablements and severity overrides can be configured declaratively via `config/rules.yaml`:

```yaml
rules:
  - name: event_id_not_null
    enabled: true
    severity: CRITICAL
```

Loading configuration validates rule existence, type safety, and duplicate protection:

```python
from config.loader import load_rule_config

load_rule_config("config/rules.yaml", registry=registry)
```

---

## 6. Running the CLI Demonstration

```bash
# Run with default configuration
python quality-engine/main.py

# Run with custom YAML configuration
python quality-engine/main.py --config quality-engine/config/rules.yaml
```

---

## 7. Running Unit Tests

```bash
pytest -v quality-engine/tests
```
