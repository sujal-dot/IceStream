import React from 'react';
import { Database, HardDrive, Clock, Table, Layers, FileText } from 'lucide-react';

export const IcebergPage: React.FC = () => {
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

      {/* Lakehouse Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 font-mono">
        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex items-center justify-between">
          <div>
            <span className="text-[11px] text-slate-400 uppercase tracking-wider block">
              Active Tables
            </span>
            <span className="text-2xl font-extrabold text-cyan-400 mt-1 block">3 Tables</span>
          </div>
          <Table className="w-6 h-6 text-cyan-500/80" />
        </div>

        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex items-center justify-between">
          <div>
            <span className="text-[11px] text-slate-400 uppercase tracking-wider block">
              Total Storage
            </span>
            <span className="text-2xl font-extrabold text-emerald-400 mt-1 block">1.42 GB</span>
          </div>
          <HardDrive className="w-6 h-6 text-emerald-500/80" />
        </div>

        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex items-center justify-between">
          <div>
            <span className="text-[11px] text-slate-400 uppercase tracking-wider block">
              Parquet Files
            </span>
            <span className="text-2xl font-extrabold text-amber-400 mt-1 block">1,248</span>
          </div>
          <FileText className="w-6 h-6 text-amber-500/80" />
        </div>

        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex items-center justify-between">
          <div>
            <span className="text-[11px] text-slate-400 uppercase tracking-wider block">
              Current Snapshot ID
            </span>
            <span className="text-sm font-extrabold text-purple-400 mt-1 block truncate max-w-[140px]">
              89432098421098
            </span>
          </div>
          <Clock className="w-6 h-6 text-purple-500/80" />
        </div>
      </div>

      {/* Iceberg Tables Spec & Snapshot History */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Table Spec Card */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h2 className="text-sm font-bold text-white font-mono flex items-center gap-2">
              <Table className="w-4 h-4 text-cyan-400" />
              Target Table Schema: icestream.db.orders_sanitized
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
                  <td className="py-2.5 px-3 text-slate-400">decimal(18,2)</td>
                  <td className="py-2.5 px-3 text-rose-400">REQUIRED</td>
                  <td className="py-2.5 px-3 text-slate-500">Sanitized monetary amount</td>
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
                  <td className="py-2.5 px-3 text-slate-500">Partitioned by day</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        {/* Snapshot Time-Travel Log */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h2 className="text-sm font-bold text-white font-mono flex items-center gap-2">
              <Clock className="w-4 h-4 text-purple-400" />
              Recent Iceberg Snapshot Commit History
            </h2>
            <span className="text-xs text-slate-400 font-mono">Time-Travel Enabled</span>
          </div>

          <div className="space-y-3 font-mono text-xs">
            <div className="p-3 bg-slate-950 rounded-xl border border-slate-800 space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-purple-400 font-bold">Snapshot #89432098421098</span>
                <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                  CURRENT
                </span>
              </div>
              <p className="text-slate-400 text-[11px]">
                Operation: append | Committed: {new Date().toLocaleTimeString()}
              </p>
              <div className="text-slate-500 text-[10px]">
                Added Parquet Files: 12 | Added Records: 4,500
              </div>
            </div>

            <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800/80 space-y-1 opacity-80">
              <div className="flex items-center justify-between">
                <span className="text-slate-300 font-bold">Snapshot #89432098421097</span>
                <span className="text-[10px] text-slate-500">PREVIOUS</span>
              </div>
              <p className="text-slate-400 text-[11px]">
                Operation: append | Committed: 10 mins ago
              </p>
              <div className="text-slate-500 text-[10px]">
                Added Parquet Files: 10 | Added Records: 3,800
              </div>
            </div>

            <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800/80 space-y-1 opacity-60">
              <div className="flex items-center justify-between">
                <span className="text-slate-300 font-bold">Snapshot #89432098421096</span>
                <span className="text-[10px] text-slate-500">PREVIOUS</span>
              </div>
              <p className="text-slate-400 text-[11px]">
                Operation: overwrite | Committed: 1 hour ago
              </p>
              <div className="text-slate-500 text-[10px]">
                Remediated Quarantined Batch | Replaced Records: 250
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
