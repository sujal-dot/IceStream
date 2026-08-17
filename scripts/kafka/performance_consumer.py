#!/usr/bin/env python3
"""Dedicated High-Performance Kafka Benchmark Consumer & Observability Exporter for IceStream.

Group ID: icestream-day7-performance-consumer
Target Topic: checkout-events
"""

import argparse
import datetime
import json
import logging
import signal
import sys
import time
from typing import Any, Dict, List, Optional

import numpy as np
from confluent_kafka import Consumer, KafkaError, KafkaException, TopicPartition
from prometheus_client import Counter, Gauge, Histogram, start_http_server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("performance_consumer")

# Prometheus Metrics Definitions for Consumer
CONSUMER_EVENTS_TOTAL = Counter(
    "icestream_consumer_events_total",
    "Total number of events consumed by the benchmark consumer",
)

CONSUMER_EVENTS_PER_SECOND = Gauge(
    "icestream_consumer_events_per_second",
    "Current consumer processing rate in events per second",
)

EVENT_LATENCY_SECONDS = Histogram(
    "icestream_event_latency_seconds",
    "End-to-end event latency from generation timestamp to consumer receipt (seconds)",
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

CONSUMER_LAG = Gauge(
    "icestream_consumer_lag",
    "Kafka consumer lag per partition",
    labelnames=["topic", "partition", "consumer_group"],
)

CONSUMER_LAG_TOTAL = Gauge(
    "icestream_consumer_lag_total",
    "Total consumer lag across all partitions",
)

CONSUMER_LAG_MAX = Gauge(
    "icestream_consumer_lag_max",
    "Maximum consumer lag across partitions",
)

_RUNNING = True


def _signal_handler(signum, frame):
    global _RUNNING
    logger.info("Signal received. Shutting down benchmark consumer...")
    _RUNNING = False


def parse_event_timestamp(payload: Dict[str, Any]) -> Optional[datetime.datetime]:
    """Extract and parse event timestamp from message payload.
    
    Supports ISO format strings or epoch numbers.
    """
    ts_val = payload.get("event_time") or payload.get("timestamp")
    if not ts_val:
        return None

    if isinstance(ts_val, (int, float)):
        # Epoch seconds or milliseconds
        if ts_val > 1e11:  # milliseconds
            ts_val /= 1000.0
        return datetime.datetime.fromtimestamp(ts_val, tz=datetime.timezone.utc)

    if isinstance(ts_val, str):
        # ISO string parsing
        try:
            # Replace Z with +00:00 for datetime.fromisoformat compatibility
            clean_ts = ts_val.replace("Z", "+00:00")
            dt = datetime.datetime.fromisoformat(clean_ts)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            return dt
        except Exception:
            return None

    return None


class PerformanceConsumer:
    """Dedicated benchmark consumer for measuring stream throughput, latency, and lag."""

    def __init__(
        self,
        bootstrap_servers: str = "localhost:9092",
        topic: str = "checkout-events",
        group_id: str = "icestream-day7-performance-consumer",
        delay_ms: float = 0.0,
        metrics_port: int = 8001,
        quiet: bool = False,
    ):
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.group_id = group_id
        self.delay_ms = delay_ms
        self.metrics_port = metrics_port
        self.quiet = quiet

        conf = {
            "bootstrap.servers": self.bootstrap_servers,
            "group.id": self.group_id,
            "auto.offset.reset": "latest",
            "enable.auto.commit": True,
            "auto.commit.interval.ms": 1000,
            "fetch.min.bytes": 1,
            "fetch.wait.max.ms": 100,
        }

        self.consumer = Consumer(conf)
        self.consumer.subscribe([self.topic])

        self.consumed_count = 0
        self.latency_samples: List[float] = []  # in milliseconds
        self.max_samples = 10000

        self.start_time = time.perf_counter()
        self.last_log_time = time.perf_counter()
        self.interval_consumed = 0

        self._start_metrics_server()

    def _start_metrics_server(self):
        try:
            start_http_server(self.metrics_port)
            logger.info(f"Consumer Prometheus metrics server active on port {self.metrics_port}")
        except Exception as e:
            logger.debug(f"Consumer metrics server port {self.metrics_port} already in use or error: {e}")

    def query_consumer_lag(self) -> Dict[str, Any]:
        """Query real Kafka offsets and return partition lag metrics dictionary."""
        lag_per_partition: Dict[int, int] = {}
        total_lag = 0
        max_lag = 0

        try:
            # Retrieve metadata for partitions
            metadata = self.consumer.list_topics(self.topic, timeout=2.0)
            if not metadata or self.topic not in metadata.topics:
                return {"total_lag": 0, "max_lag": 0, "partition_lag": {}}

            partitions = metadata.topics[self.topic].partitions
            tp_list = [TopicPartition(self.topic, p_id) for p_id in partitions.keys()]

            # Fetch committed offsets for this group
            committed_tps = self.consumer.committed(tp_list, timeout=2.0)
            committed_map = {tp.partition: tp.offset for tp in committed_tps}

            for p_id in partitions.keys():
                low, high = self.consumer.get_watermark_offsets(
                    TopicPartition(self.topic, p_id), timeout=2.0, cached=False
                )
                committed_offset = committed_map.get(p_id, -1)
                
                if committed_offset < 0:
                    # If position / committed not available yet, default to 0 lag
                    partition_lag = 0
                else:
                    partition_lag = max(0, high - committed_offset)

                lag_per_partition[p_id] = partition_lag
                total_lag += partition_lag
                max_lag = max(max_lag, partition_lag)

                CONSUMER_LAG.labels(
                    topic=self.topic,
                    partition=str(p_id),
                    consumer_group=self.group_id,
                ).set(partition_lag)

            CONSUMER_LAG_TOTAL.set(total_lag)
            CONSUMER_LAG_MAX.set(max_lag)

        except Exception as e:
            logger.debug(f"Error querying consumer lag: {e}")

        return {
            "total_lag": total_lag,
            "max_lag": max_lag,
            "partition_lag": lag_per_partition,
        }

    def calculate_latency_stats(self) -> Dict[str, float]:
        """Calculate p50, p95, p99, avg, and max consumer latency stats in ms."""
        if not self.latency_samples:
            return {"avg": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0}

        arr = np.array(self.latency_samples)
        return {
            "avg": float(np.mean(arr)),
            "p50": float(np.percentile(arr, 50)),
            "p95": float(np.percentile(arr, 95)),
            "p99": float(np.percentile(arr, 99)),
            "max": float(np.max(arr)),
        }


    def run(self, duration: Optional[float] = None):
        """Run the consumption loop until duration expires or SIGINT/SIGTERM received."""
        global _RUNNING
        _RUNNING = True
        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)

        logger.info(
            f"Benchmark Consumer started (Group: '{self.group_id}', Topic: '{self.topic}', Delay: {self.delay_ms}ms)"
        )

        try:
            while _RUNNING:
                msg = self.consumer.poll(timeout=0.1)

                now_perf = time.perf_counter()
                now_utc = datetime.datetime.now(datetime.timezone.utc)

                if msg is not None:
                    if msg.error():
                        if msg.error().code() != KafkaError._PARTITION_EOF:
                            logger.error(f"Consumer Kafka error: {msg.error()}")
                    else:
                        self.consumed_count += 1
                        self.interval_consumed += 1
                        CONSUMER_EVENTS_TOTAL.inc()

                        # Optional artificial delay for backpressure / lag simulation
                        if self.delay_ms > 0:
                            time.sleep(self.delay_ms / 1000.0)

                        # Latency measurement
                        try:
                            payload = json.loads(msg.value().decode("utf-8"))
                            event_dt = parse_event_timestamp(payload)
                            if event_dt:
                                latency_sec = max(
                                    0.0, (now_utc - event_dt).total_seconds()
                                )
                                latency_ms = latency_sec * 1000.0

                                EVENT_LATENCY_SECONDS.observe(latency_sec)

                                if len(self.latency_samples) >= self.max_samples:
                                    self.latency_samples.pop(0)
                                self.latency_samples.append(latency_ms)
                        except Exception:
                            pass

                # Periodic logging & lag query
                if now_perf - self.last_log_time >= 1.0:
                    elapsed_interval = now_perf - self.last_log_time
                    current_rate = self.interval_consumed / elapsed_interval
                    CONSUMER_EVENTS_PER_SECOND.set(current_rate)

                    lag_info = self.query_consumer_lag()
                    lat_stats = self.calculate_latency_stats()

                    if not self.quiet:
                        print(
                            f"[Consumer] Rate: {current_rate:6.1f} ev/s | "
                            f"Consumed: {self.consumed_count:7d} | "
                            f"Lag Total: {lag_info['total_lag']:4d} (Max: {lag_info['max_lag']:4d}) | "
                            f"Latency p50: {lat_stats['p50']:5.1f}ms, p95: {lat_stats['p95']:5.1f}ms, p99: {lat_stats['p99']:5.1f}ms"
                        )

                    self.last_log_time = now_perf
                    self.interval_consumed = 0

                if duration and (now_perf - self.start_time) >= duration:
                    logger.info(f"Configured duration limit of {duration}s reached.")
                    break

        finally:
            self.close()

    def close(self):
        """Close consumer connection cleanly."""
        logger.info("Closing Kafka consumer...")
        try:
            self.consumer.close()
        except Exception:
            pass
        logger.info("Consumer shutdown cleanly.")


