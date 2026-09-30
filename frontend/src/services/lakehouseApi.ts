import { ApiTokenManager } from './apiTokenManager';

export interface TableHealth {
  table_name: string;
  exists: boolean;
  total_files: number;
  total_records: number;
  total_bytes: number;
  avg_file_size_bytes: number;
  small_files_count: number;
  snapshot_count: number;
  fragmentation_status: string;
  partition_count: number;
  current_snapshot_id: number | string | null;
  last_updated_at: string | null;
}

export interface MaintenanceHistoryItem {
  id: string;
  table_name: string;
  operation: string;
  status: string;
  files_before: number;
  files_after: number;
  records_compacted: number;
  snapshots_expired: number;
  orphan_files_deleted: number;
  bytes_reclaimed: number;
  duration_ms: number;
  error?: string | null;
  started_at: string;
  completed_at?: string | null;
}

export interface MaintenanceHistoryResponse {
  runs: MaintenanceHistoryItem[];
  total: number;
}

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

export class LakehouseApiService {
  /**
   * Fetch diagnostic health metrics across all registered lakehouse tables.
   */
  static async getLakehouseHealth(): Promise<TableHealth[]> {
    const headers: Record<string, string> = {
      'Accept': 'application/json',
    };
    const token = ApiTokenManager.getToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${BASE_URL}/lakehouse/health`, {
      method: 'GET',
      headers,
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch lakehouse health: ${response.status} ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Fetch audit history of lakehouse maintenance operations.
   */
  static async getMaintenanceHistory(tableName?: string, limit: number = 50): Promise<MaintenanceHistoryResponse> {
    const headers: Record<string, string> = {
      'Accept': 'application/json',
    };
    const token = ApiTokenManager.getToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    let url = `${BASE_URL}/lakehouse/maintenance/history?limit=${limit}`;
    if (tableName) {
      url += `&table_name=${encodeURIComponent(tableName)}`;
    }

    const response = await fetch(url, {
      method: 'GET',
      headers,
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch maintenance history: ${response.status} ${response.statusText}`);
    }

    return response.json();
  }
}
