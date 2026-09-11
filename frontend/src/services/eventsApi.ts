import { EventListResponse } from '../types/dashboard';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

export class EventsApiService {
  /**
   * Fetch sanitized event metadata list.
   */
  static async getEvents(limit: number = 50, offset: number = 0): Promise<EventListResponse> {
    const response = await fetch(`${BASE_URL}/events?limit=${limit}&offset=${offset}`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch events: ${response.status} ${response.statusText}`);
    }

    return response.json();
  }
}
