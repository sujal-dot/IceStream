"""Integration tests for Day 7: Kafka streaming observability, performance consumer, and metrics."""

import time
import pytest
from generator.config import GeneratorConfig
from generator.event_generator import EventGeneratorEngine
from generator.producer import EventProducer
from scripts.kafka.performance_consumer import PerformanceConsumer


@pytest.fixture
def kafka_bootstrap():
    return "localhost:9092"


@pytest.fixture
def topic_name():
    return "checkout-events"


def test_producer_latency_and_metrics(kafka_bootstrap, topic_name):
    """Verify producer delivery acknowledgment tracking and latency metrics."""
    producer = EventProducer(bootstrap_servers=kafka_bootstrap, client_id="test-day7-producer")
    
    event_payload = {
        "event_id": "test-day7-evt-001",
        "event_type": "checkout",
        "event_time": "2026-08-17T10:00:00.000000Z",
        "customer_id": "cust-12345",
        "cart_id": "cart-67890",
        "currency": "USD",
        "total_amount": 149.99,
        "payment_method": "credit_card",
        "schema_version": "v1.0",
    }
    
    producer.send_event(topic=topic_name, event_payload=event_payload, is_corrupted=False)
    producer.flush(timeout=5.0)
    
    assert producer.generated_count >= 1
    assert producer.published_count >= 1
    assert producer.failed_count == 0
    
    stats = producer.get_latency_stats()
    assert "p50" in stats
    assert "p95" in stats
    assert "p99" in stats
    producer.close()


def test_performance_consumer_e2e_flow(kafka_bootstrap, topic_name):
    """Verify end-to-end flow from EventProducer to PerformanceConsumer."""
    group_id = "icestream-day7-test-consumer-group-1"
    
    # Initialize consumer first
    consumer = PerformanceConsumer(
        bootstrap_servers=kafka_bootstrap,
        topic=topic_name,
        group_id=group_id,
        quiet=True,
    )
    
    # Force partition assignment
    consumer.consumer.poll(timeout=0.2)
    
    config = GeneratorConfig(
        rate=500,
        error_rate=0.0,
        bootstrap_server=kafka_bootstrap,
        topic=topic_name,
        duration=2.0,
    )
    
    producer = EventProducer(bootstrap_servers=kafka_bootstrap, client_id="test-day7-gen")
    engine = EventGeneratorEngine(config=config, producer=producer)
    
    # Generate batch of clean events
    for _ in range(50):
        engine.produce_next_event()
    producer.flush(timeout=5.0)
    
    # Consume using PerformanceConsumer
    consumed = 0
    start = time.perf_counter()
    while time.perf_counter() - start < 3.0:
        msg = consumer.consumer.poll(timeout=0.1)
        if msg is not None and not msg.error():
            consumed += 1
            
    lag_info = consumer.query_consumer_lag()
    lat_stats = consumer.calculate_latency_stats()
    
    assert consumed > 0, "Consumer should receive published events"
    assert "total_lag" in lag_info
    assert "max_lag" in lag_info
    assert "p50" in lat_stats
    
    consumer.close()
    producer.close()


def test_fault_injection_stream_consumption(kafka_bootstrap, topic_name):
    """Verify stream with injected faults is consumed without consumer failure."""
    consumer = PerformanceConsumer(
        bootstrap_servers=kafka_bootstrap,
        topic=topic_name,
        group_id="icestream-day7-fault-test-group-2",
        quiet=True,
    )
    
    # Force partition assignment
    consumer.consumer.poll(timeout=0.2)
    
    config = GeneratorConfig(
        rate=500,
        null_rate=2.0,
        duplicate_rate=1.0,
        negative_rate=1.0,
        bootstrap_server=kafka_bootstrap,
        topic=topic_name,
        duration=2.0,
    )
    
    producer = EventProducer(bootstrap_servers=kafka_bootstrap, client_id="test-day7-fault-gen")
    engine = EventGeneratorEngine(config=config, producer=producer)
    
    # Generate events with faults
    for _ in range(50):
        engine.produce_next_event()
    producer.flush(timeout=5.0)
    
    assert producer.injected_error_count > 0, "Faults should be injected into stream"
    
    consumed = 0
    start = time.perf_counter()
    while time.perf_counter() - start < 3.0:
        msg = consumer.consumer.poll(timeout=0.1)
        if msg is not None and not msg.error():
            consumed += 1
            
    assert consumed > 0, "Consumer should receive corrupted events"
    consumer.close()
    producer.close()
