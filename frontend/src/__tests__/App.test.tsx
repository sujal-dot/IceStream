import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import App from '../App';
import { MetricsApiService } from '../services/metricsApi';
import { PipelineApiService } from '../services/pipelineApi';
import { LineageApiService } from '../services/lineageApi';
import { IncidentsApiService } from '../services/incidentsApi';
import { QualityApiService } from '../services/qualityApi';

vi.mock('../services/metricsApi', () => ({
  MetricsApiService: { getMetrics: vi.fn() },
}));

vi.mock('../services/pipelineApi', () => ({
  PipelineApiService: { getStatus: vi.fn() },
}));

vi.mock('../services/lineageApi', () => ({
  LineageApiService: { getLineage: vi.fn(), getPipelineSummary: vi.fn() },
}));

vi.mock('../services/incidentsApi', () => ({
  IncidentsApiService: { getIncidents: vi.fn() },
}));

vi.mock('../services/qualityApi', () => ({
  QualityApiService: { getQuality: vi.fn() },
}));

describe('App Navigation Integration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.history.pushState({}, '', '/');

    vi.mocked(PipelineApiService.getStatus).mockResolvedValue({
      pipeline_id: 'icestream',
      state: 'HEALTHY',
      recovery_attempt: 0,
    });

    vi.mocked(MetricsApiService.getMetrics).mockResolvedValue({
      service: 'icestream-quality-engine',
      status: 'ok',
      timestamp: new Date().toISOString(),
      windows: {
        '1m': {
          window_seconds: 60,
          total_events: 3000,
          valid_events: 2980,
          failed_events: 20,
          error_rate: 0.0066,
          error_rate_percent: 0.66,
          health: 'HEALTHY',
          data_available: true,
        },
      },
      circuit_breaker: {
        state: 'CLOSED',
        enabled: true,
        can_process: true,
        can_probe: false,
        error_rate: 0.0066,
        threshold: 0.02,
      },
      remediation: { attempts: 0, successes: 0, failures: 0, recovered_events: 0 },
      pipeline_state: { uptime: '99.99%', kafka_lag: 50 },
      history: [],
    });

    vi.mocked(LineageApiService.getLineage).mockResolvedValue({
      nodes: [
        { id: 'kafka', type: 'source', label: 'Kafka', status: 'HEALTHY' },
        { id: 'flink', type: 'engine', label: 'Apache Flink', status: 'HEALTHY' },
      ],
      edges: [{ id: 'e1', source: 'kafka', target: 'flink' }],
    });

    vi.mocked(LineageApiService.getPipelineSummary).mockResolvedValue({
      pipeline_id: 'icestream',
      state: 'RUNNING',
      circuit_breaker_state: 'CLOSED',
      error_rate: 0.005,
      open_incidents: 0,
    });

    vi.mocked(IncidentsApiService.getIncidents).mockResolvedValue({
      items: [],
      total: 0,
    });

    vi.mocked(QualityApiService.getQuality).mockResolvedValue({
      overall_status: 'HEALTHY',
      windows: {},
      rules: { passed: 14, failed: 0 },
      severity: { critical: 0, high: 0, warning: 0 },
      total_events: 3000,
      valid_events: 2980,
      failed_events: 20,
      current_error_rate: 0.0066,
    });
  });

  it('allows seamless navigation from Dashboard to Lineage DAG and back without page refresh', async () => {
    render(<App />);

    // Initially on Dashboard
    await waitFor(() => {
      expect(screen.getByText('Error Rate Timeline')).toBeInTheDocument();
    });

    // Click 'Lineage DAG' in top nav header
    const lineageNavBtn = screen.getByRole('button', { name: /Lineage DAG/i });
    fireEvent.click(lineageNavBtn);

    // Now on LineagePage with Header and Back button present
    await waitFor(() => {
      expect(screen.getByText('Back to Dashboard')).toBeInTheDocument();
      expect(screen.getByText('Pipeline Lineage')).toBeInTheDocument();
    });

    // Click 'Back to Dashboard' button
    const backBtn = screen.getByText('Back to Dashboard');
    fireEvent.click(backBtn);

    // Returns to Dashboard
    await waitFor(() => {
      expect(screen.getByText('Error Rate Timeline')).toBeInTheDocument();
    });
  });
});
