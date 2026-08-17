#!/usr/bin/env python3
"""CLI utility to compare two event schemas for compatibility and breaking changes."""

import argparse
import json
import sys
from pathlib import Path

# Add project root to sys.path if executing directly
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from schema.compatibility import check_compatibility
from schema.loader import SchemaValidationError, load_schema
from schema.models import Classification
from schema.registry import SchemaRegistry


def resolve_schema(schema_arg: str):
    """Resolve schema argument as a file path or registry version tag."""
    path = Path(schema_arg)
    if path.exists() and path.is_file():
        return load_schema(path)

    # Try resolving via registry
    try:
        registry = SchemaRegistry()
        return registry.get(schema_arg)
    except Exception as err:
        raise ValueError(
            f"Could not resolve schema '{schema_arg}'. Specify a valid JSON file path or registered version tag. Error: {err}"
        )


def format_human_output(result) -> str:
    """Format compatibility result into clean human-readable text."""
    lines = []
    lines.append("Schema Compatibility Check")
    lines.append("==========================")
    lines.append("")
    lines.append(f"Old schema: {result.old_version}")
    lines.append(f"New schema: {result.new_version}")
    lines.append("")

    if not result.changes:
        lines.append("Changes:")
        lines.append("  (No changes detected)")
        lines.append("")
        lines.append("Classification:")
        lines.append("COMPATIBLE ✓")
        return "\n".join(lines)

    lines.append("Changes:")
    for change in result.changes:
        field = change.field
        ctype = change.change_type
        if ctype == "FIELD_ADDED":
            req_str = "required" if change.new_value and change.new_value.get("required") else "optional"
            ftype = change.new_value.get("type") if change.new_value else "unknown"
            lines.append(f"+ {field}: {req_str} {ftype}")
        elif ctype == "FIELD_REMOVED":
            lines.append(f"- {field}: removed")
        elif ctype == "FIELD_TYPE_CHANGED":
            lines.append(f"~ {field}")
            lines.append(f"  {change.old_value} → {change.new_value}")
        elif ctype == "FIELD_REQUIRED_CHANGED":
            lines.append(f"~ {field}")
            lines.append(f"  required: {change.old_value} → {change.new_value}")
        elif ctype == "ENUM_VALUE_ADDED":
            lines.append(f"+ {field} (enum value added)")
            lines.append(f"  {change.description}")
        elif ctype == "ENUM_VALUE_REMOVED":
            lines.append(f"- {field} (enum value removed)")
            lines.append(f"  {change.description}")
        else:
            lines.append(f"~ {field}: {change.description}")

    lines.append("")
    lines.append("Classification:")
    if result.compatible:
        lines.append("COMPATIBLE ✓")
    else:
        lines.append("BREAKING ✗")
        lines.append("")
        lines.append("Reason:")
        breaking_descs = [c.description for c in result.changes if c.classification == Classification.BREAKING]
        for desc in breaking_descs:
            lines.append(f"- {desc}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="IceStream Schema Compatibility & Breaking Change Detection CLI"
    )
    parser.add_argument(
        "--old",
        required=True,
        help="Path to old schema JSON file or version tag (e.g. schema/v1.json or v1)",
    )
    parser.add_argument(
        "--new",
        required=True,
        help="Path to new schema JSON file or version tag (e.g. schema/v2.json or v2)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output structured JSON instead of human-readable text",
    )

    args = parser.parse_args()

    try:
        old_schema = resolve_schema(args.old)
        new_schema = resolve_schema(args.new)

        result = check_compatibility(old_schema, new_schema)

        if args.json_output:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(format_human_output(result))

        sys.exit(0 if result.compatible else 1)

    except (SchemaValidationError, ValueError, FileNotFoundError) as err:
        if args.json_output:
            print(json.dumps({"error": str(err)}, indent=2))
        else:
            print(f"Error: {err}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
