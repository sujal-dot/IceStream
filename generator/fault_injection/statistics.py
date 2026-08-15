"""Thread-safe statistics tracking for IceStream Fault Injection Engine."""

import threading
from typing import Any, Dict, Optional
from generator.fault_injection.modes import FaultMode


class FaultStatistics:
    """Tracks runtime fault injection statistics and observed error rates."""

    def __init__(self, configured_rates: Optional[Dict[str, float]] = None):
        self._lock = threading.Lock()
        self.configured_rates: Dict[str, float] = (
            dict(configured_rates) if configured_rates else {}
        )

        self.total_events: int = 0
        self.clean_events: int = 0
        self.faulty_events: int = 0

        self.fault_counts: Dict[str, int] = {
            FaultMode.NULL.value: 0,
            FaultMode.DUPLICATE.value: 0,
            FaultMode.NEGATIVE.value: 0,
            FaultMode.INVALID_ENUM.value: 0,
            FaultMode.SCHEMA_DRIFT.value: 0,
            FaultMode.TYPE_CHANGE.value: 0,
            FaultMode.TIMESTAMP_DRIFT.value: 0,
        }

    def record_event(self, fault_mode: Optional[str] = None):
        """Record an event generation, clean or faulty."""
        with self._lock:
            self.total_events += 1
            if fault_mode is None:
                self.clean_events += 1
            else:
                self.faulty_events += 1
                if fault_mode in self.fault_counts:
                    self.fault_counts[fault_mode] += 1
                else:
                    self.fault_counts[fault_mode] = 1

    def get_stats(self) -> Dict[str, Any]:
        """Return a snapshot dictionary of current statistics."""
        with self._lock:
            total = self.total_events
            stats = {
                "total_events": total,
                "clean_events": self.clean_events,
                "faulty_events": self.faulty_events,
                "overall_faulty_pct": (self.faulty_events / total * 100.0) if total > 0 else 0.0,
                "fault_counts": dict(self.fault_counts),
                "observed_rates": {},
                "configured_rates": dict(self.configured_rates),
            }

            for mode, count in self.fault_counts.items():
                stats["observed_rates"][mode] = (count / total * 100.0) if total > 0 else 0.0

            return stats

    def format_summary_report(self) -> str:
        """Format a human-readable fault statistics report."""
        stats = self.get_stats()
        total = stats["total_events"]

        lines = [
            "=" * 50,
            "Fault Injection Statistics",
            "=" * 50,
            f"Total events:       {total:>10}",
            f"Clean events:       {stats['clean_events']:>10}",
            f"Faulty events:      {stats['faulty_events']:>10}  ({stats['overall_faulty_pct']:.3f}%)",
            "",
        ]

        display_names = [
            (FaultMode.NULL.value, "NULL"),
            (FaultMode.DUPLICATE.value, "DUPLICATE"),
            (FaultMode.NEGATIVE.value, "NEGATIVE"),
            (FaultMode.INVALID_ENUM.value, "INVALID_ENUM"),
            (FaultMode.SCHEMA_DRIFT.value, "Schema Drift"),
            (FaultMode.TYPE_CHANGE.value, "Type Change"),
            (FaultMode.TIMESTAMP_DRIFT.value, "Timestamp Drift"),
        ]

        for mode_key, label in display_names:
            count = stats["fault_counts"].get(mode_key, 0)
            obs_pct = stats["observed_rates"].get(mode_key, 0.0)
            cfg_pct = self.configured_rates.get(mode_key, 0.0)
            lines.append(
                f"{label:<18}: {count:>8}  ({obs_pct:.3f}% observed, {cfg_pct:.2f}% configured)"
            )

        lines.append("=" * 50)
        return "\n".join(lines)
