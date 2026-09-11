import React, { useState } from 'react';
import { NavView } from '../../types/dashboard';
import { useDashboardData } from '../../hooks/useDashboardData';
import { SystemStatusBar } from './SystemStatusBar';
import { Sidebar } from './Sidebar';
import { TopHeader } from './TopHeader';
import { CommandCenterModal } from '../dashboard/CommandCenterModal';

// Views / Pages
import { DashboardPage } from '../../pages/DashboardPage';
import { PipelinePage } from '../../pages/PipelinePage';
import { QualityPage } from '../../pages/QualityPage';
import { SchemaPage } from '../../pages/SchemaPage';
import { QuarantinePage } from '../../pages/QuarantinePage';
import { IcebergPage } from '../../pages/IcebergPage';
import { EventsPage } from '../../pages/EventsPage';
import { IncidentsPage } from '../../pages/IncidentsPage';
import { SystemHealthPage } from '../../pages/SystemHealthPage';
import { SettingsPage } from '../../pages/SettingsPage';

export const AppShell: React.FC = () => {
  const [activeNav, setActiveNav] = useState<NavView>('dashboard');
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState<boolean>(false);
  const [isCommandCenterOpen, setIsCommandCenterOpen] = useState<boolean>(false);

  const {
    metrics,
    pipelineStatus,
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
          <main className="flex-1 bg-slate-950/80">{renderActiveView()}</main>
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
