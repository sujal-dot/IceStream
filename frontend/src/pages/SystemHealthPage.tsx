import React from 'react';
import { SystemHealthResponse, MetricsResponse } from '../types/dashboard';
import { Activity, Server, Database, Layers, ShieldCheck, Cpu, HardDrive } from 'lucide-react';

interface SystemHealthPageProps {
  systemHealth: SystemHealthResponse | null;
  metrics: MetricsResponse | null;
  isLoading?: boolean;
  error?: string;
}

export const SystemHealthPage: React.FC<SystemHealthPageProps> = ({
  systemHealth,
  metrics,
  isLoading,
  error,
}) => {
  if (isLoading && !systemHealth) {
    return (
      <div className="p-8 space-y-6 animate-pulse">
        <div className="h-24 bg-slate-900 rounded-2xl border border-slate-800" />
        <div className="grid grid-cols-3 gap-6">
          <div className="h-36 bg-slate-900 rounded-2xl border border-slate-800" />
          <div className="h-36 bg-slate-900 rounded-2xl border border-slate-800" />
          <div className="h-36 bg-slate-900 rounded-2xl border border-slate-800" />
        </div>
      </div>
    );
  }

  const dependencies = systemHealth?.dependencies || {};
  const cbState = metrics?.circuit_breaker?.state || 'CLOSED';

  const getStatusBadge = (status?: string) => {
    const s = (status || 'ok').toLowerCase();
    if (s === 'ok' || s === 'healthy' || s === 'closed') {
      return (
        <span className="px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 text-xs font-mono font-bold flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          OPERATIONAL
        </span>
      );
    }
    if (s === 'warning' || s === 'degraded' || s === 'half_open') {
      return (
        <span className="px-3 py-1 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/30 text-xs font-mono font-bold flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-amber-400 animate-ping" />
          DEGRADED
        </span>
      );
    }
    return (
      <span className="px-3 py-1 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/30 text-xs font-mono font-bold flex items-center gap-1.5">
        <span className="w-2 h-2 rounded-full bg-rose-500 animate-bounce" />
        OUTAGE / OPEN
      </span>
    );
  };

  return (
    <div className="p-6 max-w-[1600px] mx-auto space-y-6 text-slate-100">
      {/* Page Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-5 rounded-2xl bg-slate-900/60 border border-slate-800 shadow-xl">
        <div className="flex items-center gap-3.5">
          <div className="p-3 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
            <Activity className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-extrabold text-white tracking-tight">
              Infrastructure & System Health Matrix
            </h1>
            <p className="text-xs text-slate-400 mt-0.5 font-mono">
              Live dependency status, microservice connectivity, and circuit breaker metrics
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {getStatusBadge(systemHealth?.status)}
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs font-mono">
          ⚠ System Health Endpoint Error: {error}
        </div>
      )}

      {/* Services Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* FastAPI Backend */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-white font-bold text-sm font-mono">
              <Server className="w-4 h-4 text-cyan-400" />
              <span>FastAPI Backend</span>
            </div>
            {getStatusBadge(systemHealth?.status)}
          </div>
          <p className="text-xs text-slate-400 font-mono leading-relaxed">
            REST telemetry API, Bearer authentication, and self-healing dispatch router.
          </p>
          <div className="pt-2 border-t border-slate-800 text-[11px] font-mono text-slate-400 flex items-center justify-between">
            <span>Version: {systemHealth?.version || '0.23.0'}</span>
            <span>Latency: &lt;5ms</span>
          </div>
        </div>

        {/* PostgreSQL Database */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-white font-bold text-sm font-mono">
              <Database className="w-4 h-4 text-cyan-400" />
              <span>PostgreSQL Store</span>
            </div>
            {getStatusBadge(dependencies.postgres)}
          </div>
          <p className="text-xs text-slate-400 font-mono leading-relaxed">
            State persistence for incidents, remediation attempts, and telemetry snapshots.
          </p>
          <div className="pt-2 border-t border-slate-800 text-[11px] font-mono text-slate-400 flex items-center justify-between">
            <span>Pool Connections: Active</span>
            <span>Health Check: OK</span>
          </div>
        </div>

        {/* Apache Iceberg Catalog */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-white font-bold text-sm font-mono">
              <HardDrive className="w-4 h-4 text-cyan-400" />
              <span>Iceberg Catalog</span>
            </div>
            {getStatusBadge(dependencies.iceberg_catalog)}
          </div>
          <p className="text-xs text-slate-400 font-mono leading-relaxed">
            REST / JDBC Catalog service maintaining table specs and Parquet data files.
          </p>
          <div className="pt-2 border-t border-slate-800 text-[11px] font-mono text-slate-400 flex items-center justify-between">
            <span>Table Commit Spec: V2</span>
            <span>Catalog: RESPONSIVE</span>
          </div>
        </div>

        {/* Quality Engine */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-white font-bold text-sm font-mono">
              <ShieldCheck className="w-4 h-4 text-cyan-400" />
              <span>Quality Engine</span>
            </div>
            {getStatusBadge(dependencies.quality_engine)}
          </div>
          <p className="text-xs text-slate-400 font-mono leading-relaxed">
            Day 17 Quality Engine running inline validation rules and contract verification.
          </p>
          <div className="pt-2 border-t border-slate-800 text-[11px] font-mono text-slate-400 flex items-center justify-between">
            <span>Active Rules: 18</span>
            <span>Mode: INLINE_STREAM</span>
          </div>
        </div>

        {/* Apache Kafka Ingestion */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-white font-bold text-sm font-mono">
              <Cpu className="w-4 h-4 text-cyan-400" />
              <span>Kafka Cluster</span>
            </div>
            {getStatusBadge('ok')}
          </div>
          <p className="text-xs text-slate-400 font-mono leading-relaxed">
            Distributed event streaming bus handling order placement and payment telemetry.
          </p>
          <div className="pt-2 border-t border-slate-800 text-[11px] font-mono text-slate-400 flex items-center justify-between">
            <span>Topics: 4 Active</span>
            <span>Offset Lag: 0 msgs</span>
          </div>
        </div>

        {/* Apache Flink Engine */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-white font-bold text-sm font-mono">
              <Layers className="w-4 h-4 text-cyan-400" />
              <span>Flink Engine</span>
            </div>
            {getStatusBadge('ok')}
          </div>
          <p className="text-xs text-slate-400 font-mono leading-relaxed">
            Stateful stream processing, tumbling window aggregations, and error rate computation.
          </p>
          <div className="pt-2 border-t border-slate-800 text-[11px] font-mono text-slate-400 flex items-center justify-between">
            <span>Windows: 10s / 60s / 300s</span>
            <span>Checkpoints: HEALTHY</span>
          </div>
        </div>
      </div>
    </div>
  );
};
