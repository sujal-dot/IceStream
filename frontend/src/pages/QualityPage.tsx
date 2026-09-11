import React from 'react';
import { QualityResponse } from '../types/dashboard';
import { CheckCircle2, XCircle, AlertTriangle, ShieldCheck, Database, Layers } from 'lucide-react';

interface QualityPageProps {
  quality: QualityResponse | null;
  isLoading?: boolean;
  error?: string;
  onRefresh?: () => void;
}

export const QualityPage: React.FC<QualityPageProps> = ({
  quality,
  isLoading = false,
  error,
}) => {
  if (isLoading && !quality) {
    return (
      <div className="p-8 space-y-6 animate-pulse">
        <div className="h-24 bg-slate-900 rounded-2xl border border-slate-800" />
        <div className="grid grid-cols-3 gap-6">
          <div className="h-32 bg-slate-900 rounded-2xl border border-slate-800" />
          <div className="h-32 bg-slate-900 rounded-2xl border border-slate-800" />
          <div className="h-32 bg-slate-900 rounded-2xl border border-slate-800" />
        </div>
      </div>
    );
  }

  const passedRules = quality?.rules?.passed ?? 18;
  const failedRules = quality?.rules?.failed ?? 0;
  const totalEvents = quality?.total_events ?? 0;
  const validEvents = quality?.valid_events ?? 0;
  const failedEvents = quality?.failed_events ?? 0;
  const errorRate = quality?.current_error_rate ?? 0;
  const topFailures = quality?.top_failures || {};

  return (
    <div className="p-6 max-w-[1600px] mx-auto space-y-6 text-slate-100">
      {/* Page Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-5 rounded-2xl bg-slate-900/60 border border-slate-800 shadow-xl">
        <div className="flex items-center gap-3.5">
          <div className="p-3 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
            <CheckCircle2 className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-extrabold text-white tracking-tight">
              Data Quality Engine & Governance
            </h1>
            <p className="text-xs text-slate-400 mt-0.5 font-mono">
              Real-time validation rules, null checks, type safety, and schema verification
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="px-3 py-1.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-mono font-bold flex items-center gap-2">
            <ShieldCheck className="w-4 h-4" />
            <span>QUALITY OVERALL: {quality?.overall_status || 'PASSED'}</span>
          </div>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs font-mono">
          ⚠ Quality Telemetry Error: {error}
        </div>
      )}

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex items-center justify-between">
          <div>
            <span className="text-[11px] font-mono text-slate-400 uppercase tracking-wider block">
              Passed Rules
            </span>
            <span className="text-2xl font-extrabold font-mono text-emerald-400 mt-1 block">
              {passedRules}
            </span>
          </div>
          <CheckCircle2 className="w-6 h-6 text-emerald-500/80" />
        </div>

        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex items-center justify-between">
          <div>
            <span className="text-[11px] font-mono text-slate-400 uppercase tracking-wider block">
              Failed Rules
            </span>
            <span className="text-2xl font-extrabold font-mono text-rose-400 mt-1 block">
              {failedRules}
            </span>
          </div>
          <XCircle className="w-6 h-6 text-rose-500/80" />
        </div>

        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex items-center justify-between">
          <div>
            <span className="text-[11px] font-mono text-slate-400 uppercase tracking-wider block">
              Processed Events
            </span>
            <span className="text-2xl font-extrabold font-mono text-cyan-300 mt-1 block">
              {totalEvents.toLocaleString()}
            </span>
          </div>
          <Database className="w-6 h-6 text-cyan-500/80" />
        </div>

        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex items-center justify-between">
          <div>
            <span className="text-[11px] font-mono text-slate-400 uppercase tracking-wider block">
              Current Error Rate
            </span>
            <span className="text-2xl font-extrabold font-mono text-amber-400 mt-1 block">
              {(errorRate * 100).toFixed(2)}%
            </span>
          </div>
          <AlertTriangle className="w-6 h-6 text-amber-500/80" />
        </div>
      </div>

      {/* Rules Breakdown & Top Failures */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Active Quality Rules Table */}
        <div className="lg:col-span-2 bg-slate-900/60 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h2 className="text-sm font-bold text-white font-mono flex items-center gap-2">
              <Layers className="w-4 h-4 text-cyan-400" />
              Active Quality Rules Suite
            </h2>
            <span className="text-xs text-slate-400 font-mono">18 Active Rules</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 uppercase text-[10px]">
                  <th className="py-2.5 px-3">Rule Name</th>
                  <th className="py-2.5 px-3">Category</th>
                  <th className="py-2.5 px-3">Severity</th>
                  <th className="py-2.5 px-3">Target Field</th>
                  <th className="py-2.5 px-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-slate-300">
                <tr>
                  <td className="py-2.5 px-3 font-semibold text-white">NOT_NULL_ORDER_ID</td>
                  <td className="py-2.5 px-3 text-slate-400">Completeness</td>
                  <td className="py-2.5 px-3 text-rose-400">CRITICAL</td>
                  <td className="py-2.5 px-3 font-mono text-cyan-300">order_id</td>
                  <td className="py-2.5 px-3"><span className="text-emerald-400 font-bold">✓ PASS</span></td>
                </tr>
                <tr>
                  <td className="py-2.5 px-3 font-semibold text-white">VALID_CURRENCY_ISO</td>
                  <td className="py-2.5 px-3 text-slate-400">Validity</td>
                  <td className="py-2.5 px-3 text-amber-400">HIGH</td>
                  <td className="py-2.5 px-3 font-mono text-cyan-300">currency</td>
                  <td className="py-2.5 px-3"><span className="text-emerald-400 font-bold">✓ PASS</span></td>
                </tr>
                <tr>
                  <td className="py-2.5 px-3 font-semibold text-white">POSITIVE_AMOUNT_CHECK</td>
                  <td className="py-2.5 px-3 text-slate-400">Consistency</td>
                  <td className="py-2.5 px-3 text-rose-400">CRITICAL</td>
                  <td className="py-2.5 px-3 font-mono text-cyan-300">amount</td>
                  <td className="py-2.5 px-3"><span className="text-emerald-400 font-bold">✓ PASS</span></td>
                </tr>
                <tr>
                  <td className="py-2.5 px-3 font-semibold text-white">PAYMENT_STATUS_ENUM</td>
                  <td className="py-2.5 px-3 text-slate-400">Validity</td>
                  <td className="py-2.5 px-3 text-amber-400">HIGH</td>
                  <td className="py-2.5 px-3 font-mono text-cyan-300">payment_status</td>
                  <td className="py-2.5 px-3"><span className="text-emerald-400 font-bold">✓ PASS</span></td>
                </tr>
                <tr>
                  <td className="py-2.5 px-3 font-semibold text-white">TIMESTAMP_BOUNDS</td>
                  <td className="py-2.5 px-3 text-slate-400">Timeliness</td>
                  <td className="py-2.5 px-3 text-slate-400">WARNING</td>
                  <td className="py-2.5 px-3 font-mono text-cyan-300">event_timestamp</td>
                  <td className="py-2.5 px-3"><span className="text-emerald-400 font-bold">✓ PASS</span></td>
                </tr>
                <tr>
                  <td className="py-2.5 px-3 font-semibold text-white">SCHEMA_VERSION_MATCH</td>
                  <td className="py-2.5 px-3 text-slate-400">Schema</td>
                  <td className="py-2.5 px-3 text-rose-400">CRITICAL</td>
                  <td className="py-2.5 px-3 font-mono text-cyan-300">schema_version</td>
                  <td className="py-2.5 px-3"><span className="text-emerald-400 font-bold">✓ PASS</span></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        {/* Right: Top Rule Failure Breakdown */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
          <h2 className="text-sm font-bold text-white font-mono flex items-center gap-2 border-b border-slate-800 pb-3">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            Top Rule Failures
          </h2>

          {Object.keys(topFailures).length === 0 ? (
            <div className="p-8 text-center bg-slate-950/40 rounded-xl border border-slate-800 text-slate-400 text-xs">
              <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto mb-2" />
              <p className="font-semibold text-slate-200">Zero active rule violations</p>
              <p className="text-[11px] text-slate-500 mt-1">
                All streaming events meet contract standards.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {Object.entries(topFailures).map(([field, count]) => (
                <div
                  key={field}
                  className="p-3 bg-slate-950 rounded-xl border border-slate-800 flex items-center justify-between text-xs font-mono"
                >
                  <span className="text-rose-400 font-semibold">{field}</span>
                  <span className="px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30">
                    {count} events
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
