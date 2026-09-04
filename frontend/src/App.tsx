import React from 'react';
import { LineagePage } from './pages/LineagePage';
import { Activity, ShieldCheck, Cpu } from 'lucide-react';

export const App: React.FC = () => {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-sky-500 selection:text-white">
      {/* Primary Navigation Header */}
      <header className="sticky top-0 z-40 bg-slate-950/80 border-b border-slate-800/80 backdrop-blur-xl px-4 sm:px-6 lg:px-8 py-3 flex items-center justify-between shadow-md">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-gradient-to-br from-sky-500 to-indigo-600 text-white shadow-lg shadow-sky-500/20">
            <Cpu className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-extrabold text-base tracking-tight text-white">IceStream</span>
              <span className="text-[10px] font-mono font-bold text-sky-400 bg-sky-500/10 border border-sky-500/20 px-1.5 py-0.5 rounded">
                v0.25
              </span>
            </div>
            <p className="text-[10px] text-slate-400 font-mono">Real-Time Lakehouse Observability & Self-Healing Pipeline</p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="flex items-center gap-1 bg-slate-900/90 border border-slate-800 p-1 rounded-xl">
          <a
            href="/lineage"
            className="flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-sky-600 text-white font-medium text-xs shadow-sm transition-all"
          >
            <Activity className="w-3.5 h-3.5" />
            <span>Lineage DAG</span>
          </a>
          <div className="flex items-center gap-1 px-3 py-1.5 text-xs text-slate-500 cursor-not-allowed">
            <ShieldCheck className="w-3.5 h-3.5 text-slate-600" />
            <span className="hidden sm:inline">Telemetry & Incidents</span>
          </div>
        </nav>
      </header>

      {/* Main Page Area */}
      <main className="flex-1">
        <LineagePage />
      </main>
    </div>
  );
};

export default App;
