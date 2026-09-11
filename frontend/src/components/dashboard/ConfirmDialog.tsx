import React, { useState } from 'react';
import { AlertTriangle, ShieldCheck, X } from 'lucide-react';

interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  description: string;
  actionLabel: string;
  actionType?: 'danger' | 'warning' | 'primary';
  requiresReason?: boolean;
  onConfirm: (reason?: string) => Promise<void>;
  onClose: () => void;
}

export const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
  isOpen,
  title,
  description,
  actionLabel,
  actionType = 'primary',
  requiresReason = false,
  onConfirm,
  onClose,
}) => {
  const [reason, setReason] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleConfirm = async () => {
    try {
      setIsSubmitting(true);
      setError(null);
      await onConfirm(requiresReason ? reason : undefined);
      setReason('');
      onClose();
    } catch (err: any) {
      setError(err.message || 'Operation failed');
    } finally {
      setIsSubmitting(false);
    }
  };

  const getButtonColor = () => {
    switch (actionType) {
      case 'danger':
        return 'bg-rose-600 hover:bg-rose-500 text-white shadow-rose-950/50';
      case 'warning':
        return 'bg-amber-600 hover:bg-amber-500 text-white shadow-amber-950/50';
      default:
        return 'bg-cyan-600 hover:bg-cyan-500 text-white shadow-cyan-950/50';
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-fadeIn">
      <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-md w-full shadow-2xl overflow-hidden">
        {/* Modal Header */}
        <div className="p-4 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2 text-slate-200 font-semibold text-sm">
            {actionType === 'danger' ? (
              <AlertTriangle className="w-5 h-5 text-rose-400" />
            ) : (
              <ShieldCheck className="w-5 h-5 text-cyan-400" />
            )}
            <span>{title}</span>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-5 space-y-4 text-xs">
          <p className="text-slate-300 leading-relaxed">{description}</p>

          {requiresReason && (
            <div className="space-y-1.5">
              <label className="block font-mono text-[11px] text-slate-400 uppercase font-semibold">
                Operational Reason / Ticket ID (Optional):
              </label>
              <input
                type="text"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="e.g. Scheduled maintenance / Investigating error spike"
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 font-mono text-xs focus:outline-none focus:border-cyan-500 transition-colors"
              />
            </div>
          )}

          {error && (
            <div className="p-3 bg-rose-500/10 border border-rose-500/30 rounded-lg text-rose-300 text-xs font-mono">
              ⚠ {error}
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="p-4 bg-slate-950/50 border-t border-slate-800 flex items-center justify-end gap-3">
          <button
            onClick={onClose}
            disabled={isSubmitting}
            className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium text-xs transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            disabled={isSubmitting}
            className={`px-4 py-2 rounded-lg font-medium text-xs shadow-lg transition-all flex items-center gap-2 ${getButtonColor()} ${
              isSubmitting ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          >
            {isSubmitting ? 'Executing...' : actionLabel}
          </button>
        </div>
      </div>
    </div>
  );
};
