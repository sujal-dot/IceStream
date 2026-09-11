import React, { useState, useEffect } from 'react';
import { EventItem } from '../types/dashboard';
import { EventsApiService } from '../services/eventsApi';
import { ListFilter, Search, RefreshCw, ShieldCheck, ChevronLeft, ChevronRight, Lock } from 'lucide-react';

export const EventsPage: React.FC = () => {
  const [events, setEvents] = useState<EventItem[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [limit] = useState<number>(20);
  const [offset, setOffset] = useState<number>(0);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');

  const fetchEvents = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await EventsApiService.getEvents(limit, offset);
      setEvents(res.items || []);
      setTotal(res.total || 0);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch sanitized events');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchEvents();
  }, [offset, limit]);

  const filteredEvents = events.filter(
    (ev) =>
      ev.order_id?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      ev.event_id?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      ev.currency?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const currentPage = Math.floor(offset / limit) + 1;
  const totalPages = Math.ceil(total / limit) || 1;

  return (
    <div className="p-6 max-w-[1600px] mx-auto space-y-6 text-slate-100">
      {/* Page Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-5 rounded-2xl bg-slate-900/60 border border-slate-800 shadow-xl">
        <div className="flex items-center gap-3.5">
          <div className="p-3 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
            <ListFilter className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-extrabold text-white tracking-tight">
              Sanitized Telemetry Event Explorer
            </h1>
            <p className="text-xs text-slate-400 mt-0.5 font-mono">
              Real-time stream event metadata inspection. Payment credentials and secrets strictly masked.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-mono font-bold flex items-center gap-1.5">
            <Lock className="w-3.5 h-3.5" />
            <span>PII / SECRETS REDACTED</span>
          </div>

          <button
            onClick={fetchEvents}
            disabled={isLoading}
            className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 transition-all disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin text-cyan-400' : ''}`} />
            <span>Refresh Events</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs font-mono">
          ⚠ Event Query Error: {error}
        </div>
      )}

      {/* Filter & Pagination Control Bar */}
      <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex flex-wrap items-center justify-between gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search by Order ID, Event ID, or Currency..."
            className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-9 pr-3 py-2 text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-500"
          />
        </div>

        <div className="flex items-center gap-4 text-xs font-mono text-slate-400">
          <span>
            Page <strong className="text-white">{currentPage}</strong> of{' '}
            <strong className="text-white">{totalPages}</strong> (Total: {total.toLocaleString()})
          </span>

          <div className="flex items-center gap-1">
            <button
              onClick={() => setOffset(Math.max(0, offset - limit))}
              disabled={offset === 0 || isLoading}
              className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 disabled:opacity-30 disabled:cursor-not-allowed text-slate-300"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              onClick={() => setOffset(offset + limit)}
              disabled={offset + limit >= total || isLoading}
              className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 disabled:opacity-30 disabled:cursor-not-allowed text-slate-300"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Events Data Table */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 shadow-xl">
        {isLoading ? (
          <div className="p-16 text-center text-slate-400 text-xs font-mono">
            Fetching sanitized events from backend...
          </div>
        ) : filteredEvents.length === 0 ? (
          <div className="p-16 text-center text-slate-400 text-xs font-mono bg-slate-950/40 rounded-xl border border-slate-800/60">
            <ShieldCheck className="w-8 h-8 text-cyan-400 mx-auto mb-2" />
            <p className="font-semibold text-slate-300">No events found matching search query</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 uppercase text-[10px]">
                  <th className="py-2.5 px-3">Timestamp</th>
                  <th className="py-2.5 px-3">Order ID</th>
                  <th className="py-2.5 px-3">Event UUID</th>
                  <th className="py-2.5 px-3">Amount</th>
                  <th className="py-2.5 px-3">Currency</th>
                  <th className="py-2.5 px-3">Payment Status</th>
                  <th className="py-2.5 px-3">Pipeline Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-slate-300">
                {filteredEvents.map((ev) => (
                  <tr key={ev.event_id} className="hover:bg-slate-800/40 transition-colors">
                    <td className="py-2.5 px-3 text-slate-400">
                      {ev.event_timestamp ? new Date(ev.event_timestamp).toLocaleTimeString() : 'N/A'}
                    </td>
                    <td className="py-2.5 px-3 font-semibold text-white">{ev.order_id}</td>
                    <td className="py-2.5 px-3 text-cyan-400 truncate max-w-[140px]">
                      {ev.event_id}
                    </td>
                    <td className="py-2.5 px-3 text-emerald-400 font-bold">
                      ${ev.amount ?? 0}
                    </td>
                    <td className="py-2.5 px-3 text-amber-300">{ev.currency || 'USD'}</td>
                    <td className="py-2.5 px-3 text-slate-300">{ev.payment_status || 'COMPLETED'}</td>
                    <td className="py-2.5 px-3">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          ev.status?.toUpperCase() === 'FAILED'
                            ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                            : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                        }`}
                      >
                        {ev.status || 'VALID'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
