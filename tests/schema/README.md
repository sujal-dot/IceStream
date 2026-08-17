# IceStream Schema Testing Suite

This directory contains automated unit and integration tests for the IceStream Schema Versioning & Compatibility Engine.

## Test Structure

- `test_schema_loader.py`: Verifies JSON parsing, schema validation rules, error handling for malformed definitions, unsupported field types, and missing required attributes.
- `test_schema_registry.py`: Tests the `SchemaRegistry` abstraction, schema version discovery (`v1`, `v2`, `v3`), current version retrieval, dynamic version registration, and error handling.
- `test_compatibility.py`: Validates the compatibility engine (`check_compatibility`), testing:
  - Compatible evolutions (v1 → v2, optional field addition, enum value expansion, safe numeric type promotion).
  - Breaking evolutions (v2 → v3, incompatible type change float → string, required field additions/removals, optional → required field transitions, enum value removals).

## Running Tests

Execute the schema test suite with `pytest`:

```bash
pytest tests/schema -v
```
