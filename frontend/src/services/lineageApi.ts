import { ApiLineageResponse, PipelineSummary } from '../types/lineage';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

export class LineageApiService {
  /**
   * Fetch primary end-to-end data lineage graph from backend FastAPI service.
   */
  static async getLineage(): Promise<ApiLineageResponse> {
    const response = await fetch(`${BASE_URL}/lineage`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch lineage: ${response.status} ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Optional helper to fetch aggregate pipeline status telemetry.
   */
  static async getPipelineSummary(): Promise<PipelineSummary | null> {
    try {
      const response = await fetch(`${BASE_URL}/pipeline/status`, {
        method: 'GET',
        headers: {
          'Accept': 'application/json',
        },
      });

      if (!response.ok) {
        return null;
      }

      return response.json();
    } catch {
      return null;
    }
  }
}
