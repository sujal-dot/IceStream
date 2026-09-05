import {
  IncidentActionResponse,
  IncidentDetailResponse,
  IncidentListResponse,
} from '../types/dashboard';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

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
      headers: {
        'Accept': 'application/json',
      },
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
      headers: {
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      const errBody = await response.json().catch(() => ({}));
      const msg = errBody.detail || `Failed to resolve incident: ${response.status} ${response.statusText}`;
      throw new Error(msg);
    }

    return response.json();
  }
}
