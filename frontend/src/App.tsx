import React, { useState, useEffect } from 'react';
import { DashboardPage } from './pages/DashboardPage';
import { LineagePage } from './pages/LineagePage';
import { IncidentsPage } from './pages/IncidentsPage';

export const App: React.FC = () => {
  const [activeView, setActiveView] = useState<'dashboard' | 'lineage' | 'incidents'>(() => {
    const path = window.location.pathname.toLowerCase();
    if (path.includes('lineage')) return 'lineage';
    if (path.includes('incidents')) return 'incidents';
    return 'dashboard';
  });

  const handleSelectView = (view: 'dashboard' | 'lineage' | 'incidents') => {
    setActiveView(view);
    const path = view === 'dashboard' ? '/' : `/${view}`;
    if (window.location.pathname !== path) {
      window.history.pushState({ view }, '', path);
    }
  };

  useEffect(() => {
    const handlePopState = () => {
      const path = window.location.pathname.toLowerCase();
      if (path.includes('lineage')) {
        setActiveView('lineage');
      } else if (path.includes('incidents')) {
        setActiveView('incidents');
      } else {
        setActiveView('dashboard');
      }
    };

    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-sky-500 selection:text-white">
      {activeView === 'lineage' ? (
        <LineagePage activeView={activeView} onSelectView={handleSelectView} />
      ) : activeView === 'incidents' ? (
        <IncidentsPage activeView={activeView} onSelectView={handleSelectView} />
      ) : (
        <DashboardPage activeView={activeView} onSelectView={handleSelectView} />
      )}
    </div>
  );
};

export default App;
