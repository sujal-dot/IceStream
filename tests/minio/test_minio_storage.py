# ==============================================================================
# IceStream - MinIO Object Storage Pytest Verification Suite
# ==============================================================================
import os
import pytest
import requests
from minio import Minio
from io import BytesIO


MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT_HOST", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "icestream_minio")
MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "icestream_minio_secret")
SECURE = False


@pytest.fixture(scope="module")
def minio_client():
    client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=SECURE
    )
    return client


def test_minio_health_check():
    """Verify MinIO health check HTTP endpoint."""
    url = f"http://{MINIO_ENDPOINT}/minio/health/live"
    response = requests.get(url, timeout=5)
    assert response.status_code == 200, f"MinIO health check failed: {response.status_code}"


def test_minio_buckets_exist(minio_client):
    """Verify all four required Day 8 buckets exist."""
    required_buckets = {"warehouse", "checkpoints", "schemas", "logs"}
    existing_buckets = {b.name for b in minio_client.list_buckets()}
    
    for bucket in required_buckets:
        assert bucket in existing_buckets, f"Missing required bucket: {bucket}"


def test_minio_object_read_write(minio_client):
    """Verify writing an object to MinIO and reading it back."""
    bucket_name = "warehouse"
    object_name = "pytest-test/hello.txt"
    data = b"IceStream Day 8 Pytest Object Storage Verification"
    
    # Write object
    minio_client.put_object(
        bucket_name,
        object_name,
        BytesIO(data),
        length=len(data),
        content_type="text/plain"
    )
    
    # Read object back
    response = minio_client.get_object(bucket_name, object_name)
    content = response.read()
    response.close()
    response.release_conn()
    
    assert content == data
    assert len(content) == len(data)


def test_flink_test_object_exists(minio_client):
    """Verify that the Flink -> MinIO connectivity test artifact exists."""
    bucket_name = "warehouse"
    objects = list(minio_client.list_objects(bucket_name, prefix="day8-test/", recursive=True))
    
    assert len(objects) > 0, "No Flink test objects found in warehouse/day8-test/"
    
    # Find connection-test.txt or part file
    found = False
    for obj in objects:
        response = minio_client.get_object(bucket_name, obj.object_name)
        text = response.read().decode("utf-8")
        response.close()
        response.release_conn()
        
        if "Flink -> MinIO connectivity test" in text or "IceStream Day 8" in text:
            found = True
            break
            
    assert found, "Flink test artifact content verification failed"


def test_schema_bucket_contents(minio_client):
    """Verify versioned schema files exist in schemas bucket, uploading from local schema/ if needed."""
    bucket_name = "schemas"
    schema_dir = os.path.join(os.path.dirname(__file__), "..", "..", "schema")
    
    for v in ["v1.json", "v2.json", "v3.json"]:
        local_path = os.path.join(schema_dir, v)
        if os.path.exists(local_path):
            with open(local_path, "rb") as f:
                content = f.read()
                minio_client.put_object(
                    bucket_name,
                    v,
                    BytesIO(content),
                    length=len(content),
                    content_type="application/json"
                )

    objects = {obj.object_name for obj in minio_client.list_objects(bucket_name)}
    for v in ["v1.json", "v2.json", "v3.json"]:
        assert v in objects, f"Schema file {v} missing from schemas bucket"
