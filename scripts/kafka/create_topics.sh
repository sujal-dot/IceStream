#!/usr/bin/env bash
# ==============================================================================
# IceStream Kafka Topic Initialization Script (HA Ready: RF=3, min.isr=2)
# ==============================================================================
# Creates and configures required Kafka topics across Kafka brokers.
# Idempotent execution: safe to execute multiple times without erroring.
# ==============================================================================

set -euo pipefail

# Configuration parameters
CONTAINER_NAME="${KAFKA_CONTAINER_NAME:-icestream-kafka}"
BOOTSTRAP_SERVER="${KAFKA_BOOTSTRAP_SERVER:-localhost:9092}"
REPLICATION_FACTOR="${KAFKA_REPLICATION_FACTOR:-3}"
MIN_ISR="${KAFKA_MIN_ISR:-2}"

# Auto-detect broker count if possible
if command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
  BROKER_COUNT=$(docker exec "${CONTAINER_NAME}" /opt/kafka/bin/kafka-broker-api-versions.sh --bootstrap-server localhost:9092 2>/dev/null | grep -c "id:" || echo 1)
  if [ "${BROKER_COUNT}" -lt "${REPLICATION_FACTOR}" ]; then
    echo "Notice: Detected ${BROKER_COUNT} broker(s). Adjusting replication-factor to ${BROKER_COUNT} for local execution."
    REPLICATION_FACTOR="${BROKER_COUNT}"
    MIN_ISR=1
  fi
fi

# Topic definition tuples: "name:partitions:retention_ms"
TOPICS=(
  "checkout-events:3:604800000"
  "checkout-valid:3:604800000"
  "checkout-invalid:3:1209600000"
  "checkout-dlq:3:2592000000"
  "pipeline-control:1:604800000"
  "schema-events:1:2592000000"
)

echo "Initializing High Availability Kafka Topics (RF=${REPLICATION_FACTOR}, min.isr=${MIN_ISR})..."
echo ""

# Helper to check container state
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
  echo "Error: Kafka container '${CONTAINER_NAME}' is not running." >&2
  exit 1
fi

for ITEM in "${TOPICS[@]}"; do
  IFS=":" read -r TOPIC_NAME PARTITIONS RETENTION_MS <<< "$ITEM"

  # Execute kafka-topics command inside container with --if-not-exists
  docker exec "${CONTAINER_NAME}" /opt/kafka/bin/kafka-topics.sh \
    --bootstrap-server "${BOOTSTRAP_SERVER}" \
    --create \
    --if-not-exists \
    --topic "${TOPIC_NAME}" \
    --partitions "${PARTITIONS}" \
    --replication-factor "${REPLICATION_FACTOR}" \
    --config min.insync.replicas="${MIN_ISR}" \
    --config retention.ms="${RETENTION_MS}" \
    > /dev/null 2>&1

  echo "✓ ${TOPIC_NAME} (Partitions: ${PARTITIONS}, RF: ${REPLICATION_FACTOR}, Min.ISR: ${MIN_ISR})"
done

echo ""
echo "Kafka topic initialization complete."
