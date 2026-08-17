"""High-throughput Kafka Producer wrapper using confluent-kafka."""

import json
import logging
import threading
import time
from typing import Any, Dict, List, Optional

import numpy as np
from confluent_kafka import KafkaException, Producer

from generator.metrics import GeneratorMetricsTracker

logger = logging.getLogger(__name__)


class EventProducer:
    """High-throughput Kafka producer with delivery callback tracking and latency metrics."""

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

        # Thread-safe counters and latency reservoir
        self._lock = threading.Lock()
        self.generated_count = 0
        self.published_count = 0
        self.failed_count = 0
        self.valid_count = 0
        self.injected_error_count = 0
        self._latency_samples: List[float] = []
        self._max_samples = 10000

    def _delivery_callback(self, err, msg, send_time: float):
        """Callback executed on Kafka message delivery acknowledgment."""
        latency_sec = time.perf_counter() - send_time
        with self._lock:
            if err is not None:
                self.failed_count += 1
                GeneratorMetricsTracker.record_failure()
                logger.error(f"Kafka message delivery failed: {err}")
            else:
                self.published_count += 1
                if len(self._latency_samples) >= self._max_samples:
                    # Maintain bounded sample size
                    self._latency_samples.pop(0)
                self._latency_samples.append(latency_sec)
                GeneratorMetricsTracker.record_published(latency_sec)

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
            GeneratorMetricsTracker.record_generated()

        payload_bytes = json.dumps(event_payload).encode("utf-8")
        key = str(event_payload.get("customer_id", ""))
        send_time = time.perf_counter()

        cb = lambda err, msg, st=send_time: self._delivery_callback(err, msg, st)

        try:
            self.producer.produce(
                topic=topic,
                value=payload_bytes,
                key=key if key else None,
                on_delivery=cb,
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
                on_delivery=cb,
            )
            self.producer.poll(0)

    def get_latency_stats(self) -> Dict[str, float]:
        """Calculate producer delivery latency statistics (p50, p95, p99, avg)."""
        with self._lock:
            if not self._latency_samples:
                return {"avg": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0}
            arr = np.array(self._latency_samples) * 1000.0  # Convert to ms
            return {
                "avg": float(np.mean(arr)),
                "p50": float(np.percentile(arr, 50)),
                "p95": float(np.percentile(arr, 95)),
                "p99": float(np.percentile(arr, 99)),
                "max": float(np.max(arr)),
            }

    def poll(self, timeout: float = 0):
        """Serve delivery callbacks."""
        self.producer.poll(timeout)

    def flush(self, timeout: float = 5.0) -> int:
        """Flush outstanding messages."""
        return self.producer.flush(timeout)

    def close(self, timeout: float = 5.0):
        """Flush remaining messages and close producer."""
        self.flush(timeout)

