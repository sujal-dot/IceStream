import React, { useState } from 'react';
import {
  X,
  ShieldAlert,
  AlertOctagon,
  CheckCircle2,
  Clock,
  Activity,
  Layers,
  AlertTriangle,
  RotateCw,
} from 'lucide-react';
import { IncidentItem } from '../../types/dashboard';
import { IncidentsApiService } from '../../services/incidentsApi';

interface IncidentDetailModalProps {
  incident: IncidentItem | null;
  onClose: () => void;
  onIncidentUpdated: () => void;
}

export const IncidentDetailModal: React.FC<IncidentDetailModalProps> = ({
  incident,
  onClose,
  onIncidentUpdated,
}) => {
  const [isAcknowledging, setIsAcknowledging] = useState<boolean>(false);
  const [isResolving, setIsResolving] = useState<boolean>(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  if (!incident) return null;

  const isCritical = incident.severity === 'CRITICAL';
  const isOpen = incident.status === 'OPEN';
  const isAcknowledged = incident.status === 'ACKNOWLEDGED';
  const isResolved = incident.status === 'RESOLVED';

  const handleAcknowledge = async () => {
    setIsAcknowledging(true);
    setActionError(null);
    setActionSuccess(null);

    try {
      await IncidentsApiService.acknowledgeIncident(incident.incident_id);
      setActionSuccess(`Incident ${incident.incident_id} acknowledged.`);
      onIncidentUpdated();
    } catch (err: any) {
      setActionError(err.message || 'Failed to acknowledge incident.');
    } finally {
      setIsAcknowledging(false);
    }
  };

  const handleResolve = async () => {
    setIsResolving(true);
    setActionError(null);
    setActionSuccess(null);

    try {
      await IncidentsApiService.resolveIncident(incident.incident_id);
      setActionSuccess(`Incident ${incident.incident_id} successfully resolved.`);
      onIncidentUpdated();
    } catch (err: any) {
      // Gracefully show backend rejection message (e.g. circuit still OPEN)
      setActionError(err.message || 'Unable to resolve incident.');
    } finally {
      setIsResolving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-md flex items-center justify-center p-4">
      <div className="w-full max-w-xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-slate-800 bg-slate-950/80">
          <div className="flex items-center gap-3">
            <div
              className={`p-2.5 rounded-xl ${
                isCritical
                  ? 'bg-rose-500/10 border border-rose-500/20 text-rose-400'
                  : 'bg-amber-500/10 border border-amber-500/20 text-amber-400'
              }`}
            >
              <ShieldAlert className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="font-extrabold font-mono text-base text-slate-100">
                  {incident.incident_id}
                </h2>
                <span
                  className={`px-2 py-0.5 rounded font-mono text-[11px] font-bold ${
                    isOpen
                      ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                      : isAcknowledged
                      ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                      : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                  }`}
                >
                  {incident.status}
                </span>
              </div>
              <p className="text-xs text-slate-400 font-mono">
                Pipeline: <span className="text-sky-400">{incident.pipeline_name}</span>
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 overflow-y-auto space-y-5">
          {/* Action Notification Messages */}
          {actionError && (
            <div className="p-3.5 rounded-xl bg-rose-950/50 border border-rose-800/80 text-rose-300 text-xs font-mono flex items-start gap-2.5">
              <AlertOctagon className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
              <div>
                <strong className="block text-rose-200 font-bold mb-0.5">Action Rejection</strong>
                {actionError}
              </div>
            </div>
          )}

          {actionSuccess && (
            <div className="p-3 rounded-xl bg-emerald-950/50 border border-emerald-800/80 text-emerald-300 text-xs font-mono flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>{actionSuccess}</span>
            </div>
          )}

          {/* Key Incident Metrics Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 font-mono text-xs">
            <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
              <span className="text-slate-500 block text-[10px] uppercase">Severity</span>
              <span className={`font-bold ${isCritical ? 'text-rose-400' : 'text-amber-400'}`}>
                {incident.severity}
              </span>
            </div>

            <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
              <span className="text-slate-500 block text-[10px] uppercase">Error Rate</span>
              <span className="font-bold text-slate-100">
                {(incident.error_rate * 100).toFixed(2)}%
              </span>
              <span className="text-slate-500 text-[10px] ml-1">
                (limit: {(incident.threshold * 100).toFixed(1)}%)
              </span>
            </div>

            <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
              <span className="text-slate-500 block text-[10px] uppercase">Failed Records</span>
              <span className="font-bold text-amber-400">
                {incident.failed_records.toLocaleString()}
              </span>
            </div>

            <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
              <span className="text-slate-500 block text-[10px] uppercase">Circuit Breaker</span>
              <span
                className={`font-bold ${
                  incident.circuit_state === 'OPEN' ? 'text-rose-400' : 'text-slate-200'
                }`}
              >
                {incident.circuit_state}
              </span>
            </div>

            <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
              <span className="text-slate-500 block text-[10px] uppercase">Trigger</span>
              <span className="font-bold text-sky-400">{incident.trigger}</span>
            </div>

            <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
              <span className="text-slate-500 block text-[10px] uppercase">Detected</span>
              <span className="text-slate-300">
                {new Date(incident.created_at || incident.detected_at || Date.now()).toLocaleTimeString()}
              </span>
            </div>
          </div>

          {/* Action Taken Description */}
          {incident.action_taken && (
            <div className="space-y-1.5">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                <Activity className="w-3.5 h-3.5 text-sky-400" />
                Action Taken
              </h4>
              <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800 text-xs text-slate-300 font-mono leading-relaxed">
                {incident.action_taken}
              </div>
            </div>
          )}

          {/* Remediation Details & Attempts */}
          <div className="space-y-1.5">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-indigo-400" />
              Automated Remediation Status
            </h4>
            <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800 text-xs font-mono space-y-2">
              <div className="flex justify-between text-slate-400">
                <span>Recovery Attempts:</span>
                <span className="text-slate-200 font-bold">{incident.recovery_attempt}</span>
              </div>
              {incident.last_error && (
                <div className="pt-2 border-t border-slate-800 text-rose-400">
                  Last error: {incident.last_error}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Modal Footer Controls */}
        <div className="p-4 border-t border-slate-800 bg-slate-950/90 flex items-center justify-between gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold transition-colors"
          >
            Close
          </button>

          <div className="flex items-center gap-2">
            {/* Acknowledge Button */}
            {isOpen && (
              <button
                onClick={handleAcknowledge}
                disabled={isAcknowledging}
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold shadow-md transition-all disabled:opacity-50"
              >
                {isAcknowledging ? (
                  <RotateCw className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Clock className="w-3.5 h-3.5" />
                )}
                <span>Acknowledge</span>
              </button>
            )}

            {/* Resolve Button */}
            {!isResolved && (
              <button
                onClick={handleResolve}
                disabled={isResolving}
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold shadow-md transition-all disabled:opacity-50"
              >
                {isResolving ? (
                  <RotateCw className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <CheckCircle2 className="w-3.5 h-3.5" />
                )}
                <span>Resolve Incident</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
