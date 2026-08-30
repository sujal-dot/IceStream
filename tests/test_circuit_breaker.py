"""Comprehensive Test Suite for Day 20 Circuit Breaker State Machine."""

import concurrent.futures
import time
import pytest
from fastapi.testclient import TestClient

from rules.clock import FixedClock
from circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    InvalidStateTransitionError,
)
from backend.app import create_app, get_circuit_breaker, get_error_rate_engine


# ---------------------------------------------------------------------------
# 1. Initial State & Threshold Semantics Tests
# ---------------------------------------------------------------------------

def test_initial_closed_state():
    """Verify initial state is CLOSED with processing allowed."""
    breaker = CircuitBreaker()
    assert breaker.current_state() == CircuitState.CLOSED
    assert breaker.can_process() is True
    assert breaker.can_probe() is False


def test_warning_rate_remains_closed():
    """Verify error rate at WARNING level (1.5%) keeps circuit CLOSED."""
    breaker = CircuitBreaker()
    state = breaker.evaluate(0.015)
    assert state == CircuitState.CLOSED
    assert breaker.can_process() is True


def test_exact_2_percent_remains_closed():
    """Verify exact 2.00% boundary error rate keeps circuit CLOSED."""
    breaker = CircuitBreaker()
    state = breaker.evaluate(0.0200)
    assert state == CircuitState.CLOSED
    assert breaker.can_process() is True


def test_above_2_percent_opens_circuit():
    """Verify error rate strictly above 2% (2.01%) opens circuit."""
    breaker = CircuitBreaker()
    state = breaker.evaluate(0.0201)
    assert state == CircuitState.OPEN
    assert breaker.can_process() is False
    assert breaker.can_probe() is False


# ---------------------------------------------------------------------------
# 2. OPEN State Stability & Recovery Timeout Tests
# ---------------------------------------------------------------------------

def test_open_stability_before_timeout():
    """Verify OPEN state remains OPEN even if error rate drops before timeout."""
    clock = FixedClock("2026-08-30T10:00:00Z")
    breaker = CircuitBreaker(clock=clock)

    breaker.evaluate(0.025)
    assert breaker.current_state() == CircuitState.OPEN

    # Advance 30s (less than 60s timeout)
    clock.advance(30)
    # Re-evaluate with zero error rate
    state = breaker.evaluate(0.000)
    assert state == CircuitState.OPEN
    assert breaker.can_process() is False


def test_open_timeout_transition_to_half_open():
    """Verify exact 60s timeout transitions OPEN -> HALF_OPEN."""
    clock = FixedClock("2026-08-30T10:00:00Z")
    config = CircuitBreakerConfig(recovery_timeout_seconds=60.0)
    breaker = CircuitBreaker(config=config, clock=clock)

    breaker.evaluate(0.025)
    assert breaker.current_state() == CircuitState.OPEN

    # At 59s: still OPEN
    clock.advance(59)
    assert breaker.current_state() == CircuitState.OPEN
    assert breaker.can_process() is False
    assert breaker.can_probe() is False

    # At 60s: transitions to HALF_OPEN automatically
    clock.advance(1)
    assert breaker.current_state() == CircuitState.HALF_OPEN
    assert breaker.can_process() is False
    assert breaker.can_probe() is True


# ---------------------------------------------------------------------------
# 3. HALF_OPEN Probe & Recovery Pass / Fail Tests
# ---------------------------------------------------------------------------

def test_half_open_success_recovery():
    """Verify successful recovery probe (rate <= 2%) transitions HALF_OPEN -> CLOSED."""
    clock = FixedClock("2026-08-30T10:00:00Z")
    breaker = CircuitBreaker(clock=clock)

    breaker.evaluate(0.025)
    clock.advance(60)
    assert breaker.current_state() == CircuitState.HALF_OPEN

    # Initiate probe
    assert breaker.begin_recovery_probe() is True
    assert breaker.can_probe() is False  # Active probe prevents second probe

    # Probe passes
    res_state = breaker.record_recovery_result(error_rate=0.005)
    assert res_state == CircuitState.CLOSED
    assert breaker.current_state() == CircuitState.CLOSED
    assert breaker.can_process() is True


def test_half_open_failure_recovery():
    """Verify failed recovery probe (rate > 2%) transitions HALF_OPEN -> OPEN."""
    clock = FixedClock("2026-08-30T10:00:00Z")
    breaker = CircuitBreaker(clock=clock)

    breaker.evaluate(0.025)
    clock.advance(60)
    assert breaker.current_state() == CircuitState.HALF_OPEN

    # Initiate probe
    assert breaker.begin_recovery_probe() is True

    # Probe fails
    res_state = breaker.record_recovery_result(error_rate=0.035)
    assert res_state == CircuitState.OPEN
    assert breaker.current_state() == CircuitState.OPEN
    assert breaker.can_process() is False

    status = breaker.get_status()
    assert status.failed_recoveries == 1
    assert status.successful_recoveries == 0


