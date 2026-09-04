import React from 'react';

export const LineageLegend: React.FC = () => {
  return (
    <div className="flex flex-wrap items-center justify-between gap-4 p-3 rounded-lg bg-slate-900/70 border border-slate-800/80 text-xs font-mono text-slate-400 mt-4 shadow-md">
      {/* Status Legends */}
      <div className="flex items-center gap-4 flex-wrap">
        <span className="text-slate-500 font-semibold uppercase text-[10px] tracking-wider">
          Node Status:
        </span>
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-emerald-500" />
          <span className="text-slate-300">Healthy</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-amber-500" />
          <span className="text-slate-300">Warning / Active</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-rose-500" />
          <span className="text-slate-300">Critical / Open</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-slate-500" />
          <span className="text-slate-300">Idle / Unknown</span>
        </div>
      </div>

      {/* Edge Legends */}
      <div className="flex items-center gap-4">
        <span className="text-slate-500 font-semibold uppercase text-[10px] tracking-wider">
          Edge Flow:
        </span>
        <div className="flex items-center gap-1.5">
          <span className="w-4 h-0.5 bg-sky-400 inline-block" />
          <span className="text-slate-300">Main Pipeline</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-4 h-0.5 bg-amber-500 border-b border-dashed border-amber-500 inline-block" />
          <span className="text-slate-300">Quarantine / DLQ</span>
        </div>
      </div>
    </div>
  );
};
