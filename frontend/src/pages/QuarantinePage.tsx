import React, { useState, useEffect } from 'react';
import { EventItem } from '../types/dashboard';
import { EventsApiService } from '../services/eventsApi';
import { AlertTriangle, Code, Search, RefreshCw, Database, ShieldAlert } from 'lucide-react';

export const QuarantinePage: React.FC = () => {
  const [quarantinedEvents, setQuarantinedEvents] = useState<EventItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedEvent, setSelectedEvent] = useState<EventItem | null>(null);

  const fetchQuarantined = async () => {
    setIsLoading(true);
    setError(null);
    try {
      // Fetch events with limit 50
      const res = await EventsApiService.getEvents(50, 0);
      // Filter quarantined or failed events
      const filtered = (res.items || []).filter(
        (ev) =>
          ev.status?.toUpperCase() === 'FAILED' ||
          ev.status?.toUpperCase() === 'QUARANTINED' ||
          ev.failure_reason
      );
      setQuarantinedEvents(filtered);
      if (filtered.length > 0) setSelectedEvent(filtered[0]);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch quarantine vault events');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchQuarantined();
  }, []);

  const searchFiltered = quarantinedEvents.filter(
    (ev) =>
      ev.order_id?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      ev.event_id?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      ev.failure_reason?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="p-6 max-w-[1600px] mx-auto space-y-6 text-slate-100">
      {/* Page Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-5 rounded-2xl bg-slate-900/60 border border-slate-800 shadow-xl">
        <div className="flex items-center gap-3.5">
          <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-400">
            <AlertTriangle className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-extrabold text-white tracking-tight">
              Quarantine Vault Explorer
            </h1>
            <p className="text-xs text-slate-400 mt-0.5 font-mono">
              Inspect corrupted payload events isolated from primary Iceberg catalog ingestion
            </p>
          </div>
        </div>

        <button
          onClick={fetchQuarantined}
          disabled={isLoading}
          className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 transition-all disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin text-cyan-400' : ''}`} />
          <span>Refresh Vault</span>
        </button>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs font-mono">
          ⚠ Vault Error: {error}
        </div>
      )}

      {/* Main Grid: Left Event List, Right Payload JSON Inspector */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Search & Quarantined List */}
        <div className="lg:col-span-5 bg-slate-900/60 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4 flex flex-col h-[650px]">
          {/* Search Bar */}
          <div className="relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by Order ID, Event ID, or Reason..."
              className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-9 pr-3 py-2 text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-500"
            />
          </div>

          <div className="flex items-center justify-between text-xs font-mono text-slate-400 px-1">
            <span>Isolated Records: {searchFiltered.length}</span>
            <span>Target: quarantine_db</span>
          </div>

          {/* Event List */}
          <div className="flex-1 overflow-y-auto space-y-2.5 pr-1">
            {isLoading ? (
              <div className="p-12 text-center text-slate-400 text-xs font-mono">
                Loading quarantine vault...
              </div>
            ) : searchFiltered.length === 0 ? (
              <div className="p-12 text-center text-slate-400 text-xs font-mono bg-slate-950/40 rounded-xl border border-slate-800/60">
                <ShieldAlert className="w-8 h-8 text-emerald-400 mx-auto mb-2" />
                <p className="font-semibold text-slate-300">No Quarantined Events</p>
                <p className="text-[11px] text-slate-500 mt-1">
                  Vault is empty. All stream events passed schema validation.
                </p>
              </div>
            ) : (
              searchFiltered.map((ev) => {
                const isSelected = selectedEvent?.event_id === ev.event_id;
                return (
                  <button
                    key={ev.event_id}
                    onClick={() => setSelectedEvent(ev)}
                    className={`w-full text-left p-3.5 rounded-xl border transition-all ${
                      isSelected
                        ? 'bg-cyan-500/10 border-cyan-500/40 shadow-lg shadow-cyan-950/30'
                        : 'bg-slate-950/60 hover:bg-slate-800/40 border-slate-800/80'
                    }`}
                  >
                    <div className="flex items-center justify-between font-mono text-xs mb-1">
                      <span className="font-bold text-white truncate max-w-[180px]">
                        {ev.order_id || ev.event_id}
                      </span>
                      <span className="px-2 py-0.5 rounded text-[10px] bg-rose-500/20 text-rose-300 border border-rose-500/30 font-bold">
                        {ev.status || 'QUARANTINED'}
                      </span>
                    </div>

                    <p className="text-[11px] text-rose-300 font-mono line-clamp-1 mb-2">
                      Reason: {ev.failure_reason || 'Null field threshold violation'}
                    </p>

                    <div className="flex items-center justify-between text-[10px] font-mono text-slate-500">
                      <span>{ev.event_timestamp ? new Date(ev.event_timestamp).toLocaleTimeString() : 'N/A'}</span>
                      <span>Amount: ${ev.amount ?? 'N/A'}</span>
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </div>

        {/* Right Column: Detailed Payload & Inspection Drawer */}
        <div className="lg:col-span-7 bg-slate-900/60 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4 flex flex-col h-[650px]">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h2 className="text-sm font-bold text-white font-mono flex items-center gap-2">
              <Code className="w-4 h-4 text-cyan-400" />
              Event Payload & Malformation Details
            </h2>
            {selectedEvent && (
              <span className="text-xs font-mono text-cyan-400 font-semibold">
                {selectedEvent.event_id}
              </span>
            )}
          </div>

          {selectedEvent ? (
            <div className="flex-1 overflow-y-auto space-y-4 pr-1">
              {/* Event Metadata Breakdown */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 bg-slate-950 p-4 rounded-xl border border-slate-800 font-mono text-xs">
                <div>
                  <span className="text-slate-500 text-[10px] block">Order ID:</span>
                  <span className="text-white font-bold">{selectedEvent.order_id || 'N/A'}</span>
                </div>
                <div>
                  <span className="text-slate-500 text-[10px] block">Currency:</span>
                  <span className="text-amber-400 font-bold">{selectedEvent.currency || 'MISSING'}</span>
                </div>
                <div>
                  <span className="text-slate-500 text-[10px] block">Amount:</span>
                  <span className="text-cyan-300 font-bold">${selectedEvent.amount ?? 0}</span>
                </div>
                <div>
                  <span className="text-slate-500 text-[10px] block">Schema Version:</span>
                  <span className="text-slate-300">{selectedEvent.schema_version || 'v2.1.0'}</span>
                </div>
              </div>

              {/* Quarantine Reason Callout */}
              <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 font-mono text-xs space-y-1">
                <span className="text-rose-400 font-bold block uppercase tracking-wider text-[10px]">
                  Isolation Trigger Reason
                </span>
                <p className="text-rose-200">
                  {selectedEvent.failure_reason ||
                    'Rule violation: NOT_NULL constraint failed on mandatory payload attributes.'}
                </p>
              </div>

              {/* Raw JSON Payload Viewer */}
              <div className="space-y-1.5 flex-1">
                <span className="text-slate-400 font-mono text-[11px] uppercase font-semibold block">
                  Quarantined Raw Payload JSON:
                </span>
                <pre className="bg-slate-950 p-4 rounded-xl border border-slate-800 text-xs font-mono text-emerald-400 overflow-x-auto max-h-[300px] leading-relaxed">
                  {selectedEvent.payload_json
                    ? selectedEvent.payload_json
                    : JSON.stringify(selectedEvent, null, 2)}
                </pre>
              </div>
            </div>
          ) : (
            <div className="flex-1 flex items-center justify-center text-slate-500 text-xs font-mono">
              Select a quarantined event on the left to inspect raw payload details.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
