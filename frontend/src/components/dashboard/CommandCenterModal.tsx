import React, { useState } from 'react';
import { PipelineStatusResponse } from '../../types/dashboard';
import { PipelineApiService } from '../../services/pipelineApi';
import { ApiTokenManager } from '../../services/apiTokenManager';
import { ConfirmDialog } from './ConfirmDialog';
import {
  Terminal,
  PauseCircle,
  PlayCircle,
  RefreshCw,
  X,
  AlertCircle,
  CheckCircle2,
  Lock,
  Key,
} from 'lucide-react';

interface CommandCenterModalProps {
  isOpen: boolean;
  onClose: () => void;
  pipelineStatus: PipelineStatusResponse | null;
  onRefreshData: () => Promise<void>;
  onOpenSettings: () => void;
}

export const CommandCenterModal: React.FC<CommandCenterModalProps> = ({
  isOpen,
  onClose,
  pipelineStatus,
  onRefreshData,
  onOpenSettings,
}) => {
  const [confirmConfig, setConfirmConfig] = useState<{
    isOpen: boolean;
    title: string;
    description: string;
    actionLabel: string;
    actionType: 'danger' | 'warning' | 'primary';
    action: (reason?: string) => Promise<void>;
  }>({
    isOpen: false,
    title: '',
    description: '',
    actionLabel: '',
    actionType: 'primary',
    action: async () => {},
  });

  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  if (!isOpen) return null;

  const currentState = pipelineStatus?.state || 'HEALTHY';
  const hasToken = ApiTokenManager.hasToken();

  const handlePause = async (reason?: string) => {
    try {
      const res = await PipelineApiService.pause(reason || 'Operator triggered manual pause');
      setFeedback({ type: 'success', message: res.message || 'Pipeline successfully paused.' });
      await onRefreshData();
    } catch (err: any) {
      setFeedback({ type: 'error', message: err.message || 'Failed to pause pipeline' });
    }
  };

  const handleResume = async (reason?: string) => {
    try {
      const res = await PipelineApiService.resume(reason || 'Operator triggered manual resume');
      setFeedback({ type: 'success', message: res.message || 'Pipeline successfully resumed.' });
      await onRefreshData();
    } catch (err: any) {
      setFeedback({ type: 'error', message: err.message || 'Failed to resume pipeline' });
    }
  };

  const handleRecover = async (reason?: string) => {
    try {
      const res = await PipelineApiService.recover(pipelineStatus?.incident_id);
      setFeedback({
        type: 'success',
        message: res.message || 'Automated self-healing recovery flow triggered.',
      });
      await onRefreshData();
    } catch (err: any) {
      setFeedback({ type: 'error', message: err.message || 'Failed to trigger recovery' });
    }
  };

  const promptPause = () => {
    setFeedback(null);
    setConfirmConfig({
      isOpen: true,
      title: 'Pause Data Ingestion & Processing',
      description:
        'This will send an authoritative PAUSE instruction to the pipeline. Kafka offset consumption and Flink windowing will safely halt.',
      actionLabel: 'Confirm Pause',
      actionType: 'warning',
      action: handlePause,
    });
  };

  const promptResume = () => {
    setFeedback(null);
    setConfirmConfig({
      isOpen: true,
      title: 'Resume Data Processing',
      description:
        'This will resume stream processing. Kafka offsets will pick up from the last committed checkpoint.',
      actionLabel: 'Confirm Resume',
      actionType: 'primary',
      action: handleResume,
    });
  };

  const promptRecover = () => {
    setFeedback(null);
    setConfirmConfig({
      isOpen: true,
      title: 'Trigger Automated Self-Healing Recovery',
      description:
        'This will initiate the 11-stage self-healing remediation pipeline: refetching lost window data, purging invalid quarantine offsets, and validating data integrity.',
      actionLabel: 'Execute Recovery',
      actionType: 'danger',
      action: handleRecover,
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md animate-fadeIn">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-2xl w-full shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="p-5 border-b border-slate-800 flex items-center justify-between bg-slate-900/50">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
              <Terminal className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white tracking-wide">
                Operational Command Center
              </h2>
              <p className="text-xs text-slate-400 font-mono">
                Authoritative Control & Emergency Intervention
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6 overflow-y-auto flex-1 text-xs">
          {/* Feedback banner */}
          {feedback && (
            <div
              className={`p-4 rounded-xl border flex items-center gap-3 font-mono ${
                feedback.type === 'success'
                  ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                  : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
              }`}
            >
              {feedback.type === 'success' ? (
                <CheckCircle2 className="w-5 h-5 shrink-0 text-emerald-400" />
              ) : (
                <AlertCircle className="w-5 h-5 shrink-0 text-rose-400" />
              )}
              <span>{feedback.message}</span>
            </div>
          )}

          {/* Pipeline Status Summary Card */}
          <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-slate-400 font-mono font-semibold uppercase text-[11px]">
                Active Pipeline State
              </span>
              <span className="px-3 py-0.5 rounded-full text-xs font-mono font-bold bg-cyan-500/10 text-cyan-300 border border-cyan-500/30">
                {currentState}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-4 text-slate-300 font-mono">
              <div>
                <span className="text-slate-500 block text-[10px]">Pipeline ID:</span>
                <span className="text-white font-semibold">{pipelineStatus?.pipeline_id || 'icestream-main'}</span>
              </div>
              <div>
                <span className="text-slate-500 block text-[10px]">Recovery Attempt:</span>
                <span className="text-white font-semibold">#{pipelineStatus?.recovery_attempt || 0}</span>
              </div>
              <div>
                <span className="text-slate-500 block text-[10px]">Current Stage:</span>
                <span className="text-cyan-400 font-semibold">{pipelineStatus?.stage || 'IDLE'}</span>
              </div>
              <div>
                <span className="text-slate-500 block text-[10px]">Last Status Update:</span>
                <span>{pipelineStatus?.updated_at ? new Date(pipelineStatus.updated_at).toLocaleTimeString() : 'Just now'}</span>
              </div>
            </div>
          </div>

          {/* Operational Action Controls */}
          <div className="space-y-3">
            <h3 className="text-slate-400 font-mono font-semibold uppercase text-[11px]">
              Available Operations
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {/* Pause Action */}
              <button
                onClick={promptPause}
                disabled={currentState === 'PAUSED'}
                className="p-4 rounded-xl border border-slate-800 bg-slate-950 hover:bg-amber-950/20 hover:border-amber-500/40 text-left transition-all disabled:opacity-40 disabled:cursor-not-allowed group"
              >
                <div className="flex items-center gap-2 text-amber-400 font-semibold mb-1">
                  <PauseCircle className="w-4 h-4" />
                  <span>Pause Pipeline</span>
                </div>
                <p className="text-slate-400 text-[11px] leading-relaxed">
                  Safely halt stream ingestion and Flink windowing.
                </p>
              </button>

              {/* Resume Action */}
              <button
                onClick={promptResume}
                disabled={currentState === 'HEALTHY' || currentState === 'RUNNING'}
                className="p-4 rounded-xl border border-slate-800 bg-slate-950 hover:bg-emerald-950/20 hover:border-emerald-500/40 text-left transition-all disabled:opacity-40 disabled:cursor-not-allowed group"
              >
                <div className="flex items-center gap-2 text-emerald-400 font-semibold mb-1">
                  <PlayCircle className="w-4 h-4" />
                  <span>Resume Processing</span>
                </div>
                <p className="text-slate-400 text-[11px] leading-relaxed">
                  Re-enable Kafka stream processing from last offset.
                </p>
              </button>

              {/* Self-Healing Trigger */}
              <button
                onClick={promptRecover}
                className="p-4 rounded-xl border border-rose-900/40 bg-rose-950/10 hover:bg-rose-950/30 hover:border-rose-500/60 text-left transition-all group"
              >
                <div className="flex items-center gap-2 text-rose-400 font-semibold mb-1">
                  <RefreshCw className="w-4 h-4 group-hover:rotate-180 transition-transform duration-500" />
                  <span>Force Recovery</span>
                </div>
                <p className="text-slate-400 text-[11px] leading-relaxed">
                  Trigger automated 11-stage self-healing pipeline.
                </p>
              </button>
            </div>
          </div>

          {/* Bearer Token & Authentication Header Status */}
          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Lock className="w-4 h-4 text-cyan-400" />
              <div>
                <span className="text-slate-200 font-semibold block">Bearer Token Authentication</span>
                <span className="text-slate-400 text-[11px] font-mono">
                  {hasToken ? 'Using configured admin Bearer token' : 'Using default development token'}
                </span>
              </div>
            </div>
            <button
              onClick={() => {
                onClose();
                onOpenSettings();
              }}
              className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-mono text-[11px] flex items-center gap-1.5 transition-colors"
            >
              <Key className="w-3.5 h-3.5" />
              <span>Configure Key</span>
            </button>
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-800 bg-slate-950/50 flex items-center justify-between">
          <span className="text-slate-500 font-mono text-[11px]">
            IceStream SRE Control Plane v0.25.0
          </span>
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium text-xs transition-colors"
          >
            Close Window
          </button>
        </div>
      </div>

      {/* Confirmation Dialog */}
      <ConfirmDialog
        isOpen={confirmConfig.isOpen}
        title={confirmConfig.title}
        description={confirmConfig.description}
        actionLabel={confirmConfig.actionLabel}
        actionType={confirmConfig.actionType}
        requiresReason={true}
        onConfirm={confirmConfig.action}
        onClose={() => setConfirmConfig((prev) => ({ ...prev, isOpen: false }))}
      />
    </div>
  );
};
