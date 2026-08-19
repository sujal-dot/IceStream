"""
Unit and Integration Tests for Iceberg Catalog Connection
"""
import pytest
from iceberg.config.catalog import get_catalog, get_catalog_config
from pyiceberg.catalog.rest import RestCatalog


def test_catalog_config():
    config = get_catalog_config(is_internal=False)
    assert config["type"] == "rest"
    assert config["uri"] == "http://localhost:8181"
    assert config["warehouse"] == "s3://warehouse/"


def test_catalog_connection():
    catalog = get_catalog()
    assert isinstance(catalog, RestCatalog)
    assert catalog.name == "icestream"