def test_half_open_single_probe_concurrency():
    """Verify only ONE recovery probe is permitted concurrently in HALF_OPEN."""
    clock = FixedClock("2026-08-30T10:00:00Z")
    breaker = CircuitBreaker(clock=clock)

    breaker.evaluate(0.025)
    clock.advance(60)
    assert breaker.current_state() == CircuitState.HALF_OPEN

    first_caller = breaker.begin_recovery_probe()
    second_caller = breaker.begin_recovery_probe()

    assert first_caller is True
    assert second_caller is False


def test_recovery_probe_denied_when_closed_or_open():
    """Verify begin_recovery_probe is denied when in CLOSED or OPEN state."""
    breaker = CircuitBreaker()
    # In CLOSED state
    assert breaker.begin_recovery_probe() is False

    # In OPEN state
    breaker.evaluate(0.025)
    assert breaker.begin_recovery_probe() is False


# ---------------------------------------------------------------------------
# 4. State Transition Protection & History Bounding
# ---------------------------------------------------------------------------

def test_invalid_state_transitions():
    """Verify direct invalid transitions (CLOSED -> HALF_OPEN, OPEN -> CLOSED) are rejected."""
    breaker = CircuitBreaker()

    # CLOSED -> HALF_OPEN directly
    with pytest.raises(InvalidStateTransitionError):
        breaker.transition_to(CircuitState.HALF_OPEN)

    # Move to OPEN
    breaker.evaluate(0.025)

    # OPEN -> CLOSED directly
    with pytest.raises(InvalidStateTransitionError):
        breaker.transition_to(CircuitState.CLOSED)


def test_transition_history_and_bounding():
    """Verify transition history is recorded accurately and bounded by max_history."""
    clock = FixedClock("2026-08-30T10:00:00Z")
    config = CircuitBreakerConfig(max_history=3)
    breaker = CircuitBreaker(config=config, clock=clock)

    # Generate 4 transitions
    # 1. CLOSED -> OPEN
    breaker.evaluate(0.025)
    # 2. OPEN -> HALF_OPEN
    clock.advance(60)
    breaker.current_state()
    # 3. HALF_OPEN -> CLOSED
    breaker.begin_recovery_probe()
    breaker.record_recovery_result(0.005)
    # 4. CLOSED -> OPEN
    breaker.evaluate(0.030)

    history = breaker.get_history()
    assert len(history) == 3  # Bounded to max_history=3
    assert history[-1]["from"] == "CLOSED"
    assert history[-1]["to"] == "OPEN"
    assert history[-1]["reason"] == "error_rate_above_threshold"


# ---------------------------------------------------------------------------
# 5. Configuration Validation & Disabled Mode Tests
# ---------------------------------------------------------------------------

def test_invalid_config_validation():
    """Verify configuration validation rejects out-of-bound parameters."""
    with pytest.raises(ValueError):
        CircuitBreakerConfig(error_threshold=-1.0)

    with pytest.raises(ValueError):
        CircuitBreakerConfig(error_threshold=2.0)

    with pytest.raises(ValueError):
        CircuitBreakerConfig(recovery_timeout_seconds=-10.0)

    with pytest.raises(ValueError):
        CircuitBreakerConfig(max_history=0)

    with pytest.raises(ValueError):
        CircuitBreakerConfig(half_open_success_threshold=0)


def test_disabled_circuit_breaker():
    """Verify disabled circuit breaker remains CLOSED and processing allowed."""
    config = CircuitBreakerConfig(enabled=False)
    breaker = CircuitBreaker(config=config)

    assert breaker.current_state() == CircuitState.CLOSED
    assert breaker.can_process() is True

    # High error rate does not open disabled breaker
    state = breaker.evaluate(0.50)
    assert state == CircuitState.CLOSED
    assert breaker.can_process() is True
    assert breaker.begin_recovery_probe() is False


# ---------------------------------------------------------------------------
# 6. Concurrency Tests
# ---------------------------------------------------------------------------

