# Kafka Test Suite

> **Status Notice**: Day 3 Python Kafka testing suite for verifying producer connectivity, consumer deserialization, end-to-end payload flow, and topic verification.

---

## Test Suite Components

| Test File | Description | Execution Command | Expected Result |
| :--- | :--- | :--- | :--- |
| `test_producer.py` | Validates message publication to `checkout-events` topic | `python tests/kafka/test_producer.py` | `Kafka producer test: PASS` |
| `test_consumer.py` | Validates message consumption from `checkout-events` topic | `python tests/kafka/test_consumer.py` | `Kafka consumer test: PASS` |
| `test_kafka_flow.py` | End-to-end message publication, retrieval & payload validation | `pytest tests/kafka/test_kafka_flow.py -v` | `RESULT: PASS` |

---

## Prerequisites & Setup

Install test dependencies into python virtual environment:
```bash
pip install -r tests/kafka/requirements.txt
```

---

## Execution Guide

### 1. Topic Initialization & Verification
```bash
# Initialize all 6 topics
bash scripts/kafka/create_topics.sh

# Verify topic partitions and retention settings
bash scripts/kafka/verify_topics.sh
```

### 2. Run End-to-End Flow Test
```bash
python tests/kafka/test_kafka_flow.py
```

Expected Output:
```text
========================================
IceStream Kafka Flow Test
========================================

Kafka connection       ✓
Topic exists           ✓
Producer connected     ✓
Message published      ✓
Consumer connected     ✓
Message received       ✓
Payload validated      ✓

RESULT: PASS
```

### 3. Failure & Restart Test Procedure
To verify message durability and broker recovery:
```bash
# 1. Verify environment is healthy
docker compose ps

# 2. Restart Kafka broker
docker compose restart kafka

# 3. Wait 10 seconds for broker health check
sleep 10

# 4. Re-run topic verification & flow test
bash scripts/kafka/verify_topics.sh
python tests/kafka/test_kafka_flow.py
```
