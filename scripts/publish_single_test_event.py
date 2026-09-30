#!/usr/bin/env python3
import json
import time
from confluent_kafka import Producer

conf = {
    'bootstrap.servers': 'localhost:9092',
    'client.id': 'verify-live-producer'
}

producer = Producer(conf)

event = {
    "event_id": "evt_VERIFY_LIVE_9999",
    "order_id": "ord_VERIFY_9999",
    "customer_id": "cust_VERIFY_9999",
    "amount": 999.99,
    "currency": "USD",
    "payment_status": "COMPLETED",
    "event_timestamp": "2026-09-28T13:30:00.000000Z",
    "schema_version": 1,
    "device": "desktop",
    "country": "US"
}

def ack(err, msg):
    if err is not None:
        print(f"Delivery failed: {err}")
    else:
        print(f"Message delivered to {msg.topic()} [{msg.partition()}] at offset {msg.offset()}")

producer.produce("checkout-events", key="ord_VERIFY_9999", value=json.dumps(event).encode("utf-8"), callback=ack)
producer.flush(timeout=10)
