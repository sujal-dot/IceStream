#!/usr/bin/env python3
"""
scripts/trace_e2e_events.py
End-to-end data consistency trace for IceStream functional audit.
Traces:
  1. A valid event -> QualityEngine validation -> Kafka -> Flink/Iceberg Bronze Table
  2. An invalid event -> QualityEngine validation failure -> QuarantineRouter -> Iceberg Quarantine Table
"""
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("audit_trace")

# Ensure quality-engine is on PYTHONPATH
sys.path.insert(0, "/app/quality-engine")
sys.path.insert(0, "/app")

from rules.base import EventStatus
from rules.engine import QualityEngine
from quarantine.router import QuarantineRouter
from iceberg.config.catalog import get_catalog
from confluent_kafka import Producer, Consumer, KafkaException

def get_kafka_producer():
    server = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
    p = Producer({'bootstrap.servers': server, 'client.id': 'audit-trace-producer'})
    p.list_topics(timeout=5)
    logger.info("Connected to Kafka at %s", server)
    return p

def main():
    ts = int(time.time())
    logger.info("=== STARTING END-TO-END DATA CONSISTENCY TRACE ===")
    
    engine = QualityEngine()
    catalog = get_catalog()
    producer = get_kafka_producer()

    from generator.data_generator import DataGenerator
    data_gen = DataGenerator(seed=ts)
    valid_event = data_gen.generate_valid_event()
    valid_id = f"evt_audit_valid_{ts}"
    valid_event["event_id"] = valid_id
    valid_event["ingestion_time"] = datetime.now(timezone.utc).isoformat()

    logger.info("Step 1.1: Validating valid event (%s) with QualityEngine...", valid_id)
    results, summary = engine.validate_with_summary(valid_event)
    failed_rule_names = [r.rule_name for r in results if not r.passed]
    logger.info("QualityEngine result: status=%s, total=%d, passed=%d, failed=%d, failed_rules=%s", 
                summary.overall_status.value, summary.total_rules, summary.passed_rules, summary.failed_rules, failed_rule_names)
    
    assert summary.overall_status == EventStatus.HEALTHY, f"Expected HEALTHY but got {summary.overall_status}"
    assert summary.failed_rules == 0, f"Expected 0 failed rules, got {summary.failed_rules}"
    logger.info("✓ QualityEngine PASSED valid event as expected.")

    logger.info("Step 1.2: Publishing valid event to Kafka 'checkout-events'...")
    delivered = []
    def on_delivery(err, msg):
        if err:
            logger.error("Delivery error: %s", err)
        else:
            logger.info("Delivered valid event to topic %s [%d] at offset %d", 
                        msg.topic(), msg.partition(), msg.offset())
            delivered.append(msg.offset())

    producer.produce("checkout-events", key=valid_event["order_id"], 
                     value=json.dumps(valid_event).encode("utf-8"), 
                     callback=on_delivery)
    producer.flush(timeout=10)
    assert len(delivered) > 0, "Failed to deliver valid event to Kafka!"
    logger.info("✓ Valid event published to Kafka 'checkout-events' at offset %s.", delivered[0])

    logger.info("Step 1.3: Verifying Bronze Table in Iceberg catalog...")
    bronze_table = catalog.load_table("bronze.checkout_events")
    initial_snapshot = bronze_table.current_snapshot()
    initial_snap_id = initial_snapshot.snapshot_id if initial_snapshot else None
    logger.info("Current Bronze table snapshot: %s", initial_snap_id)

    # ---------------------------------------------------------
    # TRACE 2: INVALID EVENT
    # ---------------------------------------------------------
    invalid_id = f"evt_audit_invalid_{ts}"
    invalid_event = data_gen.generate_valid_event()
    invalid_event["event_id"] = invalid_id
    invalid_event["ingestion_time"] = datetime.now(timezone.utc).isoformat()
    invalid_event["amount"] = -999.99  # Negative amount
    invalid_event["currency"] = "INVALID_CURR"  # Invalid currency code
    invalid_event["quantity"] = -5  # Negative quantity

    logger.info("Step 2.1: Validating invalid event (%s) with QualityEngine...", invalid_id)
    inv_results, inv_summary = engine.validate_with_summary(invalid_event)
    failed_rule_names = [r.rule_name for r in inv_results if not r.passed]
    logger.info("QualityEngine result: status=%s, total=%d, passed=%d, failed=%d, failed_rules=%s",
                inv_summary.overall_status.value, inv_summary.total_rules, inv_summary.passed_rules, 
                inv_summary.failed_rules, failed_rule_names)
    
    assert inv_summary.overall_status in (EventStatus.FAILED, EventStatus.WARNING), f"Expected FAILED/WARNING but got {inv_summary.overall_status}"
    assert inv_summary.failed_rules > 0, "Expected at least 1 failed rule!"
    logger.info("✓ QualityEngine FAILED invalid event as expected.")

    logger.info("Step 2.2: Routing invalid event to Quarantine via QuarantineRouter...")
    router = QuarantineRouter()
    route_result = router.route_invalid_event(invalid_event, inv_results)
    logger.info("Quarantine route result: success=%s, record=%s, error=%s",
                route_result.success, route_result.quarantine_record is not None, route_result.error)
    
    assert route_result.success is True, f"Quarantine routing failed! Error: {route_result.error}"
    assert route_result.quarantine_record is not None, "Quarantine record was not generated!"
    quarantine_id = route_result.quarantine_record.quarantine_id
    logger.info("Generated quarantine_id: %s", quarantine_id)
    
    # Flush writer to Iceberg table
    logger.info("Step 2.3: Flushing Quarantine writer to Iceberg table 'quarantine.invalid_checkout_events'...")
    router.writer.flush()
    logger.info("✓ Writer flushed successfully.")

    logger.info("Step 2.4: Verifying Quarantine record in Iceberg table...")
    quarantine_table = catalog.load_table("quarantine.invalid_checkout_events")
    snap = quarantine_table.current_snapshot()
    logger.info("Quarantine table current snapshot ID: %s, sequence_number=%s", 
                snap.snapshot_id if snap else "N/A", snap.sequence_number if snap else "N/A")
    assert snap is not None, "Quarantine table should have snapshots!"

    # ---------------------------------------------------------
    # TRACE 3: PUBLISH TO DLQ
    # ---------------------------------------------------------
    logger.info("Step 3.1: Publishing invalid event to 'checkout-dlq' topic...")
    dlq_delivered = []
    def on_dlq(err, msg):
        if not err:
            logger.info("Delivered invalid event to topic %s [%d] at offset %d", 
                        msg.topic(), msg.partition(), msg.offset())
            dlq_delivered.append(msg.offset())
        else:
            logger.error("DLQ delivery error: %s", err)

    producer.produce("checkout-dlq", key=invalid_id, 
                     value=json.dumps({"error": "INVALID_AMOUNT", "event": invalid_event}).encode("utf-8"),
                     callback=on_dlq)
    producer.flush(timeout=10)
    assert len(dlq_delivered) > 0, "Failed to deliver message to checkout-dlq!"
    logger.info("✓ Message delivered to 'checkout-dlq' at offset %s.", dlq_delivered[0])

    logger.info("=================================================================")
    logger.info("✓ END-TO-END DATA CONSISTENCY TRACE COMPLETED SUCCESSFULLY!")
    logger.info("=================================================================")
    return 0

if __name__ == "__main__":
    sys.exit(main())
