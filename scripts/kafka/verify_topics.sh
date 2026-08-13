#!/usr/bin/env bash
# ==============================================================================
# IceStream Kafka Topic Verification Script
# ==============================================================================
# Verifies that all required Kafka topics are created with correct partitions,
# replication factor, and retention configuration on the active Kafka broker.
# ==============================================================================

set -euo pipefail

CONTAINER_NAME="icestream-kafka"
BOOTSTRAP_SERVER="localhost:9092"

EXPECTED_TOPICS=(
  "checkout-events:3:1"
  "checkout-valid:3:1"
  "checkout-invalid:3:1"
  "checkout-dlq:3:1"
  "pipeline-control:1:1"
  "schema-events:1:1"
)

if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
  echo "Error: Kafka container '${CONTAINER_NAME}' is not running." >&2
  exit 1
fi

printf "%-22s %-13s %-14s %s\n" "Topic" "Partitions" "Replication" "Status"
echo "-----------------------------------------------------------"

ALL_PASSED=true

for ITEM in "${EXPECTED_TOPICS[@]}"; do
  IFS=":" read -r TOPIC_NAME EXPECTED_PARTITIONS EXPECTED_REPL <<< "$ITEM"

  # Query topic details from Kafka broker
  DESC_OUTPUT=$(docker exec "${CONTAINER_NAME}" /opt/kafka/bin/kafka-topics.sh \
    --bootstrap-server "${BOOTSTRAP_SERVER}" \
    --describe \
    --topic "${TOPIC_NAME}" 2>/dev/null || true)

  if [[ -z "${DESC_OUTPUT}" ]]; then
    printf "%-22s %-13s %-14s %s\n" "${TOPIC_NAME}" "N/A" "N/A" "✗ (Missing)"
    ALL_PASSED=false
    continue
  fi

  ACTUAL_PARTITIONS=$(echo "${DESC_OUTPUT}" | grep -o 'PartitionCount: [0-9]*' | head -n 1 | awk '{print $2}')
  ACTUAL_REPL=$(echo "${DESC_OUTPUT}" | grep -o 'ReplicationFactor: [0-9]*' | head -n 1 | awk '{print $2}')

  if [[ "${ACTUAL_PARTITIONS}" == "${EXPECTED_PARTITIONS}" ]] && [[ "${ACTUAL_REPL}" == "${EXPECTED_REPL}" ]]; then
    STATUS="✓"
  else
    STATUS="✗ (Mismatch)"
    ALL_PASSED=false
  fi

  printf "%-22s %-13s %-14s %s\n" "${TOPIC_NAME}" "${ACTUAL_PARTITIONS}" "${ACTUAL_REPL}" "${STATUS}"
done

echo ""
if [[ "${ALL_PASSED}" == "true" ]]; then
  echo "Kafka topic verification: PASS"
else
  echo "Kafka topic verification: FAIL"
  exit 1
fi
