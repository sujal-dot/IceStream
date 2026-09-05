import { QualityResponse } from '../types/dashboard';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

export class QualityApiService {
  /**
   * Fetch data quality overview and rule failure breakdowns.
   */
  static async getQuality(): Promise<QualityResponse> {
    const response = await fetch(`${BASE_URL}/quality`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch quality status: ${response.status} ${response.statusText}`);
    }

    return response.json();
  }
}
