"""High-throughput Kafka Producer wrapper using confluent-kafka."""

import json
import logging
import threading
from typing import Any, Dict, Optional

from confluent_kafka import KafkaException, Producer

logger = logging.getLogger(__name__)


class EventProducer:
    """High-throughput Kafka producer with delivery callback tracking."""

    def __init__(
        self,
        bootstrap_servers: str = "localhost:9092",
        client_id: str = "icestream-generator",
        extra_config: Optional[Dict[str, Any]] = None,
    ):
        config = {
            "bootstrap.servers": bootstrap_servers,
            "client.id": client_id,
            "linger.ms": 5,
            "batch.num.messages": 10000,
            "queue.buffering.max.messages": 100000,
            "acks": 1,
            "compression.type": "snappy",
        }
        if extra_config:
            config.update(extra_config)

        self.producer = Producer(config)

        # Thread-safe counters
        self._lock = threading.Lock()
        self.generated_count = 0
        self.published_count = 0
        self.failed_count = 0
        self.valid_count = 0
        self.injected_error_count = 0

    def _delivery_callback(self, err, msg):
        """Callback executed on Kafka message delivery acknowledgment."""
        with self._lock:
            if err is not None:
                self.failed_count += 1
                logger.error(f"Kafka message delivery failed: {err}")
            else:
                self.published_count += 1

    def send_event(
        self, topic: str, event_payload: Dict[str, Any], is_corrupted: bool = False
    ):
        """Serialize and produce event to Kafka topic asynchronously."""
        with self._lock:
            self.generated_count += 1
            if is_corrupted:
                self.injected_error_count += 1
            else:
                self.valid_count += 1

        payload_bytes = json.dumps(event_payload).encode("utf-8")
        key = str(event_payload.get("customer_id", ""))

        try:
            self.producer.produce(
                topic=topic,
                value=payload_bytes,
                key=key if key else None,
                on_delivery=self._delivery_callback,
            )
            # Service delivery events without blocking
            self.producer.poll(0)
        except BufferError:
            # Buffer is full, flush synchronously briefly and retry once
            self.producer.flush(1.0)
            self.producer.produce(
                topic=topic,
                value=payload_bytes,
                key=key if key else None,
                on_delivery=self._delivery_callback,
            )
            self.producer.poll(0)

    def poll(self, timeout: float = 0):
        """Serve delivery callbacks."""
        self.producer.poll(timeout)

    def flush(self, timeout: float = 5.0) -> int:
        """Flush outstanding messages."""
        return self.producer.flush(timeout)

    def close(self, timeout: float = 5.0):
        """Flush remaining messages and close producer."""
        self.flush(timeout)
