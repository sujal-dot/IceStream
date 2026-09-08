import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { AlertCircle, RefreshCw, Layers } from 'lucide-react';
import { ApiLineageResponse, ApiLineageNode, PipelineSummary } from '../types/lineage';
import { PipelineStatusResponse } from '../types/dashboard';
import { LineageApiService } from '../services/lineageApi';
import { Header } from '../components/dashboard/Header';
import { LineageToolbar } from '../components/lineage/LineageToolbar';
import { LineageCanvas } from '../components/lineage/LineageCanvas';
import { NodeDetailsPanel } from '../components/lineage/NodeDetailsPanel';
import { LineageLegend } from '../components/lineage/LineageLegend';

interface LineagePageProps {
  activeView?: 'dashboard' | 'lineage' | 'incidents';
  onSelectView?: (view: 'dashboard' | 'lineage' | 'incidents') => void;
}

export const LineagePage: React.FC<LineagePageProps> = ({
  activeView = 'lineage',
  onSelectView = () => {},
}) => {
  const [lineageData, setLineageData] = useState<ApiLineageResponse | null>(null);
  const [pipelineSummary, setPipelineSummary] = useState<PipelineSummary | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const fetchLineage = useCallback(async (isManualRefresh = false) => {
    if (isManualRefresh) {
      setIsRefreshing(true);
    } else {
      setIsLoading(true);
    }
    setError(null);

    try {
      const data = await LineageApiService.getLineage();
      setLineageData(data);
      setLastUpdated(new Date().toLocaleTimeString());

      // Fetch summary telemetry
      const summary = await LineageApiService.getPipelineSummary();
      if (summary) {
        setPipelineSummary(summary);
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Unknown backend API connection error';
      setError(message);
      setLineageData(null);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchLineage(false);
    const intervalId = setInterval(() => {
      fetchLineage(true);
    }, 1000);
    return () => clearInterval(intervalId);
  }, [fetchLineage]);

  // Selected node object lookup
  const selectedNode: ApiLineageNode | null = useMemo(() => {
    if (!lineageData || !selectedNodeId) return null;
    return lineageData.nodes.find((n) => n.id === selectedNodeId) || null;
  }, [lineageData, selectedNodeId]);

  const pipelineStatus: PipelineStatusResponse | null = useMemo(() => {
    if (!pipelineSummary) return null;
    return {
      pipeline_id: pipelineSummary.pipeline_id || 'icestream',
      state: pipelineSummary.state || 'RUNNING',
      recovery_attempt: 0,
      updated_at: lastUpdated || '',
    };
  }, [pipelineSummary, lastUpdated]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-sky-500 selection:text-white">
      {/* Top Header Navigation */}
      <Header
        pipelineStatus={pipelineStatus}
        lastUpdated={lastUpdated}
        isRefreshing={isRefreshing}
        onRefresh={() => fetchLineage(true)}
        activeView={activeView}
        onSelectView={onSelectView}
      />

      <div className="flex-1 flex flex-col h-full bg-slate-950 text-slate-100 p-4 sm:p-6 lg:p-8 font-sans">
        {/* Top Lineage Toolbar */}
        <LineageToolbar
          streamName="checkout-stream"
          lastUpdated={lastUpdated}
          isRefreshing={isRefreshing}
          pipelineSummary={pipelineSummary}
          onRefresh={() => fetchLineage(true)}
          onBack={() => onSelectView('dashboard')}
        />

      {/* Main Viewport Content Area */}
      <div className="flex-1 flex flex-col relative">
        {/* Loading State */}
        {isLoading && (
          <div className="flex-1 flex flex-col items-center justify-center p-12 rounded-xl bg-slate-900/60 border border-slate-800 min-h-[550px]">
            <RefreshCw className="w-8 h-8 text-sky-400 animate-spin mb-4" />
            <h3 className="text-base font-semibold text-slate-200">Loading pipeline lineage...</h3>
            <p className="text-xs text-slate-400 mt-1">Connecting to IceStream Telemetry Backend</p>
          </div>
        )}

        {/* Error State */}
        {!isLoading && error && (
          <div className="flex-1 flex flex-col items-center justify-center p-12 rounded-xl bg-slate-900/60 border border-slate-800/80 min-h-[550px] text-center">
            <div className="p-3 rounded-full bg-rose-500/10 border border-rose-500/20 text-rose-400 mb-4">
              <AlertCircle className="w-8 h-8" />
            </div>
            <h3 className="text-lg font-bold text-slate-100">Unable to load pipeline lineage</h3>
            <p className="text-xs text-slate-400 max-w-md mt-2 leading-relaxed">
              The observability backend service is currently unavailable or unreachable.
            </p>
            <div className="mt-2 font-mono text-[11px] text-rose-400 bg-rose-950/40 px-3 py-1 rounded border border-rose-900/60">
              {error}
            </div>
            <button
              onClick={() => fetchLineage(false)}
              className="mt-6 flex items-center gap-2 px-4 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold shadow-lg transition-colors"
            >
              <RefreshCw className="w-4 h-4" />
              <span>Retry Connection</span>
            </button>
          </div>
        )}

        {/* Empty State */}
        {!isLoading && !error && lineageData && lineageData.nodes.length === 0 && (
          <div className="flex-1 flex flex-col items-center justify-center p-12 rounded-xl bg-slate-900/60 border border-slate-800 min-h-[550px] text-center">
            <Layers className="w-8 h-8 text-slate-500 mb-3" />
            <h3 className="text-base font-semibold text-slate-300">No lineage data available</h3>
            <p className="text-xs text-slate-400 mt-1">
              The pipeline has not reported lineage information yet.
            </p>
          </div>
        )}

        {/* Live Lineage Graph Canvas */}
        {!isLoading && !error && lineageData && lineageData.nodes.length > 0 && (
          <div className="flex-1 flex flex-col h-[650px] relative">
            <LineageCanvas
              data={lineageData}
              selectedNodeId={selectedNodeId}
              onSelectNode={setSelectedNodeId}
            />

            {/* Bottom Legend */}
            <LineageLegend />
          </div>
        )}

        {/* Right Drawer Node Details Panel */}
        <NodeDetailsPanel
          node={selectedNode}
          edges={lineageData?.edges || []}
          nodes={lineageData?.nodes || []}
          onClose={() => setSelectedNodeId(null)}
        />
      </div>
    </div>
  </div>
);
};
