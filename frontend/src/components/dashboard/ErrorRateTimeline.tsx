import React, { useState, useMemo, useRef } from 'react';
import { TrendingUp, AlertCircle, Info, Activity, Zap } from 'lucide-react';
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
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const thresholdPercent = threshold * 100; // 2.0%

  // Compute summary stats
  const stats = useMemo(() => {
    if (!history || history.length === 0) {
      return { current: 0, peak: 0, avg: 0, latestPoint: null, totalEvents: 0 };
    }
    const rates = history.map((p) => p.error_rate_percent);
    const current = rates[rates.length - 1] || 0;
    const peak = Math.max(...rates);
    const avg = rates.reduce((a, b) => a + b, 0) / rates.length;
    const latestPoint = history[history.length - 1];
    const totalEvents = history.reduce((acc, p) => acc + (p.total_events || 0), 0);

    return { current, peak, avg, latestPoint, totalEvents };
  }, [history]);

  // Loading skeleton
  if (isLoading) {
    return (
      <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800/80 shadow-xl min-h-[300px] flex flex-col justify-between">
        <div className="flex items-center justify-between border-b border-slate-800/80 pb-3 mb-4">
          <div className="flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-sky-400" />
            <h3 className="font-bold text-sm text-slate-100">Error Rate Timeline</h3>
          </div>
          <div className="h-6 w-32 bg-slate-800/60 rounded-lg animate-pulse" />
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="h-40 w-full bg-slate-800/30 rounded-xl animate-pulse" />
        </div>
      </div>
    );
  }

  // Graceful empty state
  if (!history || history.length === 0) {
    return (
      <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800/80 shadow-xl min-h-[300px] flex flex-col">
        <div className="flex items-center justify-between border-b border-slate-800/80 pb-3 mb-4">
          <div className="flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-sky-400" />
            <h3 className="font-bold text-sm text-slate-100">Error Rate Timeline</h3>
          </div>
          <span className="text-[11px] font-mono text-slate-500">2% Circuit Breaker Threshold</span>
        </div>
        <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-slate-950/40 rounded-xl border border-slate-800/60">
          <AlertCircle className="w-8 h-8 text-slate-500 mb-2" />
          <h4 className="text-xs font-semibold text-slate-300">Error rate history unavailable</h4>
          <p className="text-[11px] text-slate-500 mt-1 max-w-xs leading-relaxed">
            Historical metrics are not currently available. Timeline updates as events flow.
          </p>
        </div>
      </div>
    );
  }

  // Dimensions & Coordinate Mapping
  const svgWidth = 700;
  const svgHeight = 180;
  const paddingX = 35;
  const paddingTop = 25;
  const paddingBottom = 30;

  // Y-axis upper limit (minimum 4%, or 1.3x max recorded error rate)
  const maxVal = Math.max(thresholdPercent * 2, ...history.map((p) => p.error_rate_percent * 1.3), 4.0);

  const getX = (index: number) => {
    if (history.length <= 1) return paddingX + (svgWidth - 2 * paddingX) / 2;
    return paddingX + (index / (history.length - 1)) * (svgWidth - 2 * paddingX);
  };

  const getY = (valPercent: number) => {
    const chartHeight = svgHeight - paddingTop - paddingBottom;
    return svgHeight - paddingBottom - (valPercent / maxVal) * chartHeight;
  };

  const thresholdY = getY(thresholdPercent);
  const baselineY = getY(0);

  // Build point pairs for path drawing
  const points = history.map((p, i) => ({
    x: getX(i),
    y: getY(p.error_rate_percent),
    data: p,
  }));

  // Smooth Bezier Curve generator
  const getSmoothPath = (pts: { x: number; y: number }[]) => {
    if (pts.length === 0) return '';
    if (pts.length === 1) return `M ${pts[0].x},${pts[0].y}`;

    let path = `M ${pts[0].x},${pts[0].y}`;
    for (let i = 0; i < pts.length - 1; i++) {
      const curr = pts[i];
      const next = pts[i + 1];
      const mx = (curr.x + next.x) / 2;
      path += ` C ${mx},${curr.y} ${mx},${next.y} ${next.x},${next.y}`;
    }
    return path;
  };

  const smoothLinePath = getSmoothPath(points);
  const areaPath = points.length > 0
    ? `${smoothLinePath} L ${points[points.length - 1].x},${baselineY} L ${points[0].x},${baselineY} Z`
    : '';

  // Handle Mouse Over Track
  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!containerRef.current || points.length === 0) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const scaleX = svgWidth / rect.width;
    const chartX = mouseX * scaleX;

    // Find nearest point
    let closestIndex = 0;
    let minDistance = Infinity;
    points.forEach((pt, i) => {
      const dist = Math.abs(pt.x - chartX);
      if (dist < minDistance) {
        minDistance = dist;
        closestIndex = i;
      }
    });

    setHoveredIdx(closestIndex);
  };

  const activePoint = hoveredIdx !== null ? points[hoveredIdx] : null;
  const isBreached = stats.current >= thresholdPercent;

  return (
    <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800/80 shadow-xl min-h-[300px] flex flex-col justify-between">
      {/* Header with Title & Stat Pills */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800/80 pb-3 mb-3">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-xl bg-sky-500/10 border border-sky-500/20 text-sky-400">
            <TrendingUp className="w-4 h-4" />
          </div>
          <div>
            <h3 className="font-extrabold text-sm text-slate-100 tracking-tight">
              Error Rate Timeline
            </h3>
            <p className="text-[11px] text-slate-400 font-mono">
              1m rolling window telemetry
            </p>
          </div>
        </div>

        {/* Real-time Summary KPI Badges */}
        <div className="flex flex-wrap items-center gap-2 text-xs font-mono">
          {/* Current Rate Pill */}
          <div className={`px-2.5 py-1 rounded-lg border flex items-center gap-1.5 font-bold ${
            isBreached
              ? 'bg-rose-500/10 border-rose-500/30 text-rose-400'
              : 'bg-sky-500/10 border-sky-500/20 text-sky-400'
          }`}>
            <span className={`w-1.5 h-1.5 rounded-full ${isBreached ? 'bg-rose-400 animate-ping' : 'bg-sky-400'}`} />
            <span>Current: {stats.current.toFixed(2)}%</span>
          </div>

          {/* Peak Rate Pill */}
          <div className="px-2.5 py-1 rounded-lg bg-slate-950/60 border border-slate-800 text-slate-300 font-medium">
            <span className="text-slate-500 mr-1">Peak:</span>
            <span className={stats.peak >= thresholdPercent ? 'text-amber-400 font-bold' : 'text-slate-200'}>
              {stats.peak.toFixed(2)}%
            </span>
          </div>

          {/* Threshold Legend Pill */}
          <div className="px-2.5 py-1 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 font-semibold flex items-center gap-1.5">
            <span className="w-2.5 h-0.5 bg-rose-500 rounded" />
            <span>2% Circuit Threshold</span>
          </div>
        </div>
      </div>

      {/* SVG Responsive Chart Viewport */}
      <div ref={containerRef} className="relative flex-1 flex flex-col justify-center my-1 select-none">
        <svg
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          className="w-full h-auto overflow-visible"
          onMouseMove={handleMouseMove}
          onMouseLeave={() => setHoveredIdx(null)}
        >
          <defs>
            {/* Smooth Cyan to Dark Slate Area Fill */}
            <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.35" />
              <stop offset="100%" stopColor="#38bdf8" stopOpacity="0.0" />
            </linearGradient>

            {/* Red Breach Area Fill */}
            <linearGradient id="breachGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#f43f5e" stopOpacity="0.45" />
              <stop offset="100%" stopColor="#f43f5e" stopOpacity="0.0" />
            </linearGradient>

            {/* Stroke Line Gradient */}
            <linearGradient id="lineGradient" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#38bdf8" />
              <stop offset="70%" stopColor={stats.peak >= thresholdPercent ? '#fb7185' : '#38bdf8'} />
              <stop offset="100%" stopColor={isBreached ? '#f43f5e' : '#38bdf8'} />
            </linearGradient>

            {/* Shaded Red Danger Zone above 2% */}
            <pattern id="dangerPattern" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <line x1="0" y1="0" x2="0" y2="8" stroke="#f43f5e" strokeWidth="1" strokeOpacity="0.15" />
            </pattern>
          </defs>

          {/* Danger Zone Shading Above 2% Line */}
          {thresholdY > paddingTop && (
            <rect
              x={paddingX}
              y={paddingTop}
              width={svgWidth - 2 * paddingX}
              height={thresholdY - paddingTop}
              fill="url(#dangerPattern)"
            />
          )}

          {/* Baseline Grid Line (0%) */}
          <line
            x1={paddingX}
            y1={baselineY}
            x2={svgWidth - paddingX}
            y2={baselineY}
            stroke="#334155"
            strokeWidth="1.5"
          />

          {/* Midpoint Grid Line */}
          <line
            x1={paddingX}
            y1={getY(maxVal / 2)}
            x2={svgWidth - paddingX}
            y2={getY(maxVal / 2)}
            stroke="#1e293b"
            strokeWidth="1"
            strokeDasharray="4 4"
          />

          {/* 2% Circuit Breaker Threshold Reference Line */}
          <g>
            <line
              x1={paddingX}
              y1={thresholdY}
              x2={svgWidth - paddingX}
              y2={thresholdY}
              stroke="#f43f5e"
              strokeWidth="1.75"
              strokeDasharray="6 4"
            />
            <rect
              x={svgWidth - paddingX - 28}
              y={thresholdY - 9}
              width="26"
              height="16"
              rx="4"
              fill="#881337"
              stroke="#f43f5e"
              strokeWidth="1"
            />
            <text
              x={svgWidth - paddingX - 15}
              y={thresholdY + 3}
              fill="#fecdd3"
              fontSize="9"
              fontWeight="bold"
              fontFamily="monospace"
              textAnchor="middle"
            >
              2%
            </text>
          </g>

          {/* Gradient Filled Area Under Curve */}
          {areaPath && (
            <path
              d={areaPath}
              fill={isBreached ? 'url(#breachGradient)' : 'url(#areaGradient)'}
            />
          )}

          {/* Smooth Line Path */}
          {smoothLinePath && (
            <path
              d={smoothLinePath}
              fill="none"
              stroke="url(#lineGradient)"
              strokeWidth="3"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}

          {/* Individual Data Point Markers */}
          {points.map((pt, idx) => {
            const isHovered = hoveredIdx === idx;
            const isExceeded = pt.data.error_rate_percent >= thresholdPercent;
            const isLatest = idx === points.length - 1;

            return (
              <g key={idx} className="transition-all duration-150">
                {/* Outer ring for hovered point */}
                {isHovered && (
                  <circle
                    cx={pt.x}
                    cy={pt.y}
                    r="8"
                    fill="none"
                    stroke={isExceeded ? '#f43f5e' : '#38bdf8'}
                    strokeWidth="2"
                    opacity="0.8"
                  />
                )}

                {/* Point Node */}
                <circle
                  cx={pt.x}
                  cy={pt.y}
                  r={isHovered ? '5' : '3.5'}
                  fill={isExceeded ? '#f43f5e' : '#38bdf8'}
                  stroke="#0f172a"
                  strokeWidth="2"
                />

                {/* Pulsing ring on latest data point */}
                {isLatest && !isHovered && (
                  <circle
                    cx={pt.x}
                    cy={pt.y}
                    r="6"
                    fill="none"
                    stroke={isExceeded ? '#f43f5e' : '#38bdf8'}
                    strokeWidth="1.5"
                    className="animate-ping opacity-75"
                  />
                )}
              </g>
            );
          })}

          {/* Interactive Mouse Hover Crosshair Line */}
          {activePoint && (
            <g className="pointer-events-none">
              <line
                x1={activePoint.x}
                y1={paddingTop}
                x2={activePoint.x}
                y2={baselineY}
                stroke="#38bdf8"
                strokeWidth="1"
                strokeDasharray="3 3"
                opacity="0.6"
              />
            </g>
          )}
        </svg>

        {/* Floating Tooltip Card */}
        {activePoint && (
          <div
            className="absolute z-20 pointer-events-none p-3 rounded-xl bg-slate-950/95 border border-slate-800 shadow-2xl text-[11px] font-mono space-y-1.5 backdrop-blur-xl min-w-[170px]"
            style={{
              left: `${Math.min(Math.max(activePoint.x - 85, 10), svgWidth - 180)}px`,
              top: `${Math.max(activePoint.y - 75, 10)}px`,
            }}
          >
            <div className="flex items-center justify-between border-b border-slate-800 pb-1 text-slate-400 font-sans text-[10px]">
              <span>Time</span>
              <span className="font-mono text-slate-300">
                {new Date(activePoint.data.timestamp).toLocaleTimeString()}
              </span>
            </div>

            <div className="flex justify-between items-center gap-2 pt-0.5">
              <span className="text-slate-400">Error rate:</span>
              <span
                className={`font-bold text-xs ${
                  activePoint.data.error_rate_percent >= thresholdPercent
                    ? 'text-rose-400'
                    : 'text-sky-400'
                }`}
              >
                {activePoint.data.error_rate_percent.toFixed(2)}%
              </span>
            </div>

            <div className="flex justify-between items-center text-[10px]">
              <span className="text-slate-500">Failed events:</span>
              <span className="text-amber-400 font-semibold">{activePoint.data.failed_events}</span>
            </div>

            <div className="flex justify-between items-center text-[10px]">
              <span className="text-slate-500">Total events:</span>
              <span className="text-slate-300">{activePoint.data.total_events}</span>
            </div>
          </div>
        )}
      </div>

      {/* Footer Details */}
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
