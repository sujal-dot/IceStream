import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { IncidentsPage } from '../IncidentsPage';
import { IncidentsApiService } from '../../services/incidentsApi';
import { PipelineApiService } from '../../services/pipelineApi';

vi.mock('../../services/incidentsApi', () => ({
  IncidentsApiService: { getIncidents: vi.fn() },
}));

vi.mock('../../services/pipelineApi', () => ({
  PipelineApiService: { getStatus: vi.fn() },
}));

describe('IncidentsPage Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders dedicated incident management view with stats and incident items', async () => {
    vi.mocked(PipelineApiService.getStatus).mockResolvedValue({
      pipeline_id: 'icestream',
      state: 'HEALTHY',
      recovery_attempt: 0,
    });

    vi.mocked(IncidentsApiService.getIncidents).mockResolvedValue({
      items: [
        {
          incident_id: 'INC-2026-001',
          pipeline_name: 'checkout-stream',
          pipeline_id: 'icestream',
          status: 'OPEN',
          severity: 'CRITICAL',
          error_rate: 0.05,
          threshold: 0.02,
          failed_records: 120,
          total_records: 1000,
          failed_event_count: 120,
          quarantine_count: 120,
          trigger: 'Circuit Breaker Open',
          trigger_type: 'CIRCUIT_OPEN',
          circuit_state: 'OPEN',
          slack_sent: false,
          created_at: new Date().toISOString(),
          recovery_attempt: 1,
        },
      ],
      total: 1,
    });

    render(<IncidentsPage />);

    expect(screen.getByText('Incidents & Remediation Center')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('INC-2026-001')).toBeInTheDocument();
      expect(screen.getByText('Circuit Breaker Open')).toBeInTheDocument();
    });
  });

  it('filters incidents by status tab', async () => {
    vi.mocked(IncidentsApiService.getIncidents).mockResolvedValue({
      items: [
        {
          incident_id: 'INC-OPEN-1',
          pipeline_name: 'checkout-stream',
          pipeline_id: 'icestream',
          status: 'OPEN',
          severity: 'CRITICAL',
          error_rate: 0.05,
          threshold: 0.02,
          failed_records: 10,
          total_records: 100,
          failed_event_count: 10,
          quarantine_count: 10,
          trigger: 'Error rate spiked',
          trigger_type: 'SPIKE',
          circuit_state: 'OPEN',
          slack_sent: false,
          created_at: new Date().toISOString(),
          recovery_attempt: 1,
        },
        {
          incident_id: 'INC-RESOLVED-1',
          pipeline_name: 'checkout-stream',
          pipeline_id: 'icestream',
          status: 'RESOLVED',
          severity: 'WARNING',
          error_rate: 0.01,
          threshold: 0.02,
          failed_records: 0,
          total_records: 100,
          failed_event_count: 0,
          quarantine_count: 0,
          trigger: 'Minor lag',
          trigger_type: 'LAG',
          circuit_state: 'CLOSED',
          slack_sent: false,
          created_at: new Date().toISOString(),
          recovery_attempt: 0,
        },
      ],
      total: 2,
    });

    render(<IncidentsPage />);

    await waitFor(() => {
      expect(screen.getByText('INC-OPEN-1')).toBeInTheDocument();
      expect(screen.getByText('INC-RESOLVED-1')).toBeInTheDocument();
    });

    // Click OPEN filter tab
    const openTab = screen.getByRole('button', { name: /^OPEN$/i });
    fireEvent.click(openTab);

    expect(screen.getByText('INC-OPEN-1')).toBeInTheDocument();
    expect(screen.queryByText('INC-RESOLVED-1')).not.toBeInTheDocument();
  });
});
