"""
Tests for Stream Quality Validator and Quarantine Routing.

Validates:
- Valid event evaluation & error rate tracking
- Invalid event detection & quarantine persistence routing
- Malformed JSON handling & quarantine
- Automated circuit breaker tripping when error rate exceeds threshold (2%)
- Pipeline state transition to CIRCUIT_OPEN and incident creation
- Batch processing and buffer flushing
"""

from datetime import datetime, timezone
import json
from unittest.mock import MagicMock
import pytest

from streaming.stream_validator import StreamQualityValidator, ValidationOutcome
from rules.engine import QualityEngine
from rules.registry import create_default_registry
from quarantine.router import QuarantineRouter
from quarantine.writer import QuarantineWriter
from metrics.error_rate import ErrorRateEngine, ErrorRateConfig
from circuit_breaker.breaker import CircuitBreaker
from circuit_breaker.config import CircuitBreakerConfig
from circuit_breaker.state import CircuitState
from remediation.state_manager import PipelineState, PipelineStateManager
from remediation.controller import RemediationController
from storage.db import StorageBackend


def make_valid_event(event_id="evt_stream_001", amount=100.0):
    """Construct an event that satisfies all default quality rules."""
    now_iso = datetime.now(timezone.utc).isoformat()
    return {
        "event_id": event_id,
        "order_id": f"ORD_{event_id}",
        "customer_id": "CUST_999",
        "session_id": "SESS_999",
        "product_id": "PROD_100",
        "amount": float(amount),
        "currency": "USD",
        "payment_method": "CREDIT_CARD",
        "payment_status": "SUCCESS",
        "device": "desktop",
        "country": "US",
        "source_version": "v1",
        "event_time": now_iso,
        "ingestion_time": now_iso,
    }


def make_invalid_event(event_id="evt_bad_001", amount=-50.0):
    """Construct an event with an invalid amount violating AmountPositiveRule."""
    evt = make_valid_event(event_id=event_id, amount=amount)
    return evt


@pytest.fixture
def test_setup():
    """Build isolated in-memory instances of all streaming components."""
    storage = StorageBackend(use_sqlite=True)
    state_mgr = PipelineStateManager(pipeline_id="test-pipeline", storage=storage)
    breaker = CircuitBreaker(
        config=CircuitBreakerConfig(
            error_threshold=0.02,  # 2% threshold
            recovery_timeout_seconds=30.0,
        )
    )
    controller = RemediationController(
        pipeline_id="test-pipeline",
        state_manager=state_mgr,
        circuit_breaker=breaker,
        storage=storage,
    )
    quarantine_writer = MagicMock(spec=QuarantineWriter)
    quarantine_writer.write_record.return_value = True
    quarantine_writer.flush.return_value = (1, True)

    quarantine_router = QuarantineRouter(writer=quarantine_writer)
    quality_engine = QualityEngine(registry=create_default_registry())
    error_rate_engine = ErrorRateEngine(
        config=ErrorRateConfig(healthy_max=0.01, warning_max=0.02),
        windows=[60],
    )

    validator = StreamQualityValidator(
        quality_engine=quality_engine,
        quarantine_router=quarantine_router,
        error_rate_engine=error_rate_engine,
        circuit_breaker=breaker,
        state_manager=state_mgr,
        remediation_controller=controller,
        pipeline_id="test-pipeline",
        auto_quarantine=True,
        auto_trip_circuit=True,
    )

    return {
        "validator": validator,
        "storage": storage,
        "state_mgr": state_mgr,
        "breaker": breaker,
        "controller": controller,
        "quarantine_writer": quarantine_writer,
        "error_rate_engine": error_rate_engine,
    }


def test_valid_event_processing(test_setup):
    """Verify clean event returns valid outcome, updates metrics, and does not quarantine."""
    validator = test_setup["validator"]
    writer = test_setup["quarantine_writer"]
    engine = test_setup["error_rate_engine"]

    valid_event = make_valid_event("evt_clean_001", amount=250.0)

    outcome = validator.validate_event(valid_event)

    assert outcome.is_valid is True
    assert outcome.event_id == "evt_clean_001"
    assert outcome.quarantine_result is None
    assert outcome.circuit_state == "CLOSED"

    # Verify error rate engine recorded valid event
    metrics = engine.calculate(60)
    assert metrics.total_events == 1
    assert metrics.valid_events == 1
    assert metrics.failed_events == 0
    assert metrics.error_rate == 0.0

    # Verify quarantine writer was never called
    writer.write_record.assert_not_called()


