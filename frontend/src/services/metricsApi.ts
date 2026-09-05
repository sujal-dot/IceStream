import { MetricsResponse } from '../types/dashboard';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

export class MetricsApiService {
  /**
   * Fetch aggregated real-time metrics, circuit breaker status, and error rate history.
   */
  static async getMetrics(): Promise<MetricsResponse> {
    const response = await fetch(`${BASE_URL}/metrics`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch metrics: ${response.status} ${response.statusText}`);
    }

    return response.json();
  }
}
