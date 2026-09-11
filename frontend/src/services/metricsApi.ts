import { CircuitBreakerMetrics, MetricsResponse, SystemHealthResponse } from '../types/dashboard';

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

  /**
   * Fetch current authoritative circuit breaker machine status.
   */
  static async getCircuitBreakerStatus(): Promise<CircuitBreakerMetrics & Record<string, any>> {
    const response = await fetch(`${BASE_URL}/circuit-breaker`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch circuit breaker status: ${response.status} ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Fetch backend service & infrastructure dependency health status.
   */
  static async getSystemHealth(): Promise<SystemHealthResponse> {
    const response = await fetch(`${BASE_URL}/health`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch system health: ${response.status} ${response.statusText}`);
    }

    return response.json();
  }
}
