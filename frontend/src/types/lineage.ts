/**
 * Data Lineage TypeScript Types matching IceStream Telemetry Backend specifications.
 */

export type NodeStatus =
  | 'HEALTHY'
  | 'WARNING'
  | 'DEGRADED'
  | 'CRITICAL'
  | 'CIRCUIT_OPEN'
  | 'PAUSED'
  | 'UNKNOWN'
  | 'IDLE'
  | 'ACTIVE';

export type NodeType =
  | 'source'
  | 'queue'
  | 'engine'
  | 'storage'
  | 'quarantine'
  | 'dlq'
  | 'sink'
  | 'observability'
  | 'circuit_breaker'
  | 'remediation';

export interface LineageNodeData {
  label: string;
  type: string;
  status: NodeStatus;
  details?: Record<string, string>;
  selected?: boolean;
}

export interface ApiLineageNode {
  id: string;
  type: string;
  label: string;
  status?: string;
  details?: Record<string, string>;
}

export interface ApiLineageEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
  animated?: boolean;
}

export interface ApiLineageResponse {
  nodes: ApiLineageNode[];
  edges: ApiLineageEdge[];
}

export interface PipelineSummary {
  pipeline_id: string;
  state: string;
  circuit_breaker_state: string;
  error_rate: number;
  open_incidents: number;
  last_updated?: string;
}
