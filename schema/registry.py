"""Schema Registry abstraction for managing and retrieving versioned schemas."""

json_import_needed = False
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from schema.compatibility import check_compatibility
from schema.loader import load_schema, validate_schema_dict
from schema.models import CompatibilityResult, EventSchema


class SchemaRegistry:
    """Lightweight local Schema Registry abstraction for IceStream."""

    def __init__(
        self,
        schema_dir: Optional[Union[str, Path]] = None,
        manifest_path: Optional[Union[str, Path]] = None,
    ):
        if schema_dir is None:
            self.schema_dir = Path(__file__).resolve().parent
        else:
            self.schema_dir = Path(schema_dir).resolve()

        if manifest_path is None:
            self.manifest_path = self.schema_dir / "registry.json"
        else:
            self.manifest_path = Path(manifest_path).resolve()

        self._schemas: Dict[str, EventSchema] = {}
        self._current_version: str = "v1"
        self._load_registry()

    def _load_registry(self):
        """Discover and load schemas from schema_dir and registry.json."""
        if self.manifest_path.exists():
            try:
                with open(self.manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                    self._current_version = manifest.get("current_version", "v1")
            except Exception:
                pass

        # Load all v*.json files in schema_dir
        if self.schema_dir.exists() and self.schema_dir.is_dir():
            for json_file in sorted(self.schema_dir.glob("v*.json")):
                try:
                    schema = load_schema(json_file)
                    self._schemas[schema.schema_version] = schema
                except Exception:
                    pass

    def get(self, version_str: str) -> EventSchema:
        """Retrieve an EventSchema by version tag (e.g., 'v1', 'v2')."""
        if version_str in self._schemas:
            return self._schemas[version_str]

        # Try to load directly from schema_dir file if not cached
        target_file = self.schema_dir / f"{version_str}.json"
        if target_file.exists():
            schema = load_schema(target_file)
            self._schemas[version_str] = schema
            return schema

        # Major version fallback: e.g. "v1.0.0" -> "v1"
        if "." in version_str:
            major_ver = version_str.split(".")[0]
            if major_ver in self._schemas:
                return self._schemas[major_ver]
            target_major_file = self.schema_dir / f"{major_ver}.json"
            if target_major_file.exists():
                schema = load_schema(target_major_file)
                self._schemas[major_ver] = schema
                return schema

        raise KeyError(f"Schema version '{version_str}' not found in registry (available: {self.list_versions()})")

    def list_versions(self) -> List[str]:
        """List all available schema version identifiers sorted."""
        return sorted(list(self._schemas.keys()))

    def current(self) -> EventSchema:
        """Retrieve the current active version EventSchema."""
        if self._current_version in self._schemas:
            return self._schemas[self._current_version]
        elif self._schemas:
            latest = self.list_versions()[-1]
            return self._schemas[latest]
        raise KeyError("No schemas available in registry.")

    def get_current_version_tag(self) -> str:
        """Get the current version string."""
        return self._current_version

    def register(
        self,
        version_str: str,
        schema_input: Union[EventSchema, Dict[str, Any], Path, str],
    ) -> EventSchema:
        """Register a new schema version in the registry."""
        if isinstance(schema_input, EventSchema):
            schema = schema_input
        elif isinstance(schema_input, dict):
            schema = validate_schema_dict(schema_input, source_name=version_str)
        elif isinstance(schema_input, (Path, str)):
            schema = load_schema(schema_input)
        else:
            raise ValueError(f"Unsupported schema_input type: {type(schema_input)}")

        if schema.schema_version != version_str:
            schema.schema_version = version_str

        self._schemas[version_str] = schema
        return schema

    def compare_versions(self, old_ver: str, new_ver: str) -> CompatibilityResult:
        """Compare two version tags using the compatibility engine."""
        old_schema = self.get(old_ver)
        new_schema = self.get(new_ver)
        return check_compatibility(old_schema, new_schema)
