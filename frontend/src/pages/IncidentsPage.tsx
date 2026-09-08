import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  ShieldAlert,
  AlertCircle,
  CheckCircle2,
  Clock,
  RefreshCw,
  Filter,
  ShieldCheck,
  ArrowRight,
  AlertTriangle,
} from 'lucide-react';
import { Header } from '../components/dashboard/Header';
import { IncidentDetailModal } from '../components/dashboard/IncidentDetailModal';
import { IncidentsApiService } from '../services/incidentsApi';
import { PipelineApiService } from '../services/pipelineApi';
import { IncidentItem, PipelineStatusResponse } from '../types/dashboard';

interface IncidentsPageProps {
  activeView?: 'dashboard' | 'lineage' | 'incidents';
  onSelectView?: (view: 'dashboard' | 'lineage' | 'incidents') => void;
}

export const IncidentsPage: React.FC<IncidentsPageProps> = ({
  activeView = 'incidents',
  onSelectView = () => {},
}) => {
  const [incidents, setIncidents] = useState<IncidentItem[]>([]);
  const [pipelineStatus, setPipelineStatus] = useState<PipelineStatusResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  const [statusFilter, setStatusFilter] = useState<'ALL' | 'OPEN' | 'ACKNOWLEDGED' | 'RESOLVED'>('ALL');
  const [severityFilter, setSeverityFilter] = useState<'ALL' | 'CRITICAL' | 'WARNING'>('ALL');
  const [selectedIncident, setSelectedIncident] = useState<IncidentItem | null>(null);

  const fetchIncidents = useCallback(async (isManualRefresh = false) => {
    if (isManualRefresh) {
      setIsRefreshing(true);
    } else {
      setIsLoading(true);
    }
    setError(null);

    try {
      const data = await IncidentsApiService.getIncidents();
      setIncidents(data.items || []);
      setLastUpdated(new Date().toLocaleTimeString());

      const status = await PipelineApiService.getStatus().catch(() => null);
      if (status) {
        setPipelineStatus(status);
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to fetch incident telemetry';
      setError(message);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchIncidents(false);
    const intervalId = setInterval(() => {
      fetchIncidents(true);
    }, 1000);
    return () => clearInterval(intervalId);
  }, [fetchIncidents]);

  // Filtered incidents list
  const filteredIncidents = useMemo(() => {
    return incidents.filter((incident) => {
      if (statusFilter !== 'ALL' && incident.status !== statusFilter) return false;
      if (severityFilter !== 'ALL' && incident.severity !== severityFilter) return false;
      return true;
    });
  }, [incidents, statusFilter, severityFilter]);

  // Incident counts breakdown
  const counts = useMemo(() => {
    return {
      total: incidents.length,
      open: incidents.filter((i) => i.status === 'OPEN').length,
      acknowledged: incidents.filter((i) => i.status === 'ACKNOWLEDGED').length,
      resolved: incidents.filter((i) => i.status === 'RESOLVED').length,
    };
  }, [incidents]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-sky-500 selection:text-white">
      {/* Header Bar */}
      <Header
        pipelineStatus={pipelineStatus}
        lastUpdated={lastUpdated}
        isRefreshing={isRefreshing}
        onRefresh={() => fetchIncidents(true)}
        activeView={activeView}
        onSelectView={onSelectView}
      />

      <main className="flex-1 p-4 sm:p-6 lg:px-8 space-y-6 max-w-[1600px] w-full mx-auto">
        {/* Page Banner & Summary Stat Cards */}
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center justify-between gap-4 p-5 rounded-2xl bg-slate-900/60 border border-slate-800/80 shadow-xl">
            <div className="flex items-center gap-3.5">
              <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400 shadow-md">
                <ShieldAlert className="w-6 h-6" />
              </div>
              <div>
                <h1 className="text-xl font-extrabold text-slate-100 tracking-tight">
                  Incidents & Remediation Center
                </h1>
                <p className="text-xs text-slate-400 mt-0.5">
                  Real-time pipeline failure detection, circuit breaker events, and automated self-healing
                </p>
              </div>
            </div>
            <button
              onClick={() => fetchIncidents(true)}
              disabled={isRefreshing}
              className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 transition-all disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-sky-400' : ''}`} />
              <span>Refresh Incidents</span>
            </button>
          </div>

          {/* Quick Stats Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80 flex items-center justify-between">
              <div>
                <p className="text-[11px] font-mono text-slate-400 uppercase tracking-wider">Total Recorded</p>
                <p className="text-2xl font-extrabold font-mono text-slate-100 mt-1">{counts.total}</p>
              </div>
              <ShieldAlert className="w-5 h-5 text-slate-500" />
            </div>

            <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-between">
              <div>
                <p className="text-[11px] font-mono text-rose-300 uppercase tracking-wider">Open / Active</p>
                <p className="text-2xl font-extrabold font-mono text-rose-400 mt-1">{counts.open}</p>
              </div>
              <AlertCircle className="w-5 h-5 text-rose-400 animate-pulse" />
            </div>

            <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-between">
              <div>
                <p className="text-[11px] font-mono text-amber-300 uppercase tracking-wider">Acknowledged</p>
                <p className="text-2xl font-extrabold font-mono text-amber-400 mt-1">{counts.acknowledged}</p>
              </div>
              <AlertTriangle className="w-5 h-5 text-amber-400" />
            </div>

            <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-between">
              <div>
                <p className="text-[11px] font-mono text-emerald-300 uppercase tracking-wider">Resolved</p>
                <p className="text-2xl font-extrabold font-mono text-emerald-400 mt-1">{counts.resolved}</p>
              </div>
              <CheckCircle2 className="w-5 h-5 text-emerald-400" />
            </div>
          </div>
        </div>

        {/* Filter Controls Bar */}
        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80 shadow-md flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-sky-400" />
            <span className="text-xs font-bold text-slate-200">Filter Incidents:</span>
          </div>

          <div className="flex flex-wrap items-center gap-4">
            {/* Status Filter Tabs */}
            <div className="flex items-center gap-1 bg-slate-950/80 p-1 rounded-lg border border-slate-800 text-xs font-mono">
              {(['ALL', 'OPEN', 'ACKNOWLEDGED', 'RESOLVED'] as const).map((status) => (
                <button
                  key={status}
                  onClick={() => setStatusFilter(status)}
                  className={`px-3 py-1 rounded-md transition-all font-semibold ${
                    statusFilter === status
                      ? 'bg-sky-600 text-white shadow-sm'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {status}
                </button>
              ))}
            </div>

            {/* Severity Filter Tabs */}
            <div className="flex items-center gap-1 bg-slate-950/80 p-1 rounded-lg border border-slate-800 text-xs font-mono">
              {(['ALL', 'CRITICAL', 'WARNING'] as const).map((sev) => (
                <button
                  key={sev}
                  onClick={() => setSeverityFilter(sev)}
                  className={`px-3 py-1 rounded-md transition-all font-semibold ${
                    severityFilter === sev
                      ? 'bg-indigo-600 text-white shadow-sm'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {sev}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Main Incident List View */}
        <div className="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-5 shadow-xl min-h-[400px]">
          {isLoading && (
            <div className="flex flex-col items-center justify-center p-16 text-center">
              <RefreshCw className="w-8 h-8 text-sky-400 animate-spin mb-4" />
              <h3 className="text-sm font-semibold text-slate-200">Loading incident telemetry...</h3>
            </div>
          )}

          {!isLoading && error && (
            <div className="flex flex-col items-center justify-center p-12 text-center text-rose-400">
              <AlertCircle className="w-8 h-8 mb-2" />
              <h3 className="font-bold text-sm">Error Loading Incidents</h3>
              <p className="text-xs font-mono mt-1 text-slate-400">{error}</p>
            </div>
          )}

          {!isLoading && !error && filteredIncidents.length === 0 && (
            <div className="flex flex-col items-center justify-center p-16 text-center bg-slate-950/40 rounded-xl border border-slate-800/60">
              <ShieldCheck className="w-10 h-10 text-emerald-400/80 mb-3" />
              <h3 className="text-base font-bold text-slate-200">No matching incidents found</h3>
              <p className="text-xs text-slate-400 mt-1 max-w-sm">
                No incidents match the selected filter parameters. Pipeline quality standards are being maintained.
              </p>
            </div>
          )}

          {!isLoading && !error && filteredIncidents.length > 0 && (
            <div className="space-y-3">
              {filteredIncidents.map((incident) => {
                const isOpen = incident.status === 'OPEN';
                const isAcknowledged = incident.status === 'ACKNOWLEDGED';
                const isCritical = incident.severity === 'CRITICAL';

                return (
                  <div
                    key={incident.incident_id}
                    className="p-4 rounded-xl bg-slate-950/60 hover:bg-slate-800/50 border border-slate-800 hover:border-slate-700 transition-all flex flex-col lg:flex-row lg:items-center justify-between gap-4 group"
                  >
                    <div className="flex items-start gap-3.5">
                      <div
                        className={`p-2.5 rounded-xl shrink-0 mt-0.5 ${
                          isCritical
                            ? 'bg-rose-500/10 border border-rose-500/20 text-rose-400'
                            : 'bg-amber-500/10 border border-amber-500/20 text-amber-400'
                        }`}
                      >
                        <AlertCircle className="w-5 h-5" />
                      </div>

                      <div className="space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-mono text-sm font-extrabold text-slate-100 group-hover:text-sky-400 transition-colors">
                            {incident.incident_id}
                          </span>
                          <span className="text-xs font-mono text-slate-400 bg-slate-900 border border-slate-800 px-2 py-0.5 rounded">
                            {incident.pipeline_name}
                          </span>
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
                          <span className="text-[10px] font-mono text-slate-400 uppercase bg-slate-900 px-1.5 py-0.5 rounded border border-slate-800">
                            {incident.severity}
                          </span>
                        </div>

                        <p className="text-xs text-slate-300 font-sans leading-relaxed">
                          {incident.trigger || incident.message || 'Pipeline quality threshold violation detected.'}
                        </p>

                        <div className="flex flex-wrap items-center gap-4 text-[11px] font-mono text-slate-400 pt-1">
                          <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3 text-slate-500" />
                            Detected: {new Date(incident.created_at || incident.detected_at || Date.now()).toLocaleTimeString()}
                          </span>
                          {incident.error_rate > 0 && (
                            <span>Error rate: <strong className="text-slate-200">{(incident.error_rate * 100).toFixed(2)}%</strong></span>
                          )}
                          {incident.failed_records > 0 && (
                            <span>Quarantine: <strong className="text-amber-400">{incident.failed_records} events</strong></span>
                          )}
                          {incident.circuit_state && (
                            <span>Circuit: <strong className={incident.circuit_state === 'CLOSED' ? 'text-emerald-400' : 'text-rose-400'}>{incident.circuit_state}</strong></span>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 self-end lg:self-center shrink-0">
                      <button
                        onClick={() => setSelectedIncident(incident)}
                        className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold shadow-md transition-colors"
                      >
                        <span>Inspect & Remediate</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </main>

      {/* Incident Detail Inspection & Action Modal */}
      <IncidentDetailModal
        incident={selectedIncident}
        onClose={() => setSelectedIncident(null)}
        onIncidentUpdated={() => fetchIncidents(true)}
      />
    </div>
  );
};
