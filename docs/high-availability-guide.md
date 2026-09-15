# IceStream High Availability (HA) Architecture & Operating Guide

This document details the High Availability (HA) architecture of **IceStream — Real-Time Lakehouse Observability & Self-Healing Data Pipeline**.

---

## 1. High Availability Architecture Overview

```mermaid
graph TD
    Client[Producers / Web UI] --> LB[Nginx Load Balancer]
    
    subgraph FastAPI Multi-Worker Cluster
        LB --> BE1[FastAPI Backend Node 1 (4 Workers)]
        LB --> BE2[FastAPI Backend Node 2 (4 Workers)]
    end
    
    subgraph Multi-Broker Kafka Cluster (RF=3, min.isr=2)
        BE1 & BE2 --> K1[Kafka Broker 1 (KRaft)]
        BE1 & BE2 --> K2[Kafka Broker 2 (KRaft)]
        BE1 & BE2 --> K3[Kafka Broker 3 (KRaft)]
    end
    
    subgraph Flink Cluster HA (ZooKeeper / Kubernetes HA)
        ZK[ZooKeeper Quorum] <--> JM1[Flink JobManager 1 (Leader)]
        ZK <--> JM2[Flink Standby JobManager 2]
        JM1 & JM2 --> TM1[TaskManager Worker 1]
        JM1 & JM2 --> TM2[TaskManager Worker 2]
    end
    
    K1 & K2 & K3 --> TM1 & TM2
    TM1 & TM2 --> S3[MinIO S3 / Checkpoints / Iceberg Catalog]
    BE1 & BE2 --> PG[(PostgreSQL Metadata Store)]
```

---

## 2. Component Failure Tolerance Specifications

### A. Multi-Broker Kafka Cluster (`RF=3`, `min.isr=2`)
- **Quorum Voting**: 3 KRaft brokers (`kafka1`, `kafka2`, `kafka3`) form a distributed quorum (`1@kafka1:9093,2@kafka2:9093,3@kafka3:9093`).
- **Data Durability**: All streams (`checkout-events`, `checkout-valid`, `checkout-invalid`, `checkout-dlq`, `pipeline-control`, `schema-events`) run with `ReplicationFactor: 3` and `min.insync.replicas: 2`.
- **Broker Failure**: Loss of any single Kafka broker allows continuous read/write operations without data loss or pipeline interruption.

### B. Flink Stream Processing HA
- **Leader Election**: ZooKeeper (`zookeeper:2181`) or Kubernetes (`KubernetesHaServices`) manages active JobManager election.
- **Standby JobManager**: If the primary JobManager fails, the standby JobManager automatically assumes leadership and recovers streaming state from S3 checkpoints (`s3://checkpoints/flink/ha/`).
- **Parallel Workers**: Multiple TaskManagers process event streams in parallel across assigned task slots.

### C. Multi-Worker & Multi-Instance FastAPI Backend
- **Process Scaling**: Uvicorn runs with multiple worker processes (`WEB_WORKERS=4`).
- **Instance Scaling**: Nginx reverse proxy load balances incoming REST traffic across backend instances (`backend1`, `backend2`).
- **Kubernetes Autoscaling**: Horizontal Pod Autoscaler (`icestream-backend-hpa`) dynamically scales replicas between 3 and 10 based on CPU/RAM load.

---

## 3. Running High Availability (HA) Locally

To start the full High Availability stack with 3 Kafka brokers, ZooKeeper, dual JobManagers, and Nginx load balancer:

```bash
docker compose -f docker-compose.ha.yml up -d
```

Initialize HA topics with Replication Factor 3:

```bash
./scripts/kafka/create_topics.sh
```

Execute HA verification and failover audit:

```bash
./scripts/ha/test_ha_failover.sh
```

---

## 4. Kubernetes Production Deployment

Production Kubernetes manifests are located in `deploy/k8s/`:

```bash
# Apply 3-broker KRaft StatefulSet
kubectl apply -f deploy/k8s/kafka-ha-kraft.yaml

# Apply Flink Kubernetes HA Services Deployment
kubectl apply -f deploy/k8s/flink-ha-k8s.yaml

# Apply FastAPI Multi-Replica Backend & HPA
kubectl apply -f deploy/k8s/fastapi-ha-deployment.yaml
```
