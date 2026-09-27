import { PipelineStatusResponse } from '../types/dashboard';
import { ApiTokenManager } from './apiTokenManager';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

const getAuthHeaders = (): Record<string, string> => {
  return ApiTokenManager.getAuthHeaders();
};

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
    try {
      const response = await fetch(`${BASE_URL}/pipeline/pause`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ reason }),
      });

      if (!response.ok) {
        const errBody = await response.json().catch(() => ({}));
        const msg = typeof errBody.detail === 'string'
          ? errBody.detail
          : (errBody.detail?.message || errBody.message || `Failed to pause pipeline: ${response.status}`);
        throw new Error(msg);
      }

      return response.json();
    } catch (err: any) {
      if (err.name === 'TypeError' || err.message === 'Failed to fetch') {
        throw new Error('FastAPI backend is offline (http://localhost:8000). Run ./start.sh to start all services.');
      }
      throw err;
    }
  }

  /**
   * Resume pipeline operations.
   */
  static async resume(reason?: string): Promise<any> {
    try {
      const response = await fetch(`${BASE_URL}/pipeline/resume`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ reason }),
      });

      if (!response.ok) {
        const errBody = await response.json().catch(() => ({}));
        const msg = typeof errBody.detail === 'string'
          ? errBody.detail
          : (errBody.detail?.message || errBody.message || `Failed to resume pipeline: ${response.status}`);
        throw new Error(msg);
      }

      return response.json();
    } catch (err: any) {
      if (err.name === 'TypeError' || err.message === 'Failed to fetch') {
        throw new Error('FastAPI backend is offline (http://localhost:8000). Run ./start.sh to start all services.');
      }
      throw err;
    }
  }

  /**
   * Trigger automated recovery flow.
   */
  static async recover(incidentId?: string): Promise<any> {
    try {
      const response = await fetch(`${BASE_URL}/pipeline/recover`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ incident_id: incidentId }),
      });

      if (!response.ok) {
        const errBody = await response.json().catch(() => ({}));
        const msg = typeof errBody.detail === 'string'
          ? errBody.detail
          : (errBody.detail?.message || errBody.message || `Failed to trigger recovery: ${response.status}`);
        throw new Error(msg);
      }

      return response.json();
    } catch (err: any) {
      if (err.name === 'TypeError' || err.message === 'Failed to fetch') {
        throw new Error('FastAPI backend is offline (http://localhost:8000). Run ./start.sh to start all services.');
      }
      throw err;
    }
  }
}
