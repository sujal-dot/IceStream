import React from 'react';
import { SchemaDriftResponse } from '../types/dashboard';
import { FileDiff, AlertTriangle, CheckCircle2, GitBranch, Layers } from 'lucide-react';

interface SchemaPageProps {
  schemaDrift: SchemaDriftResponse | null;
  isLoading?: boolean;
  error?: string;
}

export const SchemaPage: React.FC<SchemaPageProps> = ({ schemaDrift, isLoading, error }) => {
  if (isLoading && !schemaDrift) {
    return (
      <div className="p-8 space-y-6 animate-pulse">
        <div className="h-24 bg-slate-900 rounded-2xl border border-slate-800" />
        <div className="h-64 bg-slate-900 rounded-2xl border border-slate-800" />
      </div>
    );
  }

  const isDrift = schemaDrift?.drift_detected ?? false;
  const changes = schemaDrift?.changes || [];
  const currentVersion = schemaDrift?.current_version || 'v2.1.0';
  const previousVersion = schemaDrift?.previous_version || 'v2.0.0';

  return (
    <div className="p-6 max-w-[1600px] mx-auto space-y-6 text-slate-100">
      {/* Page Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-5 rounded-2xl bg-slate-900/60 border border-slate-800 shadow-xl">
        <div className="flex items-center gap-3.5">
          <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-400">
            <FileDiff className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-extrabold text-white tracking-tight">
              Schema Registry & Drift Detector
            </h1>
            <p className="text-xs text-slate-400 mt-0.5 font-mono">
              Detect breaking field modifications, missing parameters, and backward-incompatible events
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div
            className={`px-3 py-1.5 rounded-xl border text-xs font-mono font-bold flex items-center gap-2 ${
              isDrift
                ? 'bg-rose-500/10 border-rose-500/30 text-rose-400 animate-pulse'
                : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
            }`}
          >
            {isDrift ? <AlertTriangle className="w-4 h-4" /> : <CheckCircle2 className="w-4 h-4" />}
            <span>DRIFT STATUS: {isDrift ? 'DRIFT DETECTED' : 'IN SYNC'}</span>
          </div>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs font-mono">
          ⚠ Schema Registry Sync Error: {error}
        </div>
      )}

      {/* Version Matrix & Schema Overview */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-2">
          <span className="text-[11px] font-mono text-slate-400 uppercase tracking-wider block">
            Current Active Schema
          </span>
          <div className="flex items-center justify-between">
            <span className="text-2xl font-extrabold font-mono text-cyan-400">
              {currentVersion}
            </span>
            <GitBranch className="w-5 h-5 text-cyan-500" />
          </div>
          <span className="text-xs text-slate-400 font-mono block">Registered in Confluent / Glue</span>
        </div>

        <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-2">
          <span className="text-[11px] font-mono text-slate-400 uppercase tracking-wider block">
            Previous Registered Schema
          </span>
          <div className="flex items-center justify-between">
            <span className="text-2xl font-extrabold font-mono text-slate-300">
              {previousVersion}
            </span>
            <GitBranch className="w-5 h-5 text-slate-500" />
          </div>
          <span className="text-xs text-slate-400 font-mono block">Baseline comparative target</span>
        </div>

        <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-2">
          <span className="text-[11px] font-mono text-slate-400 uppercase tracking-wider block">
            Compatibility Mode
          </span>
          <div className="flex items-center justify-between">
            <span className="text-xl font-extrabold font-mono text-emerald-400">
              FULL_TRANSITIVE
            </span>
            <Layers className="w-5 h-5 text-emerald-500" />
          </div>
          <span className="text-xs text-slate-400 font-mono block">Backward & forward compatible</span>
        </div>
      </div>

      {/* Schema Diff Changes Inspector */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <h2 className="text-sm font-bold text-white font-mono flex items-center gap-2">
            <FileDiff className="w-4 h-4 text-cyan-400" />
            Field-Level Schema Differences
          </h2>
          <span className="text-xs text-slate-400 font-mono">
            {changes.length} Difference(s) Recorded
          </span>
        </div>

        {changes.length === 0 ? (
          <div className="p-12 text-center bg-slate-950/40 rounded-xl border border-slate-800/60 text-slate-400 text-xs">
            <CheckCircle2 className="w-10 h-10 text-emerald-400 mx-auto mb-3" />
            <p className="font-semibold text-slate-200 text-sm">No schema drift or field mismatch detected</p>
            <p className="text-slate-400 mt-1 max-w-md mx-auto">
              All incoming Kafka events strictly match the registered Avro / JSON Schema spec.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {changes.map((item, idx) => (
              <div
                key={idx}
                className="p-4 bg-slate-950 rounded-xl border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4 font-mono text-xs"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-cyan-400 font-bold">{item.field}</span>
                    <span className="px-2 py-0.5 rounded text-[10px] bg-amber-500/20 text-amber-300 border border-amber-500/30">
                      {item.change}
                    </span>
                  </div>
                  <div className="flex items-center gap-4 text-slate-400 text-[11px]">
                    {item.expected && (
                      <span>
                        Expected: <strong className="text-emerald-400">{item.expected}</strong>
                      </span>
                    )}
                    {item.actual && (
                      <span>
                        Actual: <strong className="text-rose-400">{item.actual}</strong>
                      </span>
                    )}
                  </div>
                </div>

                <div className="px-3 py-1 rounded bg-slate-900 border border-slate-800 text-slate-300 text-[11px]">
                  Impact: Quarantine / Remediation Active
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
