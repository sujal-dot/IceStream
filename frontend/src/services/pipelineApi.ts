import { PipelineStatusResponse } from '../types/dashboard';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

export class PipelineApiService {
  /**
   * Fetch authoritative current pipeline state from backend.
   */
  static async getStatus(): Promise<PipelineStatusResponse> {
    const response = await fetch(`${BASE_URL}/pipeline/status`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch pipeline status: ${response.status} ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Pause pipeline operations.
   */
  static async pause(reason?: string): Promise<any> {
    const response = await fetch(`${BASE_URL}/pipeline/pause`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({ reason }),
    });

    if (!response.ok) {
      const errBody = await response.json().catch(() => ({}));
      throw new Error(errBody.detail || `Failed to pause pipeline: ${response.status}`);
    }

    return response.json();
  }

  /**
   * Resume pipeline operations.
   */
  static async resume(reason?: string): Promise<any> {
    const response = await fetch(`${BASE_URL}/pipeline/resume`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({ reason }),
    });

    if (!response.ok) {
      const errBody = await response.json().catch(() => ({}));
      throw new Error(errBody.detail || `Failed to resume pipeline: ${response.status}`);
    }

    return response.json();
  }

  /**
   * Trigger automated recovery flow.
   */
  static async recover(incidentId?: string): Promise<any> {
    const response = await fetch(`${BASE_URL}/pipeline/recover`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({ incident_id: incidentId }),
    });

    if (!response.ok) {
      const errBody = await response.json().catch(() => ({}));
      throw new Error(errBody.detail || `Failed to trigger recovery: ${response.status}`);
    }

    return response.json();
  }
}
