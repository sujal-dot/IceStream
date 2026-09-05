import React, { useState } from 'react';
import { TrendingUp, AlertCircle, Info } from 'lucide-react';
import { ErrorRateHistoryPoint } from '../../types/dashboard';

interface ErrorRateTimelineProps {
  history?: ErrorRateHistoryPoint[];
  threshold?: number; // default 0.02 (2%)
  isLoading?: boolean;
}

export const ErrorRateTimeline: React.FC<ErrorRateTimelineProps> = ({
  history = [],
  threshold = 0.02,
  isLoading = false,
}) => {
  const [hoveredPoint, setHoveredPoint] = useState<ErrorRateHistoryPoint | null>(null);

  const thresholdPercent = threshold * 100; // 2.0%

  if (isLoading) {
    return (
      <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800/80 shadow-md flex flex-col justify-between min-h-[260px]">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
          <div className="flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-sky-400" />
            <h3 className="font-bold text-sm text-slate-100">Error Rate Timeline</h3>
          </div>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="h-32 w-full bg-slate-800/40 rounded animate-pulse" />
        </div>
      </div>
    );
  }

  // Graceful empty state when no historical metric points exist
  if (!history || history.length === 0) {
    return (
      <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800/80 shadow-md min-h-[260px] flex flex-col">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
          <div className="flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-sky-400" />
            <h3 className="font-bold text-sm text-slate-100">Error Rate Timeline</h3>
          </div>
          <span className="text-[11px] font-mono text-slate-500">2% Circuit Breaker Threshold</span>
        </div>
        <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-slate-950/40 rounded-xl border border-slate-800/60">
          <AlertCircle className="w-7 h-7 text-slate-500 mb-2" />
          <h4 className="text-xs font-semibold text-slate-300">Error rate history unavailable</h4>
          <p className="text-[11px] text-slate-500 mt-1 max-w-xs leading-relaxed">
            Historical metrics are not currently available. Timeline updates as events flow.
          </p>
        </div>
      </div>
    );
  }

  // Calculate SVG line dimensions
  const svgWidth = 600;
  const svgHeight = 160;
  const padding = 30;

  // Determine Y-axis max (at least 5% or highest error rate percent + margin)
  const maxVal = Math.max(
    thresholdPercent * 2,
    ...history.map((p) => p.error_rate_percent * 1.25),
    4.0
  );

  const getX = (index: number) => {
    if (history.length <= 1) return padding + (svgWidth - 2 * padding) / 2;
    return padding + (index / (history.length - 1)) * (svgWidth - 2 * padding);
  };

  const getY = (valPercent: number) => {
    return svgHeight - padding - (valPercent / maxVal) * (svgHeight - 2 * padding);
  };

  // Generate SVG path for error rate points
  const pointsString = history
    .map((p, i) => `${getX(i)},${getY(p.error_rate_percent)}`)
    .join(' ');

  const thresholdY = getY(thresholdPercent);

  return (
    <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800/80 shadow-md min-h-[260px] flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
        <div className="flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-sky-400" />
          <h3 className="font-bold text-sm text-slate-100">Error Rate Timeline</h3>
        </div>
        <div className="flex items-center gap-4 text-[11px] font-mono">
          <div className="flex items-center gap-1.5 text-rose-400">
            <span className="w-2.5 h-0.5 bg-rose-500 rounded" />
            <span>2% Circuit Threshold</span>
          </div>
          <div className="flex items-center gap-1.5 text-sky-400">
            <span className="w-2 h-2 rounded-full bg-sky-400" />
            <span>Error Rate %</span>
          </div>
        </div>
      </div>

      {/* SVG Responsive Chart Container */}
      <div className="relative flex-1 flex flex-col justify-center">
        <svg
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          className="w-full h-auto overflow-visible select-none"
        >
          {/* Grid lines */}
          <line
            x1={padding}
            y1={getY(0)}
            x2={svgWidth - padding}
            y2={getY(0)}
            stroke="#334155"
            strokeWidth="1"
          />
          <line
            x1={padding}
            y1={getY(maxVal / 2)}
            x2={svgWidth - padding}
            y2={getY(maxVal / 2)}
            stroke="#1e293b"
            strokeWidth="1"
            strokeDasharray="4 4"
          />

          {/* 2% Threshold Reference Line */}
          <line
            x1={padding}
            y1={thresholdY}
            x2={svgWidth - padding}
            y2={thresholdY}
            stroke="#f43f5e"
            strokeWidth="1.5"
            strokeDasharray="5 4"
          />
          <text
            x={svgWidth - padding + 4}
            y={thresholdY + 3}
            fill="#f43f5e"
            fontSize="9"
            fontFamily="monospace"
          >
            2%
          </text>

          {/* Error Rate Line Path */}
          {history.length > 1 && (
            <polyline
              fill="none"
              stroke="#38bdf8"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              points={pointsString}
            />
          )}

          {/* Data Points */}
          {history.map((point, idx) => {
            const cx = getX(idx);
            const cy = getY(point.error_rate_percent);
            const isExceeded = point.error_rate_percent >= thresholdPercent;

            return (
              <g key={idx} className="cursor-pointer">
                <circle
                  cx={cx}
                  cy={cy}
                  r="4"
                  fill={isExceeded ? '#f43f5e' : '#38bdf8'}
                  stroke="#0f172a"
                  strokeWidth="2"
                  onMouseEnter={() => setHoveredPoint(point)}
                  onMouseLeave={() => setHoveredPoint(null)}
                />
              </g>
            );
          })}
        </svg>

        {/* Hover Tooltip display */}
        {hoveredPoint && (
          <div className="absolute top-2 right-2 p-2.5 rounded-lg bg-slate-950/95 border border-slate-800 shadow-xl text-[11px] font-mono space-y-1 backdrop-blur-md">
            <div className="text-slate-400 font-sans">
              Time: {new Date(hoveredPoint.timestamp).toLocaleTimeString()}
            </div>
            <div className="flex justify-between gap-3">
              <span className="text-slate-500">Error rate:</span>
              <span
                className={`font-bold ${
                  hoveredPoint.error_rate_percent >= thresholdPercent
                    ? 'text-rose-400'
                    : 'text-sky-400'
                }`}
              >
                {hoveredPoint.error_rate_percent.toFixed(2)}%
              </span>
            </div>
            <div className="flex justify-between gap-3 text-[10px]">
              <span className="text-slate-500">Events:</span>
              <span className="text-slate-300">
                {hoveredPoint.failed_events} failed / {hoveredPoint.total_events} total
              </span>
            </div>
          </div>
        )}
      </div>

      <div className="flex justify-between items-center text-[10px] font-mono text-slate-500 mt-2 border-t border-slate-800/60 pt-2">
        <span>Oldest: {new Date(history[0].timestamp).toLocaleTimeString()}</span>
        <span className="flex items-center gap-1">
          <Info className="w-3 h-3 text-slate-600" />
          <span>Calculated by ErrorRateEngine (1m sliding windows)</span>
        </span>
        <span>Latest: {new Date(history[history.length - 1].timestamp).toLocaleTimeString()}</span>
      </div>
    </div>
  );
};
