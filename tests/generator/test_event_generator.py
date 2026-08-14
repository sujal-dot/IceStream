"""Unit tests for baseline event data generation."""

import datetime
from generator.data_generator import DataGenerator
from generator.event_schema import REQUIRED_FIELDS, CheckoutEvent


def test_data_generator_valid_event():
    gen = DataGenerator(seed=42)
    event = gen.generate_valid_event()

    # Verify all required fields exist
    for field_name in REQUIRED_FIELDS:
        assert field_name in event, f"Missing field {field_name} in event payload"
        assert event[field_name] is not None, f"Field {field_name} should not be None"

    # Verify deterministic fields for valid event
    assert event["event_type"] == "checkout"
    assert event["currency"] == "INR"
    assert event["country"] == "IN"
    assert event["source"] == "web"
    assert event["source_version"] == "v1"

    # Verify calculation: amount = quantity * unit_price
    expected_amount = round(event["quantity"] * event["unit_price"], 2)
    assert abs(event["amount"] - expected_amount) < 0.001


def test_event_id_uniqueness():
    gen = DataGenerator(seed=100)
    event_ids = set()
    for _ in range(1000):
        evt = gen.generate_valid_event()
        assert evt["event_id"] not in event_ids
        event_ids.add(evt["event_id"])
    assert len(event_ids) == 1000


def test_utc_timestamp_format():
    gen = DataGenerator(seed=42)
    evt = gen.generate_valid_event()
    time_str = evt["event_time"]

    # Verify ends with Z
    assert time_str.endswith("Z")

    # Verify standard ISO datetime parsing
    iso_part = time_str[:-1]
    parsed_dt = datetime.datetime.fromisoformat(iso_part)
    assert parsed_dt is not None


def test_reproducible_generation_with_seed():
    gen1 = DataGenerator(seed=999)
    evt1 = gen1.generate_valid_event()

    gen2 = DataGenerator(seed=999)
    evt2 = gen2.generate_valid_event()

    assert evt1["customer_id"] == evt2["customer_id"]
    assert evt1["product_id"] == evt2["product_id"]
    assert evt1["quantity"] == evt2["quantity"]
    assert evt1["amount"] == evt2["amount"]
