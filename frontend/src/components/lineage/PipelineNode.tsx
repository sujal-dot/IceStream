import React, { memo } from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';
import {
  Database,
  Cpu,
  Radio,
  ShieldCheck,
  AlertOctagon,
  BarChart3,
  Archive,
  Activity,
  Zap,
  RefreshCw,
} from 'lucide-react';
import { LineageNodeData } from '../../types/lineage';
import { getStatusStyle } from '../../utils/statusStyles';

function getNodeIcon(id: string, type: string) {
  const key = (id || type || '').toLowerCase();
  if (key.includes('kafka')) return <Radio className="w-4 h-4 text-sky-400" />;
  if (key.includes('flink')) return <Cpu className="w-4 h-4 text-indigo-400" />;
  if (key.includes('quality')) return <ShieldCheck className="w-4 h-4 text-emerald-400" />;
  if (key.includes('iceberg') || key.includes('bronze') || key.includes('silver')) {
    return <Database className="w-4 h-4 text-cyan-400" />;
  }
  if (key.includes('quarantine')) return <Archive className="w-4 h-4 text-amber-400" />;
  if (key.includes('dlq')) return <AlertOctagon className="w-4 h-4 text-rose-400" />;
  if (key.includes('analytics')) return <BarChart3 className="w-4 h-4 text-purple-400" />;
  if (key.includes('circuit')) return <Zap className="w-4 h-4 text-yellow-400" />;
  if (key.includes('remediation')) return <RefreshCw className="w-4 h-4 text-blue-400" />;
  return <Activity className="w-4 h-4 text-slate-400" />;
}

export const PipelineNode = memo(({ id, data, selected }: NodeProps) => {
  const nodeData = data as unknown as LineageNodeData;
  const statusStyle = getStatusStyle(nodeData?.status);
  const resource = nodeData?.details?.resource || nodeData?.details?.subtitle || nodeData?.details?.topic || nodeData?.details?.table;
  const description = nodeData?.details?.description;

  return (
    <div
      className={`relative min-w-[210px] max-w-[240px] rounded-xl border p-3.5 shadow-lg transition-all duration-200 bg-slate-900/90 backdrop-blur-md ${
        selected ? 'ring-2 ring-sky-500 border-sky-400 shadow-sky-500/20' : 'border-slate-800 hover:border-slate-700'
      }`}
      style={{
        borderColor: selected ? '#38BDF8' : undefined,
      }}
    >
      {/* Input handles (Left and Top) */}
      <Handle
        type="target"
        position={Position.Left}
        id="target-left"
        className="!bg-slate-500 !w-3 !h-3 !border-2 !border-slate-900"
      />
      <Handle
        type="target"
        position={Position.Top}
        id="target-top"
        className="!bg-slate-500 !w-3 !h-3 !border-2 !border-slate-900"
      />

      {/* Header with status dot and title */}
      <div className="flex items-center justify-between gap-2 mb-2">
        <div className="flex items-center gap-2 overflow-hidden">
          <div className="p-1.5 rounded-lg bg-slate-800/80 border border-slate-700/60">
            {getNodeIcon(id, nodeData?.type)}
          </div>
          <span className="font-semibold text-sm text-slate-100 truncate tracking-tight">
            {nodeData?.label}
          </span>
        </div>

        {/* Status Dot */}
        <div className="flex items-center gap-1.5 shrink-0">
          <span
            className="w-2.5 h-2.5 rounded-full inline-block animate-pulse"
            style={{ backgroundColor: statusStyle.dotBg }}
            title={statusStyle.ariaLabel}
          />
        </div>
      </div>

      {/* Subtitle / Resource tag */}
      {resource && (
        <div className="font-mono text-[11px] text-slate-400 bg-slate-950/60 px-2 py-0.5 rounded border border-slate-800/80 truncate mb-1.5">
          {resource}
        </div>
      )}

      {/* Description */}
      {description && (
        <div className="text-[11px] text-slate-400 line-clamp-2 leading-relaxed mb-2">
          {description}
        </div>
      )}

      {/* Footer Status Badge */}
      <div className="flex items-center justify-between pt-1 border-t border-slate-800/60 text-[10px]">
        <span className="text-slate-500 font-mono uppercase tracking-wider text-[9px]">
          {nodeData?.type}
        </span>
        <span
          className="font-medium px-1.5 py-0.5 rounded text-[10px]"
          style={{
            backgroundColor: statusStyle.badgeBg,
            color: statusStyle.badgeText,
          }}
        >
          {statusStyle.label}
        </span>
      </div>

      {/* Output handles (Right and Bottom) */}
      <Handle
        type="source"
        position={Position.Right}
        id="source-right"
        className="!bg-sky-500 !w-3 !h-3 !border-2 !border-slate-900"
      />
      <Handle
        type="source"
        position={Position.Bottom}
        id="source-bottom"
        className="!bg-amber-500 !w-3 !h-3 !border-2 !border-slate-900"
      />
    </div>
  );
});

PipelineNode.displayName = 'PipelineNode';
