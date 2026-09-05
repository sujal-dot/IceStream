import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { KpiCards } from '../KpiCards';
import { MetricsResponse, PipelineStatusResponse, QualityResponse } from '../../../types/dashboard';

const mockMetrics: MetricsResponse = {
  service: 'icestream-quality-engine',
  status: 'ok',
  timestamp: new Date().toISOString(),
  windows: {
    '1m': {
      window_seconds: 60,
      total_events: 2400,
      valid_events: 2380,
      failed_events: 20,
      error_rate: 0.0083,
      error_rate_percent: 0.83,
      health: 'HEALTHY',
      data_available: true,
    },
  },
  circuit_breaker: {
    state: 'CLOSED',
    enabled: true,
    can_process: true,
    can_probe: false,
    error_rate: 0.0083,
    threshold: 0.02,
  },
  remediation: {
    attempts: 0,
    successes: 0,
    failures: 0,
    recovered_events: 0,
  },
  pipeline_state: {
    uptime: '99.98%',
    kafka_lag: 142,
  },
};

const mockStatus: PipelineStatusResponse = {
  pipeline_id: 'icestream',
  state: 'HEALTHY',
  recovery_attempt: 0,
};

const mockQuality: QualityResponse = {
  overall_status: 'HEALTHY',
  windows: {},
  rules: { passed: 14, failed: 0 },
  severity: { critical: 0, high: 0, warning: 0 },
  total_events: 2400,
  valid_events: 2380,
  failed_events: 20,
  current_error_rate: 0.0083,
};

describe('KpiCards Component', () => {
  it('renders real backend metric values correctly', () => {
    render(
      <KpiCards
        metrics={mockMetrics}
        pipelineStatus={mockStatus}
        quality={mockQuality}
        isLoading={false}
      />
    );

    // Events/sec: 2400 / 60 = 40.0
    expect(screen.getByText('40.0')).toBeInTheDocument();
    // Error Rate: 0.83%
    expect(screen.getByText('0.83%')).toBeInTheDocument();
    // Kafka Lag: 142
    expect(screen.getByText('142')).toBeInTheDocument();
    // Pipeline Status: Healthy
    expect(screen.getByText('Healthy')).toBeInTheDocument();
    // Quarantined: 20
    expect(screen.getByText('20')).toBeInTheDocument();
    // Uptime: 99.98%
    expect(screen.getByText('99.98%')).toBeInTheDocument();
  });

  it('handles missing or unavailable metrics gracefully with N/A', () => {
    render(
      <KpiCards
        metrics={null}
        pipelineStatus={null}
        quality={null}
        isLoading={false}
      />
    );

    expect(screen.getAllByText('N/A').length).toBeGreaterThan(0);
  });
});
