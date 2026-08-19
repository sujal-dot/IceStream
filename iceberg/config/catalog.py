"""
IceStream Apache Iceberg Catalog Configuration & Factory
"""
import os
from typing import Dict, Any, Optional
from pyiceberg.catalog import load_catalog, Catalog


def get_catalog_config(is_internal: bool = False) -> Dict[str, Any]:
    """
    Returns the Iceberg REST catalog properties dictionary.
    
    :param is_internal: Set to True if connecting from within Docker network.
    """
    rest_uri = os.getenv(
        "ICEBERG_REST_URI_INTERNAL" if is_internal else "ICEBERG_REST_URI",
        "http://iceberg-rest:8181" if is_internal else "http://localhost:8181"
    )
    minio_endpoint = os.getenv(
        "MINIO_ENDPOINT_INTERNAL" if is_internal else "MINIO_ENDPOINT",
        "http://minio:9000" if is_internal else "http://localhost:9000"
    )
    access_key = os.getenv("MINIO_ROOT_USER", os.getenv("MINIO_ACCESS_KEY", "icestream_minio"))
    secret_key = os.getenv("MINIO_ROOT_PASSWORD", os.getenv("MINIO_SECRET_KEY", "icestream_minio_secret"))
    region = os.getenv("MINIO_REGION", "us-east-1")
    warehouse = os.getenv("ICEBERG_WAREHOUSE", "s3://warehouse/")

    return {
        "type": "rest",
        "uri": rest_uri,
        "warehouse": warehouse,
        "s3.endpoint": minio_endpoint,
        "s3.access-key-id": access_key,
        "s3.secret-access-key": secret_key,
        "s3.path-style-access": "true",
        "s3.region": region,
    }


def get_catalog(name: Optional[str] = None, is_internal: bool = False) -> Catalog:
    """
    Instantiates and returns the Iceberg REST Catalog.
    """
    catalog_name = name or os.getenv("ICEBERG_CATALOG_NAME", "icestream")
    config = get_catalog_config(is_internal=is_internal)
    return load_catalog(catalog_name, **config)
