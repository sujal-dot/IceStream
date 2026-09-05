import React from 'react';
import { Cpu, RefreshCw, Activity, ShieldCheck } from 'lucide-react';
import { PipelineStatusResponse } from '../../types/dashboard';
import { getStatusStyle } from '../../utils/statusStyles';

interface HeaderProps {
  pipelineStatus: PipelineStatusResponse | null;
  lastUpdated: string | null;
  isRefreshing: boolean;
  onRefresh: () => void;
  activeView: 'dashboard' | 'lineage' | 'incidents';
  onSelectView: (view: 'dashboard' | 'lineage' | 'incidents') => void;
}

export const Header: React.FC<HeaderProps> = ({
  pipelineStatus,
  lastUpdated,
  isRefreshing,
  onRefresh,
  activeView,
  onSelectView,
}) => {
  // Derive backend health state
  const rawState = pipelineStatus?.state || 'UNKNOWN';
  const statusStyle = getStatusStyle(rawState);

  return (
    <header className="sticky top-0 z-40 bg-slate-950/90 border-b border-slate-800/80 backdrop-blur-xl px-4 sm:px-6 lg:px-8 py-3 flex flex-wrap items-center justify-between gap-4 shadow-xl">
      {/* Brand & Subtitle */}
      <div className="flex items-center gap-3.5">
        <div className="p-2.5 rounded-xl bg-gradient-to-br from-sky-500 to-indigo-600 text-white shadow-lg shadow-sky-500/20">
          <Cpu className="w-5 h-5" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <span className="font-extrabold text-lg tracking-tight text-white">IceStream</span>
            <span className="text-[10px] font-mono font-bold text-sky-400 bg-sky-500/10 border border-sky-500/20 px-1.5 py-0.5 rounded">
              v0.26
            </span>
          </div>
          <p className="text-xs text-slate-400 font-mono tracking-tight">
            Real-Time Lakehouse Observability & Self-Healing Data Pipeline
          </p>
        </div>
      </div>

      {/* Navigation Tabs */}
      <nav className="flex items-center gap-1 bg-slate-900/90 border border-slate-800 p-1 rounded-xl shadow-inner">
        <button
          onClick={() => onSelectView('dashboard')}
          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
            activeView === 'dashboard'
              ? 'bg-sky-600 text-white shadow-md'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
          }`}
        >
          <Activity className="w-3.5 h-3.5" />
          <span>Dashboard</span>
        </button>
        <button
          onClick={() => onSelectView('lineage')}
          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
            activeView === 'lineage'
              ? 'bg-sky-600 text-white shadow-md'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
          }`}
        >
          <Cpu className="w-3.5 h-3.5" />
          <span>Lineage DAG</span>
        </button>
        <button
          onClick={() => onSelectView('incidents')}
          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
            activeView === 'incidents'
              ? 'bg-sky-600 text-white shadow-md'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
          }`}
        >
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>Incidents</span>
        </button>
      </nav>

      {/* Pipeline Status Indicator & Refresh */}
      <div className="flex items-center gap-4">
        {/* Status Badge */}
        <div
          className="flex items-center gap-2.5 px-3.5 py-1.5 rounded-xl border text-xs font-semibold transition-all shadow-sm"
          style={{
            backgroundColor: statusStyle.badgeBg,
            borderColor: statusStyle.borderColor,
            color: statusStyle.badgeText,
          }}
        >
          <span
            className="w-2.5 h-2.5 rounded-full animate-pulse"
            style={{ backgroundColor: statusStyle.dotBg }}
          />
          <span className="font-mono tracking-wide font-bold">{statusStyle.label}</span>
        </div>

        {/* Refresh button & Last Updated */}
        <div className="flex items-center gap-2">
          {lastUpdated && (
            <span className="hidden sm:inline text-[11px] font-mono text-slate-500">
              Updated {lastUpdated}
            </span>
          )}
          <button
            onClick={onRefresh}
            disabled={isRefreshing}
            className="p-2 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 hover:text-white transition-all disabled:opacity-50"
            title="Refresh Telemetry"
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin text-sky-400' : ''}`} />
          </button>
        </div>
      </div>
    </header>
  );
};
