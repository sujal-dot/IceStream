"""
Tests for Centralized Circuit Breaker and Error Rate State.

Validates:
- Multi-instance / cross-process state synchronization (split-brain elimination)
- State machine durability across process restarts / re-instantiations
- Timeout transition persistence in central database storage
- Cross-process rolling error rate aggregation and health classification
- Recovery probe and result propagation across instances
"""

from datetime import datetime, timezone
import pytest

from rules.clock import FixedClock
from circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
)
from metrics.error_rate import ErrorRateEngine, ErrorRateConfig, HealthStatus
from metrics.persistence import MetricsPersistenceStore
from storage.db import StorageBackend


@pytest.fixture
def shared_storage():
    """Isolated SQLite database backend for multi-instance testing."""
    return StorageBackend(use_sqlite=True)


def test_multi_instance_synchronization(shared_storage):
    """Verify state transitions in worker instance immediately sync to API instance."""
    pipeline_id = "test-sync-pipe"

    worker_breaker = CircuitBreaker(
        storage=shared_storage,
        pipeline_id=pipeline_id,
        sync_interval_seconds=0.0,  # sync on every check
    )
    api_breaker = CircuitBreaker(
        storage=shared_storage,
        pipeline_id=pipeline_id,
        sync_interval_seconds=0.0,
    )

    # Initial state for both is CLOSED
    assert worker_breaker.current_state() == CircuitState.CLOSED
    assert api_breaker.current_state() == CircuitState.CLOSED
    assert api_breaker.can_process() is True

    # Worker encounters error rate spike and trips to OPEN
    worker_breaker.evaluate(0.05)  # 5% > 2% threshold
    assert worker_breaker.current_state() == CircuitState.OPEN
    assert worker_breaker.can_process() is False

    # API instance checks state - must immediately observe OPEN from central storage
    assert api_breaker.current_state() == CircuitState.OPEN
    assert api_breaker.can_process() is False
    assert api_breaker.get_status().error_rate == 0.05


def test_process_restart_state_durability(shared_storage):
    """Verify that a newly instantiated breaker hydrates its state, counters, and history from DB."""
    pipeline_id = "test-restart-pipe"

    breaker_v1 = CircuitBreaker(
        storage=shared_storage,
        pipeline_id=pipeline_id,
        sync_interval_seconds=0.0,
    )

    # Transition to OPEN
    breaker_v1.transition_to(
        CircuitState.OPEN,
        reason="incident_triggered_trip",
        error_rate=0.08,
        metadata={"incident_id": "INC-999"},
    )
    assert breaker_v1.current_state() == CircuitState.OPEN
    assert breaker_v1._open_total_count == 1

    # Destroy breaker_v1 (simulating process death / container restart)
    del breaker_v1

    # Instantiate fresh breaker pointing to same DB
    breaker_v2 = CircuitBreaker(
        storage=shared_storage,
        pipeline_id=pipeline_id,
        sync_interval_seconds=0.0,
    )

    # Must hydrate in OPEN state with lineage intact
    assert breaker_v2.current_state() == CircuitState.OPEN
    assert breaker_v2.can_process() is False
    assert breaker_v2._open_total_count == 1
    assert breaker_v2.get_status().error_rate == 0.08

    # History must be preserved
    history = breaker_v2.get_history()
    assert len(history) >= 1
    assert history[-1]["from"] == "CLOSED"
    assert history[-1]["to"] == "OPEN"
    assert history[-1]["reason"] == "incident_triggered_trip"


def test_timeout_transition_persisted_to_storage(shared_storage):
    """Verify automatic recovery timeout transition persists to central storage."""
    pipeline_id = "test-timeout-pipe"
    clock = FixedClock("2026-09-21T10:00:00Z")
    config = CircuitBreakerConfig(recovery_timeout_seconds=30.0)

    breaker = CircuitBreaker(
        config=config,
        clock=clock,
        storage=shared_storage,
        pipeline_id=pipeline_id,
        sync_interval_seconds=0.0,
    )

    breaker.evaluate(0.04)
    assert breaker.current_state() == CircuitState.OPEN

    # Advance clock past timeout
    clock.advance(35)

    # Calling current_state triggers timeout transition to HALF_OPEN
    assert breaker.current_state() == CircuitState.HALF_OPEN

    # Verify central database storage contains HALF_OPEN
    db_state = shared_storage.get_circuit_breaker_state(pipeline_id)
    assert db_state is not None
    assert db_state["state"] == "HALF_OPEN"

    # Second instance immediately observes HALF_OPEN
    breaker_peer = CircuitBreaker(
        config=config,
        clock=clock,
        storage=shared_storage,
        pipeline_id=pipeline_id,
        sync_interval_seconds=0.0,
    )
    assert breaker_peer.current_state() == CircuitState.HALF_OPEN
    assert breaker_peer.can_probe() is True


def test_recovery_result_propagation(shared_storage):
    """Verify probe success in one instance restores CLOSED state across all instances."""
    pipeline_id = "test-recovery-pipe"
    clock = FixedClock("2026-09-21T10:00:00Z")
    config = CircuitBreakerConfig(recovery_timeout_seconds=10.0, error_threshold=0.02)

    inst_a = CircuitBreaker(
        config=config,
        clock=clock,
        storage=shared_storage,
        pipeline_id=pipeline_id,
        sync_interval_seconds=0.0,
    )
    inst_b = CircuitBreaker(
        config=config,
        clock=clock,
        storage=shared_storage,
        pipeline_id=pipeline_id,
        sync_interval_seconds=0.0,
    )

    inst_a.evaluate(0.05)
    clock.advance(15)

    # Both are now in HALF_OPEN
    assert inst_a.current_state() == CircuitState.HALF_OPEN
    assert inst_b.current_state() == CircuitState.HALF_OPEN

    # Instance A acquires probe and succeeds
    assert inst_a.begin_recovery_probe() is True
    inst_a.record_recovery_result(error_rate=0.005)  # 0.5% < 2% threshold

    assert inst_a.current_state() == CircuitState.CLOSED
    assert inst_a.can_process() is True

    # Instance B synchronizes
    assert inst_b.current_state() == CircuitState.CLOSED
    assert inst_b.can_process() is True


def test_error_rate_engine_cross_process_counts(shared_storage):
    """Verify ErrorRateEngine flushes event counts and read-only instance aggregates correctly."""
    persistence = MetricsPersistenceStore(db_storage=shared_storage)

    # Worker engine: Ingests 20 events (18 valid, 2 invalid)
    worker_engine = ErrorRateEngine(
        config=ErrorRateConfig(healthy_max=0.01, warning_max=0.02),
        persistence=persistence,
        flush_interval_events=5,  # flush every 5 events
    )

    for i in range(18):
        worker_engine.record_event_outcome(is_valid=True)
    for i in range(2):
        worker_engine.record_event_outcome(is_valid=False)

    # Ensure flushed to storage
    worker_engine.flush_event_counts()

    # Web backend engine: Clean in-memory instance pointing to same storage
    api_engine = ErrorRateEngine(
        config=ErrorRateConfig(healthy_max=0.01, warning_max=0.02),
        persistence=persistence,
    )

    # Local in-memory events are 0, should fallback to persisted storage counts
    metrics = api_engine.calculate(window_seconds=60)

    assert metrics.total_events == 20
    assert metrics.valid_events == 18
    assert metrics.failed_events == 2
    assert metrics.error_rate == 0.10
    assert metrics.error_rate_percent == 10.0
    assert metrics.health_status == HealthStatus.CRITICAL
