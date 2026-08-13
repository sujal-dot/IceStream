#!/usr/bin/env python3
"""
IceStream Day 3 - End-to-End Kafka Message Flow Test
Verifies complete message publication, consumption, and payload validation flow.
"""

import json
import os
import sys
import uuid
from kafka import KafkaAdminClient, KafkaProducer, KafkaConsumer

BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPIC_NAME = "checkout-events"
CONSUMER_GROUP = f"icestream-e2e-test-group-{uuid.uuid4().hex[:6]}"

def run_e2e_flow_test():
    print("========================================")
    print("IceStream Kafka Flow Test")
    print("========================================")
    print("")

    # Step 1: Kafka Connection
    try:
        admin_client = KafkaAdminClient(
            bootstrap_servers=BOOTSTRAP_SERVERS,
            request_timeout_ms=5000
        )
        print("Kafka connection       ✓")
    except Exception as e:
        print(f"Kafka connection       ✗ ({e})")
        print("\nRESULT: FAIL")
        return False

    # Step 2: Topic Exists
    try:
        existing_topics = admin_client.list_topics()
        admin_client.close()
        if TOPIC_NAME in existing_topics:
            print("Topic exists           ✓")
        else:
            print(f"Topic exists           ✗ ({TOPIC_NAME} not found)")
            print("\nRESULT: FAIL")
            return False
    except Exception as e:
        print(f"Topic exists           ✗ ({e})")
        print("\nRESULT: FAIL")
        return False

    # Unique test event for this run
    test_event_id = f"e2e-evt-{uuid.uuid4().hex[:8]}"
    test_payload = {
        "event_id": test_event_id,
        "event_type": "checkout",
        "event_time": "2026-08-13T10:15:00Z",
        "customer_id": "CUST_E2E_99",
        "amount": 2999.50,
        "currency": "INR",
        "source": "e2e-flow-test"
    }

    # Step 3: Producer Connected
    try:
        producer = KafkaProducer(
            bootstrap_servers=BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
            request_timeout_ms=5000
        )
        print("Producer connected     ✓")
    except Exception as e:
        print(f"Producer connected     ✗ ({e})")
        print("\nRESULT: FAIL")
        return False

    # Step 4: Message Published
    try:
        future = producer.send(TOPIC_NAME, key=test_event_id, value=test_payload)
        metadata = future.get(timeout=10)
        producer.flush()
        producer.close()
        print("Message published      ✓")
    except Exception as e:
        print(f"Message published      ✗ ({e})")
        print("\nRESULT: FAIL")
        return False

    # Step 5: Consumer Connected
    try:
        consumer = KafkaConsumer(
            TOPIC_NAME,
            bootstrap_servers=BOOTSTRAP_SERVERS,
            group_id=CONSUMER_GROUP,
            auto_offset_reset="earliest",
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            consumer_timeout_ms=10000
        )
        print("Consumer connected     ✓")
    except Exception as e:
        print(f"Consumer connected     ✗ ({e})")
        print("\nRESULT: FAIL")
        return False

    # Step 6 & 7: Message Received & Payload Validated
    message_received = False
    payload_valid = False

    for msg in consumer:
        val = msg.value
        if isinstance(val, dict) and val.get("event_id") == test_event_id:
            message_received = True
            if (val.get("amount") == 2999.50 and
                val.get("currency") == "INR" and
                val.get("customer_id") == "CUST_E2E_99"):
                payload_valid = True
            break

    consumer.close()

    if message_received:
        print("Message received       ✓")
    else:
        print("Message received       ✗ (Timed out)")

    if payload_valid:
        print("Payload validated      ✓")
    else:
        print("Payload validated      ✗ (Content mismatch)")

    if message_received and payload_valid:
        print("\nRESULT: PASS")
        return True
    else:
        print("\nRESULT: FAIL")
        return False

# Pytest wrapper
def test_kafka_e2e_flow():
    assert run_e2e_flow_test() is True

if __name__ == "__main__":
    success = run_e2e_flow_test()
    sys.exit(0 if success else 1)
