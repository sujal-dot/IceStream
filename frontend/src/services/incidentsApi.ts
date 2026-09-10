import {
  IncidentActionResponse,
  IncidentDetailResponse,
  IncidentListResponse,
} from '../types/dashboard';
import { ApiTokenManager } from './apiTokenManager';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

const getAuthHeaders = (): Record<string, string> => {
  return ApiTokenManager.getAuthHeaders();
};

export class IncidentsApiService {
  /**
   * List pipeline incidents with optional status and severity filtering.
   */
  static async getIncidents(
    statusFilter?: string,
    severityFilter?: string,
    limit: number = 50,
    offset: number = 0
  ): Promise<IncidentListResponse> {
    const params = new URLSearchParams();
    if (statusFilter) params.append('status', statusFilter);
    if (severityFilter) params.append('severity', severityFilter);
    params.append('limit', limit.toString());
    params.append('offset', offset.toString());

    const response = await fetch(`${BASE_URL}/incidents?${params.toString()}`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch incidents: ${response.status} ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Get detailed record for a specific incident.
   */
  static async getIncidentDetail(incidentId: string): Promise<IncidentDetailResponse> {
    const response = await fetch(`${BASE_URL}/incidents/${encodeURIComponent(incidentId)}`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch incident ${incidentId}: ${response.status} ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Acknowledge an open incident (OPEN -> ACKNOWLEDGED).
   */
  static async acknowledgeIncident(incidentId: string): Promise<IncidentActionResponse> {
    const response = await fetch(`${BASE_URL}/incidents/${encodeURIComponent(incidentId)}/acknowledge`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });

    if (!response.ok) {
      const errBody = await response.json().catch(() => ({}));
      const msg = errBody.detail || `Failed to acknowledge incident: ${response.status} ${response.statusText}`;
      throw new Error(msg);
    }

    return response.json();
  }

  /**
   * Resolve an incident (ACKNOWLEDGED/OPEN -> RESOLVED).
   * Backend will reject if circuit breaker is still OPEN or pipeline is unhealthy.
   */
  static async resolveIncident(incidentId: string): Promise<IncidentActionResponse> {
    const response = await fetch(`${BASE_URL}/incidents/${encodeURIComponent(incidentId)}/resolve`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });

    if (!response.ok) {
      const errBody = await response.json().catch(() => ({}));
      const msg = errBody.detail || `Failed to resolve incident: ${response.status} ${response.statusText}`;
      throw new Error(msg);
    }

    return response.json();
  }

  /**
   * Trigger / generate a test incident in active backend server.
   */
  static async triggerTestIncident(triggerName: string = 'NULL_FIELD_SPIKE'): Promise<any> {
    const response = await fetch(`${BASE_URL}/incidents/trigger`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({
        trigger: triggerName,
        error_rate: 0.045,
        failed_event_count: 45,
        quarantine_count: 45,
      }),
    });

    if (!response.ok) {
      const errBody = await response.json().catch(() => ({}));
      const msg = errBody.detail || `Failed to trigger test incident: ${response.status} ${response.statusText}`;
      throw new Error(msg);
    }

    return response.json();
  }
}
