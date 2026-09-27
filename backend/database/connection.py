"""Database connection management and health checks."""

import logging
import time
from typing import Dict, Tuple
from backend.storage.db import StorageBackend, get_db_storage

logger = logging.getLogger("icestream.database.connection")

_health_cache: Tuple[float, str] = (0.0, "ok")
_CACHE_TTL_SECONDS = 3.0


def check_db_health(storage: StorageBackend) -> str:
    """Perform lightweight health check on database connection with 3s TTL caching."""
    global _health_cache
    now = time.time()
    last_time, last_status = _health_cache

    if now - last_time < _CACHE_TTL_SECONDS:
        return last_status

    try:
        if storage.use_sqlite:
            conn = storage._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            status = "ok"
        else:
            conn = storage._get_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
            conn.close()
            status = "ok"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        status = "unhealthy"

    _health_cache = (now, status)
    return status
