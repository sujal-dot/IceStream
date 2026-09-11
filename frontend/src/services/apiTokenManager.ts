/**
 * Dynamic API Token Manager for IceStream Frontend.
 *
 * Prevents embedding sensitive API keys in static client-side JavaScript bundles.
 * Tokens are managed dynamically at runtime via sessionStorage or explicit configuration.
 */

const TOKEN_STORAGE_KEY = 'icestream_api_token';

let inMemoryToken: string | null = null;

export class ApiTokenManager {
  /**
   * Retrieve the current authorization Bearer token.
   */
  static getToken(): string | null {
    if (inMemoryToken) {
      return inMemoryToken;
    }
    try {
      return sessionStorage.getItem(TOKEN_STORAGE_KEY) || null;
    } catch {
      return null;
    }
  }

  /**
   * Check if a custom authorization token is configured.
   */
  static hasToken(): boolean {
    return Boolean(ApiTokenManager.getToken());
  }

  /**
   * Set or update the active authorization Bearer token.
   */
  static setToken(token: string): void {
    const trimmed = typeof token === 'string' ? token.trim() : '';
    inMemoryToken = trimmed;
    try {
      sessionStorage.setItem(TOKEN_STORAGE_KEY, trimmed);
    } catch {
      // Fallback to in-memory storage if sessionStorage is blocked
    }
  }

  /**
   * Clear the stored authorization token.
   */
  static clearToken(): void {
    inMemoryToken = null;
    try {
      sessionStorage.removeItem(TOKEN_STORAGE_KEY);
    } catch {
      // Ignore storage errors
    }
  }

  /**
   * Helper method to generate HTTP request authorization headers.
   */
  static getAuthHeaders(): Record<string, string> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    };
    const token = ApiTokenManager.getToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
  }
}
