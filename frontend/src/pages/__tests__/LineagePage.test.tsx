import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { LineagePage } from '../LineagePage';
import { LineageApiService } from '../../services/lineageApi';
import { ApiLineageResponse } from '../../types/lineage';

// Mock LineageApiService
vi.mock('../../services/lineageApi', () => ({
  LineageApiService: {
    getLineage: vi.fn(),
    getPipelineSummary: vi.fn(),
  },
}));

const mockLineageData: ApiLineageResponse = {
  nodes: [
    {
      id: 'kafka',
      type: 'source',
      label: 'Kafka',
      status: 'HEALTHY',
      details: { resource: 'checkout-events', description: 'Event ingestion stream' },
    },
    {
      id: 'flink',
      type: 'engine',
      label: 'Apache Flink',
      status: 'HEALTHY',
      details: { resource: 'Streaming Processor', description: 'Parse, validate, detect anomalies' },
    },
    {
      id: 'quality-engine',
      type: 'engine',
      label: 'Quality Engine',
      status: 'HEALTHY',
      details: { resource: 'Validate / Detect', description: 'Data quality validation' },
    },
    {
      id: 'iceberg-bronze',
      type: 'storage',
      label: 'Iceberg Bronze',
      status: 'HEALTHY',
      details: { resource: 'bronze.checkout_events', description: 'Raw validated event storage' },
    },
    {
      id: 'iceberg-silver',
      type: 'storage',
      label: 'Iceberg Silver',
      status: 'HEALTHY',
      details: { resource: 'silver.valid_checkout_events', description: 'Clean analytical event layer' },
    },
    {
      id: 'analytics',
      type: 'sink',
      label: 'Analytics',
      status: 'HEALTHY',
      details: { resource: 'Downstream Consumption', description: 'Downstream analytical consumption' },
    },
    {
      id: 'quarantine',
      type: 'quarantine',
      label: 'Quarantine',
      status: 'IDLE',
      details: { resource: 'quarantine.invalid_checkout_events', description: 'Quarantine storage' },
    },
    {
      id: 'dlq',
      type: 'dlq',
      label: 'DLQ',
      status: 'IDLE',
      details: { resource: 'checkout-dlq', description: 'Dead Letter Queue' },
    },
  ],
  edges: [
    { id: 'e1', source: 'kafka', target: 'flink', label: 'events' },
    { id: 'e2', source: 'flink', target: 'quality-engine', label: 'validated' },
    { id: 'e3', source: 'quality-engine', target: 'iceberg-bronze', label: 'valid' },
    { id: 'e4', source: 'iceberg-bronze', target: 'iceberg-silver', label: 'valid' },
    { id: 'e5', source: 'iceberg-silver', target: 'analytics', label: 'analytics' },
    { id: 'e6', source: 'quality-engine', target: 'quarantine', label: 'invalid' },
    { id: 'e7', source: 'quarantine', target: 'dlq', label: 'DLQ' },
  ],
};

describe('LineagePage Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('displays loading state initially', () => {
    vi.mocked(LineageApiService.getLineage).mockImplementation(
      () => new Promise(() => {}) // never resolves
    );

    render(<LineagePage />);
    expect(screen.getByText(/Loading pipeline lineage/i)).toBeInTheDocument();
  });

  it('renders lineage nodes when API call succeeds', async () => {
    vi.mocked(LineageApiService.getLineage).mockResolvedValue(mockLineageData);
    vi.mocked(LineageApiService.getPipelineSummary).mockResolvedValue({
      pipeline_id: 'icestream',
      state: 'RUNNING',
      circuit_breaker_state: 'CLOSED',
      error_rate: 0.005,
      open_incidents: 0,
    });

    render(<LineagePage />);

    await waitFor(() => {
      expect(screen.getByText('Kafka')).toBeInTheDocument();
      expect(screen.getByText('Apache Flink')).toBeInTheDocument();
      expect(screen.getByText('Quality Engine')).toBeInTheDocument();
      expect(screen.getByText('Iceberg Bronze')).toBeInTheDocument();
      expect(screen.getByText('Iceberg Silver')).toBeInTheDocument();
      expect(screen.getByText('Analytics')).toBeInTheDocument();
      expect(screen.getByText('Quarantine')).toBeInTheDocument();
      expect(screen.getByText('DLQ')).toBeInTheDocument();
    });
  });

  it('displays error state and retries on API failure', async () => {
    vi.mocked(LineageApiService.getLineage).mockRejectedValue(
      new Error('500 Internal Server Error')
    );

    render(<LineagePage />);

    await waitFor(() => {
      expect(screen.getByText(/Unable to load pipeline lineage/i)).toBeInTheDocument();
    });

    const retryButton = screen.getByRole('button', { name: /Retry Connection/i });
    expect(retryButton).toBeInTheDocument();

    // Now mock success for retry
    vi.mocked(LineageApiService.getLineage).mockResolvedValue(mockLineageData);

    fireEvent.click(retryButton);

    await waitFor(() => {
      expect(screen.getByText('Kafka')).toBeInTheDocument();
    });
  });
});
