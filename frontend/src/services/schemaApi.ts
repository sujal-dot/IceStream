import { SchemaDriftResponse } from '../types/dashboard';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

export class SchemaApiService {
  /**
   * Fetch real schema drift details from backend.
   */
  static async getSchemaDrift(): Promise<SchemaDriftResponse> {
    const response = await fetch(`${BASE_URL}/schema/drift`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch schema drift: ${response.status} ${response.statusText}`);
    }

    return response.json();
  }
}
