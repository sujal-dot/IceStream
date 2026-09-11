import React from 'react';
import { NavView } from '../../types/dashboard';
import {
  LayoutDashboard,
  GitCommit,
  CheckCircle2,
  FileDiff,
  AlertTriangle,
  Database,
  ListFilter,
  ShieldAlert,
  Activity,
  Settings,
  ChevronLeft,
  ChevronRight,
  Flame,
} from 'lucide-react';

interface SidebarProps {
  activeNav: NavView;
  setActiveNav: (nav: NavView) => void;
  isCollapsed: boolean;
  setIsCollapsed: (collapsed: boolean) => void;
  openIncidentCount?: number;
  schemaDriftDetected?: boolean;
}

interface NavItem {
  id: NavView;
  label: string;
  group: 'OVERVIEW' | 'PIPELINE' | 'DATA GOVERNANCE' | 'LAKEHOUSE' | 'OPERATIONS' | 'SETTINGS';
  icon: React.ComponentType<{ className?: string }>;
  badge?: number | string;
  badgeColor?: string;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeNav,
  setActiveNav,
  isCollapsed,
  setIsCollapsed,
  openIncidentCount = 0,
  schemaDriftDetected = false,
}) => {
  const navItems: NavItem[] = [
    { id: 'dashboard', label: 'Overview Dashboard', group: 'OVERVIEW', icon: LayoutDashboard },
    { id: 'pipeline', label: 'Pipeline Topology', group: 'PIPELINE', icon: GitCommit },
    { id: 'quality', label: 'Quality Engine', group: 'DATA GOVERNANCE', icon: CheckCircle2 },
    {
      id: 'schema',
      label: 'Schema Drift',
      group: 'DATA GOVERNANCE',
      icon: FileDiff,
      badge: schemaDriftDetected ? 'DRIFT' : undefined,
      badgeColor: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
    },
    { id: 'quarantine', label: 'Quarantine Vault', group: 'DATA GOVERNANCE', icon: AlertTriangle },
    { id: 'iceberg', label: 'Iceberg Catalog', group: 'LAKEHOUSE', icon: Database },
    { id: 'events', label: 'Sanitized Events', group: 'LAKEHOUSE', icon: ListFilter },
    {
      id: 'incidents',
      label: 'Incident Center',
      group: 'OPERATIONS',
      icon: ShieldAlert,
      badge: openIncidentCount > 0 ? openIncidentCount : undefined,
      badgeColor: 'bg-rose-500/20 text-rose-300 border-rose-500/40',
    },
    { id: 'system-health', label: 'System Health', group: 'OPERATIONS', icon: Activity },
    { id: 'settings', label: 'Settings & Auth', group: 'SETTINGS', icon: Settings },
  ];

  // Group items by category
  const groups: { [key: string]: NavItem[] } = {};
  navItems.forEach((item) => {
    if (!groups[item.group]) groups[item.group] = [];
    groups[item.group].push(item);
  });

  return (
    <aside
      className={`bg-slate-900 border-r border-slate-800 flex flex-col justify-between transition-all duration-300 z-20 ${
        isCollapsed ? 'w-16' : 'w-64'
      }`}
    >
      {/* Sidebar Header / Brand */}
      <div className="p-4 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-3 overflow-hidden">
          <div className="p-2 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 shrink-0">
            <Flame className="w-5 h-5 animate-pulse" />
          </div>
          {!isCollapsed && (
            <div className="flex flex-col">
              <span className="font-bold text-white tracking-wide text-sm font-mono">IceStream</span>
              <span className="text-[10px] text-slate-400 tracking-wider uppercase font-semibold">
                Control Plane
              </span>
            </div>
          )}
        </div>

        <button
          onClick={() => setIsCollapsed(!isCollapsed)}
          className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {isCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>
      </div>

      {/* Navigation Group Sections */}
      <nav className="flex-1 overflow-y-auto p-3 space-y-4 text-xs font-medium">
        {Object.entries(groups).map(([groupName, items]) => (
          <div key={groupName} className="space-y-1">
            {!isCollapsed && (
              <div className="px-3 py-1 text-[10px] uppercase tracking-wider font-semibold text-slate-500">
                {groupName}
              </div>
            )}

            {items.map((item) => {
              const Icon = item.icon;
              const isActive = activeNav === item.id;

              return (
                <button
                  key={item.id}
                  onClick={() => setActiveNav(item.id)}
                  title={isCollapsed ? item.label : undefined}
                  className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg transition-all ${
                    isActive
                      ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/30 shadow-lg shadow-cyan-950/40 font-semibold'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 border border-transparent'
                  }`}
                >
                  <div className="flex items-center gap-3 overflow-hidden">
                    <Icon className={`w-4 h-4 shrink-0 ${isActive ? 'text-cyan-400' : 'text-slate-400'}`} />
                    {!isCollapsed && <span className="truncate">{item.label}</span>}
                  </div>

                  {!isCollapsed && item.badge !== undefined && (
                    <span
                      className={`px-1.5 py-0.5 rounded text-[10px] font-mono border font-semibold ${
                        item.badgeColor || 'bg-slate-800 text-slate-300 border-slate-700'
                      }`}
                    >
                      {item.badge}
                    </span>
                  )}

                  {isCollapsed && item.badge !== undefined && (
                    <span className="w-2 h-2 rounded-full bg-rose-500 animate-ping absolute right-2 top-2" />
                  )}
                </button>
              );
            })}
          </div>
        ))}
      </nav>

      {/* Footer Info */}
      <div className="p-3 border-t border-slate-800 text-[11px] text-slate-500">
        {!isCollapsed ? (
          <div className="flex items-center justify-between font-mono">
            <span>SRE Lakehouse</span>
            <span className="text-cyan-400">v0.25.0</span>
          </div>
        ) : (
          <div className="text-center font-mono text-cyan-400 text-[10px]">v0.25</div>
        )}
      </div>
    </aside>
  );
};
