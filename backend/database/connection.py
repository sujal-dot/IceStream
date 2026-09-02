"""Database connection management and health checks."""

import logging
from typing import Dict
from backend.storage.db import StorageBackend, get_db_storage

logger = logging.getLogger("icestream.database.connection")


def check_db_health(storage: StorageBackend) -> str:
    """Perform lightweight health check on database connection."""
    try:
        if storage.use_sqlite:
            conn = storage._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            return "ok"
        else:
            conn = storage._get_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
            conn.close()
            return "ok"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return "unhealthy"
