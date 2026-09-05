import React, { useState, useMemo } from 'react';
import { AlertCircle, RefreshCw, Layers } from 'lucide-react';
import { Header } from '../components/dashboard/Header';
import { KpiCards } from '../components/dashboard/KpiCards';
import { ErrorRateTimeline } from '../components/dashboard/ErrorRateTimeline';
import { RecentIncidents } from '../components/dashboard/RecentIncidents';
import { IncidentDetailModal } from '../components/dashboard/IncidentDetailModal';
import { LineageCanvas } from '../components/lineage/LineageCanvas';
import { LineageLegend } from '../components/lineage/LineageLegend';
import { NodeDetailsPanel } from '../components/lineage/NodeDetailsPanel';
import { useDashboardData } from '../hooks/useDashboardData';
import { ApiLineageNode } from '../types/lineage';
import { IncidentItem } from '../types/dashboard';

interface DashboardPageProps {
  activeView?: 'dashboard' | 'lineage' | 'incidents';
  onSelectView?: (view: 'dashboard' | 'lineage' | 'incidents') => void;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({
  activeView = 'dashboard',
  onSelectView = () => {},
}) => {
  const {
    metrics,
    pipelineStatus,
    lineage,
    incidents,
    quality,
    isLoading,
    isRefreshing,
    errors,
    lastUpdated,
    refreshData,
  } = useDashboardData(15000);

  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedIncident, setSelectedIncident] = useState<IncidentItem | null>(null);

  // Selected node lookup
  const selectedNode: ApiLineageNode | null = useMemo(() => {
    if (!lineage || !selectedNodeId) return null;
    return lineage.nodes.find((n) => n.id === selectedNodeId) || null;
  }, [lineage, selectedNodeId]);

  // Active open incident (if any)
  const activeIncident: IncidentItem | null = useMemo(() => {
    return incidents.find((i) => i.status === 'OPEN' || i.status === 'ACKNOWLEDGED') || null;
  }, [incidents]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-sky-500 selection:text-white">
      {/* Top Main Application Header */}
      <Header
        pipelineStatus={pipelineStatus}
        lastUpdated={lastUpdated}
        isRefreshing={isRefreshing}
        onRefresh={() => refreshData(true)}
        activeView={activeView}
        onSelectView={onSelectView}
      />

      {/* Main Dashboard Body Container */}
      <main className="flex-1 p-4 sm:p-6 lg:px-8 space-y-6 max-w-[1600px] w-full mx-auto">
        {/* KPI Cards Row */}
        <KpiCards
          metrics={metrics}
          pipelineStatus={pipelineStatus}
          quality={quality}
          isLoading={isLoading}
        />

        {/* Operational Lineage Section */}
        <section className="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-4 sm:p-5 shadow-xl flex flex-col min-h-[580px] relative">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800/80 mb-4">
            <div className="flex items-center gap-2">
              <Layers className="w-4 h-4 text-sky-400" />
              <h2 className="font-bold text-sm text-slate-100">Pipeline Data Lineage DAG</h2>
            </div>
            {lineage?.nodes && (
              <span className="text-[11px] font-mono text-slate-500">
                {lineage.nodes.length} nodes • {lineage.edges.length} edges
              </span>
            )}
          </div>

          {/* Lineage Loading State */}
          {isLoading && (
            <div className="flex-1 flex flex-col items-center justify-center p-12 rounded-xl bg-slate-950/40 border border-slate-800/60 min-h-[450px]">
              <RefreshCw className="w-8 h-8 text-sky-400 animate-spin mb-4" />
              <h3 className="text-base font-semibold text-slate-200">Loading pipeline lineage...</h3>
              <p className="text-xs text-slate-400 mt-1">Connecting to IceStream Observability Telemetry</p>
            </div>
          )}

          {/* Lineage Error State */}
          {!isLoading && errors.lineage && (
            <div className="flex-1 flex flex-col items-center justify-center p-12 rounded-xl bg-slate-950/40 border border-slate-800/60 min-h-[450px] text-center">
              <div className="p-3 rounded-full bg-rose-500/10 border border-rose-500/20 text-rose-400 mb-4">
                <AlertCircle className="w-8 h-8" />
              </div>
              <h3 className="text-base font-bold text-slate-100">Lineage unavailable</h3>
              <p className="text-xs text-slate-400 max-w-md mt-1 font-mono text-rose-400">
                {errors.lineage}
              </p>
              <button
                onClick={() => refreshData(true)}
                className="mt-4 px-4 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold shadow-lg transition-colors flex items-center gap-2"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Retry Lineage Connection</span>
              </button>
            </div>
          )}

          {/* Live Lineage Graph Canvas */}
          {!isLoading && !errors.lineage && lineage && (
            <div className="flex-1 flex flex-col min-h-[480px] relative">
              <LineageCanvas
                data={lineage}
                selectedNodeId={selectedNodeId}
                onSelectNode={setSelectedNodeId}
              />
              <LineageLegend />
            </div>
          )}
        </section>

        {/* Timeline & Recent Incidents Section (Side by side on desktop) */}
        <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <ErrorRateTimeline
            history={metrics?.history}
            threshold={metrics?.circuit_breaker?.threshold || 0.02}
            isLoading={isLoading}
          />

          <RecentIncidents
            incidents={incidents}
            isLoading={isLoading}
            onSelectIncident={setSelectedIncident}
          />
        </section>
      </main>

      {/* Right Drawer Node Details & Diagnostic Panel */}
      <NodeDetailsPanel
        node={selectedNode}
        edges={lineage?.edges || []}
        nodes={lineage?.nodes || []}
        metrics={metrics}
        pipelineStatus={pipelineStatus}
        quality={quality}
        activeIncident={activeIncident}
        onOpenIncident={(inc) => {
          setSelectedNodeId(null);
          setSelectedIncident(inc);
        }}
        onClose={() => setSelectedNodeId(null)}
      />

      {/* Incident Detail Modal */}
      <IncidentDetailModal
        incident={selectedIncident}
        onClose={() => setSelectedIncident(null)}
        onIncidentUpdated={() => refreshData(true)}
      />
    </div>
  );
};
