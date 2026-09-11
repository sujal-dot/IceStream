import React from 'react';
import { MetricsResponse, SystemHealthResponse } from '../../types/dashboard';
import { Activity, Server, Database, Layers, Shield, Cpu } from 'lucide-react';

interface SystemStatusBarProps {
  systemHealth: SystemHealthResponse | null;
  metrics: MetricsResponse | null;
  error?: string;
}

export const SystemStatusBar: React.FC<SystemStatusBarProps> = ({ systemHealth, metrics, error }) => {
  const getStatusColor = (status?: string) => {
    if (!status) return 'bg-slate-600 text-slate-400 border-slate-700';
    const s = status.toLowerCase();
    if (s === 'ok' || s === 'healthy' || s === 'closed') {
      return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30';
    }
    if (s === 'warning' || s === 'degraded' || s === 'half_open') {
      return 'bg-amber-500/10 text-amber-400 border-amber-500/30';
    }
    return 'bg-rose-500/10 text-rose-400 border-rose-500/30';
  };

  const getDotColor = (status?: string) => {
    if (!status) return 'bg-slate-500';
    const s = status.toLowerCase();
    if (s === 'ok' || s === 'healthy' || s === 'closed') return 'bg-emerald-400 animate-pulse';
    if (s === 'warning' || s === 'degraded' || s === 'half_open') return 'bg-amber-400 animate-ping';
    return 'bg-rose-500 animate-bounce';
  };

  const cbState = metrics?.circuit_breaker?.state || 'UNKNOWN';
  const dependencies = systemHealth?.dependencies || {};

  return (
    <div className="bg-slate-900/90 backdrop-blur border-b border-slate-800 px-4 py-1.5 text-xs text-slate-300 flex flex-wrap items-center justify-between gap-3 select-none">
      <div className="flex items-center gap-4 overflow-x-auto py-0.5">
        <span className="text-slate-500 uppercase tracking-widest font-semibold text-[10px] flex items-center gap-1.5">
          <Activity className="w-3 h-3 text-cyan-400" />
          Infra Status
        </span>

        {/* Kafka Ingestion */}
        <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded border ${getStatusColor('ok')}`}>
          <Cpu className="w-3 h-3" />
          <span className="font-mono">Kafka:</span>
          <span className="font-semibold">INGESTING</span>
          <span className={`w-1.5 h-1.5 rounded-full ${getDotColor('ok')}`} />
        </div>

        {/* Flink Streaming */}
        <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded border ${getStatusColor('ok')}`}>
          <Layers className="w-3 h-3" />
          <span className="font-mono">Flink:</span>
          <span className="font-semibold">WINDOWING</span>
          <span className={`w-1.5 h-1.5 rounded-full ${getDotColor('ok')}`} />
        </div>

        {/* Iceberg Catalog */}
        <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded border ${getStatusColor(dependencies.iceberg_catalog)}`}>
          <Database className="w-3 h-3" />
          <span className="font-mono">Iceberg Catalog:</span>
          <span className="font-semibold uppercase">{dependencies.iceberg_catalog || 'PENDING'}</span>
          <span className={`w-1.5 h-1.5 rounded-full ${getDotColor(dependencies.iceberg_catalog)}`} />
        </div>

        {/* Postgres Event Store */}
        <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded border ${getStatusColor(dependencies.postgres)}`}>
          <Server className="w-3 h-3" />
          <span className="font-mono">PostgreSQL:</span>
          <span className="font-semibold uppercase">{dependencies.postgres || 'PENDING'}</span>
          <span className={`w-1.5 h-1.5 rounded-full ${getDotColor(dependencies.postgres)}`} />
        </div>

        {/* API Backend */}
        <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded border ${getStatusColor(systemHealth?.status)}`}>
          <Activity className="w-3 h-3" />
          <span className="font-mono">FastAPI:</span>
          <span className="font-semibold uppercase">{systemHealth?.status === 'ok' ? 'ONLINE' : 'DEGRADED'}</span>
          <span className={`w-1.5 h-1.5 rounded-full ${getDotColor(systemHealth?.status)}`} />
        </div>

        {/* Circuit Breaker */}
        <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded border ${getStatusColor(cbState)}`}>
          <Shield className="w-3 h-3" />
          <span className="font-mono">Circuit Breaker:</span>
          <span className="font-semibold">{cbState}</span>
          <span className={`w-1.5 h-1.5 rounded-full ${getDotColor(cbState)}`} />
        </div>
      </div>

      {error && (
        <div className="text-rose-400 font-mono text-[11px] truncate max-w-md">
          ⚠ API Sync Error: {error}
        </div>
      )}
    </div>
  );
};
