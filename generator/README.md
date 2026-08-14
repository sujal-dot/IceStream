# IceStream High-Throughput Checkout Event Generator

High-performance Python generator for synthesizing real-time e-commerce checkout telemetry streams with configurable target rates, error injection rates, and realistic data distributions.

---

## 1. Purpose

The IceStream Event Generator simulates high-velocity e-commerce checkout events. It enables end-to-end testing of streaming data pipelines, real-time quality validation engines, schema drift detection, quarantine processing, and lakehouse storage.

It produces both clean, schema-compliant events and controlled schema anomalies (null values, negative amounts, type mismatches, missing keys, future timestamps, and duplicate event IDs).

---

## 2. Architecture

```text
┌─────────────────────────┐         JSON Events        ┌─────────────────────────┐
│  Python Event Generator │ ─────────────────────────> │   Apache Kafka Cluster  │
│  (confluent-kafka)      │    (1,000+ events/sec)     │  Topic: checkout-events │
└─────────────────────────┘                            └─────────────────────────┘
```

The generator module separates concerns into clear components:
- `config.py`: CLI parsing and configuration validation.
- `data_generator.py`: Synthetic product catalog, customer pools, and clean payload generation.
- `error_injector.py`: Controlled schema anomaly and corruption injection.
- `producer.py`: High-performance C-backed Kafka producer wrapper with asynchronous delivery callbacks.
- `event_generator.py`: Core orchestration engine combining data generation, error injection, and publishing.
- `utils.py`: Batch-based precision rate limiter and throughput statistics tracker.
- `main.py`: CLI entrypoint with signal handling and periodic statistics logging.

---

## 3. Event Schema

Baseline valid events match the following structure:

```json
{
  "event_id": "evt_8f3a9b1c2d4e5f60",
  "event_time": "2026-08-14T05:15:21.123Z",
  "event_type": "checkout",
  "customer_id": "CUS000102",
  "session_id": "SES881920",
  "order_id": "ORD9918273",
  "product_id": "PROD003",
  "quantity": 2,
  "unit_price": 2990.00,
  "amount": 5980.00,
  "currency": "INR",
  "payment_method": "UPI",
  "payment_status": "SUCCESS",
  "device": "mobile",
  "country": "IN",
  "source": "web",
  "source_version": "v1"
}
```

Detailed schema definitions and corrupt payload examples are documented in [docs/event-schema.md](../docs/event-schema.md).

---

## 4. Installation

Activate your virtual environment and install requirements:

```bash
pip install -r generator/requirements.txt
```

---

## 5. CLI Usage

The primary command to start generating events at 1,000 events/sec with a 0.5% error rate is:

```bash
python generator/main.py --rate 1000 --error-rate 0.5
```

### Supported CLI Arguments

| Parameter | Default Value | Description |
| :--- | :--- | :--- |
| `--rate` | `1000` | Target generation rate in events/second. |
| `--error-rate` | `0.0` | Percentage of events containing injected errors (e.g. `0.5` = 0.5%). |
| `--bootstrap-server` | `localhost:9092` | Kafka broker host and port. |
| `--topic` | `checkout-events` | Target Kafka topic. |
| `--error-types` | `None` (all) | Comma-separated list of specific error types to inject. |
| `--seed` | `None` | Random seed for reproducible generation. |
| `--duration` | `None` | Run duration in seconds (continuous if omitted). |
| `--log-interval` | `1.0` | Seconds between throughput log outputs. |

---

## 6. Rate Configuration

Rate limiting is implemented using a high-precision batch pacing loop to avoid OS thread sleep overhead.

Examples:
- Standard throughput (1,000 ev/s): `--rate 1000`
- High throughput (5,000 ev/s): `--rate 5000`
- Benchmark burst (10,000 ev/s): `--rate 10000`

---

## 7. Error-Rate Configuration

The `--error-rate` argument is specified as a **percentage**:
- `--error-rate 0`: 0.0% invalid events (100% valid clean events).
- `--error-rate 0.5`: 0.5% invalid events (5 corrupted events per 1,000 generated).
- `--error-rate 5.0`: 5.0% invalid events (50 corrupted events per 1,000 generated).

---

## 8. Supported Error Types

Injected corrupted events contain **one** primary schema anomaly:
1. `null_amount`: Sets `amount` to JSON `null`.
2. `null_customer_id`: Sets `customer_id` to JSON `null`.
3. `negative_amount`: Sets `amount` to a negative float value.
4. `duplicate_event_id`: Reuses a previously published valid `event_id`.
5. `invalid_currency`: Sets `currency` to `"XXX"` or `"INVALID"`.
6. `missing_required_field`: Removes a required key completely from the JSON dictionary.
7. `wrong_data_type`: Mutates numerical fields to strings (e.g., `quantity: "two"`).
8. `future_timestamp`: Sets `event_time` to +1 hour in the future.

To restrict error injection to specific types:

```bash
python generator/main.py --rate 1000 --error-rate 1.0 --error-types null_amount,negative_amount,invalid_currency
```

---

## 9. Kafka Configuration

The generator connects to Kafka via `confluent-kafka` using optimized producer options:
- `linger.ms`: 5ms batch window.
- `batch.num.messages`: 10,000 messages.
- `queue.buffering.max.messages`: 100,000.
- `compression.type`: `snappy`.
- `acks`: 1.

---

## 10. Throughput Measurement

During execution, runtime throughput statistics are printed to standard output:

```text
==================================================
IceStream Event Generator
==================================================
Kafka Bootstrap : localhost:9092
Target Topic    : checkout-events
Target Rate     : 1000 events/sec
Error Rate      : 0.5%
Error Types     : null_amount, null_customer_id, negative_amount, duplicate_event_id, invalid_currency, missing_required_field, wrong_data_type, future_timestamp
Random Seed     : None
==================================================
Running...

Elapsed: 10.0s | Generated: 10042 | Published: 10042 | Errors Injected: 48 (0.48%) | Publish Failures: 0 | Current Rate: 1003 ev/s | Avg Rate: 1004 ev/s
```

---

## 11. Graceful Shutdown

Upon receiving a termination signal (`Ctrl+C` / `SIGINT` or `SIGTERM`):
1. Event generation stops immediately.
2. Pending Kafka messages are flushed (`producer.flush(5.0)`).
3. The Kafka producer connection is closed cleanly.
4. A final execution summary report is displayed.

---

## 12. Troubleshooting

### Connection Refused to Kafka (`localhost:9092`)
Ensure the Day 3 Docker infrastructure is running:
```bash
docker compose ps
```
If Kafka is down, start containers:
```bash
docker compose up -d
```

### Topic `checkout-events` does not exist
Create topics using the Day 3 script:
```bash
bash scripts/kafka/create_topics.sh
```

---

## 13. Examples

### Run 1,000 ev/sec for 30 Seconds (Clean Stream)
```bash
python generator/main.py --rate 1000 --error-rate 0 --duration 30
```

### Run 2,000 ev/sec with 1% Error Rate
```bash
python generator/main.py --rate 2000 --error-rate 1.0
```

### Reproducible Run with Fixed Random Seed
```bash
python generator/main.py --rate 500 --error-rate 5.0 --seed 42 --duration 10
```
