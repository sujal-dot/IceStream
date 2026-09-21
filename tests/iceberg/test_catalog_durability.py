"""Iceberg REST Catalog Durability and Persistence Tests.

Validates:
1. REST Catalog connection and presence of required namespaces.
2. Table schema contracts and properties across bronze, silver, quarantine, and audit.
3. Underlying persistent backend storage in PostgreSQL (iceberg_tables, iceberg_namespace_properties).
4. Client transparent connection over REST protocol.
"""

import os
import sys
from pathlib import Path
import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from iceberg.config.catalog import get_catalog, get_catalog_config
from pyiceberg.catalog.rest import RestCatalog


@pytest.fixture(scope="module")
def catalog():
    return get_catalog(is_internal=False)


def test_catalog_instance_and_namespaces(catalog):
    """Verify catalog connects via RestCatalog and exposes all required namespaces."""
    assert isinstance(catalog, RestCatalog)
    assert catalog.name == "icestream"

    namespaces = [ns[0] if isinstance(ns, tuple) else ns for ns in catalog.list_namespaces()]
    for expected_ns in ["bronze", "silver", "quarantine", "audit"]:
        assert expected_ns in namespaces, f"Expected namespace '{expected_ns}' missing from catalog"


def test_catalog_table_contracts(catalog):
    """Verify all 4 core tables exist and expose valid schemas."""
    expected_tables = [
        "bronze.checkout_events",
        "silver.valid_checkout_events",
        "quarantine.invalid_checkout_events",
        "audit.data_quality_results",
    ]

    for tbl_identifier in expected_tables:
        assert catalog.table_exists(tbl_identifier), f"Table '{tbl_identifier}' does not exist"
        tbl = catalog.load_table(tbl_identifier)
        assert tbl is not None
        assert len(tbl.schema().fields) > 0


def test_postgres_backend_persistence():
    """Verify metadata is persisted in PostgreSQL iceberg_catalog database."""
    import psycopg2
    import psycopg2.extras

    host = os.getenv("POSTGRES_HOST", "127.0.0.1")
    port = int(os.getenv("POSTGRES_PORT", "5433"))
    user = os.getenv("ICEBERG_POSTGRES_USER") or ("icestream_user" if os.getenv("TESTING") else os.getenv("POSTGRES_USER", "icestream_user"))
    password = os.getenv("ICEBERG_POSTGRES_PASSWORD") or ("change-me-postgres-secret" if os.getenv("TESTING") else os.getenv("POSTGRES_PASSWORD", "change-me-postgres-secret"))

    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname="iceberg_catalog",
            user=user,
            password=password,
            cursor_factory=psycopg2.extras.DictCursor,
        )
    except Exception as e:
        pytest.skip(f"PostgreSQL iceberg_catalog not reachable directly on {host}:{port}: {e}")

    with conn.cursor() as cur:
        # 1. Verify tables catalog relation exists and contains entries
        cur.execute("SELECT table_namespace, table_name, metadata_location FROM iceberg_tables;")
        rows = cur.fetchall()
        table_tuples = [(r["table_namespace"], r["table_name"]) for r in rows]

        assert ("bronze", "checkout_events") in table_tuples
        assert ("silver", "valid_checkout_events") in table_tuples
        assert ("quarantine", "invalid_checkout_events") in table_tuples
        assert ("audit", "data_quality_results") in table_tuples

        for r in rows:
            assert r["metadata_location"].startswith("s3://warehouse/"), f"Invalid metadata location: {r['metadata_location']}"

        # 2. Verify namespace properties relation
        cur.execute("SELECT namespace, property_key, property_value FROM iceberg_namespace_properties;")
        ns_rows = cur.fetchall()
        namespaces_found = {r["namespace"] for r in ns_rows}
        assert {"bronze", "silver", "quarantine", "audit"}.issubset(namespaces_found)

    conn.close()
