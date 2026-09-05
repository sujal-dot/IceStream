import React from 'react';
import { ShieldAlert, AlertCircle, CheckCircle2, Clock, ChevronRight } from 'lucide-react';
import { IncidentItem } from '../../types/dashboard';

interface RecentIncidentsProps {
  incidents: IncidentItem[];
  isLoading?: boolean;
  onSelectIncident: (incident: IncidentItem) => void;
}

export const RecentIncidents: React.FC<RecentIncidentsProps> = ({
  incidents = [],
  isLoading = false,
  onSelectIncident,
}) => {
  if (isLoading) {
    return (
      <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800/80 shadow-md min-h-[260px] flex flex-col">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
          <div className="flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-amber-400" />
            <h3 className="font-bold text-sm text-slate-100">Recent Incidents</h3>
          </div>
        </div>
        <div className="space-y-3">
          <div className="h-12 bg-slate-800/40 rounded-lg animate-pulse" />
          <div className="h-12 bg-slate-800/40 rounded-lg animate-pulse" />
          <div className="h-12 bg-slate-800/40 rounded-lg animate-pulse" />
        </div>
      </div>
    );
  }

  return (
    <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800/80 shadow-md min-h-[260px] flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
        <div className="flex items-center gap-2">
          <ShieldAlert className="w-4 h-4 text-amber-400" />
          <h3 className="font-bold text-sm text-slate-100">Recent Incidents</h3>
        </div>
        <span className="text-[11px] font-mono text-slate-500">
          {incidents.length} total incident{incidents.length === 1 ? '' : 's'}
        </span>
      </div>

      {/* Incidents List Container */}
      {incidents.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-slate-950/40 rounded-xl border border-slate-800/60">
          <CheckCircle2 className="w-7 h-7 text-emerald-500/80 mb-2" />
          <h4 className="text-xs font-semibold text-slate-300">No active or recorded incidents</h4>
          <p className="text-[11px] text-slate-500 mt-1">Pipeline is operating within normal quality thresholds.</p>
        </div>
      ) : (
        <div className="space-y-2.5 overflow-y-auto max-h-[320px] pr-1">
          {incidents.map((incident) => {
            const isCritical = incident.severity === 'CRITICAL';
            const isOpen = incident.status === 'OPEN';
            const isAcknowledged = incident.status === 'ACKNOWLEDGED';

            return (
              <button
                key={incident.incident_id}
                onClick={() => onSelectIncident(incident)}
                className="w-full text-left p-3 rounded-xl bg-slate-950/60 hover:bg-slate-800/60 border border-slate-800/80 hover:border-slate-700 transition-all flex items-center justify-between gap-3 group"
              >
                {/* Left side: ID, stream, timing */}
                <div className="flex items-center gap-3 overflow-hidden">
                  <div
                    className={`p-2 rounded-lg shrink-0 ${
                      isCritical
                        ? 'bg-rose-500/10 border border-rose-500/20 text-rose-400'
                        : 'bg-amber-500/10 border border-amber-500/20 text-amber-400'
                    }`}
                  >
                    <AlertCircle className="w-4 h-4" />
                  </div>

                  <div className="overflow-hidden">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-slate-100 group-hover:text-sky-400 transition-colors">
                        {incident.incident_id}
                      </span>
                      <span className="text-[10px] font-mono text-slate-400 bg-slate-800 px-1.5 py-0.5 rounded">
                        {incident.pipeline_name}
                      </span>
                    </div>

                    <div className="flex items-center gap-3 text-[11px] font-mono text-slate-500 mt-1">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3 text-slate-600" />
                        {new Date(incident.created_at || incident.detected_at || Date.now()).toLocaleTimeString()}
                      </span>
                      {incident.error_rate > 0 && (
                        <span>Error rate: {(incident.error_rate * 100).toFixed(2)}%</span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Right side: Status badge & Arrow */}
                <div className="flex items-center gap-3 shrink-0">
                  <div className="flex flex-col items-end gap-1">
                    <span
                      className={`px-2 py-0.5 rounded font-mono text-[10px] font-bold ${
                        isOpen
                          ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30 animate-pulse'
                          : isAcknowledged
                          ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                          : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                      }`}
                    >
                      {incident.status}
                    </span>
                    <span className="text-[10px] font-mono text-slate-400 uppercase">
                      {incident.severity}
                    </span>
                  </div>
                  <ChevronRight className="w-4 h-4 text-slate-600 group-hover:text-sky-400 transition-colors" />
                </div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
};
