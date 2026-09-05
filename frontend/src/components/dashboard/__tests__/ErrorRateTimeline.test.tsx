import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { ErrorRateTimeline } from '../ErrorRateTimeline';
import { ErrorRateHistoryPoint } from '../../../types/dashboard';

const mockHistory: ErrorRateHistoryPoint[] = [
  {
    timestamp: '2026-09-05T10:00:00Z',
    error_rate: 0.005,
    error_rate_percent: 0.5,
    total_events: 1000,
    failed_events: 5,
    health: 'HEALTHY',
  },
  {
    timestamp: '2026-09-05T10:01:00Z',
    error_rate: 0.015,
    error_rate_percent: 1.5,
    total_events: 1000,
    failed_events: 15,
    health: 'WARNING',
  },
  {
    timestamp: '2026-09-05T10:02:00Z',
    error_rate: 0.035,
    error_rate_percent: 3.5,
    total_events: 1000,
    failed_events: 35,
    health: 'CRITICAL',
  },
];

describe('ErrorRateTimeline Component', () => {
  it('renders SVG chart with 2% threshold line when history is present', () => {
    render(<ErrorRateTimeline history={mockHistory} threshold={0.02} isLoading={false} />);

    expect(screen.getByText('Error Rate Timeline')).toBeInTheDocument();
    expect(screen.getByText('2% Circuit Threshold')).toBeInTheDocument();
  });

  it('renders clean empty state when no history data is available', () => {
    render(<ErrorRateTimeline history={[]} threshold={0.02} isLoading={false} />);

    expect(screen.getByText('Error rate history unavailable')).toBeInTheDocument();
    expect(
      screen.getByText(/Historical metrics are not currently available/i)
    ).toBeInTheDocument();
  });
});
