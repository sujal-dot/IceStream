import React from 'react';
import { X, Server, Layers, ShieldCheck, Tag, Info, ArrowRight, AlertOctagon, ExternalLink } from 'lucide-react';
import { ApiLineageNode, ApiLineageEdge } from '../../types/lineage';
import { IncidentItem, MetricsResponse, PipelineStatusResponse, QualityResponse } from '../../types/dashboard';
import { getStatusStyle } from '../../utils/statusStyles';

interface NodeDetailsPanelProps {
  node: ApiLineageNode | null;
  edges: ApiLineageEdge[];
  nodes: ApiLineageNode[];
  metrics?: MetricsResponse | null;
  pipelineStatus?: PipelineStatusResponse | null;
  quality?: QualityResponse | null;
  activeIncident?: IncidentItem | null;
  onOpenIncident?: (incident: IncidentItem) => void;
  onClose: () => void;
}

export const NodeDetailsPanel: React.FC<NodeDetailsPanelProps> = ({
  node,
  edges,
  nodes,
  metrics,
  pipelineStatus,
  quality,
  activeIncident,
  onOpenIncident,
  onClose,
}) => {
  if (!node) return null;

  const statusStyle = getStatusStyle(node.status);
  const details = node.details || {};

  // Check if node is unhealthy or experiencing active pipeline degradation
  const isUnhealthy =
    node.status === 'CRITICAL' ||
    node.status === 'WARNING' ||
    node.status === 'DEGRADED' ||
    node.status === 'CIRCUIT_OPEN' ||
    node.status === 'PAUSED' ||
    pipelineStatus?.state === 'CIRCUIT_OPEN' ||
    !!activeIncident;

  const m1 = metrics?.windows?.['1m'];
  const errorRateText = m1 ? `${m1.error_rate_percent.toFixed(2)}%` : '0.00%';
  const cbState = metrics?.circuit_breaker?.state || pipelineStatus?.state || 'CLOSED';

  // Top failures breakdown
  const topFailures = quality?.top_failures || {};
  const hasFailures = Object.keys(topFailures).length > 0;

  // Find downstream target node labels
  const downstreamNodeIds = edges
    .filter((e) => e.source === node.id)
    .map((e) => e.target);

  const downstreamNodes = nodes.filter((n) => downstreamNodeIds.includes(n.id));

  // Find upstream source node labels
  const upstreamNodeIds = edges
    .filter((e) => e.target === node.id)
    .map((e) => e.source);

  const upstreamNodes = nodes.filter((n) => upstreamNodeIds.includes(n.id));

  return (
    <div className="fixed inset-y-0 right-0 w-80 sm:w-96 bg-slate-900/95 border-l border-slate-800 shadow-2xl backdrop-blur-xl z-50 flex flex-col transition-all duration-300 transform translate-x-0">
      {/* Drawer Header */}
      <div className="flex items-center justify-between p-4 border-b border-slate-800 bg-slate-950/60">
        <div className="flex items-center gap-2 overflow-hidden">
          <Server className="w-4 h-4 text-sky-400 shrink-0" />
          <h2 className="font-bold text-sm text-slate-100 truncate">{node.label}</h2>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
          title="Close Details Panel"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Drawer Content Body */}
      <div className="flex-1 overflow-y-auto p-5 space-y-6">
        {/* Status Section */}
        <div className="p-3.5 rounded-xl bg-slate-950/80 border border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span
              className="w-3 h-3 rounded-full animate-pulse"
              style={{ backgroundColor: statusStyle.dotBg }}
            />
            <span className="text-xs font-semibold text-slate-300">Runtime Health</span>
          </div>
          <span
            className="px-2 py-0.5 rounded font-mono text-xs font-semibold"
            style={{
              backgroundColor: statusStyle.badgeBg,
              color: statusStyle.badgeText,
            }}
          >
            {statusStyle.label}
          </span>
        </div>

        {/* Why is this node red? / Diagnostic Panel */}
        {isUnhealthy && (
          <div className="p-4 rounded-xl bg-rose-950/30 border border-rose-900/60 space-y-3 shadow-inner">
            <div className="flex items-center gap-2 text-rose-400">
              <AlertOctagon className="w-4 h-4 shrink-0" />
              <h3 className="font-bold text-xs uppercase tracking-wider text-rose-200">
                Why is this node red?
              </h3>
            </div>

            <div className="space-y-2 text-xs font-mono">
              <div className="flex justify-between py-1 border-b border-rose-900/40">
                <span className="text-slate-400">Error rate:</span>
                <span className="text-rose-300 font-bold">{errorRateText}</span>
              </div>

              <div className="flex justify-between py-1 border-b border-rose-900/40">
                <span className="text-slate-400">Circuit breaker:</span>
                <span className={`font-bold ${cbState === 'OPEN' ? 'text-rose-400' : 'text-slate-200'}`}>
                  {cbState}
                </span>
              </div>

              <div className="flex justify-between py-1 border-b border-rose-900/40">
                <span className="text-slate-400">Expected recovery:</span>
                <span className="text-sky-300 font-semibold">
                  {pipelineStatus?.stage ? pipelineStatus.stage : 'automatic'}
                </span>
              </div>

              {pipelineStatus?.updated_at && (
                <div className="flex justify-between py-1 border-b border-rose-900/40">
                  <span className="text-slate-400">State updated:</span>
                  <span className="text-slate-300">
                    {new Date(pipelineStatus.updated_at).toLocaleTimeString()}
                  </span>
                </div>
              )}
            </div>

            {/* Top Failures */}
            <div className="pt-2">
              <span className="text-[11px] font-bold uppercase tracking-wide text-slate-300 block mb-1">
                Top failures
              </span>
              {hasFailures ? (
                <div className="space-y-1 bg-slate-950/60 p-2.5 rounded-lg border border-slate-800 text-[11px] font-mono">
                  {Object.entries(topFailures).map(([rule, count]) => (
                    <div key={rule} className="flex justify-between items-center">
                      <span className="text-slate-400">{rule}</span>
                      <span className="text-rose-400 font-semibold">{count}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-[11px] text-slate-400 italic">No recent quality failures</p>
              )}
            </div>

            {/* Active Incident Link */}
            {activeIncident && onOpenIncident && (
              <div className="pt-2 border-t border-rose-900/50">
                <div className="text-[11px] text-slate-400 mb-1">Active Incident:</div>
                <button
                  onClick={() => onOpenIncident(activeIncident)}
                  className="w-full flex items-center justify-between px-3 py-2 rounded-lg bg-rose-900/40 hover:bg-rose-900/60 border border-rose-800 text-xs font-mono text-rose-200 transition-colors"
                >
                  <span className="font-bold">{activeIncident.incident_id}</span>
                  <div className="flex items-center gap-1.5 text-sky-400 font-sans text-[11px]">
                    <span>View Details</span>
                    <ExternalLink className="w-3.5 h-3.5" />
                  </div>
                </button>
              </div>
            )}
          </div>
        )}

        {/* Basic Node Spec */}
        <div className="space-y-3">
          <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
            <Tag className="w-3.5 h-3.5 text-sky-400" />
            Component Spec
          </h3>
          <div className="rounded-xl bg-slate-950/60 border border-slate-800/80 p-3.5 space-y-2.5 text-xs font-mono">
            <div className="flex justify-between">
              <span className="text-slate-500">Node ID:</span>
              <span className="text-slate-200 font-semibold">{node.id}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Component Type:</span>
              <span className="text-sky-400 uppercase font-semibold">{node.type}</span>
            </div>
            {details.description && (
              <div className="pt-2 border-t border-slate-800/60 font-sans text-slate-300 leading-relaxed">
                {details.description}
              </div>
            )}
          </div>
        </div>

        {/* Key Metadata Details */}
        {Object.keys(details).length > 0 && (
          <div className="space-y-3">
            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
              <Info className="w-3.5 h-3.5 text-indigo-400" />
              Runtime Parameters
            </h3>
            <div className="rounded-xl bg-slate-950/60 border border-slate-800/80 divide-y divide-slate-800/60 text-xs font-mono">
              {Object.entries(details).map(([key, val]) => {
                if (key === 'description') return null;
                return (
                  <div key={key} className="p-3 flex items-center justify-between gap-4">
                    <span className="text-slate-500 capitalize">{key.replace(/_/g, ' ')}</span>
                    <span className="text-slate-200 text-right truncate max-w-[180px]" title={val}>
                      {val}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Upstream Components */}
        {upstreamNodes.length > 0 && (
          <div className="space-y-3">
            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-emerald-400" />
              Upstream Sources
            </h3>
            <div className="space-y-1.5">
              {upstreamNodes.map((uNode) => (
                <div
                  key={uNode.id}
                  className="flex items-center gap-2 p-2.5 rounded-lg bg-slate-950/60 border border-slate-800/80 text-xs text-slate-300"
                >
                  <ArrowRight className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                  <span className="font-semibold text-slate-200">{uNode.label}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Downstream Components */}
        {downstreamNodes.length > 0 && (
          <div className="space-y-3">
            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-sky-400" />
              Downstream Targets
            </h3>
            <div className="space-y-1.5">
              {downstreamNodes.map((dNode) => (
                <div
                  key={dNode.id}
                  className="flex items-center gap-2 p-2.5 rounded-lg bg-slate-950/60 border border-slate-800/80 text-xs text-slate-300"
                >
                  <ArrowRight className="w-3.5 h-3.5 text-sky-400 shrink-0" />
                  <span className="font-semibold text-slate-200">{dNode.label}</span>
                  {dNode.id === 'quarantine' || dNode.id === 'dlq' ? (
                    <span className="ml-auto font-mono text-[10px] text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded border border-amber-500/20">
                      Failure Branch
                    </span>
                  ) : null}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Drawer Footer */}
      <div className="p-4 border-t border-slate-800 bg-slate-950/80 text-[11px] text-slate-500 text-center font-mono">
        IceStream Telemetry • Real-Time Lineage Inspector
      </div>
    </div>
  );
};
