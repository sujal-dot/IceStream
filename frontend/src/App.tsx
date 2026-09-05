import React, { useState } from 'react';
import { DashboardPage } from './pages/DashboardPage';
import { LineagePage } from './pages/LineagePage';

export const App: React.FC = () => {
  const [activeView, setActiveView] = useState<'dashboard' | 'lineage' | 'incidents'>('dashboard');

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-sky-500 selection:text-white">
      {activeView === 'lineage' ? (
        <LineagePage />
      ) : (
        <DashboardPage activeView={activeView} onSelectView={setActiveView} />
      )}
    </div>
  );
};

export default App;
