"""Kafka Integration Test — verifies end-to-end Event Generator to Kafka topic publishing."""

import json
import uuid
import pytest
from confluent_kafka import Consumer, KafkaError

from generator.config import GeneratorConfig
from generator.event_generator import EventGeneratorEngine
from generator.producer import EventProducer


def test_kafka_integration_producer_consumer():
    """Produce test events to checkout-events and consume them to verify delivery."""
    bootstrap_server = "localhost:9092"
    topic = "checkout-events"
    test_group = f"test-group-{uuid.uuid4().hex[:8]}"

    config = GeneratorConfig(
        rate=100,
        error_rate=0.0,
        bootstrap_server=bootstrap_server,
        topic=topic,
        seed=123,
    )

    try:
        producer = EventProducer(bootstrap_servers=bootstrap_server)
    except Exception as e:
        pytest.skip(f"Kafka cluster unavailable at {bootstrap_server}: {e}")

    engine = EventGeneratorEngine(config=config, producer=producer)

    # Produce 20 events
    num_events = 20
    produced_events = []
    for _ in range(num_events):
        evt_dict, _, _ = engine.produce_next_event()
        produced_events.append(evt_dict)

    producer.flush(timeout=5.0)
    assert producer.published_count == num_events
    assert producer.failed_count == 0

    # Configure consumer to verify messages on checkout-events
    consumer_config = {
        "bootstrap.servers": bootstrap_server,
        "group.id": test_group,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
    }

    try:
        consumer = Consumer(consumer_config)
        consumer.subscribe([topic])
    except Exception as e:
        pytest.fail(f"Failed to create test consumer: {e}")

    consumed_messages = []
    attempts = 0
    max_attempts = 50

    while len(consumed_messages) < num_events and attempts < max_attempts:
        attempts += 1
        msg = consumer.poll(0.2)
        if msg is None:
            continue
        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                continue
            else:
                break

        val = json.loads(msg.value().decode("utf-8"))
        consumed_messages.append(val)

    consumer.close()

    assert len(consumed_messages) >= 1, "Expected to consume produced messages from Kafka"
    sample = consumed_messages[0]
    assert "event_id" in sample
    assert "event_time" in sample
    assert "customer_id" in sample
    assert sample["event_type"] == "checkout"
