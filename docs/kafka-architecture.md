# IceStream Apache Kafka Architecture & Messaging Specification

> **Status Notice**: This document specifies the **Kafka Topology, Topic Architecture, and Consumer Group Strategy** implemented in Day 3. Local topics, partitioning, retention policies, and producer/consumer verification tests are fully operational.

---

## 1. Role of Apache Kafka in IceStream

Apache Kafka acts as the distributed, fault-tolerant event streaming backbone for IceStream. It decouples high-velocity ingestion producers from downstream stream processing (Apache Flink), data quality evaluation, lakehouse storage (Apache Iceberg), and observability components.

Kafka provides:
- **Low-Latency Message Buffering**: Absorbs traffic surges without overloading downstream systems.
- **Strict Partition Ordering**: Guarantees ordered processing per partition key (e.g., `event_id` or `customer_id`).
- **Replayability & Auditing**: Durable log retention allows reprocessing quarantined or historical event streams.

---

## 2. Kafka Topic Architecture

IceStream employs a multi-topic stream topology isolating raw ingestion, validated events, quality exceptions, dead-letter records, and control signals.

```
                 ┌───────────────────┐
                 │  Python Producer  │
                 └─────────┬─────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ checkout-events │
                  │   3 partitions  │
                  └────────┬────────┘
                           │
                ┌──────────┼──────────┐
                ▼          ▼          ▼
          Partition 0 Partition 1 Partition 2
                           │
       +-------------------+-------------------+
       | (Planned Day 4+ Flink Validation Engine)
       v                                       v
┌──────────────┐                       ┌────────────────┐
│checkout-valid│                       │checkout-invalid│
│ 3 partitions │                       │  3 partitions  │
└──────────────┘                       └───────┬────────┘
                                               │
                                               v
                                       ┌────────────────┐
                                       │  checkout-dlq  │
                                       │  3 partitions  │
                                       └────────────────┘
```

---

## 3. Topic Purpose Matrix

| Topic Name | Partitions | Replication | Retention | Purpose | Data Flow |
| :--- | :---: | :---: | :---: | :--- | :--- |
| `checkout-events` | 3 | 1 | 7 Days | Primary raw checkout transaction event stream | `Producer -> checkout-events` |
| `checkout-valid` | 3 | 1 | 7 Days | Stream containing successfully validated records | `Flink -> checkout-valid` *(Planned)* |
| `checkout-invalid` | 3 | 1 | 14 Days | Stream containing events failing data-quality rules | `Flink -> checkout-invalid` *(Planned)* |
| `checkout-dlq` | 3 | 1 | 30 Days | Dead-letter queue for severely corrupt payloads | `Quality Engine -> checkout-dlq` *(Planned)* |
| `pipeline-control` | 1 | 1 | 7 Days | Pipeline control events (`PAUSE`, `RESUME`, `CIRCUIT_OPEN`) | `Control Plane -> Pipeline` *(Planned)* |
| `schema-events` | 1 | 1 | 30 Days | Schema change notifications & drift events | `Schema Monitor -> Pipeline` *(Planned)* |

---

## 4. Partitioning Strategy

- **High-Throughput Data Streams (`checkout-events`, `checkout-valid`, `checkout-invalid`, `checkout-dlq`)**: Configured with **3 partitions** for local development. This allows parallel processing across multiple Flink task slots while preserving order per key.
- **Control & Schema Streams (`pipeline-control`, `schema-events`)**: Configured with **1 partition**. Control signals and schema version mutations require strict global sequence ordering across the entire cluster.

---

## 5. Replication Strategy

- **Local Development**: `replication.factor = 1` across all topics (single-node KRaft broker).
- **Production Architecture Target**: `replication.factor = 3` with `min.insync.replicas = 2` across multiple availability zones for high availability and zero data loss.

---

## 6. Retention Strategy

- `checkout-events` & `checkout-valid` (**7 Days / 604,800,000 ms**): Sufficient window for local stream reprocessing and Flink checkpoint recovery.
- `checkout-invalid` (**14 Days / 1,209,600,000 ms**): Extended retention to allow platform operators to inspect quarantined events and tune quality rules.
- `checkout-dlq` & `schema-events` (**30 Days / 2,592,000,000 ms**): Maximum retention for audit compliance, root-cause investigation, and schema evolution tracking.

---

## 7. Consumer Group Strategy

Kafka consumer groups enable independent processing applications to read from the same topic without interfering with each other's offset state.

### Planned Production Consumer Groups

1. **`icestream-flink-validation`**: Flink stream processing job consuming `checkout-events` to execute real-time schema and data-quality checks.
2. **`icestream-quality-engine`**: Standalone monitoring service evaluating windowed error rates and managing circuit breaker state.
3. **`icestream-observability`**: FastAPI backend service consuming stream telemetry for WebSocket dashboard updates.
4. **`icestream-schema-monitor`**: Service tracking schema version evolution and reporting schema drift.

### Day 3 Test Consumer Group
- **`icestream-day3-test-consumer`**: Dedicated test consumer group used for Day 3 verification (`test_consumer.py`).

---

## 8. Offset & Commit Semantics

- **Initial Offset Strategy**: `auto.offset.reset = earliest` ensures new consumer groups start reading from the beginning of topic logs.
- **Commit Semantics**: Production consumer groups will use stateful checkpoint-managed offset commits (via Flink RocksDB state backend) to achieve exact-once processing semantics.

---

## 9. Day 3 Verification & Validation Results

The messaging foundation was verified using automated unit/flow scripts:
- **Topic Creation**: `scripts/kafka/create_topics.sh` (Idempotent creation of all 6 topics).
- **Topic Verification**: `scripts/kafka/verify_topics.sh` (Direct broker inspection of partition count and retention).
- **Producer Test**: `tests/kafka/test_producer.py` (Publishes JSON payload to `checkout-events`).
- **Consumer Test**: `tests/kafka/test_consumer.py` (Reads and deserializes JSON payload).
- **E2E Flow Test**: `tests/kafka/test_kafka_flow.py` (Verified message publication, retrieval, and payload integrity).
