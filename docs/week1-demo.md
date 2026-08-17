# IceStream — Week 1 Demonstration Guide

This guide provides step-by-step instructions for demonstrating the Week 1 streaming foundation of **IceStream**.

---

## Storyline

> *"IceStream can generate thousands of realistic e-commerce events per second and intentionally corrupt the stream in controlled ways while measuring real-time throughput, latency, consumer lag, and failure metrics in Grafana."*

---

## Step 1: Start Infrastructure

Ensure Docker containers for Kafka, Prometheus, and Grafana are running:

```bash
docker compose up -d
docker compose ps
```

Verify services:
- Kafka (`localhost:9092`)
- Prometheus (`http://localhost:9090`)
- Grafana (`http://localhost:3000`)

---

## Step 2: Open Grafana Telemetry Dashboard

1. Open your browser and navigate to `http://localhost:3000`.
2. Login with credentials `admin` / `admin`.
3. Open the dashboard **"IceStream — Week 1 Streaming Overview"**.

---

## Step 3: Launch Performance Consumer

In a terminal window, start the performance consumer:

```bash
python scripts/kafka/performance_consumer.py
```

Output should show initial readiness logs.

---

## Step 4: Run Clean Stream Generation

In a second terminal window, run the event generator at 1,000 events/sec:

```bash
python generator/main.py --rate 1000 --error-rate 0
```

### Observed Behavior:
- **Producer Throughput**: ~1,000 events/sec in Grafana panel.
- **Consumer Throughput**: ~1,000 events/sec matching producer.
- **Consumer Lag**: Near 0.
- **p95 Latency**: < 20 ms.
- **Publish Failures**: 0.

---

## Step 5: Stop Clean Stream

Press `Ctrl+C` in the generator terminal window.

### Observed Behavior:
- Throughput drops cleanly to 0.
- Grafana metrics update dynamically within 2 seconds.

---

## Step 6: Inject Controlled Stream Faults

Restart the event generator with fault injection enabled:

```bash
python generator/main.py \
  --rate 1000 \
  --null-rate 2.0 \
  --duplicate-rate 1.0 \
  --negative-rate 1.0 \
  --invalid-enum-rate 0.5 \
  --schema-drift-rate 0.5 \
  --type-change-rate 0.5 \
  --timestamp-drift-rate 0.5
```

### Observed Behavior:
- Stream continues at ~1,000 events/sec.
- **Fault Injection Breakdown** panel populates with live fault distribution.
- Consumer continues consuming events continuously without crashing.

---

## Step 7: Automated Week 1 Checkpoint Validation

Run the full automated checkpoint test script:

```bash
python scripts/week1_checkpoint.py
```

Expected Output:
```text
========================================
IceStream Week 1 Checkpoint Summary
========================================

Infrastructure
Kafka                 ✓
Prometheus            ✓
Grafana               ✓

Streaming
Producer              ✓
Kafka                 ✓
Consumer              ✓

Performance
Producer throughput   1,000 events/sec
Consumer throughput   990 events/sec
Consumer lag          0
p95 latency           12.4 ms

Fault Injection
NULL                  1.01%
DUPLICATE             0.49%
NEGATIVE              0.51%
SCHEMA_DRIFT          0.20%

Observability
Prometheus            ✓
Grafana               ✓
Dashboard             ✓

RESULT: WEEK 1 PASS
```
