import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { AlertCircle, RefreshCw, Layers, GitCommit } from 'lucide-react';
import { ApiLineageResponse, ApiLineageNode, PipelineSummary } from '../types/lineage';
import { LineageApiService } from '../services/lineageApi';
import { LineageToolbar } from '../components/lineage/LineageToolbar';
import { LineageCanvas } from '../components/lineage/LineageCanvas';
import { NodeDetailsPanel } from '../components/lineage/NodeDetailsPanel';
import { LineageLegend } from '../components/lineage/LineageLegend';

export const PipelinePage: React.FC = () => {
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
    }, 2000);
    return () => clearInterval(intervalId);
  }, [fetchLineage]);

  const selectedNode: ApiLineageNode | null = useMemo(() => {
    if (!lineageData || !selectedNodeId) return null;
    return lineageData.nodes.find((n) => n.id === selectedNodeId) || null;
  }, [lineageData, selectedNodeId]);

  return (
    <div className="p-6 max-w-[1600px] mx-auto space-y-6 text-slate-100 font-sans">
      {/* Page Title Banner */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-5 rounded-2xl bg-slate-900/60 border border-slate-800 shadow-xl">
        <div className="flex items-center gap-3.5">
          <div className="p-3 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
            <GitCommit className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-extrabold text-white tracking-tight">
              Live Pipeline Topology & Data Lineage
            </h1>
            <p className="text-xs text-slate-400 mt-0.5 font-mono">
              Interactive end-to-end stream topology visualizer (Kafka → Flink → Quality Engine → Iceberg / Quarantine)
            </p>
          </div>
        </div>

        <button
          onClick={() => fetchLineage(true)}
          disabled={isRefreshing}
          className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 transition-all disabled:opacity-50 font-mono"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-cyan-400' : ''}`} />
          <span>Refresh Lineage</span>
        </button>
      </div>

      {/* Lineage Toolbar */}
      <LineageToolbar
        streamName="checkout-stream"
        lastUpdated={lastUpdated}
        isRefreshing={isRefreshing}
        pipelineSummary={pipelineSummary}
        onRefresh={() => fetchLineage(true)}
      />

      {/* Main Graph Content */}
      <div className="flex-1 flex flex-col relative min-h-[650px]">
        {isLoading && (
          <div className="flex-1 flex flex-col items-center justify-center p-12 rounded-xl bg-slate-900/60 border border-slate-800 h-[600px]">
            <RefreshCw className="w-8 h-8 text-cyan-400 animate-spin mb-4" />
            <h3 className="text-base font-semibold text-slate-200 font-mono">
              Loading pipeline lineage topology...
            </h3>
          </div>
        )}

        {!isLoading && error && (
          <div className="flex-1 flex flex-col items-center justify-center p-12 rounded-xl bg-slate-900/60 border border-slate-800 h-[600px] text-center">
            <AlertCircle className="w-8 h-8 text-rose-400 mb-3" />
            <h3 className="text-lg font-bold text-slate-100">Unable to load topology</h3>
            <p className="text-xs text-slate-400 font-mono mt-1">{error}</p>
          </div>
        )}

        {!isLoading && !error && lineageData && (
          <div className="relative flex-1">
            <LineageCanvas
              data={lineageData}
              selectedNodeId={selectedNodeId}
              onSelectNode={setSelectedNodeId}
            />
            <LineageLegend />
          </div>
        )}

        <NodeDetailsPanel
          node={selectedNode}
          edges={lineageData?.edges || []}
          nodes={lineageData?.nodes || []}
          onClose={() => setSelectedNodeId(null)}
        />
      </div>
    </div>
  );
};
