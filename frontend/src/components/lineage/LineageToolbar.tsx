import React from 'react';
import { RefreshCw, Maximize2, RotateCcw, Activity } from 'lucide-react';
import { PipelineSummary } from '../../types/lineage';

interface LineageToolbarProps {
  streamName?: string;
  lastUpdated: string | null;
  isRefreshing: boolean;
  pipelineSummary: PipelineSummary | null;
  onRefresh: () => void;
  onFitView?: () => void;
  onResetLayout?: () => void;
}

export const LineageToolbar: React.FC<LineageToolbarProps> = ({
  streamName = 'checkout-stream',
  lastUpdated,
  isRefreshing,
  pipelineSummary,
  onRefresh,
  onFitView,
  onResetLayout,
}) => {
  const isHealthy = !pipelineSummary || pipelineSummary.circuit_breaker_state === 'CLOSED';

  return (
    <div className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-xl bg-slate-900/80 border border-slate-800/80 backdrop-blur-md mb-4 shadow-lg">
      {/* Title & Stream Pill */}
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-sky-500/10 border border-sky-500/20 text-sky-400">
          <Activity className="w-5 h-5" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-lg font-bold text-slate-100 tracking-tight">
              Pipeline Lineage
            </h1>
            <span className="font-mono text-xs text-sky-400 bg-sky-500/10 border border-sky-500/20 px-2 py-0.5 rounded-full font-medium">
              {streamName}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Real-time end-to-end data pipeline & quarantine flow topology
          </p>
        </div>
      </div>

      {/* Summary telemetry if available */}
      {pipelineSummary && (
        <div className="hidden lg:flex items-center gap-4 px-3 py-1.5 rounded-lg bg-slate-950/60 border border-slate-800 text-xs font-mono">
          <div>
            <span className="text-slate-500">State: </span>
            <span className="text-emerald-400 font-semibold">{pipelineSummary.state}</span>
          </div>
          <div className="h-3 w-px bg-slate-800" />
          <div>
            <span className="text-slate-500">Circuit: </span>
            <span
              className={
                pipelineSummary.circuit_breaker_state === 'CLOSED'
                  ? 'text-emerald-400 font-semibold'
                  : 'text-rose-400 font-semibold'
              }
            >
              {pipelineSummary.circuit_breaker_state}
            </span>
          </div>
          <div className="h-3 w-px bg-slate-800" />
          <div>
            <span className="text-slate-500">Error Rate: </span>
            <span className="text-slate-200">
              {(pipelineSummary.error_rate * 100).toFixed(2)}%
            </span>
          </div>
        </div>
      )}

      {/* Toolbar Action Buttons */}
      <div className="flex items-center gap-2">
        {lastUpdated && (
          <span className="text-[11px] text-slate-400 font-mono hidden sm:inline-block mr-2">
            Updated: {lastUpdated}
          </span>
        )}

        {onFitView && (
          <button
            onClick={onFitView}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700/80 transition-colors shadow-sm"
            title="Fit View"
          >
            <Maximize2 className="w-3.5 h-3.5 text-slate-400" />
            <span className="hidden sm:inline">Fit View</span>
          </button>
        )}

        {onResetLayout && (
          <button
            onClick={onResetLayout}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700/80 transition-colors shadow-sm"
            title="Reset Layout"
          >
            <RotateCcw className="w-3.5 h-3.5 text-slate-400" />
            <span className="hidden sm:inline">Reset Layout</span>
          </button>
        )}

        <button
          onClick={onRefresh}
          disabled={isRefreshing}
          className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-500 active:bg-sky-700 text-white text-xs font-medium transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
          title="Refresh Lineage Data"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
          <span>{isRefreshing ? 'Refreshing...' : 'Refresh'}</span>
        </button>
      </div>
    </div>
  );
};
