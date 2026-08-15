"""Comprehensive unit tests for IceStream Fault Injection Engine."""

import datetime
import pytest

from generator.config import GeneratorConfig, parse_args
from generator.data_generator import DataGenerator
from generator.fault_injection.engine import FaultInjectionEngine
from generator.fault_injection.modes import FaultMode, VALID_PAYMENT_METHODS, VALID_PAYMENT_STATUSES


def test_null_fault():
    data_gen = DataGenerator(seed=42)
    valid_evt = data_gen.generate_valid_event()

    engine = FaultInjectionEngine(
        rates={FaultMode.NULL.value: 100.0},
        seed=42,
    )

    mutated, is_faulty, mode = engine.process_event(valid_evt, target_fault_mode=FaultMode.NULL.value)

    assert is_faulty is True
    assert mode == FaultMode.NULL.value

    # Exactly one field from target list should be null
    nullable_fields = [
        "customer_id", "session_id", "order_id", "product_id",
        "amount", "currency", "payment_method", "payment_status"
    ]
    null_fields = [f for f in nullable_fields if mutated.get(f) is None]
    assert len(null_fields) == 1
    # Check that event wasn't completely emptied
    assert mutated["event_id"] is not None


def test_duplicate_fault():
    data_gen = DataGenerator(seed=42)
    evt1 = data_gen.generate_valid_event()
    evt2 = data_gen.generate_valid_event()

    engine = FaultInjectionEngine(seed=42)
    # Record evt1 into history
    engine.record_clean_event(evt1)

    mutated, is_faulty, mode = engine.process_event(evt2, target_fault_mode=FaultMode.DUPLICATE.value)

    assert is_faulty is True
    assert mode == FaultMode.DUPLICATE.value
    # Mutated event should reuse evt1's identity/event_id
    assert mutated["event_id"] == evt1["event_id"]


def test_negative_fault():
    data_gen = DataGenerator(seed=42)
    valid_evt = data_gen.generate_valid_event()

    engine = FaultInjectionEngine(seed=42)
    mutated, is_faulty, mode = engine.process_event(valid_evt, target_fault_mode=FaultMode.NEGATIVE.value)

    assert is_faulty is True
    assert mode == FaultMode.NEGATIVE.value
    # Either amount, unit_price, or quantity must be negative
    has_negative = (
        (isinstance(mutated.get("amount"), (int, float)) and mutated["amount"] < 0)
        or (isinstance(mutated.get("unit_price"), (int, float)) and mutated["unit_price"] < 0)
        or (isinstance(mutated.get("quantity"), (int, float)) and mutated["quantity"] < 0)
    )
    assert has_negative is True


def test_invalid_enum_fault():
    data_gen = DataGenerator(seed=42)
    valid_evt = data_gen.generate_valid_event()

    engine = FaultInjectionEngine(seed=42)
    mutated, is_faulty, mode = engine.process_event(valid_evt, target_fault_mode=FaultMode.INVALID_ENUM.value)

    assert is_faulty is True
    assert mode == FaultMode.INVALID_ENUM.value
    # Either payment_method or payment_status is invalid enum
    is_invalid_method = mutated["payment_method"] not in VALID_PAYMENT_METHODS
    is_invalid_status = mutated["payment_status"] not in VALID_PAYMENT_STATUSES
    assert is_invalid_method or is_invalid_status


def test_schema_drift_add_field():
    data_gen = DataGenerator(seed=42)
    valid_evt = data_gen.generate_valid_event()

    engine = FaultInjectionEngine(
        schema_drift_types=["ADD_FIELD"],
        seed=42,
    )
    mutated, is_faulty, mode = engine.process_event(valid_evt, target_fault_mode=FaultMode.SCHEMA_DRIFT.value)

    assert is_faulty is True
    assert mode == FaultMode.SCHEMA_DRIFT.value
    assert "customer_segment" in mutated
    assert mutated["source_version"] == "v2"
    # Ensure no artificial fault_type attribute was added
    assert "fault_type" not in mutated


def test_schema_drift_remove_field():
    data_gen = DataGenerator(seed=42)
    valid_evt = data_gen.generate_valid_event()

    engine = FaultInjectionEngine(
        schema_drift_types=["REMOVE_FIELD"],
        seed=42,
    )
    mutated, is_faulty, mode = engine.process_event(valid_evt, target_fault_mode=FaultMode.SCHEMA_DRIFT.value)

    assert is_faulty is True
    assert mode == FaultMode.SCHEMA_DRIFT.value
    # A candidate field should have been removed
    removed = any(f not in mutated for f in ["payment_status", "device", "country"])
    assert removed is True
    assert "fault_type" not in mutated


def test_schema_drift_rename_field():
    data_gen = DataGenerator(seed=42)
    valid_evt = data_gen.generate_valid_event()

    engine = FaultInjectionEngine(
        schema_drift_types=["RENAME_FIELD"],
        seed=42,
    )
    mutated, is_faulty, mode = engine.process_event(valid_evt, target_fault_mode=FaultMode.SCHEMA_DRIFT.value)

    assert is_faulty is True
    assert mode == FaultMode.SCHEMA_DRIFT.value
    # Either customer_id renamed to client_id or order_id renamed to purchase_order_id
    renamed = ("client_id" in mutated and "customer_id" not in mutated) or (
        "purchase_order_id" in mutated and "order_id" not in mutated
    )
    assert renamed is True
    assert "fault_type" not in mutated


