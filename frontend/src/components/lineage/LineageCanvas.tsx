import React, { useMemo, useCallback } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Node,
  Edge,
  NodeChange,
  EdgeChange,
  applyNodeChanges,
  applyEdgeChanges,
  BackgroundVariant,
  MarkerType,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { ApiLineageNode, ApiLineageEdge, ApiLineageResponse } from '../../types/lineage';
import { PipelineNode } from './PipelineNode';

interface LineageCanvasProps {
  data: ApiLineageResponse;
  selectedNodeId: string | null;
  onSelectNode: (nodeId: string | null) => void;
}

const DEFAULT_POSITIONS: Record<string, { x: number; y: number }> = {
  kafka: { x: 40, y: 140 },
  flink: { x: 310, y: 140 },
  'quality-engine': { x: 580, y: 140 },
  'iceberg-bronze': { x: 860, y: 140 },
  'iceberg-silver': { x: 1140, y: 140 },
  analytics: { x: 1420, y: 140 },

  // Failure branch
  quarantine: { x: 580, y: 370 },
  dlq: { x: 580, y: 560 },

  // Observability & Control nodes
  'error-rate-engine': { x: 860, y: 370 },
  'circuit-breaker': { x: 1140, y: 370 },
  'remediation-controller': { x: 1420, y: 370 },
};

export const LineageCanvas: React.FC<LineageCanvasProps> = ({
  data,
  selectedNodeId,
  onSelectNode,
}) => {
  const nodeTypes = useMemo(() => ({ pipelineNode: PipelineNode }), []);

  // Transform backend nodes to React Flow Node objects
  const initialNodes: Node[] = useMemo(() => {
    return data.nodes.map((n: ApiLineageNode) => {
      const pos = DEFAULT_POSITIONS[n.id] || { x: 100, y: 100 };
      const isSelected = n.id === selectedNodeId;

      return {
        id: n.id,
        type: 'pipelineNode',
        position: pos,
        data: {
          label: n.label,
          type: n.type,
          status: n.status || 'HEALTHY',
          details: n.details || {},
          selected: isSelected,
        },
      };
    });
  }, [data.nodes, selectedNodeId]);

  // Transform backend edges to React Flow Edge objects
  const initialEdges: Edge[] = useMemo(() => {
    return data.edges.map((e: ApiLineageEdge) => {
      const isFailureEdge = e.source === 'quality-engine' && e.target === 'quarantine' || e.source === 'quarantine' && e.target === 'dlq';

      let sourceHandle = 'source-right';
      let targetHandle = 'target-left';

      if (e.source === 'quality-engine' && e.target === 'quarantine') {
        sourceHandle = 'source-bottom';
        targetHandle = 'target-top';
      } else if (e.source === 'quarantine' && e.target === 'dlq') {
        sourceHandle = 'source-bottom';
        targetHandle = 'target-top';
      }

      return {
        id: e.id,
        source: e.source,
        target: e.target,
        sourceHandle,
        targetHandle,
        label: e.label,
        animated: e.animated ?? (!isFailureEdge),
        style: {
          stroke: isFailureEdge ? '#F59E0B' : '#38BDF8',
          strokeWidth: isFailureEdge ? 2 : 2.5,
          strokeDasharray: isFailureEdge ? '5,5' : undefined,
        },
        labelStyle: {
          fill: isFailureEdge ? '#FCD34D' : '#94A3B8',
          fontWeight: 600,
          fontSize: 11,
          fontFamily: 'JetBrains Mono, monospace',
        },
        labelBgStyle: {
          fill: '#0F172A',
          fillOpacity: 0.9,
          rx: 4,
          ry: 4,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          width: 16,
          height: 16,
          color: isFailureEdge ? '#F59E0B' : '#38BDF8',
        },
      };
    });
  }, [data.edges]);

  const [nodes, setNodes] = React.useState<Node[]>(initialNodes);
  const [edges, setEdges] = React.useState<Edge[]>(initialEdges);

  React.useEffect(() => {
    setNodes(initialNodes);
    setEdges(initialEdges);
  }, [initialNodes, initialEdges]);

  const onNodesChange = useCallback(
    (changes: NodeChange[]) => setNodes((nds) => applyNodeChanges(changes, nds)),
    []
  );

  const onEdgesChange = useCallback(
    (changes: EdgeChange[]) => setEdges((eds) => applyEdgeChanges(changes, eds)),
    []
  );

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      onSelectNode(node.id);
    },
    [onSelectNode]
  );

  const onPaneClick = useCallback(() => {
    onSelectNode(null);
  }, [onSelectNode]);

  return (
    <div className="w-full h-full min-h-[650px] relative bg-slate-950 rounded-xl overflow-hidden border border-slate-800/80 shadow-2xl">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        onPaneClick={onPaneClick}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.3}
        maxZoom={1.8}
        defaultEdgeOptions={{ type: 'smoothstep' }}
        proOptions={{ hideAttribution: true }}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={24}
          size={1.5}
          color="#334155"
        />
        <Controls
          className="!bg-slate-900/90 !border-slate-800 !shadow-xl !rounded-lg overflow-hidden flex flex-col gap-1 p-1 text-slate-300 [&>button]:!bg-slate-800 [&>button]:!border-slate-700 [&>button]:!text-slate-200 hover:[&>button]:!bg-slate-700"
        />
        <MiniMap
          nodeColor={(n) => {
            if (n.id === 'quarantine' || n.id === 'dlq') return '#F59E0B';
            if (n.id === selectedNodeId) return '#38BDF8';
            return '#334155';
          }}
          maskColor="rgba(15, 23, 42, 0.75)"
          className="!bg-slate-900 !border-slate-800 !rounded-lg shadow-xl"
          zoomable
          pannable
        />
      </ReactFlow>
    </div>
  );
};
