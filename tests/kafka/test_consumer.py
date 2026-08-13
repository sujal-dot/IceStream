#!/usr/bin/env python3
"""
IceStream Day 3 - Basic Kafka Consumer Test
Validates basic message consumption and deserialization from Apache Kafka.
"""

import json
import os
import sys
import time
from kafka import KafkaConsumer

BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPIC_NAME = "checkout-events"
CONSUMER_GROUP = "icestream-day3-test-consumer"

def run_consumer_test(target_event_id="test-event-001", timeout_seconds=15):
    try:
        consumer = KafkaConsumer(
            TOPIC_NAME,
            bootstrap_servers=BOOTSTRAP_SERVERS,
            group_id=CONSUMER_GROUP,
            auto_offset_reset="earliest",
            enable_auto_commit=True,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            consumer_timeout_ms=timeout_seconds * 1000
        )
        
        received_matching_event = False
        received_event_id = None
        
        start_time = time.time()
        for message in consumer:
            payload = message.value
            if isinstance(payload, dict) and payload.get("event_id") == target_event_id:
                received_matching_event = True
                received_event_id = payload.get("event_id")
                break
            if time.time() - start_time > timeout_seconds:
                break
                
        consumer.close()
        
        if received_matching_event:
            print("Kafka consumer test: PASS")
            print(f"Received event_id={received_event_id}")
            return True
        else:
            print(f"Kafka consumer test: FAIL - Target event_id '{target_event_id}' not received within {timeout_seconds}s", file=sys.stderr)
            return False
            
    except Exception as e:
        print(f"Kafka consumer test: FAIL - {e}", file=sys.stderr)
        return False

if __name__ == "__main__":
    success = run_consumer_test()
    sys.exit(0 if success else 1)
