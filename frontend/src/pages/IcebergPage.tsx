import React, { useEffect, useState } from 'react';
import { Database, HardDrive, Clock, Table, FileText, Activity } from 'lucide-react';
import { LakehouseApiService, TableHealth, MaintenanceHistoryItem } from '../services/lakehouseApi';

function formatBytes(bytes: number, decimals: number = 2): string {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

export const IcebergPage: React.FC = () => {
  const [tables, setTables] = useState<TableHealth[]>([]);
  const [history, setHistory] = useState<MaintenanceHistoryItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    try {
      const [tableData, historyData] = await Promise.all([
        LakehouseApiService.getLakehouseHealth(),
        LakehouseApiService.getMaintenanceHistory(undefined, 10).catch(() => ({ runs: [], total: 0 })),
      ]);
      setTables(tableData);
      setHistory(historyData.runs || []);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load lakehouse metrics');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, []);

  const activeTablesCount = tables.filter((t) => t.exists).length;
  const totalStorageBytes = tables.reduce((acc, t) => acc + (t.total_bytes || 0), 0);
  const totalFilesCount = tables.reduce((acc, t) => acc + (t.total_files || 0), 0);
  const mainSnapshotId =
    tables.find((t) => t.table_name === 'bronze.checkout_events')?.current_snapshot_id ||
    tables.find((t) => t.current_snapshot_id)?.current_snapshot_id ||
    'N/A';

  return (
    <div className="p-6 max-w-[1600px] mx-auto space-y-6 text-slate-100">
      {/* Page Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-5 rounded-2xl bg-slate-900/60 border border-slate-800 shadow-xl">
        <div className="flex items-center gap-3.5">
          <div className="p-3 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
            <Database className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-extrabold text-white tracking-tight">
              Apache Iceberg Lakehouse Catalog
            </h1>
            <p className="text-xs text-slate-400 mt-0.5 font-mono">
              ACID table storage, snapshot time-travel, partition spec, and Parquet data file metrics
            </p>
          </div>
        </div>

        <div className="px-3 py-1.5 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-300 text-xs font-mono font-bold flex items-center gap-2">
          <HardDrive className="w-4 h-4" />
          <span>CATALOG: REST / JDBC CATALOG</span>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 font-mono text-xs">
          Error loading live Iceberg metrics: {error}
        </div>
      )}

      {/* Lakehouse Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 font-mono">
        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex items-center justify-between">
          <div>
            <span className="text-[11px] text-slate-400 uppercase tracking-wider block">
              Active Tables
            </span>
            <span className="text-2xl font-extrabold text-cyan-400 mt-1 block">
              {loading ? '...' : `${activeTablesCount} Tables`}
            </span>
          </div>
          <Table className="w-6 h-6 text-cyan-500/80" />
        </div>

        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex items-center justify-between">
          <div>
            <span className="text-[11px] text-slate-400 uppercase tracking-wider block">
              Total Storage
            </span>
            <span className="text-2xl font-extrabold text-emerald-400 mt-1 block">
              {loading ? '...' : formatBytes(totalStorageBytes)}
            </span>
          </div>
          <HardDrive className="w-6 h-6 text-emerald-500/80" />
        </div>

        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex items-center justify-between">
          <div>
            <span className="text-[11px] text-slate-400 uppercase tracking-wider block">
              Parquet Files
            </span>
            <span className="text-2xl font-extrabold text-amber-400 mt-1 block">
              {loading ? '...' : totalFilesCount.toLocaleString()}
            </span>
          </div>
          <FileText className="w-6 h-6 text-amber-500/80" />
        </div>

        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex items-center justify-between">
          <div>
            <span className="text-[11px] text-slate-400 uppercase tracking-wider block">
              Current Snapshot ID
            </span>
            <span className="text-xs font-extrabold text-purple-400 mt-1 block truncate max-w-[140px]" title={String(mainSnapshotId)}>
              {loading ? '...' : String(mainSnapshotId)}
            </span>
          </div>
          <Clock className="w-6 h-6 text-purple-500/80" />
        </div>
      </div>

      {/* Lakehouse Registered Tables Overview */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <h2 className="text-sm font-bold text-white font-mono flex items-center gap-2">
            <Table className="w-4 h-4 text-cyan-400" />
            Registered Catalog Tables Diagnostic Status
          </h2>
          <span className="px-2 py-0.5 rounded text-[10px] bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 font-mono">
            LIVE METRICS
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400 uppercase text-[10px]">
                <th className="py-2.5 px-3">Table Name</th>
                <th className="py-2.5 px-3">Status</th>
                <th className="py-2.5 px-3">Records</th>
                <th className="py-2.5 px-3">Parquet Files</th>
                <th className="py-2.5 px-3">Total Size</th>
                <th className="py-2.5 px-3">Fragmentation</th>
                <th className="py-2.5 px-3">Last Updated</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-300">
              {tables.map((t) => (
                <tr key={t.table_name}>
                  <td className="py-2.5 px-3 font-semibold text-cyan-300">{t.table_name}</td>
                  <td className="py-2.5 px-3">
                    {t.exists ? (
                      <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                        EXISTS
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-400">
                        EMPTY
                      </span>
                    )}
                  </td>
                  <td className="py-2.5 px-3 text-white font-bold">{t.total_records.toLocaleString()}</td>
                  <td className="py-2.5 px-3 text-amber-300">{t.total_files.toLocaleString()}</td>
                  <td className="py-2.5 px-3 text-emerald-400">{formatBytes(t.total_bytes)}</td>
                  <td className="py-2.5 px-3">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-mono border ${
                        t.fragmentation_status === 'HEALTHY'
                          ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                          : t.fragmentation_status === 'SLIGHTLY_FRAGMENTED'
                          ? 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                          : 'bg-rose-500/20 text-rose-300 border-rose-500/30'
                      }`}
                    >
                      {t.fragmentation_status}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-slate-400 text-[11px]">
                    {t.last_updated_at ? new Date(t.last_updated_at).toLocaleString() : 'N/A'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Iceberg Tables Spec & Maintenance History */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Table Spec Card */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h2 className="text-sm font-bold text-white font-mono flex items-center gap-2">
              <Table className="w-4 h-4 text-cyan-400" />
              Bronze Table Schema Spec: bronze.checkout_events
            </h2>
            <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-mono">
              V2 SPEC
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 uppercase text-[10px]">
                  <th className="py-2.5 px-3">Field Name</th>
                  <th className="py-2.5 px-3">Iceberg Type</th>
                  <th className="py-2.5 px-3">Nullability</th>
                  <th className="py-2.5 px-3">Doc</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-slate-300">
                <tr>
                  <td className="py-2.5 px-3 font-semibold text-cyan-300">event_id</td>
                  <td className="py-2.5 px-3 text-slate-400">string</td>
                  <td className="py-2.5 px-3 text-rose-400">REQUIRED</td>
                  <td className="py-2.5 px-3 text-slate-500">Unique event UUID</td>
                </tr>
                <tr>
                  <td className="py-2.5 px-3 font-semibold text-cyan-300">order_id</td>
                  <td className="py-2.5 px-3 text-slate-400">string</td>
                  <td className="py-2.5 px-3 text-rose-400">REQUIRED</td>
                  <td className="py-2.5 px-3 text-slate-500">Business identifier</td>
                </tr>
                <tr>
                  <td className="py-2.5 px-3 font-semibold text-cyan-300">amount</td>
                  <td className="py-2.5 px-3 text-slate-400">double</td>
                  <td className="py-2.5 px-3 text-rose-400">REQUIRED</td>
                  <td className="py-2.5 px-3 text-slate-500">Checkout order monetary amount</td>
                </tr>
                <tr>
                  <td className="py-2.5 px-3 font-semibold text-cyan-300">currency</td>
                  <td className="py-2.5 px-3 text-slate-400">string</td>
                  <td className="py-2.5 px-3 text-emerald-400">OPTIONAL</td>
                  <td className="py-2.5 px-3 text-slate-500">ISO-4217 code</td>
                </tr>
                <tr>
                  <td className="py-2.5 px-3 font-semibold text-cyan-300">event_timestamp</td>
                  <td className="py-2.5 px-3 text-slate-400">timestamp_tz</td>
                  <td className="py-2.5 px-3 text-rose-400">REQUIRED</td>
                  <td className="py-2.5 px-3 text-slate-500">Event timestamp</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        {/* Maintenance History Log */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h2 className="text-sm font-bold text-white font-mono flex items-center gap-2">
              <Activity className="w-4 h-4 text-purple-400" />
              Recent Lakehouse Maintenance Operations
            </h2>
            <span className="text-xs text-slate-400 font-mono">Compaction Audit</span>
          </div>

          <div className="space-y-3 font-mono text-xs">
            {history.length === 0 ? (
              <p className="text-slate-500 text-xs py-4 text-center">No maintenance tasks recorded yet.</p>
            ) : (
              history.map((item) => (
                <div key={item.id} className="p-3 bg-slate-950 rounded-xl border border-slate-800 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-purple-400 font-bold">{item.table_name}</span>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] border ${
                        item.status === 'SUCCESS'
                          ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                          : 'bg-rose-500/20 text-rose-300 border-rose-500/30'
                      }`}
                    >
                      {item.status}
                    </span>
                  </div>
                  <p className="text-slate-400 text-[11px]">
                    Operation: {item.operation} | Started: {new Date(item.started_at).toLocaleTimeString()}
                  </p>
                  <div className="text-slate-500 text-[10px]">
                    Files Before/After: {item.files_before} / {item.files_after} | Compacted: {item.records_compacted} records
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
