import { NodeStatus } from '../types/lineage';

export interface StatusStyle {
  label: string;
  badgeBg: string;
  badgeText: string;
  borderColor: string;
  dotBg: string;
  glowColor: string;
  ariaLabel: string;
}

export const STATUS_STYLES: Record<string, StatusStyle> = {
  HEALTHY: {
    label: 'Healthy',
    badgeBg: '#10B9811A',
    badgeText: '#059669',
    borderColor: '#10B981',
    dotBg: '#10B981',
    glowColor: 'rgba(16, 185, 129, 0.25)',
    ariaLabel: 'Status: Healthy',
  },
  WARNING: {
    label: 'Warning',
    badgeBg: '#F59E0B1A',
    badgeText: '#D97706',
    borderColor: '#F59E0B',
    dotBg: '#F59E0B',
    glowColor: 'rgba(245, 158, 11, 0.25)',
    ariaLabel: 'Status: Warning',
  },
  DEGRADED: {
    label: 'Degraded',
    badgeBg: '#F59E0B1A',
    badgeText: '#D97706',
    borderColor: '#F59E0B',
    dotBg: '#F59E0B',
    glowColor: 'rgba(245, 158, 11, 0.25)',
    ariaLabel: 'Status: Degraded',
  },
  CRITICAL: {
    label: 'Critical',
    badgeBg: '#EF44441A',
    badgeText: '#DC2626',
    borderColor: '#EF4444',
    dotBg: '#EF4444',
    glowColor: 'rgba(239, 68, 68, 0.25)',
    ariaLabel: 'Status: Critical',
  },
  CIRCUIT_OPEN: {
    label: 'Circuit Open',
    badgeBg: '#EF44441A',
    badgeText: '#DC2626',
    borderColor: '#EF4444',
    dotBg: '#EF4444',
    glowColor: 'rgba(239, 68, 68, 0.25)',
    ariaLabel: 'Status: Circuit Open',
  },
  PAUSED: {
    label: 'Paused',
    badgeBg: '#6B72801A',
    badgeText: '#4B5563',
    borderColor: '#6B7280',
    dotBg: '#6B7280',
    glowColor: 'rgba(107, 114, 128, 0.2)',
    ariaLabel: 'Status: Paused',
  },
  ACTIVE: {
    label: 'Active',
    badgeBg: '#3B82F61A',
    badgeText: '#2563EB',
    borderColor: '#3B82F6',
    dotBg: '#3B82F6',
    glowColor: 'rgba(59, 130, 246, 0.25)',
    ariaLabel: 'Status: Active',
  },
  IDLE: {
    label: 'Idle',
    badgeBg: '#6B72801A',
    badgeText: '#6B7280',
    borderColor: '#4B5563',
    dotBg: '#6B7280',
    glowColor: 'transparent',
    ariaLabel: 'Status: Idle',
  },
  UNKNOWN: {
    label: 'Unknown',
    badgeBg: '#6B72801A',
    badgeText: '#9CA3AF',
    borderColor: '#4B5563',
    dotBg: '#9CA3AF',
    glowColor: 'transparent',
    ariaLabel: 'Status: Unknown',
  },
};

export function getStatusStyle(status?: string): StatusStyle {
  const upper = (status || 'UNKNOWN').toUpperCase();
  return STATUS_STYLES[upper] || STATUS_STYLES.UNKNOWN;
}
