#!/usr/bin/env python3
"""Day 17 Final Demonstration Script for Schema Drift Detector."""

from pathlib import Path
import sys

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from schema.compatibility import SchemaComparator
from schema.registry import SchemaRegistry


def run_demo():
    registry = SchemaRegistry()
    v1 = registry.get("v1")
    v2 = registry.get("v2")
    v3 = registry.get("v3")

    comparator = SchemaComparator(rename_map={"customer_id": "customer"})

    # --- Demo 1: V1 -> V2 ---
    diff_v1_v2 = comparator.compare(v1, v2)
    new_col_change = next(c for c in diff_v1_v2.changes if c.field == "coupon_code")

    print("SCHEMA V1")
    print("amount:")
    print("float")
    print("        ↓")
    print("SCHEMA V2")
    print("amount:")
    print("float")
    print("coupon_code:")
    print("string")
    print("        ↓")
    print("RESULT:")
    print(new_col_change.change_type.value)
    print(new_col_change.severity.value)
    print(diff_v1_v2.classification.value)
    print()

    # --- Demo 2: V1 -> V3 ---
    diff_v1_v3 = comparator.compare(v1, v3)
    type_change = next(c for c in diff_v1_v3.changes if c.field == "amount")

    print("SCHEMA V1")
    print("amount:")
    print("float")
    print("        ↓")
    print("SCHEMA V3")
    print("amount:")
    print("string")
    print("        ↓")
    print("RESULT:")
    print("┌───────────────────────────────────────┐")
    print(f"│ CRITICAL SCHEMA DRIFT                 │")
    print(f"│                                       │")
    print(f"│ Field: {type_change.field:<31}│")
    print(f"│ Expected: {type_change.expected_type:<28}│")
    print(f"│ Actual: {type_change.actual_type:<30}│")
    print(f"│ Change: {type_change.change_type.value:<30}│")
    print(f"│ Severity: {type_change.severity.value:<28}│")
    print(f"│ Compatibility: {diff_v1_v3.classification.value:<23}│")
    print("└───────────────────────────────────────┘")


if __name__ == "__main__":
    run_demo()
