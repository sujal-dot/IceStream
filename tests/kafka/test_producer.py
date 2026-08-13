#!/usr/bin/env python3
"""
IceStream Day 3 - Basic Kafka Producer Test
Validates basic message publishing connectivity to Apache Kafka.
"""

import json
import os
import sys
from kafka import KafkaProducer

BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPIC_NAME = "checkout-events"

TEST_EVENT = {
    "event_id": "test-event-001",
    "event_type": "checkout",
    "event_time": "2026-08-13T10:00:00Z",
    "customer_id": "TEST001",
    "amount": 1499.0,
    "currency": "INR",
    "source": "day3-producer-test"
}

def run_producer_test():
    try:
        producer = KafkaProducer(
            bootstrap_servers=BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
            request_timeout_ms=10000,
            retries=3
        )
        
        future = producer.send(
            topic=TOPIC_NAME,
            key=TEST_EVENT["event_id"],
            value=TEST_EVENT
        )
        
        # Wait for delivery acknowledgment
        record_metadata = future.get(timeout=10)
        
        producer.flush()
        producer.close()
        
        print("Kafka producer test: PASS")
        print(f"Message successfully published to {record_metadata.topic} [partition {record_metadata.partition} @ offset {record_metadata.offset}]")
        return True
    except Exception as e:
        print(f"Kafka producer test: FAIL - {e}", file=sys.stderr)
        return False

if __name__ == "__main__":
    success = run_producer_test()
    sys.exit(0 if success else 1)