def main():
    parser = argparse.ArgumentParser(
        description="IceStream Dedicated Performance & Benchmarking Consumer"
    )
    parser.add_argument(
        "--bootstrap-server",
        type=str,
        default="localhost:9092",
        help="Kafka bootstrap server (default: localhost:9092)",
    )
    parser.add_argument(
        "--topic",
        type=str,
        default="checkout-events",
        help="Target Kafka topic (default: checkout-events)",
    )
    parser.add_argument(
        "--group-id",
        type=str,
        default="icestream-day7-performance-consumer",
        help="Consumer group ID (default: icestream-day7-performance-consumer)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Duration to run consumer in seconds (default: None for continuous)",
    )
    parser.add_argument(
        "--delay-ms",
        type=float,
        default=0.0,
        help="Artificial delay in milliseconds per event to simulate slow consumer / lag (default: 0.0)",
    )
    parser.add_argument(
        "--metrics-port",
        type=int,
        default=8001,
        help="Prometheus metrics HTTP server port (default: 8001)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress periodic log output",
    )

    args = parser.parse_args()

    consumer = PerformanceConsumer(
        bootstrap_servers=args.bootstrap_server,
        topic=args.topic,
        group_id=args.group_id,
        delay_ms=args.delay_ms,
        metrics_port=args.metrics_port,
        quiet=args.quiet,
    )
    consumer.run(duration=args.duration)


if __name__ == "__main__":
    main()
