# IceStream Flink Reliability & Failure Recovery Infrastructure

## Overview

Day 12 establishes stream processing reliability for the IceStream Lakehouse pipeline (`Kafka -> Flink -> Iceberg Bronze`). This document details the checkpointing architecture, S3 state storage, fixed-delay restart strategy, Kafka consumer offset recovery, and automated fault recovery testing.

```text
             KAFKA (Topic: checkout-events)
                           │
                           ▼
                 FLINK STREAM PROCESSING
                           │
                    checkpoint complete
                           │
                           ▼
                 MinIO (s3://checkpoints/flink/bronze/)
                           │
              ┌───── TASKMANAGER FAILURE ─────┐
              │                               │
              ▼                               │
        TaskManager stops                     │
              │                               │
              └──────┐                        │
                     ▼                        │
              TaskManager restarts            │
                     │                        │
                     ▼                        │
              Restore Checkpoint State        │
                     │                        │
                     ▼                        │
              Recover Kafka Offsets           │
                     │                        │
                     ▼                        │
             KAFKA CONSUMPTION RESUMED        │
                     │                        │
                     ▼                        │
                 ICEBERG SINK COMMITS         │
                     │                        │
                     ▼                        │
               Bronze Table Row Count Grows   │
```

---

## 1. Checkpoint Architecture & Configuration

Flink checkpointing periodically snapshots operator state and Kafka source positions into MinIO S3 object storage (`s3://checkpoints/flink/bronze/`).

### Flink Checkpoint Settings

| Parameter | Configuration Value | Description |
|---|---|---|
| `execution.runtime-mode` | `streaming` | Continuous stream execution mode |
| `execution.checkpointing.mode` | `EXACTLY_ONCE` | Enables two-phase commit checkpointing |
| `execution.checkpointing.interval` | `30000ms` (30s) | Periodic checkpoint trigger interval |
| `execution.checkpointing.timeout` | `60000ms` (60s) | Checkpoint abort timeout |
| `execution.checkpointing.min-pause` | `500ms` | Minimum pause between consecutive checkpoints |
| `execution.checkpointing.max-concurrent-checkpoints` | `1` | Max simultaneous checkpoints in flight |
| `state.backend` | `filesystem` | Distributed filesystem state backend |
| `state.checkpoints.dir` | `s3://checkpoints/flink/bronze/` | S3 endpoint location for checkpoint metadata |

---

## 2. Restart Strategy & State Management

### Fixed-Delay Task Restart Strategy

When an unexpected TaskManager crash or network failure occurs, Flink automatically attempts task restoration within the running cluster before failing the job:

```yaml
restart-strategy.type: fixed-delay
restart-strategy.fixed-delay.attempts: 3
restart-strategy.fixed-delay.delay: 10s
```

### State Storage Structure in MinIO S3

Checkpoints are stored in the dedicated MinIO `checkpoints` bucket:

```text
s3://checkpoints/
└── flink/
    └── bronze/
        └── <job-id>/
            ├── chk-1/
            │   └── _metadata
            ├── chk-2/
            │   └── _metadata
            ├── shared/
            └── taskowned/
```

---

## 3. Kafka Consumer Offset Recovery

1. **Source Position Checkpointing**: Flink's Kafka Source stores current partition offsets inside each Flink checkpoint metadata file in S3.
2. **Offset Restoration**: Upon TaskManager recovery, Flink reads the latest completed checkpoint from S3 and resumes consumption from the exact partition offsets recorded in the checkpoint.
3. **Consumer Group**: Uses consumer group `icestream-flink-bronze`.
4. **No Manual Offset Resets**: Offset recovery relies entirely on Flink's state restoration mechanism; manual Kafka consumer group resets (`kafka-consumer-groups --reset-offsets`) are not used.

---

## 4. End-to-End Delivery & Exactly-Once Analysis

> [!NOTE]
> **Technical Honesty Note**:
> Configuring `execution.checkpointing.mode = EXACTLY_ONCE` enables Flink's internal exactly-once state processing.
> End-to-end exactly-once delivery across `Kafka -> Flink -> Iceberg` requires:
> 1. Idempotent / transactional Kafka source (Flink Kafka connector).
> 2. Iceberg two-phase commit sink (`IcebergFilesCommitter` commits data files on Flink checkpoint boundary).
> 3. Zero duplicate event injection at the source.

During TaskManager crash recovery, uncommitted in-flight records produced between checkpoint boundaries may be re-read from Kafka, leading to duplicate records if non-idempotent fault injection is enabled. Under controlled zero-fault conditions, the pipeline demonstrates seamless resumption with 0 record loss.

---

## 5. Automated Recovery Test (`day12_recovery_test.sh`)

The automated failure recovery script (`scripts/day12_recovery_test.sh`) verifies the full recovery flow:

1. Validates Kafka, MinIO, Flink JobManager, and Iceberg Catalog services.
2. Verifies active Flink Bronze streaming job.
3. Starts background event stream generator (`300 events/sec`).
4. Waits for initial completed checkpoint in MinIO S3.
5. Records baseline row count `COUNT_BEFORE_FAILURE` from `bronze.checkout_events`.
6. Simulates TaskManager container crash (`docker compose stop flink-taskmanager`).
7. Restarts TaskManager container (`docker compose start flink-taskmanager`).
8. Verifies Flink JobManager restores checkpoint state and resumes stream processing.
9. Records post-recovery row count (`COUNT_AFTER_RESTART` and `COUNT_RECOVERED_2`) to confirm continuous growth.

### Empirical Recovery Test Results

```text
========================================
IceStream Day 12 Recovery Test
========================================

Kafka                          ✓
Flink JobManager               ✓
MinIO S3 Store                 ✓
Iceberg Catalog                ✓
Initial Flink status           RUNNING ✓

Starting continuous event stream generator...
Waiting for completed checkpoint in MinIO S3...
Checkpoint completed           ✓ (2 completed)
MinIO S3 Artifact              ✓

Count before failure           11270

Injecting Flink failure (Stopping TaskManager container)...
Failure injected               ✓
Restarting Flink TaskManager service...
Flink restarted                ✓
Checkpoint restored            ✓
Kafka resumed                  ✓
Iceberg resumed                ✓

Count after recovery           11270
Count post-recovery (T+10s)    12841
Recovery duration              7s
Count continues increasing     ✓
Duplicates observed            0

========================================
Recovery test               PASS
========================================
```

---

## Verification & Execution

To run the automated recovery test:

```bash
./scripts/day12_recovery_test.sh
```

To run the automated pytest suite:

```bash
./.venv/bin/pytest -v tests/streaming/test_reliability.py
```
