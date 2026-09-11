/**
 * Dashboard & Incident Experience TypeScript Types for IceStream Telemetry.
 */

export type PipelineHealthState =
  | 'HEALTHY'
  | 'RUNNING'
  | 'PAUSED'
  | 'DEGRADED'
  | 'QUARANTINING'
  | 'CIRCUIT_OPEN'
  | 'REMEDIATING'
  | 'REFETCHING'
  | 'REPROCESSING'
  | 'VALIDATING'
  | 'RESUMING'
  | 'RECOVERED'
  | 'RECOVERY_FAILED'
  | 'UNKNOWN';

export type IncidentStatus = 'OPEN' | 'ACKNOWLEDGED' | 'RESOLVED';
export type IncidentSeverity = 'CRITICAL' | 'WARNING' | 'HEALTHY' | 'INFO';

export interface WindowMetric {
  window_seconds: number;
  window_start?: string;
  window_end?: string;
  total_events: number;
  valid_events: number;
  failed_events: number;
  error_rate: number;
  error_rate_percent: number;
  health: string;
  data_available: boolean;
}

export interface CircuitBreakerMetrics {
  state: 'CLOSED' | 'OPEN' | 'HALF_OPEN';
  enabled: boolean;
  can_process: boolean;
  can_probe: boolean;
  error_rate: number;
  threshold: number;
}

export interface RemediationMetrics {
  attempts: number;
  successes: number;
  failures: number;
  recovered_events: number;
}

export interface ErrorRateHistoryPoint {
  timestamp: string;
  error_rate: number;
  error_rate_percent: number;
  total_events: number;
  failed_events: number;
  health: string;
}

export interface MetricsResponse {
  service: string;
  status: string;
  timestamp: string;
  windows: Record<string, WindowMetric>;
  circuit_breaker: CircuitBreakerMetrics;
  remediation: RemediationMetrics;
  pipeline_state?: Record<string, any>;
  history?: ErrorRateHistoryPoint[];
}

export interface PipelineStatusResponse {
  pipeline_id: string;
  state: string;
  previous_state?: string;
  reason?: string;
  incident_id?: string;
  recovery_attempt: number;
  stage?: string;
  last_error?: string;
  updated_at?: string;
}

export interface IncidentItem {
  incident_id: string;
  pipeline_name: string;
  pipeline_id: string;
  status: IncidentStatus;
  severity: IncidentSeverity;
  error_rate: number;
  threshold: number;
  failed_records: number;
  total_records: number;
  failed_event_count: number;
  quarantine_count: number;
  trigger: string;
  trigger_type: string;
  circuit_state: string;
  action_taken?: string;
  message?: string;
  slack_sent: boolean;
  slack_sent_at?: string;
  slack_error?: string;
  detected_at?: string;
  created_at: string;
  updated_at?: string;
  resolved_at?: string;
  recovery_attempt: number;
  last_error?: string;
}

export interface IncidentListResponse {
  items: IncidentItem[];
  total: number;
}

export interface IncidentDetailResponse {
  incident: IncidentItem;
  circuit_state: string;
  remediation_stage: string;
  recovery_attempts: number;
  attempts_history: Record<string, any>[];
  resolved_at?: string;
}

export interface IncidentActionResponse {
  incident_id: string;
  status: string;
  message: string;
  updated_at: string;
  incident: IncidentItem;
}

export interface QualityResponse {
  overall_status: string;
  windows: Record<string, any>;
  rules: {
    passed: number;
    failed: number;
  };
  severity: {
    critical: number;
    high: number;
    warning: number;
  };
  total_events: number;
  valid_events: number;
  failed_events: number;
  current_error_rate: number;
  top_failures?: Record<string, number>;
}

export type NavView =
  | 'dashboard'
  | 'pipeline'
  | 'lineage'
  | 'quality'
  | 'schema'
  | 'quarantine'
  | 'iceberg'
  | 'events'
  | 'incidents'
  | 'system-health'
  | 'settings';

export interface SystemHealthResponse {
  status: string;
  service: string;
  version: string;
  timestamp: string;
  dependencies: Record<string, string>;
}

export interface SchemaChangeItem {
  field: string;
  change: string;
  expected?: string;
  actual?: string;
}

export interface SchemaDriftResponse {
  drift_detected: boolean;
  current_version: string;
  previous_version: string;
  severity: string;
  changes: SchemaChangeItem[];
  timestamp: string;
}

export interface EventItem {
  event_id: string;
  event_timestamp: string;
  order_id: string;
  currency: string;
  amount: number;
  payment_status: string;
  status: string;
  failure_reason?: string;
  schema_version?: string;
  payload_json?: string;
}

export interface EventListResponse {
  items: EventItem[];
  total: number;
}