def test_concurrent_recovery_probes():
    """Verify thread safety when multiple tasks attempt begin_recovery_probe concurrently."""
    clock = FixedClock("2026-08-30T10:00:00Z")
    breaker = CircuitBreaker(clock=clock)

    breaker.evaluate(0.025)
    clock.advance(60)
    assert breaker.current_state() == CircuitState.HALF_OPEN

    results = []
    num_threads = 20

    def attempt_probe():
        return breaker.begin_recovery_probe()

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(attempt_probe) for _ in range(num_threads)]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    # Exactly ONE attempt must succeed
    assert results.count(True) == 1
    assert results.count(False) == num_threads - 1


# ---------------------------------------------------------------------------
# 7. FastAPI Backend API Endpoint Integration Tests
# ---------------------------------------------------------------------------

def test_backend_circuit_breaker_endpoint():
    """Test read-only GET /circuit-breaker API endpoint."""
    clock = FixedClock("2026-08-30T10:00:00Z")
    breaker = CircuitBreaker(clock=clock)
    breaker.evaluate(0.025)

    app = create_app(breaker=breaker)
    client = TestClient(app)

    response = client.get("/circuit-breaker")
    assert response.status_code == 200

    data = response.json()
    assert data["state"] == "OPEN"
    assert data["enabled"] is True
    assert data["can_process"] is False
    assert data["can_probe"] is False
    assert data["threshold"] == 0.02
    assert "opened_at" in data
    assert "last_state_change" in data


def test_backend_metrics_integration():
    """Test GET /metrics endpoint includes circuit breaker state without breaking Day 19 contract."""
    clock = FixedClock("2026-08-30T10:00:00Z")
    breaker = CircuitBreaker(clock=clock)

    app = create_app(breaker=breaker)
    client = TestClient(app)

    response = client.get("/metrics")
    assert response.status_code == 200

    data = response.json()
    assert "windows" in data
    assert "1m" in data["windows"]
    assert "5m" in data["windows"]
    assert "circuit_breaker" in data
    assert data["circuit_breaker"]["state"] == "CLOSED"
    assert data["circuit_breaker"]["can_process"] is True


# ---------------------------------------------------------------------------
# 8. Performance Benchmark Test
# ---------------------------------------------------------------------------

def test_performance_benchmark():
    """Benchmark 100,000 error rate evaluations for low overhead execution."""
    breaker = CircuitBreaker()
    evaluations = 100_000

    start_time = time.perf_counter()
    for i in range(evaluations):
        # Alternate safe values below threshold
        rate = 0.005 if i % 2 == 0 else 0.010
        breaker.evaluate(rate)
    end_time = time.perf_counter()

    elapsed = end_time - start_time
    ops_per_sec = evaluations / elapsed

    assert ops_per_sec > 50_000, f"Circuit breaker evaluation throughput too low: {ops_per_sec:.0f} ops/sec"


# ---------------------------------------------------------------------------
# 9. Complete Demonstration Sequence Test
# ---------------------------------------------------------------------------

def test_complete_demonstration_sequence():
    """Verify the full 5-step state transition demonstration required by prompt."""
    clock = FixedClock("2026-08-30T10:00:00Z")
    breaker = CircuitBreaker(clock=clock)

    # STEP 1: CLOSED state
    assert breaker.current_state() == CircuitState.CLOSED
    breaker.evaluate(0.005)
    assert breaker.current_state() == CircuitState.CLOSED
    assert breaker.can_process() is True

    # STEP 2: Error rate > 2% -> OPEN
    breaker.evaluate(0.021)
    assert breaker.current_state() == CircuitState.OPEN
    assert breaker.can_process() is False

    # STEP 3: Recovery timeout (60s) -> HALF_OPEN
    clock.advance(60)
    assert breaker.current_state() == CircuitState.HALF_OPEN
    assert breaker.can_process() is False
    assert breaker.can_probe() is True

    # STEP 4 (Success): Recovery probe error_rate = 0.5% -> CLOSED
    assert breaker.begin_recovery_probe() is True
    res = breaker.record_recovery_result(0.005)
    assert res == CircuitState.CLOSED
    assert breaker.can_process() is True

    # STEP 5 (Failure): Repeat -> OPEN -> HALF_OPEN -> Recovery probe failure (3.0%) -> OPEN
    breaker.evaluate(0.025)
    assert breaker.current_state() == CircuitState.OPEN
    clock.advance(60)
    assert breaker.current_state() == CircuitState.HALF_OPEN

    assert breaker.begin_recovery_probe() is True
    res_fail = breaker.record_recovery_result(0.030)
    assert res_fail == CircuitState.OPEN
    assert breaker.can_process() is False

    status = breaker.get_status()
    assert status.recovery_attempts == 2
    assert status.successful_recoveries == 1
    assert status.failed_recoveries == 1
