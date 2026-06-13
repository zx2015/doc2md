import { useState } from 'react';
import Dashboard from './features/dashboard/Dashboard';
import Settings from './features/settings/Settings';
import Preview from './features/preview/Preview';
import { LayoutDashboard, Settings as SettingsIcon } from 'lucide-react';

function App() {
  const [currentTab, setCurrentTab] = useState<'dashboard' | 'settings'>('dashboard');
  const [completedJobId, setCompletedJobId] = useState<string | null>(null);

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Navbar */}
      <header className="bg-white border-b sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center text-white font-bold">D</div>
            <span className="text-xl font-bold text-gray-900 tracking-tight">Doc2MD</span>
          </div>
          <nav className="flex gap-1">
            <button 
              onClick={() => { setCurrentTab('dashboard'); setCompletedJobId(null); }}
              className={`px-4 py-2 rounded-lg flex items-center gap-2 text-sm font-medium transition ${currentTab === 'dashboard' && !completedJobId ? 'bg-gray-100 text-gray-900' : 'text-gray-600 hover:bg-gray-50'}`}
            >
              <LayoutDashboard className="w-4 h-4" />
              Dashboard
            </button>
            <button 
              onClick={() => { setCurrentTab('settings'); setCompletedJobId(null); }}
              className={`px-4 py-2 rounded-lg flex items-center gap-2 text-sm font-medium transition ${currentTab === 'settings' && !completedJobId ? 'bg-gray-100 text-gray-900' : 'text-gray-600 hover:bg-gray-50'}`}
            >
              <SettingsIcon className="w-4 h-4" />
              Settings
            </button>
          </nav>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 p-6">
        {completedJobId ? (
          <Preview jobId={completedJobId} />
        ) : currentTab === 'dashboard' ? (
          <Dashboard onJobComplete={setCompletedJobId} />
        ) : (
          <Settings />
        )}
      </main>
    </div>
  );
}

export default App;
