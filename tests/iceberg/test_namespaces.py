"""
Integration Tests for Iceberg Lakehouse Namespaces
"""
import pytest
from iceberg.config.catalog import get_catalog

EXPECTED_NAMESPACES = {"bronze", "silver", "quarantine", "audit"}


def test_namespace_listing():
    catalog = get_catalog()
    namespaces = {ns[0] for ns in catalog.list_namespaces() if ns}
    assert EXPECTED_NAMESPACES.issubset(namespaces), f"Missing namespaces: {EXPECTED_NAMESPACES - namespaces}"


@pytest.mark.parametrize("ns", ["bronze", "silver", "quarantine", "audit"])
def test_namespace_exists(ns):
    catalog = get_catalog()
    namespaces = {n[0] for n in catalog.list_namespaces() if n}
    assert ns in namespaces
