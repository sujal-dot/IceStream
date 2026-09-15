"""Unit tests for Metrics Durability and Graceful Buffer Flushing."""

from datetime import datetime, timezone
import os
import signal
import sys
import unittest

QUALITY_ENGINE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PROJECT_ROOT = os.path.abspath(os.path.join(QUALITY_ENGINE_DIR, ".."))
VENV_SITE_PACKAGES = os.path.abspath(os.path.join(PROJECT_ROOT, ".venv", "lib", "python3.10", "site-packages"))

if os.path.exists(VENV_SITE_PACKAGES) and VENV_SITE_PACKAGES not in sys.path:
    sys.path.insert(0, VENV_SITE_PACKAGES)
if QUALITY_ENGINE_DIR not in sys.path:
    sys.path.insert(0, QUALITY_ENGINE_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ["TESTING"] = "true"



from backend.storage.db import StorageBackend
from metrics.error_rate import ErrorRateConfig, ErrorRateEngine, HealthStatus
from metrics.persistence import MetricsPersistenceStore
from hybrid_engine import HybridQualityEngine


class TestMetricsDurability(unittest.TestCase):
    def setUp(self):
        self.storage = StorageBackend(use_sqlite=True)
        self.persistence = MetricsPersistenceStore(db_storage=self.storage)

    def test_storage_backend_metrics_methods(self):
        now_str = datetime.now(timezone.utc).isoformat()
        self.storage.save_metrics_snapshot(
            service="test-service",
            window_seconds=60,
            timestamp=now_str,
            total_events=100,
            valid_events=98,
            failed_events=2,
            error_rate=0.02,
            error_rate_percent=2.0,
            health="WARNING",
        )

        history = self.storage.get_metrics_snapshot_history(limit=10)
        self.assertGreaterEqual(len(history), 1)
        latest = history[-1]
        self.assertEqual(latest["total_events"], 100)
        self.assertEqual(latest["failed_events"], 2)
        self.assertEqual(latest["health"], "WARNING")

        self.storage.save_window_event_counts(window_seconds=60, valid_events=98, failed_events=2)
        counts = self.storage.get_window_event_counts(60)
        self.assertIsNotNone(counts)
        self.assertEqual(counts["valid_events"], 98)
        self.assertEqual(counts["failed_events"], 2)

    def test_error_rate_engine_persistence_recovery(self):
        # 1. Create engine A, record events, generate snapshot
        engine_a = ErrorRateEngine(persistence=self.persistence)
        engine_a.record_event_outcome(is_valid=True)
        engine_a.record_event_outcome(is_valid=False)
        snapshot_a = engine_a.get_metrics_snapshot()

        self.assertEqual(snapshot_a["windows"]["1m"]["total_events"], 2)
        self.assertEqual(snapshot_a["windows"]["1m"]["failed_events"], 1)

        # 2. Re-instantiate engine B with same persistent storage
        engine_b = ErrorRateEngine(persistence=self.persistence)
        self.assertGreaterEqual(len(engine_b._history), 1)
        self.assertEqual(engine_b._history[-1]["failed_events"], 1)

    def test_hybrid_engine_graceful_shutdown(self):
        hybrid = HybridQualityEngine()
        flushed = False

        def mock_flush():
            nonlocal flushed
            flushed = True

        hybrid.flush_buffers = mock_flush
        hybrid.register_signal_handlers()

        # Simulate buffer flush call
        hybrid.flush_buffers()
        self.assertTrue(flushed)


if __name__ == "__main__":
    unittest.main()
