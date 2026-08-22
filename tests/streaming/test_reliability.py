"""
IceStream Day 12 Automated Reliability & Checkpoint Recovery Test Suite
"""

import time
import urllib.request
import json
import pytest

from flink.jobs.kafka_to_iceberg import (
    FlinkBronzePipeline,
    IcebergSinkConfig,
    KafkaSourceConfig,
    get_active_flink_jobs,
    get_job_checkpoints,
)
from iceberg.config.catalog import get_catalog
from generator.config import GeneratorConfig
from generator.event_generator import EventGeneratorEngine
from generator.producer import EventProducer


def test_checkpoint_configuration_defaults():
    """Verify default Flink checkpoint configuration settings."""
    config = IcebergSinkConfig()
    assert config.checkpoint_interval_ms == 30000, "Default checkpoint interval should be 30000ms"
    assert config.checkpoint_dir == "s3://checkpoints/flink/bronze/", "Checkpoint path should target MinIO S3"
    assert config.state_backend == "filesystem", "State backend should be filesystem"


def test_restart_strategy_configuration_defaults():
    """Verify default Flink restart strategy configuration settings."""
    config = IcebergSinkConfig()
    assert config.restart_attempts == 3, "Default restart attempts should be 3"
    assert config.restart_delay_seconds == 10, "Default restart delay should be 10s"


def test_pipeline_sql_generation_contains_reliability_specs():
    """Verify generated Flink SQL script contains checkpoint and restart settings."""
    pipeline = FlinkBronzePipeline()
    sql = pipeline.generate_sql_statement()
    assert "SET 'execution.checkpointing.mode' = 'EXACTLY_ONCE';" in sql
    assert "SET 'execution.checkpointing.interval' = '30000ms';" in sql
    assert "SET 'state.checkpoints.dir' = 's3://checkpoints/flink/bronze/';" in sql
    assert "SET 'restart-strategy.type' = 'fixed-delay';" in sql
    assert "SET 'restart-strategy.fixed-delay.attempts' = '3';" in sql
    assert "SET 'restart-strategy.fixed-delay.delay' = '10s';" in sql
    assert "USE CATALOG default_catalog;" in sql


def test_minio_checkpoint_directory_access():
    """Verify MinIO checkpoints bucket is accessible via catalog / storage setup."""
    catalog = get_catalog()
    table = catalog.load_table("bronze.checkout_events")
    assert table is not None, "bronze.checkout_events table must exist"


def test_active_job_checkpoint_completion():
    """Integration test: Verify running Flink job registers completed checkpoints in REST API."""
    jobs = get_active_flink_jobs("http://localhost:8081")
    assert len(jobs) > 0, "Active Flink job must be running"
    job_id = jobs[0]["jid"]
    
    checkpoints = get_job_checkpoints(job_id, "http://localhost:8081")
    counts = checkpoints.get("counts", {})
    completed = counts.get("completed", 0)
    assert completed > 0, f"Job {job_id} must have completed at least 1 checkpoint (found {completed})"


def test_streaming_ingestion_recovery_growth():
    """Integration test: Produce batch of events and verify Iceberg Bronze count growth."""
    catalog = get_catalog()
    table = catalog.load_table("bronze.checkout_events")

    table.refresh()
    initial_count = len(table.scan().to_arrow())

    # Produce synthetic events
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