def test_type_change_fault():
    data_gen = DataGenerator(seed=42)
    valid_evt = data_gen.generate_valid_event()

    engine = FaultInjectionEngine(seed=42)
    mutated, is_faulty, mode = engine.process_event(valid_evt, target_fault_mode=FaultMode.TYPE_CHANGE.value)

    assert is_faulty is True
    assert mode == FaultMode.TYPE_CHANGE.value
    # Check type changes
    type_changed = (
        isinstance(mutated.get("quantity"), str)
        or isinstance(mutated.get("amount"), str)
        or isinstance(mutated.get("customer_id"), int)
    )
    assert type_changed is True


def test_timestamp_drift_fault():
    data_gen = DataGenerator(seed=42)
    valid_evt = data_gen.generate_valid_event()

    engine = FaultInjectionEngine(seed=42)
    mutated, is_faulty, mode = engine.process_event(valid_evt, target_fault_mode=FaultMode.TIMESTAMP_DRIFT.value)

    assert is_faulty is True
    assert mode == FaultMode.TIMESTAMP_DRIFT.value

    time_str = mutated["event_time"]
    assert time_str.endswith("Z")
    parsed_dt = datetime.datetime.fromisoformat(time_str[:-1]).replace(tzinfo=datetime.timezone.utc)
    now_utc = datetime.datetime.now(datetime.timezone.utc)

    # Difference between parsed_dt and now should be significant (> 10 minutes offset)
    diff_sec = abs((parsed_dt - now_utc).total_seconds())
    assert diff_sec > 600


def test_fault_rate_parsing():
    args = [
        "--rate", "1000",
        "--null-rate", "1.0",
        "--duplicate-rate", "0.5",
        "--negative-rate", "0.5",
        "--invalid-enum-rate", "0.25",
        "--schema-drift-rate", "0.0",
        "--type-change-rate", "0.25",
        "--timestamp-drift-rate", "0.5",
    ]
    config = parse_args(args)
    assert config.null_rate == 1.0
    assert config.duplicate_rate == 0.5
    assert config.negative_rate == 0.5
    assert config.invalid_enum_rate == 0.25
    assert config.schema_drift_rate == 0.0
    assert config.type_change_rate == 0.25
    assert config.timestamp_drift_rate == 0.5

    rates_map = config.get_fault_mode_rates()
    assert rates_map[FaultMode.NULL.value] == 1.0
    assert rates_map[FaultMode.DUPLICATE.value] == 0.5


def test_fault_mode_validation():
    args = ["--fault-modes", "NULL,DUPLICATE,INVALID_MODE_X"]
    with pytest.raises(ValueError, match="Unsupported fault modes"):
        parse_args(args)


def test_conflicting_cli_options():
    args = ["--error-rate", "1.0", "--null-rate", "1.0"]
    with pytest.raises(ValueError, match="--error-rate cannot be combined with individual fault rates"):
        parse_args(args)


def test_single_fault_per_event():
    # If rates sum to > 100%, each event should still receive at most ONE fault type
    rates = {
        FaultMode.NULL.value: 100.0,
        FaultMode.NEGATIVE.value: 100.0,
    }
    engine = FaultInjectionEngine(rates=rates, seed=123)
    data_gen = DataGenerator(seed=123)

    for _ in range(50):
        evt = data_gen.generate_valid_event()
        mutated, is_faulty, mode = engine.process_event(evt)
        assert is_faulty is True
        assert mode in [FaultMode.NULL.value, FaultMode.NEGATIVE.value]


def test_fault_statistics():
    rates = {
        FaultMode.NULL.value: 10.0,
        FaultMode.NEGATIVE.value: 5.0,
    }
    engine = FaultInjectionEngine(rates=rates, seed=42)
    data_gen = DataGenerator(seed=42)

    total = 200
    for _ in range(total):
        evt = data_gen.generate_valid_event()
        engine.process_event(evt)

    stats = engine.statistics.get_stats()
    assert stats["total_events"] == total
    assert stats["clean_events"] + stats["faulty_events"] == total
    assert stats["fault_counts"][FaultMode.NULL.value] > 0
    assert stats["fault_counts"][FaultMode.NEGATIVE.value] > 0

    report = engine.statistics.format_summary_report()
    assert "Fault Injection Statistics" in report
    assert "NULL" in report
    assert "NEGATIVE" in report


def test_fault_rate_accuracy():
    # Verify that a 5% null rate across 10,000 events yields ~5% (within +/- 1.0% tolerance)
    rates = {FaultMode.NULL.value: 5.0}
    engine = FaultInjectionEngine(rates=rates, seed=42)
    data_gen = DataGenerator(seed=42)

    total_events = 10000
    for _ in range(total_events):
        evt = data_gen.generate_valid_event()
        engine.process_event(evt)

    stats = engine.statistics.get_stats()
    obs_pct = stats["observed_rates"][FaultMode.NULL.value]
    assert 4.0 <= obs_pct <= 6.0
