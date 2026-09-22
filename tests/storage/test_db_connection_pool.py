"""Tests for Database Connection Pooling in StorageBackend."""

from concurrent.futures import ThreadPoolExecutor
import threading
import time
import pytest

from backend.storage.db import PooledConnectionWrapper, StorageBackend
from psycopg2.extensions import STATUS_IN_TRANSACTION


def test_sqlite_pool_status():
    """Verify SQLite fallback reports non-pooled active status."""
    storage = StorageBackend(use_sqlite=True)
    status = storage.get_pool_status()
    assert status["backend"] == "sqlite"
    assert status["pooled"] is False
    assert status["is_active"] is True
    storage.close()
    assert storage.get_pool_status()["is_active"] is False


def test_pooled_connection_wrapper_lifecycle():
    """Verify PooledConnectionWrapper delegates and returns to pool on close."""
    class FakePool:
        def __init__(self):
            self.putconn_calls = []

        def putconn(self, conn, close=False):
            self.putconn_calls.append((conn, close))

    class FakeConn:
        def __init__(self):
            self.closed = False
            self.rolled_back = False
            self.status = STATUS_IN_TRANSACTION

        def rollback(self):
            self.rolled_back = True

    fake_pool = FakePool()
    fake_conn = FakeConn()

    wrapper = PooledConnectionWrapper(fake_pool, fake_conn)
    assert wrapper.status == STATUS_IN_TRANSACTION

    # Using context manager
    with wrapper as conn:
        assert conn.status == STATUS_IN_TRANSACTION

    # Verify connection was returned to pool with rollback
    assert fake_conn.rolled_back is True
    assert len(fake_pool.putconn_calls) == 1
    assert fake_pool.putconn_calls[0] == (fake_conn, False)

    # Calling close again is idempotent
    wrapper.close()
    assert len(fake_pool.putconn_calls) == 1


def test_concurrent_connection_context_manager_sqlite():
    """Verify thread-safe concurrent execution through storage.connection() in SQLite."""
    storage = StorageBackend(use_sqlite=True)

    # Create a test table
    with storage.connection() as conn:
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS test_counter (id INT, val INT);")
        cur.execute("INSERT INTO test_counter VALUES (1, 0);")
        conn.commit()

    def worker_increment(worker_id: int):
        for _ in range(10):
            with storage.connection() as conn:
                cur = conn.cursor()
                cur.execute("UPDATE test_counter SET val = val + 1 WHERE id = 1;")
                conn.commit()

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(worker_increment, i) for i in range(5)]
        for f in futures:
            f.result()

    with storage.connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT val FROM test_counter WHERE id = 1;")
        total = cur.fetchone()[0]
        assert total == 50

    storage.close()


def test_postgresql_connection_pooling_if_available():
    """Verify PostgreSQL ThreadedConnectionPool if database credentials and host are reachable."""
    try:
        storage = StorageBackend(use_sqlite=False)
        status = storage.get_pool_status()
        if not status.get("pooled"):
            pytest.skip("PostgreSQL connection pool not active")
    except Exception as e:
        pytest.skip(f"PostgreSQL connection not configured or reachable in this environment: {e}")

    assert status["backend"] == "postgresql"
    assert status["pooled"] is True
    assert status["min_connections"] >= 1
    assert status["max_connections"] >= 1

    # Concurrent operations across 8 threads
    results = []

    def query_worker(i: int):
        with storage.connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT %s as num;", (i,))
            val = cur.fetchone()[0]
            results.append(val)

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(query_worker, i) for i in range(8)]
        for f in futures:
            f.result()

    assert sorted(results) == list(range(8))

    # Test clean close
    storage.close()
    assert storage.get_pool_status()["pooled"] is False


def test_record_and_get_maintenance_run_sqlite():
    """Verify storing and retrieving lakehouse maintenance run records."""
    storage = StorageBackend(use_sqlite=True)

    run_id = storage.record_maintenance_run(
        table_name="bronze.checkout_events",
        operation="COMPACT",
        status="SUCCESS",
        files_before=15,
        files_after=1,
        records_compacted=2500,
        snapshots_expired=10,
        orphan_files_deleted=5,
        bytes_reclaimed=102400,
        duration_ms=350.0,
    )

    assert run_id is not None
    history = storage.get_maintenance_history(table_name="bronze.checkout_events", limit=10)
    assert len(history) >= 1
    latest = history[0]
    assert latest["table_name"] == "bronze.checkout_events"
    assert latest["operation"] == "COMPACT"
    assert latest["status"] == "SUCCESS"
    assert latest["files_before"] == 15
    assert latest["files_after"] == 1
    assert latest["records_compacted"] == 2500
    assert latest["snapshots_expired"] == 10
    assert latest["orphan_files_deleted"] == 5
    assert latest["bytes_reclaimed"] == 102400

    storage.close()

