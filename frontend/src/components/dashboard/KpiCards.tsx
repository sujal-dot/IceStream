import React from 'react';
import { Activity, AlertTriangle, Database, ShieldAlert, CheckCircle, Clock } from 'lucide-react';
import { MetricsResponse, PipelineStatusResponse, QualityResponse } from '../../types/dashboard';
import { getStatusStyle } from '../../utils/statusStyles';

interface KpiCardsProps {
  metrics: MetricsResponse | null;
  pipelineStatus: PipelineStatusResponse | null;
  quality: QualityResponse | null;
  isLoading: boolean;
}

export const KpiCards: React.FC<KpiCardsProps> = ({
  metrics,
  pipelineStatus,
  quality,
  isLoading,
}) => {
  // 1. Events/sec throughput calculation
  const m1 = metrics?.windows?.['1m'];
  const eventsPerSec = m1 && m1.total_events > 0 ? (m1.total_events / 60).toFixed(1) : null;

  // 2. Error Rate calculation
  const errorRatePercent = m1 ? m1.error_rate_percent.toFixed(2) : null;
  const errorHealth = m1?.health || 'HEALTHY';

  // 3. Kafka Lag (From backend if reported, otherwise N/A)
  const kafkaLag = metrics?.pipeline_state?.kafka_lag ?? null;

  // 4. Pipeline Status
  const pipeState = pipelineStatus?.state || 'UNKNOWN';
  const statusStyle = getStatusStyle(pipeState);

  // 5. Quarantined Events Count
  const quarantinedCount = quality?.failed_events ?? m1?.failed_events ?? null;

  // 6. Uptime / Availability
  const uptime = metrics?.pipeline_state?.uptime ?? 'N/A';

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3.5 mb-6">
      {/* 1. Events/sec */}
      <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800/80 shadow-md flex flex-col justify-between">
        <div className="flex items-center justify-between text-slate-400 mb-2">
          <span className="text-xs font-semibold uppercase tracking-wider">Events/sec</span>
          <Activity className="w-4 h-4 text-sky-400" />
        </div>
        <div>
          {isLoading ? (
            <div className="h-7 w-20 bg-slate-800/60 rounded animate-pulse my-1" />
          ) : (
            <div className="text-xl sm:text-2xl font-black font-mono text-slate-100">
              {eventsPerSec !== null ? eventsPerSec : 'N/A'}
            </div>
          )}
          <span className="text-[11px] font-mono text-slate-500">events/sec throughput</span>
        </div>
      </div>

      {/* 2. Error Rate */}
      <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800/80 shadow-md flex flex-col justify-between">
        <div className="flex items-center justify-between text-slate-400 mb-2">
          <span className="text-xs font-semibold uppercase tracking-wider">Error Rate</span>
          <AlertTriangle className={`w-4 h-4 ${errorHealth === 'CRITICAL' ? 'text-rose-400' : 'text-amber-400'}`} />
        </div>
        <div>
          {isLoading ? (
            <div className="h-7 w-20 bg-slate-800/60 rounded animate-pulse my-1" />
          ) : (
            <div
              className={`text-xl sm:text-2xl font-black font-mono ${
                errorHealth === 'CRITICAL'
                  ? 'text-rose-400'
                  : errorHealth === 'WARNING'
                  ? 'text-amber-400'
                  : 'text-emerald-400'
              }`}
            >
              {errorRatePercent !== null ? `${errorRatePercent}%` : 'N/A'}
            </div>
          )}
          <span className="text-[11px] font-mono text-slate-500">1m rolling window</span>
        </div>
      </div>

      {/* 3. Kafka Lag */}
      <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800/80 shadow-md flex flex-col justify-between">
        <div className="flex items-center justify-between text-slate-400 mb-2">
          <span className="text-xs font-semibold uppercase tracking-wider">Kafka Lag</span>
          <Database className="w-4 h-4 text-indigo-400" />
        </div>
        <div>
          {isLoading ? (
            <div className="h-7 w-20 bg-slate-800/60 rounded animate-pulse my-1" />
          ) : (
            <div className="text-xl sm:text-2xl font-black font-mono text-slate-100">
              {kafkaLag !== null ? kafkaLag.toLocaleString() : 'N/A'}
            </div>
          )}
          <span className="text-[11px] font-mono text-slate-500">
            {kafkaLag !== null ? 'consumer lag' : 'metric unavailable'}
          </span>
        </div>
      </div>

      {/* 4. Pipeline Status */}
      <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800/80 shadow-md flex flex-col justify-between">
        <div className="flex items-center justify-between text-slate-400 mb-2">
          <span className="text-xs font-semibold uppercase tracking-wider">Pipeline</span>
          <CheckCircle className="w-4 h-4 text-emerald-400" />
        </div>
        <div>
          {isLoading ? (
            <div className="h-7 w-20 bg-slate-800/60 rounded animate-pulse my-1" />
          ) : (
            <div
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-bold font-mono border"
              style={{
                backgroundColor: statusStyle.badgeBg,
                borderColor: statusStyle.borderColor,
                color: statusStyle.badgeText,
              }}
            >
              <span
                className="w-2 h-2 rounded-full animate-pulse"
                style={{ backgroundColor: statusStyle.dotBg }}
              />
              <span>{statusStyle.label}</span>
            </div>
          )}
          <div className="text-[11px] font-mono text-slate-500 mt-1">authoritative state</div>
        </div>
      </div>

      {/* 5. Quarantined */}
      <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800/80 shadow-md flex flex-col justify-between">
        <div className="flex items-center justify-between text-slate-400 mb-2">
          <span className="text-xs font-semibold uppercase tracking-wider">Quarantined</span>
          <ShieldAlert className="w-4 h-4 text-amber-400" />
        </div>
        <div>
          {isLoading ? (
            <div className="h-7 w-20 bg-slate-800/60 rounded animate-pulse my-1" />
          ) : (
            <div className="text-xl sm:text-2xl font-black font-mono text-slate-100">
              {quarantinedCount !== null ? quarantinedCount.toLocaleString() : 'N/A'}
            </div>
          )}
          <span className="text-[11px] font-mono text-slate-500">invalid events</span>
        </div>
      </div>

      {/* 6. Uptime */}
      <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800/80 shadow-md flex flex-col justify-between">
        <div className="flex items-center justify-between text-slate-400 mb-2">
          <span className="text-xs font-semibold uppercase tracking-wider">Uptime</span>
          <Clock className="w-4 h-4 text-sky-400" />
        </div>
        <div>
          {isLoading ? (
            <div className="h-7 w-20 bg-slate-800/60 rounded animate-pulse my-1" />
          ) : (
            <div className="text-xl sm:text-2xl font-black font-mono text-slate-100">
              {uptime}
            </div>
          )}
          <span className="text-[11px] font-mono text-slate-500">service availability</span>
        </div>
      </div>
    </div>
  );
};
