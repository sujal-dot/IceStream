#!/usr/bin/env bash
# ==============================================================================
# IceStream Kafka Topic Initialization Script
# ==============================================================================
# Creates and configures required Kafka topics in the local Kafka broker.
# Idempotent execution: safe to execute multiple times without erroring.
# ==============================================================================

set -euo pipefail

# Configuration parameters
CONTAINER_NAME="icestream-kafka"
BOOTSTRAP_SERVER="localhost:9092"

# Topic definition tuples: "name:partitions:retention_ms"
TOPICS=(
  "checkout-events:3:604800000"
  "checkout-valid:3:604800000"
  "checkout-invalid:3:1209600000"
  "checkout-dlq:3:2592000000"
  "pipeline-control:1:604800000"
  "schema-events:1:2592000000"
)

echo "Creating Kafka topics..."
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
    --replication-factor 1 \
    --config retention.ms="${RETENTION_MS}" \
    > /dev/null 2>&1

  echo "✓ ${TOPIC_NAME}"
done

echo ""
echo "Kafka topic initialization complete."
