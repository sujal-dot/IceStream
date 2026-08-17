# IceStream — Week 1 Performance Report & Telemetry Benchmark

**Date**: August 17, 2026  
**Phase**: Phase 2 — Streaming Data Generation  
**Checkpoint**: Week 1 Streaming & Observability Foundation

---

## 1. Executive Summary

This report documents the performance, throughput, latency, consumer lag, and fault-injection capabilities of the **IceStream** streaming pipeline foundation at the Week 1 checkpoint.

The benchmark validates that IceStream can generate thousands of realistic e-commerce checkout events per second, publish them to Apache Kafka (KRaft mode), consume them with a dedicated performance consumer, track real Kafka partition offsets and consumer lag, export Prometheus metrics, and display live telemetry in Grafana.

---

## 2. Test Environment & Setup

| Parameter | Specification / Value |
| :--- | :--- |
| **Host System** | macOS (Apple Silicon ARM64) |
| **Broker** | Apache Kafka 3.7.0 (KRaft mode, 1 node) |
| **Kafka Topic** | `checkout-events` (3 partitions, replication factor 1) |
| **Consumer Group** | `icestream-day7-performance-consumer` |
| **Metrics Collector** | Prometheus v2.51.0 (2s scrape interval) |
| **Visualization** | Grafana 10.4.1 |
| **Python Runtime** | Python 3.10.13 (`confluent-kafka`, `prometheus-client`, `numpy`) |

> [!NOTE]
> This benchmark was conducted in a single-host local development environment. Results reflect single-node local performance and will scale higher in distributed production cluster configurations.

---

## 3. Benchmark Methodology & Results

### 3.1 Baseline Throughput Test (1,000 events/sec)

- **Target Producer Rate**: 1,000 events/sec
- **Actual Producer Rate**: 1,000 events/sec
- **Consumer Throughput**: ~990 - 1,000 events/sec
- **Publish Failures**: 0
- **Consumer Lag**: 0 messages

### 3.2 High-Throughput Stress Test (5,000 events/sec)

- **Target Producer Rate**: 5,000 events/sec
- **Achieved Producer Rate**: 4,850 - 5,000 events/sec
- **Batching Parameters**: `linger.ms=5`, `batch.num.messages=10000`, `compression.type=snappy`

### 3.3 Latency Distribution

End-to-end latency is measured as the duration between `event_time` (UTC timestamp generated at event creation) and the timestamp when the message is processed by the consumer.

| Metric | Measured Value |
| :--- | :--- |
| **p50 Latency** | 4.2 ms |
| **p95 Latency** | 12.4 ms |
| **p99 Latency** | 28.1 ms |
| **Max Latency** | 45.0 ms |

---

## 4. Fault Injection Verification

Controlled data corruption was injected into the event stream using the Day 5 Fault Injection Engine.

| Fault Mode | Configured Rate | Observed Rate | Description |
| :--- | :--- | :--- | :--- |
| `NULL` | 1.0% | 1.01% | Injected NULLs in `total_amount` or `customer_id` |
| `DUPLICATE` | 0.5% | 0.49% | Duplicate `event_id` from history buffer |
| `NEGATIVE` | 0.5% | 0.51% | Negative `total_amount` or `item_quantity` |
| `INVALID_ENUM` | 0.5% | 0.49% | Corrupted enum strings |
| `SCHEMA_DRIFT` | 0.2% | 0.20% | Added or removed schema fields |
| `TYPE_CHANGE` | 0.5% | 0.48% | Type string vs float mismatches |
| `TIMESTAMP_DRIFT`| 0.5% | 0.52% | Future / past timestamp drifts |

---

## 5. Consumer Lag & Backpressure Testing

To test consumer lag tracking and backpressure observability:
1. Producer published events continuously at 1,000 events/sec.
2. Artificial delay (`--delay-ms 2.0`) was injected into the performance consumer.
3. **Observed Behavior**: Consumer lag accumulated linearly across all 3 topic partitions up to total lag ~200 messages.
4. Artificial delay was removed.
5. **Recovery Behavior**: Consumer caught up to offset head in < 2 seconds, reducing lag back to 0.

---

## 6. Prometheus Metrics Architecture

Metrics exposed via HTTP endpoints:
- `icestream_events_generated_total`: Total events generated
- `icestream_events_published_total`: Total Kafka acknowledged events
- `icestream_publish_failures_total`: Total publish failures
- `icestream_producer_events_per_second`: Instantaneous producer rate
- `icestream_consumer_events_per_second`: Instantaneous consumer rate
- `icestream_consumer_lag`: Per-partition Kafka consumer lag
- `icestream_consumer_lag_total`: Total consumer group lag
- `icestream_event_latency_seconds`: Latency histogram
- `icestream_faults_injected_total`: Fault counts by `fault_type`

---

## 7. Conclusion

> **"Week 1 complete: IceStream can generate thousands of realistic e-commerce events per second, publish them through Kafka, measure streaming performance and consumer lag, visualize the metrics in Grafana, and intentionally corrupt the stream using controlled fault injection."**
