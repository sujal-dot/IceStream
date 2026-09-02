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
                id="generator",
                type="source",
                label="E-Commerce Synthetic Event Generator",
                status="HEALTHY",
                details={"topic": "checkout-events", "rate": "200 eps"},
            ),
            LineageNode(
                id="kafka-checkout-events",
                type="queue",
                label="Kafka checkout-events Topic",
                status="HEALTHY",
                details={"partitions": "3", "retention": "7d"},
            ),
            LineageNode(
                id="flink-streaming",
                type="engine",
                label="Flink Streaming Ingestion Engine",
                status="HEALTHY",
                details={"checkpoint_interval": "10s", "parallelism": "2"},
            ),
            LineageNode(
                id="bronze-iceberg",
                type="storage",
                label="Bronze Apache Iceberg Raw Table",
                status="HEALTHY",
                details={"table": "bronze.checkout_events", "format": "Parquet"},
            ),
            LineageNode(
                id="quality-engine",
                type="engine",
                label="IceStream Quality Engine",
                status="HEALTHY" if pipe_state == "RUNNING" else "WARNING",
                details={"mode": "Hybrid (GE + Rules)", "rules": "14 active"},
            ),
            LineageNode(
                id="silver-iceberg",
                type="storage",
                label="Silver Apache Iceberg Validated Table",
                status="HEALTHY",
                details={"table": "silver.valid_checkout_events"},
            ),
            LineageNode(
                id="quarantine-table",
                type="quarantine",
                label="Quarantine Iceberg Dead Letter Table",
                status="ACTIVE" if pipe_state != "RUNNING" else "IDLE",
                details={"table": "quarantine.invalid_checkout_events"},
            ),
            LineageNode(
                id="error-rate-engine",
                type="observability",
                label="Error-Rate Engine (1m & 5m)",
                status="HEALTHY" if pipe_state == "RUNNING" else "CRITICAL",
                details={"healthy_threshold": "1%", "warning_threshold": "2%"},
            ),
            LineageNode(
                id="circuit-breaker",
                type="circuit_breaker",
                label="Authoritative Circuit Breaker",
                status=cb_state,
                details={"state": cb_state, "recovery_timeout": "30s"},
            ),
            LineageNode(
                id="remediation-controller",
                type="remediation",
                label="Self-Healing Remediation Controller",
                status=pipe_state,
                details={"pipeline_state": pipe_state},
            ),
        ]

        edges = [
            LineageEdge(
                id="generator-to-kafka",
                source="generator",
                target="kafka-checkout-events",
                label="Produces checkout events",
                animated=True,
            ),
            LineageEdge(
                id="kafka-to-flink",
                source="kafka-checkout-events",
                target="flink-streaming",
                label="Streams events",
                animated=True,
            ),
            LineageEdge(
                id="flink-to-bronze",
                source="flink-streaming",
                target="bronze-iceberg",
                label="Appends Parquet files",
                animated=True,
            ),
            LineageEdge(
                id="bronze-to-quality",
                source="bronze-iceberg",
                target="quality-engine",
                label="Validates batch events",
                animated=True,
            ),
            LineageEdge(
                id="quality-to-silver",
                source="quality-engine",
                target="silver-iceberg",
                label="Writes valid events",
            ),
            LineageEdge(
                id="quality-to-quarantine",
                source="quality-engine",
                target="quarantine-table",
                label="Quarantines invalid events",
            ),
            LineageEdge(
                id="quality-to-error-rate",
                source="quality-engine",
                target="error-rate-engine",
                label="Feeds validation summary",
            ),
            LineageEdge(
                id="error-rate-to-circuit",
                source="error-rate-engine",
                target="circuit-breaker",
                label="Evaluates health status",
            ),
            LineageEdge(
                id="circuit-to-remediation",
                source="circuit-breaker",
                target="remediation-controller",
                label="Triggers on OPEN circuit",
            ),
        ]

        return LineageResponse(nodes=nodes, edges=edges)
