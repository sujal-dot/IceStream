"""
Integration Test Suite for Day 11 Real-Time Kafka -> Flink -> Iceberg Bronze Pipeline
"""

import time
import urllib.request
import json
import pytest

from iceberg.config.catalog import get_catalog
from generator.config import GeneratorConfig
from generator.event_generator import EventGeneratorEngine
from generator.producer import EventProducer


def test_kafka_reachability():
    """Verify Kafka broker is reachable."""
    producer = EventProducer(bootstrap_servers="localhost:9092")
    assert producer.producer is not None, "Kafka producer should be initialized"
    producer.close()


def test_iceberg_catalog_reachability():
    """Verify Iceberg REST catalog is reachable."""
    catalog = get_catalog()
    namespaces = [ns[0] for ns in catalog.list_namespaces() if ns]
    assert "bronze" in namespaces, "Bronze namespace should exist in Iceberg catalog"
    table = catalog.load_table("bronze.checkout_events")
    assert table is not None, "bronze.checkout_events table should exist"


def test_flink_job_running():
    """Verify Flink streaming Bronze pipeline job is running."""
    req = urllib.request.urlopen("http://localhost:8081/jobs/overview", timeout=5)
    data = json.loads(req.read().decode("utf-8"))
    jobs = data.get("jobs", [])
    active_jobs = [j for j in jobs if j.get("state") == "RUNNING"]
    assert len(active_jobs) > 0, "At least one active Flink streaming job should be running"


def test_streaming_ingestion_growth():
    """Publish a batch of events to Kafka and verify count increases in Iceberg Bronze table."""
    catalog = get_catalog()
    table = catalog.load_table("bronze.checkout_events")

    table.refresh()
    initial_count = len(table.scan().to_arrow())

    # Publish synthetic events
    config = GeneratorConfig(rate=200, duration=2, bootstrap_server="localhost:9092")
    producer = EventProducer(bootstrap_servers="localhost:9092")
    engine = EventGeneratorEngine(config=config, producer=producer)

    for _ in range(100):
        event_dict, _, _ = engine.generate_single_event()
        producer.send_event("checkout-events", event_dict)
    producer.flush()
    producer.close()

    # Poll table count up to 35 seconds to allow for Flink checkpoint commit
    max_wait = 35
    poll_interval = 3
    elapsed = 0
    final_count = initial_count

    while elapsed < max_wait:
        time.sleep(poll_interval)
        elapsed += poll_interval
        table.refresh()
        final_count = len(table.scan().to_arrow())
        if final_count > initial_count:
            break

    assert final_count > initial_count, f"Bronze table record count should increase (initial: {initial_count}, final: {final_count})"
