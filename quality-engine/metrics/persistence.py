"""Durable Metrics Persistence Adapter for Quality Engine.

Provides persistent storage for sliding window error rates, event counts, and
telemetry snapshot history using PostgreSQL/SQLite and optional Redis cache acceleration.
"""

from datetime import datetime, timezone
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional

QUALITY_ENGINE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PROJECT_ROOT = os.path.abspath(os.path.join(QUALITY_ENGINE_DIR, ".."))
if QUALITY_ENGINE_DIR not in sys.path:
    sys.path.insert(0, QUALITY_ENGINE_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.storage.db import StorageBackend, get_db_storage

logger = logging.getLogger("quality_engine.metrics.persistence")


class MetricsPersistenceStore:
    """Store for persisting rolling metrics to PostgreSQL/SQLite and Redis."""

    def __init__(
        self,
        db_storage: Optional[StorageBackend] = None,
        redis_url: Optional[str] = None,
    ) -> None:
        self.db = db_storage or get_db_storage()
        self.redis_client = None

        r_url = redis_url or os.getenv("REDIS_URL")
        if r_url:
            try:
                import redis
                self.redis_client = redis.Redis.from_url(r_url, decode_responses=True)
                self.redis_client.ping()
                logger.info("MetricsPersistenceStore initialized with Redis cache acceleration.")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis at {r_url}: {e}. Operating with DB storage.")
                self.redis_client = None

    def save_snapshot_point(self, service: str, point: Dict[str, Any], window_seconds: int = 60) -> None:
        """Persist a single error rate snapshot point."""
        try:
            timestamp = point.get("timestamp") or datetime.now(timezone.utc).isoformat()
            error_rate = float(point.get("error_rate", 0.0))
            error_rate_percent = float(point.get("error_rate_percent", round(error_rate * 100, 4)))
            total_events = int(point.get("total_events", 0))
            valid_events = int(point.get("valid_events", total_events - int(point.get("failed_events", 0))))
            failed_events = int(point.get("failed_events", 0))
            health = str(point.get("health", "HEALTHY"))

            # Save to PostgreSQL / SQLite database
            self.db.save_metrics_snapshot(
                service=service,
                window_seconds=window_seconds,
                timestamp=timestamp,
                total_events=total_events,
                valid_events=valid_events,
                failed_events=failed_events,
                error_rate=error_rate,
                error_rate_percent=error_rate_percent,
                health=health,
            )

            # Also cache to Redis if available
            if self.redis_client:
                key = f"icestream:metrics:history:{window_seconds}"
                self.redis_client.lpush(key, json.dumps(point))
                self.redis_client.ltrim(key, 0, 100)
        except Exception as e:
            logger.error(f"Failed to save metrics snapshot point: {e}")

    def load_snapshot_history(self, limit: int = 60) -> List[Dict[str, Any]]:
        """Load history points from Redis cache or database storage."""
        if self.redis_client:
            try:
                raw_items = self.redis_client.lrange("icestream:metrics:history:60", 0, limit - 1)
                if raw_items:
                    items = [json.loads(item) for item in reversed(raw_items)]
                    return items
            except Exception as e:
                logger.warning(f"Failed to load metrics from Redis: {e}")

        try:
            return self.db.get_metrics_snapshot_history(limit=limit)
        except Exception as e:
            logger.error(f"Failed to load snapshot history from DB: {e}")
            return []

    def save_event_counts(self, window_seconds: int, valid_events: int, failed_events: int) -> None:
        """Persist current window event counters."""
        try:
            self.db.save_window_event_counts(
                window_seconds=window_seconds,
                valid_events=valid_events,
                failed_events=failed_events,
            )
            if self.redis_client:
                self.redis_client.hset(
                    f"icestream:metrics:counts:{window_seconds}",
                    mapping={
                        "valid_events": valid_events,
                        "failed_events": failed_events,
                        "total_events": valid_events + failed_events,
                    },
                )
        except Exception as e:
            logger.error(f"Failed to save window event counts: {e}")

    def load_event_counts(self, window_seconds: int) -> Optional[Dict[str, Any]]:
        """Load persisted event counts for window hydration."""
        if self.redis_client:
            try:
                data = self.redis_client.hgetall(f"icestream:metrics:counts:{window_seconds}")
                if data and "valid_events" in data:
                    return {
                        "window_seconds": window_seconds,
                        "valid_events": int(data["valid_events"]),
                        "failed_events": int(data["failed_events"]),
                        "total_events": int(data.get("total_events", int(data["valid_events"]) + int(data["failed_events"]))),
                    }
            except Exception as e:
                logger.warning(f"Failed to load counts from Redis: {e}")

        try:
            return self.db.get_window_event_counts(window_seconds)
        except Exception as e:
            logger.error(f"Failed to load window event counts from DB: {e}")
            return None
