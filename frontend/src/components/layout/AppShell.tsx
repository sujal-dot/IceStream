import React, { useState } from 'react';
import { NavView } from '../../types/dashboard';
import { useDashboardData } from '../../hooks/useDashboardData';
import { SystemStatusBar } from './SystemStatusBar';
import { Sidebar } from './Sidebar';
import { TopHeader } from './TopHeader';
import { CommandCenterModal } from '../dashboard/CommandCenterModal';

// Views / Pages
import { DashboardPage } from '../../pages/DashboardPage';

// Lazy-loaded secondary views to reduce initial bundle size & load time
const PipelinePage = React.lazy(() =>
  import('../../pages/PipelinePage').then((m) => ({ default: m.PipelinePage }))
);
const QualityPage = React.lazy(() =>
  import('../../pages/QualityPage').then((m) => ({ default: m.QualityPage }))
);
const SchemaPage = React.lazy(() =>
  import('../../pages/SchemaPage').then((m) => ({ default: m.SchemaPage }))
);
const QuarantinePage = React.lazy(() =>
  import('../../pages/QuarantinePage').then((m) => ({ default: m.QuarantinePage }))
);
const IcebergPage = React.lazy(() =>
  import('../../pages/IcebergPage').then((m) => ({ default: m.IcebergPage }))
);
const EventsPage = React.lazy(() =>
  import('../../pages/EventsPage').then((m) => ({ default: m.EventsPage }))
);
const IncidentsPage = React.lazy(() =>
  import('../../pages/IncidentsPage').then((m) => ({ default: m.IncidentsPage }))
);
const SystemHealthPage = React.lazy(() =>
  import('../../pages/SystemHealthPage').then((m) => ({ default: m.SystemHealthPage }))
);
const SettingsPage = React.lazy(() =>
  import('../../pages/SettingsPage').then((m) => ({ default: m.SettingsPage }))
);

export const AppShell: React.FC = () => {
  const [activeNav, setActiveNav] = useState<NavView>('dashboard');
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState<boolean>(false);
  const [isCommandCenterOpen, setIsCommandCenterOpen] = useState<boolean>(false);

  const {
    metrics,
    pipelineStatus,
    lineage,
    incidents,
    quality,
    systemHealth,
    schemaDrift,
    isLoading,
    isRefreshing,
    errors,
    lastUpdated,
    refreshData,
  } = useDashboardData(2000);

  const openIncidentsCount = incidents.filter((i) => i.status === 'OPEN').length;
  const isDriftDetected = schemaDrift?.drift_detected ?? false;

  const renderActiveView = () => {
    switch (activeNav) {
      case 'dashboard':
        return (
          <DashboardPage
            activeView="dashboard"
            onSelectView={(v) => {
              if (v === 'lineage') setActiveNav('pipeline');
              else if (v === 'incidents') setActiveNav('incidents');
              else setActiveNav('dashboard');
            }}
            metrics={metrics}
            pipelineStatus={pipelineStatus}
            lineage={lineage}
            incidents={incidents}
            quality={quality}
            isLoading={isLoading}
            isRefreshing={isRefreshing}
            errors={errors}
            lastUpdated={lastUpdated}
            refreshData={refreshData}
          />
        );
      case 'pipeline':
      case 'lineage':
        return <PipelinePage />;
      case 'quality':
        return <QualityPage quality={quality} isLoading={isLoading} error={errors.quality} />;
      case 'schema':
        return <SchemaPage schemaDrift={schemaDrift} isLoading={isLoading} error={errors.schemaDrift} />;
      case 'quarantine':
        return <QuarantinePage />;
      case 'iceberg':
        return <IcebergPage />;
      case 'events':
        return <EventsPage />;
      case 'incidents':
        return (
          <IncidentsPage
            activeView="incidents"
            onSelectView={(v) => {
              if (v === 'lineage') setActiveNav('pipeline');
              else if (v === 'dashboard') setActiveNav('dashboard');
              else setActiveNav('incidents');
            }}
          />
        );
      case 'system-health':
        return (
          <SystemHealthPage
            systemHealth={systemHealth}
            metrics={metrics}
            isLoading={isLoading}
            error={errors.systemHealth}
          />
        );
      case 'settings':
        return <SettingsPage />;
      default:
        return <DashboardPage />;
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-cyan-500 selection:text-white overflow-hidden">
      {/* 1. Global Infrastructure System Status Bar */}
      <SystemStatusBar
        systemHealth={systemHealth}
        metrics={metrics}
        error={errors.metrics || errors.systemHealth}
      />

      {/* 2. Main Layout Container: Sidebar + Workspace */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Collapsible Navigation Sidebar */}
        <Sidebar
          activeNav={activeNav}
          setActiveNav={setActiveNav}
          isCollapsed={isSidebarCollapsed}
          setIsCollapsed={setIsSidebarCollapsed}
          openIncidentCount={openIncidentsCount}
          schemaDriftDetected={isDriftDetected}
        />

        {/* Right Main Content Area */}
        <div className="flex-1 flex flex-col min-w-0 overflow-y-auto bg-slate-950">
          {/* Top Application Header */}
          <TopHeader
            pipelineState={pipelineStatus?.state || 'HEALTHY'}
            lastUpdated={lastUpdated}
            isRefreshing={isRefreshing}
            onRefresh={() => refreshData(true)}
            onOpenCommandCenter={() => setIsCommandCenterOpen(true)}
            onOpenSettings={() => setActiveNav('settings')}
          />

          {/* Active View Container */}
          <main className="flex-1 bg-slate-950/80">
            <React.Suspense
              fallback={
                <div className="flex items-center justify-center p-12 text-slate-400 font-mono text-sm animate-pulse">
                  Loading view...
                </div>
              }
            >
              {renderActiveView()}
            </React.Suspense>
          </main>
        </div>
      </div>

      {/* Operational Command Center Control Modal */}
      <CommandCenterModal
        isOpen={isCommandCenterOpen}
        onClose={() => setIsCommandCenterOpen(false)}
        pipelineStatus={pipelineStatus}
        onRefreshData={() => refreshData(true)}
        onOpenSettings={() => {
          setIsCommandCenterOpen(false);
          setActiveNav('settings');
        }}
      />
    </div>
  );
};
