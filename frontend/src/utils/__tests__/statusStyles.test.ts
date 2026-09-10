import { describe, it, expect } from 'vitest';
import { getStatusStyle, STATUS_STYLES } from '../statusStyles';

describe('statusStyles utility', () => {
  it('returns valid status style for all backend pipeline states', () => {
    const backendStates = [
      'RUNNING',
      'PAUSED',
      'DEGRADED',
      'QUARANTINING',
      'CIRCUIT_OPEN',
      'REMEDIATING',
      'REFETCHING',
      'REPROCESSING',
      'VALIDATING',
      'RESUMING',
      'RECOVERY_FAILED',
      'RECOVERED',
    ];

    backendStates.forEach((state) => {
      const style = getStatusStyle(state);
      expect(style).toBeDefined();
      expect(style.label).not.toBe('Unknown');
      expect(style).not.toEqual(STATUS_STYLES.UNKNOWN);
    });
  });

  it('correctly maps VALIDATING state', () => {
    const style = getStatusStyle('VALIDATING');
    expect(style.label).toBe('Validating');
    expect(style.badgeText).toBe('#2563EB');
  });

  it('falls back to UNKNOWN for invalid states', () => {
    const style = getStatusStyle('SOME_INVALID_STATE');
    expect(style.label).toBe('Unknown');
  });
});
