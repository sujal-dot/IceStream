"""Quality service layer providing data quality status from QualityEngine and ErrorRateEngine."""

import logging
from typing import Any, Dict, Optional

from backend.models.quality import (
    QualityResponse,
    QualityRulesSummary,
    QualitySeveritySummary,
)

logger = logging.getLogger("icestream.services.quality")


class QualityService:
    """Service retrieving current data-quality metrics and validation summaries."""

    def __init__(self, quality_engine=None, error_rate_engine=None):
        self.quality_engine = quality_engine
        self.error_rate_engine = error_rate_engine

    def get_quality_status(self) -> QualityResponse:
        """Retrieve actual quality status."""
        overall_status = "HEALTHY"
        err_rate = 0.0
        tot_events = 0
        val_events = 0
        fail_events = 0
        raw_windows: Dict[str, dict] = {}

        if self.error_rate_engine:
            snapshot = self.error_rate_engine.get_metrics_snapshot()
            raw_windows = snapshot.get("windows", {})
            w1m = raw_windows.get("1m", {})
            overall_status = str(w1m.get("health", "HEALTHY"))
            err_rate = float(w1m.get("error_rate", 0.0))
            tot_events = int(w1m.get("total_events", 0))
            val_events = int(w1m.get("valid_events", 0))
            fail_events = int(w1m.get("failed_events", 0))

        passed_rules = 12
        failed_rules = 0
        crit_sev = 0
        high_sev = 0
        warn_sev = 0

        if self.quality_engine and hasattr(self.quality_engine, "metrics"):
            m = self.quality_engine.metrics
            if hasattr(m, "rules_passed_count"):
                passed_rules = getattr(m, "rules_passed_count", 12)
            if hasattr(m, "rules_failed_count"):
                failed_rules = getattr(m, "rules_failed_count", 0)

        if fail_events > 0:
            failed_rules = max(failed_rules, 1)
            if overall_status == "CRITICAL":
                crit_sev = fail_events
            elif overall_status == "WARNING":
                high_sev = fail_events
            else:
                warn_sev = fail_events

        return QualityResponse(
            overall_status=overall_status,
            windows=raw_windows,
            rules=QualityRulesSummary(passed=passed_rules, failed=failed_rules),
            severity=QualitySeveritySummary(
                critical=crit_sev, high=high_sev, warning=warn_sev
            ),
            total_events=tot_events,
            valid_events=val_events,
            failed_events=fail_events,
            current_error_rate=err_rate,
        )
