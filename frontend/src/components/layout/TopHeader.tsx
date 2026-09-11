import React from 'react';
import { PipelineHealthState } from '../../types/dashboard';
import { RefreshCw, Terminal, Key, ShieldCheck, ShieldAlert, Cpu } from 'lucide-react';
import { ApiTokenManager } from '../../services/apiTokenManager';

interface TopHeaderProps {
  pipelineState?: PipelineHealthState | string;
  lastUpdated: string | null;
  isRefreshing: boolean;
  onRefresh: () => void;
  onOpenCommandCenter: () => void;
  onOpenSettings: () => void;
}

export const TopHeader: React.FC<TopHeaderProps> = ({
  pipelineState = 'UNKNOWN',
  lastUpdated,
  isRefreshing,
  onRefresh,
  onOpenCommandCenter,
  onOpenSettings,
}) => {
  const getBadgeStyle = (state: string) => {
    switch (state.toUpperCase()) {
      case 'HEALTHY':
      case 'RUNNING':
      case 'RECOVERED':
        return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30';
      case 'PAUSED':
        return 'bg-amber-500/10 text-amber-400 border-amber-500/30';
      case 'CIRCUIT_OPEN':
      case 'REMEDIATING':
      case 'RECOVERING':
      case 'QUARANTINING':
        return 'bg-rose-500/10 text-rose-400 border-rose-500/40 animate-pulse';
      case 'DEGRADED':
        return 'bg-orange-500/10 text-orange-400 border-orange-500/30';
      default:
        return 'bg-slate-800 text-slate-400 border-slate-700';
    }
  };

  const hasToken = ApiTokenManager.hasToken();

  return (
    <header className="bg-slate-900 border-b border-slate-800 px-6 py-3 flex items-center justify-between shadow-md select-none">
      {/* Left: View Context / App Title */}
      <div className="flex items-center gap-4">
        <div>
          <h1 className="text-lg font-bold text-white tracking-tight flex items-center gap-2">
            IceStream Observability Engine
          </h1>
          <p className="text-xs text-slate-400 font-mono flex items-center gap-2">
            <span>Lakehouse Pipeline Monitoring</span>
            <span>•</span>
            <span className="text-cyan-400 font-medium">Real-Time Telemetry</span>
          </p>
        </div>

        {/* Global Pipeline Health Status Badge */}
        <div
          className={`px-3 py-1 rounded-full border text-xs font-mono font-bold flex items-center gap-2 ${getBadgeStyle(
            pipelineState
          )}`}
        >
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-current opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-current"></span>
          </span>
          STATUS: {pipelineState.toUpperCase()}
        </div>
      </div>

      {/* Right: Actions, Auth & Refresh */}
      <div className="flex items-center gap-3">
        {/* Bearer Auth Token Pill */}
        <button
          onClick={onOpenSettings}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-xs font-mono transition-colors ${
            hasToken
              ? 'bg-emerald-950/40 text-emerald-300 border-emerald-800/60 hover:bg-emerald-900/50'
              : 'bg-amber-950/40 text-amber-300 border-amber-800/60 hover:bg-amber-900/50'
          }`}
          title="Manage Bearer API Auth Token"
        >
          {hasToken ? <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" /> : <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />}
          <span>{hasToken ? 'AUTH: VALID' : 'AUTH: DEFAULT'}</span>
          <Key className="w-3 h-3 text-slate-400 ml-1" />
        </button>

        {/* Operational Command Center Trigger */}
        <button
          onClick={onOpenCommandCenter}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-medium text-xs shadow-lg shadow-cyan-950/50 transition-all border border-cyan-400/30"
          title="Open Operational Controls (Pause/Resume/Remediate)"
        >
          <Terminal className="w-3.5 h-3.5" />
          <span>Controls</span>
        </button>

        {/* Refresh Timestamp & Button */}
        <div className="flex items-center gap-2 pl-2 border-l border-slate-800">
          <span className="text-[11px] font-mono text-slate-400">
            {lastUpdated ? `Sync: ${lastUpdated}` : 'Syncing...'}
          </span>

          <button
            onClick={onRefresh}
            disabled={isRefreshing}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors disabled:opacity-50"
            title="Force refresh backend telemetry"
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin text-cyan-400' : ''}`} />
          </button>
        </div>
      </div>
    </header>
  );
};
