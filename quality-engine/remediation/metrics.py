"""Remediation Observability Metrics for IceStream.

Provides Prometheus counters, histograms, and state gauges for self-healing operations.
"""

from prometheus_client import Counter, Gauge, Histogram

# Remediation Counters & Histograms
REMEDIATION_ATTEMPTS_TOTAL = Counter(
    "icestream_remediation_attempts_total",
    "Total number of remediation attempts executed",
    labelnames=["pipeline_id", "stage", "status"],
)

REMEDIATION_SUCCESS_TOTAL = Counter(
    "icestream_remediation_success_total",
    "Total number of successful self-healing remediations",
    labelnames=["pipeline_id"],
)

REMEDIATION_FAILURE_TOTAL = Counter(
    "icestream_remediation_failure_total",
    "Total number of failed self-healing remediations",
    labelnames=["pipeline_id", "reason"],
)

REMEDIATION_RECOVERED_EVENTS_TOTAL = Counter(
    "icestream_remediation_recovered_events_total",
    "Total number of events successfully recovered and reprocessed",
    labelnames=["pipeline_id"],
)

REMEDIATION_DURATION_SECONDS = Histogram(
    "icestream_remediation_duration_seconds",
    "Duration of complete self-healing remediation workflow in seconds",
    labelnames=["pipeline_id"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

PIPELINE_STATE_GAUGE = Gauge(
    "icestream_pipeline_state",
    "Numeric status of pipeline state (0=RUNNING, 1=DEGRADED, 2=QUARANTINING, 3=CIRCUIT_OPEN, 4=REMEDIATING, 5=REFETCHING, 6=REPROCESSING, 7=VALIDATING, 8=RESUMING, 9=RECOVERY_FAILED, 10=RECOVERED)",
    labelnames=["pipeline_id", "state"],
)

STATE_NUMERIC_MAP = {
    "RUNNING": 0,
    "DEGRADED": 1,
    "QUARANTINING": 2,
    "CIRCUIT_OPEN": 3,
    "REMEDIATING": 4,
    "REFETCHING": 5,
    "REPROCESSING": 6,
    "VALIDATING": 7,
    "RESUMING": 8,
    "RECOVERY_FAILED": 9,
    "RECOVERED": 10,
}


def record_state_metric(pipeline_id: str, state_str: str):
    """Update PIPELINE_STATE_GAUGE for given state."""
    numeric_val = STATE_NUMERIC_MAP.get(state_str.upper(), -1)
    for st, val in STATE_NUMERIC_MAP.items():
        PIPELINE_STATE_GAUGE.labels(pipeline_id=pipeline_id, state=st.lower()).set(
            1 if st.upper() == state_str.upper() else 0
        )
