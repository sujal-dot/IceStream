# Apache Kafka Messaging Backbone Component

> **Status Notice**: Day 3 Kafka architecture, topic topology, retention settings, management scripts, and verification test suites are fully configured and verified.

---

## Component Overview

The `kafka/` module contains topology configurations, topic definitions, and architectural specifications for IceStream's Kafka event streaming backbone.

For full architectural details, see [`docs/kafka-architecture.md`](../docs/kafka-architecture.md).

---

## Topic Topology

The platform manages 6 dedicated topics:

| Topic Name | Partitions | Replication | Retention | Role |
| :--- | :---: | :---: | :---: | :--- |
| `checkout-events` | 3 | 1 | 7 Days | Primary raw event stream |
| `checkout-valid` | 3 | 1 | 7 Days | Clean validated events |
| `checkout-invalid` | 3 | 1 | 14 Days | Quarantined invalid events |
| `checkout-dlq` | 3 | 1 | 30 Days | Dead-letter queue |
| `pipeline-control` | 1 | 1 | 7 Days | Circuit breaker & control signals |
| `schema-events` | 1 | 1 | 30 Days | Schema evolution notifications |

---

## Configuration Specifications

- **Topic Declarations**: Defined in [`kafka/config/topics.yaml`](config/topics.yaml).
- **Broker Mode**: Local single-node Apache Kafka `3.7.0` running in **KRaft mode** (no ZooKeeper dependency).
- **Replication**: Configured to `1` for local development.

---

## Topic Initialization & Management Commands

### Initialize Topics
```bash
bash scripts/kafka/create_topics.sh
```

### Verify Topics
```bash
bash scripts/kafka/verify_topics.sh
```

### Run Python E2E Test Flow
```bash
python tests/kafka/test_kafka_flow.py
```

---

## Troubleshooting

- **Container Status**: Ensure `icestream-kafka` container is running: `docker compose ps`
- **Broker Logs**: View broker startup logs: `docker compose logs -f kafka`
- **Topic Inspection**: Describe specific topic directly from broker:
  ```bash
  docker exec icestream-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --describe --topic checkout-events
  ```
