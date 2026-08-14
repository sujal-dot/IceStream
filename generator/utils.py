"""Utility classes for rate limiting and throughput statistics calculation."""

import time
from typing import Dict, Any


class RateLimiter:
    """High-precision batch-based rate limiter to maintain target events/second."""

    def __init__(self, target_rate: int, batch_size: int = 50):
        self.target_rate = target_rate
        self.batch_size = max(1, min(batch_size, target_rate))
        self.batch_duration = self.batch_size / float(target_rate)
        self._batch_count = 0
        self._batch_start_time = time.perf_counter()

    def sleep_if_needed(self):
        """Paces execution per batch of events to maintain configured rate."""
        self._batch_count += 1
        if self._batch_count >= self.batch_size:
            now = time.perf_counter()
            elapsed = now - self._batch_start_time
            sleep_time = self.batch_duration - elapsed

            if sleep_time > 0:
                time.sleep(sleep_time)

            # Reset batch timer
            self._batch_count = 0
            self._batch_start_time = time.perf_counter()


class StatsTracker:
    """Tracks event counts and calculates current/average throughput rates."""

    def __init__(self):
        self.start_time = time.perf_counter()
        self.last_log_time = self.start_time
        self.last_generated_count = 0

    def get_stats(
        self,
        generated: int,
        published: int,
        failed: int,
        valid: int,
        injected_errors: int,
    ) -> Dict[str, Any]:
        """Compute current and cumulative statistics."""
        now = time.perf_counter()
        total_elapsed = max(0.001, now - self.start_time)
        interval_elapsed = max(0.001, now - self.last_log_time)

        interval_generated = generated - self.last_generated_count

        current_rate = interval_generated / interval_elapsed
        average_rate = generated / total_elapsed

        # Update window markers
        self.last_log_time = now
        self.last_generated_count = generated

        return {
            "elapsed_sec": total_elapsed,
            "generated": generated,
            "published": published,
            "failed": failed,
            "valid": valid,
            "injected_errors": injected_errors,
            "current_rate": current_rate,
            "average_rate": average_rate,
            "observed_error_pct": (
                (injected_errors / generated * 100.0) if generated > 0 else 0.0
            ),
        }

    def format_stats_header(self, config_info: Dict[str, Any]) -> str:
        """Format introductory header for CLI execution."""
        lines = [
            "=" * 50,
            "IceStream Event Generator",
            "=" * 50,
            f"Kafka Bootstrap : {config_info.get('bootstrap_server')}",
            f"Target Topic    : {config_info.get('topic')}",
            f"Target Rate     : {config_info.get('rate')} events/sec",
            f"Error Rate      : {config_info.get('error_rate')}%%",
            f"Error Types     : {', '.join(config_info.get('error_types', []))}",
            f"Random Seed     : {config_info.get('seed')}",
            "=" * 50,
            "Running...",
            "",
        ]
        return "\n".join(lines)

    def format_stats_log(self, stats: Dict[str, Any]) -> str:
        """Format periodic statistics line."""
        return (
            f"Elapsed: {stats['elapsed_sec']:.1f}s | "
            f"Generated: {stats['generated']} | "
            f"Published: {stats['published']} | "
            f"Errors Injected: {stats['injected_errors']} ({stats['observed_error_pct']:.2f}%) | "
            f"Publish Failures: {stats['failed']} | "
            f"Current Rate: {stats['current_rate']:.0f} ev/s | "
            f"Avg Rate: {stats['average_rate']:.0f} ev/s"
        )
