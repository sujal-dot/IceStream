import React, { useState } from 'react';
import { ApiTokenManager } from '../services/apiTokenManager';
import { MetricsApiService } from '../services/metricsApi';
import { Settings, Key, ShieldCheck, Check, RefreshCw, AlertCircle, Server } from 'lucide-react';

export const SettingsPage: React.FC = () => {
  const [token, setToken] = useState<string>(ApiTokenManager.getToken() || '');
  const [saveSuccess, setSaveSuccess] = useState<boolean>(false);
  const [testingEndpoint, setTestingEndpoint] = useState<boolean>(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);

  const handleSaveToken = (e: React.FormEvent) => {
    e.preventDefault();
    ApiTokenManager.setToken(token.trim());
    setSaveSuccess(true);
    setTimeout(() => setSaveSuccess(false), 3000);
  };

  const handleClearToken = () => {
    ApiTokenManager.clearToken();
    setToken('');
    setSaveSuccess(true);
    setTimeout(() => setSaveSuccess(false), 3000);
  };

  const handleTestConnection = async () => {
    setTestingEndpoint(true);
    setTestResult(null);
    try {
      const res = await MetricsApiService.getSystemHealth();
      setTestResult({
        success: true,
        message: `Successfully connected to ${res.service} (Version: ${res.version}). Status: ${res.status.toUpperCase()}`,
      });
    } catch (err: any) {
      setTestResult({
        success: false,
        message: err.message || 'Connection test failed. Backend endpoint unreachable.',
      });
    } finally {
      setTestingEndpoint(false);
    }
  };

  return (
    <div className="p-6 max-w-[1600px] mx-auto space-y-6 text-slate-100">
      {/* Page Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-5 rounded-2xl bg-slate-900/60 border border-slate-800 shadow-xl">
        <div className="flex items-center gap-3.5">
          <div className="p-3 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
            <Settings className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-extrabold text-white tracking-tight">
              Control Plane Settings & API Credentials
            </h1>
            <p className="text-xs text-slate-400 mt-0.5 font-mono">
              Configure Bearer authentication tokens, backend API endpoints, and polling options
            </p>
          </div>
        </div>
      </div>

      {/* Settings Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* API Authentication Token Card */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h2 className="text-sm font-bold text-white font-mono flex items-center gap-2">
              <Key className="w-4 h-4 text-cyan-400" />
              API Bearer Token Configuration
            </h2>
            {ApiTokenManager.hasToken() ? (
              <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-mono">
                CUSTOM TOKEN ACTIVE
              </span>
            ) : (
              <span className="px-2 py-0.5 rounded text-[10px] bg-amber-500/20 text-amber-300 border border-amber-500/30 font-mono">
                DEFAULT DEV TOKEN
              </span>
            )}
          </div>

          <form onSubmit={handleSaveToken} className="space-y-4 text-xs font-mono">
            <p className="text-slate-400 leading-relaxed">
              Operational control actions (Pause, Resume, Force Recovery, Incident Resolution) require a valid
              API Bearer token.
            </p>

            <div className="space-y-1.5">
              <label className="block text-slate-300 font-semibold uppercase text-[10px]">
                Bearer Authorization Token:
              </label>
              <input
                type="password"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="Enter Bearer Token (e.g. dev-secret-token-123)"
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-slate-200 text-xs focus:outline-none focus:border-cyan-500"
              />
            </div>

            {saveSuccess && (
              <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-emerald-300 flex items-center gap-2">
                <Check className="w-4 h-4" />
                <span>API Token saved successfully.</span>
              </div>
            )}

            <div className="flex items-center justify-between pt-2">
              <button
                type="button"
                onClick={handleClearToken}
                className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition-colors"
              >
                Reset to Default
              </button>

              <button
                type="submit"
                className="px-4 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white font-semibold shadow-lg shadow-cyan-950/50 transition-colors flex items-center gap-2"
              >
                <ShieldCheck className="w-4 h-4" />
                <span>Save Token</span>
              </button>
            </div>
          </form>
        </div>

        {/* Backend API Connection Tester */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h2 className="text-sm font-bold text-white font-mono flex items-center gap-2">
              <Server className="w-4 h-4 text-cyan-400" />
              Backend Connectivity Inspector
            </h2>
            <span className="text-xs font-mono text-slate-400">REST API / Base URL</span>
          </div>

          <div className="space-y-4 text-xs font-mono">
            <div className="p-3 bg-slate-950 rounded-xl border border-slate-800 space-y-1">
              <span className="text-slate-500 text-[10px] block">Configured API Base URL:</span>
              <span className="text-cyan-300 font-bold text-sm">
                {import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000 (Relative API)'}
              </span>
            </div>

            <button
              onClick={handleTestConnection}
              disabled={testingEndpoint}
              className="w-full py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold border border-slate-700 transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${testingEndpoint ? 'animate-spin text-cyan-400' : ''}`} />
              <span>Test REST Endpoint Reachability</span>
            </button>

            {testResult && (
              <div
                className={`p-4 rounded-xl border flex items-center gap-3 ${
                  testResult.success
                    ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                    : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
                }`}
              >
                {testResult.success ? (
                  <Check className="w-5 h-5 text-emerald-400 shrink-0" />
                ) : (
                  <AlertCircle className="w-5 h-5 text-rose-400 shrink-0" />
                )}
                <span className="leading-relaxed">{testResult.message}</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
