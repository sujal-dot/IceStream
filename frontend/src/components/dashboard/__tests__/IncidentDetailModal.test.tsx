import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { IncidentDetailModal } from '../IncidentDetailModal';
import { IncidentItem } from '../../../types/dashboard';
import { IncidentsApiService } from '../../../services/incidentsApi';

vi.mock('../../../services/incidentsApi', () => ({
  IncidentsApiService: {
    acknowledgeIncident: vi.fn(),
    resolveIncident: vi.fn(),
  },
}));

const mockIncident: IncidentItem = {
  incident_id: 'INC-2026-0905-0001',
  pipeline_name: 'checkout-stream',
  pipeline_id: 'icestream',
  status: 'OPEN',
  severity: 'CRITICAL',
  error_rate: 0.0372,
  threshold: 0.02,
  failed_records: 372,
  total_records: 10000,
  failed_event_count: 372,
  quarantine_count: 372,
  trigger: 'CRITICAL_ERROR_RATE',
  trigger_type: 'CRITICAL_ERROR_RATE',
  circuit_state: 'OPEN',
  action_taken: 'Downstream pipeline paused.',
  slack_sent: false,
  created_at: '2026-09-05T10:31:05Z',
  recovery_attempt: 1,
};

describe('IncidentDetailModal Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders incident details correctly', () => {
    render(
      <IncidentDetailModal
        incident={mockIncident}
        onClose={vi.fn()}
        onIncidentUpdated={vi.fn()}
      />
    );

    expect(screen.getByText('INC-2026-0905-0001')).toBeInTheDocument();
    expect(screen.getByText('CRITICAL')).toBeInTheDocument();
    expect(screen.getByText('3.72%')).toBeInTheDocument();
    expect(screen.getByText('372')).toBeInTheDocument();
    expect(screen.getByText('Downstream pipeline paused.')).toBeInTheDocument();
  });

  it('calls acknowledge API on button click', async () => {
    vi.mocked(IncidentsApiService.acknowledgeIncident).mockResolvedValue({
      incident_id: 'INC-2026-0905-0001',
      status: 'ACKNOWLEDGED',
      message: 'Acknowledged',
      updated_at: new Date().toISOString(),
      incident: { ...mockIncident, status: 'ACKNOWLEDGED' },
    });

    const onUpdateMock = vi.fn();
    render(
      <IncidentDetailModal
        incident={mockIncident}
        onClose={vi.fn()}
        onIncidentUpdated={onUpdateMock}
      />
    );

    const ackBtn = screen.getByRole('button', { name: /Acknowledge/i });
    fireEvent.click(ackBtn);

    await waitFor(() => {
      expect(IncidentsApiService.acknowledgeIncident).toHaveBeenCalledWith('INC-2026-0905-0001');
      expect(onUpdateMock).toHaveBeenCalled();
    });
  });

  it('displays backend error message when resolution fails due to open circuit breaker', async () => {
    vi.mocked(IncidentsApiService.resolveIncident).mockRejectedValue(
      new Error('Unable to resolve incident. The pipeline is still in CIRCUIT_OPEN state.')
    );

    render(
      <IncidentDetailModal
        incident={mockIncident}
        onClose={vi.fn()}
        onIncidentUpdated={vi.fn()}
      />
    );

    const resolveBtn = screen.getByRole('button', { name: /Resolve Incident/i });
    fireEvent.click(resolveBtn);

    await waitFor(() => {
      expect(
        screen.getByText(/The pipeline is still in CIRCUIT_OPEN state/i)
      ).toBeInTheDocument();
    });
  });
});
