"""Data lineage service supplying architectural and runtime state graph for React Flow."""

import logging
from typing import Dict, List, Optional
from backend.models.lineage import LineageEdge, LineageNode, LineageResponse

logger = logging.getLogger("icestream.services.lineage")


class LineageService:
    """Provides authoritative IceStream end-to-end data lineage structure."""

    def __init__(self, state_manager=None, error_rate_engine=None, circuit_breaker=None):
        self.state_manager = state_manager
        self.error_rate_engine = error_rate_engine
        self.circuit_breaker = circuit_breaker

    def get_lineage(self) -> LineageResponse:
        """Construct nodes and edges for React Flow frontend visualizer."""
        cb_state = "CLOSED"
        if self.circuit_breaker:
            cb_state = self.circuit_breaker.state.name

        pipe_state = "RUNNING"
        if self.state_manager:
            pipe_state = self.state_manager.get_state().get("state", "RUNNING")

        nodes = [
            LineageNode(
                id="kafka",
                type="source",
                label="Kafka",
                status="HEALTHY",
                details={
                    "resource": "checkout-events",
                    "topic": "checkout-events",
                    "description": "Event ingestion stream",
                    "partitions": "3",
                    "retention": "7d",
                },
            ),
            LineageNode(
                id="flink",
                type="engine",
                label="Apache Flink",
                status="HEALTHY" if pipe_state == "RUNNING" else "DEGRADED",
                details={
                    "resource": "Streaming Processor",
                    "subtitle": "Streaming processor",
                    "description": "Parse, validate, detect anomalies",
                    "checkpoint_interval": "10s",
                    "parallelism": "2",
                },
            ),
            LineageNode(
                id="quality-engine",
                type="engine",
                label="Quality Engine",
                status="HEALTHY" if pipe_state == "RUNNING" else ("CRITICAL" if cb_state == "OPEN" else "WARNING"),
                details={
                    "resource": "Validate / Detect",
                    "subtitle": "Data quality validation",
                    "description": "Data quality validation",
                    "mode": "Hybrid (GE + Rules)",
                    "rules": "14 active",
                },
            ),
            LineageNode(
                id="iceberg-bronze",
                type="storage",
                label="Iceberg Bronze",
                status="HEALTHY",
                details={
                    "resource": "bronze.checkout_events",
                    "table": "bronze.checkout_events",
                    "description": "Raw validated event storage",
                    "storage": "Apache Iceberg / MinIO",
                    "format": "Parquet",
                },
            ),
            LineageNode(
                id="iceberg-silver",
                type="storage",
                label="Iceberg Silver",
                status="HEALTHY",
                details={
                    "resource": "silver.valid_checkout_events",
                    "table": "silver.valid_checkout_events",
                    "description": "Clean analytical event layer",
                    "storage": "Apache Iceberg / MinIO",
                    "format": "Parquet",
                },
            ),
            LineageNode(
                id="analytics",
                type="sink",
                label="Analytics",
                status="HEALTHY",
                details={
                    "resource": "Downstream Consumption",
                    "description": "Downstream analytical consumption",
                    "engine": "Trino / Spark SQL",
                },
            ),
            LineageNode(
                id="quarantine",
                type="quarantine",
                label="Quarantine",
                status="ACTIVE" if pipe_state != "RUNNING" else "IDLE",
                details={
                    "resource": "quarantine.invalid_checkout_events",
                    "table": "quarantine.invalid_checkout_events",
                    "description": "Quarantine storage for invalid events",
                    "format": "Parquet",
                },
            ),
            LineageNode(
                id="dlq",
                type="dlq",
                label="DLQ",
                status="ACTIVE" if pipe_state != "RUNNING" else "IDLE",
                details={
                    "resource": "checkout-dlq",
                    "topic": "checkout-dlq",
                    "description": "Dead Letter Queue for unrecoverable events",
                },
            ),
            LineageNode(
                id="error-rate-engine",
                type="observability",
                label="Error-Rate Engine",
                status="HEALTHY" if pipe_state == "RUNNING" else "CRITICAL",
                details={
                    "resource": "1m & 5m window",
                    "description": "Real-time pipeline error rate calculator",
                    "healthy_threshold": "1%",
                    "warning_threshold": "2%",
                },
            ),
            LineageNode(
                id="circuit-breaker",
                type="circuit_breaker",
                label="Circuit Breaker",
                status=cb_state,
                details={
                    "resource": f"State: {cb_state}",
                    "state": cb_state,
                    "description": "Authoritative pipeline circuit breaker",
                    "recovery_timeout": "30s",
                },
            ),
            LineageNode(
                id="remediation-controller",
                type="remediation",
                label="Remediation Controller",
                status=pipe_state,
                details={
                    "resource": f"Pipeline: {pipe_state}",
                    "pipeline_state": pipe_state,
                    "description": "Self-healing automated remediation controller",
                },
            ),
        ]

        edges = [
            LineageEdge(
                id="kafka-to-flink",
                source="kafka",
                target="flink",
                label="events",
                animated=True,
            ),
            LineageEdge(
                id="flink-to-quality",
                source="flink",
                target="quality-engine",
                label="validated",
                animated=True,
            ),
            LineageEdge(
                id="quality-to-bronze",
                source="quality-engine",
                target="iceberg-bronze",
                label="valid",
                animated=True,
            ),
            LineageEdge(
                id="bronze-to-silver",
                source="iceberg-bronze",
                target="iceberg-silver",
                label="valid",
            ),
            LineageEdge(
                id="silver-to-analytics",
                source="iceberg-silver",
                target="analytics",
                label="analytics",
            ),
            LineageEdge(
                id="quality-to-quarantine",
                source="quality-engine",
                target="quarantine",
                label="invalid",
            ),
            LineageEdge(
                id="quarantine-to-dlq",
                source="quarantine",
                target="dlq",
                label="DLQ",
            ),
            LineageEdge(
                id="quality-to-error-rate",
                source="quality-engine",
                target="error-rate-engine",
                label="telemetry",
            ),
            LineageEdge(
                id="error-rate-to-circuit",
                source="error-rate-engine",
                target="circuit-breaker",
                label="health",
            ),
            LineageEdge(
                id="circuit-to-remediation",
                source="circuit-breaker",
                target="remediation-controller",
                label="remediate",
            ),
        ]

        return LineageResponse(nodes=nodes, edges=edges)