def test_invalid_event_quarantined(test_setup):
    """Verify invalid event is caught, routed to quarantine, and persisted."""
    validator = test_setup["validator"]
    writer = test_setup["quarantine_writer"]
    engine = test_setup["error_rate_engine"]

    invalid_event = make_invalid_event("evt_bad_001", amount=-50.0)

    outcome = validator.validate_event(invalid_event)

    assert outcome.is_valid is False
    assert outcome.event_id == "evt_bad_001"
    assert outcome.quarantine_result is not None
    assert outcome.quarantine_result.success is True
    assert outcome.quarantine_result.quarantine_record is not None
    assert outcome.quarantine_result.quarantine_record.error_code == "INVALID_AMOUNT"

    # Verify quarantine writer was called
    writer.write_record.assert_called_once()

    # Verify error rate recorded failure
    metrics = engine.calculate(60)
    assert metrics.total_events == 1
    assert metrics.failed_events == 1
    assert metrics.error_rate == 1.0


def test_malformed_json_handling(test_setup):
    """Verify corrupt/unparseable JSON string is handled safely and quarantined."""
    validator = test_setup["validator"]
    writer = test_setup["quarantine_writer"]

    corrupt_payload = b"{not_valid_json: 1234, corrupted..."

    outcome = validator.validate_event(corrupt_payload)

    assert outcome.is_valid is False
    assert outcome.quarantine_result is not None
    assert outcome.quarantine_result.success is True
    assert outcome.quarantine_result.quarantine_record.error_code == "MALFORMED_JSON"
    writer.write_record.assert_called_once()


def test_circuit_breaker_trips_on_error_spike(test_setup):
    """Verify circuit breaker trips to OPEN and creates incident when error rate > 2%."""
    validator = test_setup["validator"]
    breaker = test_setup["breaker"]
    state_mgr = test_setup["state_mgr"]
    storage = test_setup["storage"]

    # Initial state should be CLOSED & RUNNING
    assert breaker.state == CircuitState.CLOSED
    assert state_mgr.current_state == PipelineState.RUNNING

    # Inject 5 valid events
    for i in range(5):
        validator.validate_event(make_valid_event(f"evt_clean_{i}", amount=100.0))

    assert breaker.state == CircuitState.CLOSED

    # Now inject invalid events to push error rate > 2% (e.g. 5 bad events -> 5 / 10 = 50% > 2%)
    for i in range(5):
        validator.validate_event(make_invalid_event(f"evt_spike_{i}", amount=-10.0))

    # Circuit breaker must now be OPEN
    assert breaker.state == CircuitState.OPEN
    # Pipeline state must be transitioned to CIRCUIT_OPEN
    assert state_mgr.current_state == PipelineState.CIRCUIT_OPEN

    # An incident must have been opened
    active_incident = storage.find_active_incident("test-pipeline")
    assert active_incident is not None
    assert active_incident["trigger"] == "STREAM_QUALITY_DEGRADATION"
    assert active_incident["status"] == "OPEN"
    assert active_incident["error_rate"] > 0.02


def test_batch_processing_and_flush(test_setup):
    """Verify process_batch processes multiple events and invokes flush on writer."""
    validator = test_setup["validator"]
    writer = test_setup["quarantine_writer"]

    events = [
        make_valid_event("evt_batch_1", amount=100.0),
        make_invalid_event("evt_batch_2", amount=-1.0),
    ]

    outcomes = validator.process_batch(events, flush_quarantine=True)

    assert len(outcomes) == 2
    assert outcomes[0].is_valid is True
    assert outcomes[1].is_valid is False
    writer.flush.assert_called_once()


def test_consume_stream_loop(test_setup):
    """Verify consume_stream processes messages and respects max_messages limit."""
    validator = test_setup["validator"]

    class MockMessage:
        def __init__(self, value_dict):
            self._val = json.dumps(value_dict).encode("utf-8")

        def value(self):
            return self._val

        def error(self):
            return None

    class MockConsumer:
        def __init__(self, messages):
            self._messages = list(messages)

        def poll(self, timeout=1.0):
            if self._messages:
                return self._messages.pop(0)
            return None

    mock_events = [
        MockMessage(make_valid_event(f"evt_consumer_{i}", amount=50.0))
        for i in range(3)
    ]

    consumer = MockConsumer(mock_events)
    processed = validator.consume_stream(consumer, max_messages=3)

    assert processed == 3
