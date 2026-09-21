"""
Standalone Streaming Quality Validator Worker for IceStream.

Consumes events from Kafka, validates against the Quality Engine, routes failing
events to the Iceberg quarantine table, and manages the circuit breaker state.

Usage:
    python -m stream_worker --bootstrap-servers localhost:9092 --topic checkout-events
"""

import argparse
import logging
import os
import signal
import sys
import threading

# Ensure quality-engine root is in path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

BACKEND_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from streaming.stream_validator import StreamQualityValidator
from rules.engine import QualityEngine
from rules.registry import create_default_registry
from quarantine.router import QuarantineRouter
from quarantine.writer import QuarantineWriter
from metrics.error_rate import ErrorRateEngine
from circuit_breaker.breaker import CircuitBreaker
from remediation.state_manager import PipelineStateManager
from remediation.controller import RemediationController
from storage.db import get_db_storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("icestream.stream_worker")


def build_kafka_consumer(
    bootstrap_servers: str,
    group_id: str,
    topic: str,
    auto_offset_reset: str = "latest",
):
    """Construct Confluent Kafka consumer."""
    try:
        from confluent_kafka import Consumer
    except ImportError:
        logger.error("confluent-kafka package not installed. Install with: pip install confluent-kafka")
        sys.exit(1)

    conf = {
        "bootstrap.servers": bootstrap_servers,
        "group.id": group_id,
        "auto.offset.reset": auto_offset_reset,
        "enable.auto.commit": True,
    }
    consumer = Consumer(conf)
    consumer.subscribe([topic])
    logger.info("Subscribed to topic '%s' on %s (group: %s)", topic, bootstrap_servers, group_id)
    return consumer


def main():
    parser = argparse.ArgumentParser(description="IceStream Streaming Quality Engine Worker")
    parser.add_argument(
        "--bootstrap-servers",
        default=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
        help="Kafka bootstrap broker addresses (default: localhost:9092)",
    )
    parser.add_argument(
        "--topic",
        default=os.getenv("KAFKA_TOPIC", "checkout-events"),
        help="Kafka topic to consume events from (default: checkout-events)",
    )
    parser.add_argument(
        "--group-id",
        default=os.getenv("KAFKA_GROUP_ID", "icestream-stream-validator-group"),
        help="Kafka consumer group ID",
    )
    parser.add_argument(
        "--pipeline-id",
        default="icestream",
        help="Pipeline ID (default: icestream)",
    )
    parser.add_argument(
        "--auto-remediate",
        action="store_true",
        help="Automatically trigger self-healing workflow on circuit trip",
    )
    parser.add_argument(
        "--max-messages",
        type=int,
        default=None,
        help="Optional message limit before stopping",
    )
    args = parser.parse_args()

    stop_event = threading.Event()

    def handle_sig(sig, frame):
        logger.info("Signal %d received, requesting graceful shutdown...", sig)
        stop_event.set()

    signal.signal(signal.SIGINT, handle_sig)
    signal.signal(signal.SIGTERM, handle_sig)

    # Initialize components
    storage = get_db_storage()
    state_mgr = PipelineStateManager(pipeline_id=args.pipeline_id, storage=storage)
    breaker = CircuitBreaker(storage=storage, pipeline_id=args.pipeline_id)
    remediation_ctrl = RemediationController(
        pipeline_id=args.pipeline_id,
        state_manager=state_mgr,
        circuit_breaker=breaker,
        storage=storage,
    )
    quarantine_writer = QuarantineWriter()
    quarantine_router = QuarantineRouter(writer=quarantine_writer)
    quality_engine = QualityEngine(registry=create_default_registry())
    error_rate_engine = ErrorRateEngine()

    validator = StreamQualityValidator(
        quality_engine=quality_engine,
        quarantine_router=quarantine_router,
        error_rate_engine=error_rate_engine,
        circuit_breaker=breaker,
        state_manager=state_mgr,
        remediation_controller=remediation_ctrl,
        pipeline_id=args.pipeline_id,
        auto_quarantine=True,
        auto_trip_circuit=True,
        auto_remediate=args.auto_remediate,
    )

    consumer = build_kafka_consumer(
        bootstrap_servers=args.bootstrap_servers,
        group_id=args.group_id,
        topic=args.topic,
    )

    logger.info("Streaming quality validator worker initialized successfully. Entering poll loop.")
    processed = validator.consume_stream(consumer, stop_event=stop_event, max_messages=args.max_messages)
    logger.info("Streaming worker shutdown cleanly after processing %d events.", processed)


if __name__ == "__main__":
    main()
