"""Unit tests for error injection capabilities."""

import datetime
from generator.config import GeneratorConfig
from generator.data_generator import DataGenerator
from generator.error_injector import ErrorInjector
from generator.event_generator import EventGeneratorEngine


def test_null_amount_injection():
    gen = DataGenerator(seed=1)
    valid_evt = gen.generate_valid_event()

    injector = ErrorInjector(seed=1)
    corrupted, err_type = injector.inject_error(valid_evt, target_error_type="null_amount")

    assert err_type == "null_amount"
    assert corrupted["amount"] is None
    # Ensure other fields remain intact
    assert corrupted["customer_id"] == valid_evt["customer_id"]


def test_null_customer_id_injection():
    gen = DataGenerator(seed=1)
    valid_evt = gen.generate_valid_event()

    injector = ErrorInjector(seed=1)
    corrupted, err_type = injector.inject_error(valid_evt, target_error_type="null_customer_id")

    assert err_type == "null_customer_id"
    assert corrupted["customer_id"] is None


def test_negative_amount_injection():
    gen = DataGenerator(seed=1)
    valid_evt = gen.generate_valid_event()

    injector = ErrorInjector(seed=1)
    corrupted, err_type = injector.inject_error(valid_evt, target_error_type="negative_amount")

    assert err_type == "negative_amount"
    assert isinstance(corrupted["amount"], float)
    assert corrupted["amount"] < 0


def test_duplicate_event_id_injection():
    injector = ErrorInjector(seed=1)
    injector.record_valid_event_id("evt_test_12345")

    gen = DataGenerator(seed=1)
    valid_evt = gen.generate_valid_event()
    assert valid_evt["event_id"] != "evt_test_12345"

    corrupted, err_type = injector.inject_error(valid_evt, target_error_type="duplicate_event_id")

    assert err_type == "duplicate_event_id"
    assert corrupted["event_id"] == "evt_test_12345"


def test_invalid_currency_injection():
    gen = DataGenerator(seed=1)
    valid_evt = gen.generate_valid_event()

    injector = ErrorInjector(seed=1)
    corrupted, err_type = injector.inject_error(valid_evt, target_error_type="invalid_currency")

    assert err_type == "invalid_currency"
    assert corrupted["currency"] in ["XXX", "INVALID", "USD_BAD"]


def test_missing_required_field_injection():
    gen = DataGenerator(seed=1)
    valid_evt = gen.generate_valid_event()

    injector = ErrorInjector(seed=1)
    corrupted, err_type = injector.inject_error(valid_evt, target_error_type="missing_required_field")

    assert err_type == "missing_required_field"
    # Verify exactly one field was removed
    assert len(corrupted) == len(valid_evt) - 1


def test_wrong_data_type_injection():
    gen = DataGenerator(seed=1)
    valid_evt = gen.generate_valid_event()

    injector = ErrorInjector(seed=1)
    corrupted, err_type = injector.inject_error(valid_evt, target_error_type="wrong_data_type")

    assert err_type == "wrong_data_type"
    # Check that either quantity or amount or unit_price is string
    is_type_corrupted = (
        isinstance(corrupted.get("quantity"), str)
        or isinstance(corrupted.get("amount"), str)
        or isinstance(corrupted.get("unit_price"), str)
    )
    assert is_type_corrupted


def test_future_timestamp_injection():
    gen = DataGenerator(seed=1)
    valid_evt = gen.generate_valid_event()

    injector = ErrorInjector(seed=1)
    corrupted, err_type = injector.inject_error(valid_evt, target_error_type="future_timestamp")

    assert err_type == "future_timestamp"
    time_str = corrupted["event_time"]
    assert time_str.endswith("Z")

    parsed_dt = datetime.datetime.fromisoformat(time_str[:-1]).replace(tzinfo=datetime.timezone.utc)
    now_utc = datetime.datetime.now(datetime.timezone.utc)

    # Future timestamp should be > 30 minutes in the future
    time_diff = (parsed_dt - now_utc).total_seconds()
    assert time_diff > 1800


def test_error_rate_proportion():
    # 5% error rate across 10,000 events should produce ~500 errors (+/- 100)
    config = GeneratorConfig(error_rate=5.0, seed=42)
    engine = EventGeneratorEngine(config=config)

    total_events = 10000
    corrupted_count = 0

    for _ in range(total_events):
        _, is_corrupted, _ = engine.generate_single_event()
        if is_corrupted:
            corrupted_count += 1

    observed_pct = (corrupted_count / total_events) * 100.0
    assert 4.0 <= observed_pct <= 6.0
