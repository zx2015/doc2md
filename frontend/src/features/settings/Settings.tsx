import { useState, useEffect } from 'react';
import { Settings as SettingsIcon, Save, Activity } from 'lucide-react';

export default function Settings() {
  const [config, setConfig] = useState<any>({});
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetch('/api/v1/config')
      .then(res => res.json())
      .then(data => setConfig(data))
      .catch(err => console.error(err));
  }, []);

  const handleSave = async () => {
    setLoading(true);
    try {
      await fetch('/api/v1/config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });
      alert("Settings saved");
    } catch (err) {
      console.error(err);
      alert("Error saving settings");
    }
    setLoading(false);
  };

  const handleTestConnection = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/v1/config/test', { method: 'POST' });
      if (res.ok) {
        alert("Connection Test Successful!");
      } else {
        alert("Connection Test Failed!");
      }
    } catch (err) {
      alert("Error testing connection");
    }
    setLoading(false);
  };

  return (
    <div className="max-w-2xl mx-auto p-6 bg-white rounded-xl shadow-sm border border-gray-100">
      <div className="flex items-center gap-3 mb-6 border-b pb-4">
        <SettingsIcon className="w-6 h-6 text-gray-700" />
        <h2 className="text-2xl font-semibold text-gray-800">Configuration</h2>
      </div>

      <div className="space-y-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">LLM Provider</label>
          <select 
            value={config.llm_provider || 'openai'}
            onChange={e => setConfig({...config, llm_provider: e.target.value})}
            className="w-full p-2.5 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
          >
            <option value="openai">OpenAI</option>
            <option value="gemini">Google Gemini</option>
            <option value="claude">Anthropic Claude</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Base URL</label>
          <input 
            type="text"
            value={config.llm_base_url || ''}
            onChange={e => setConfig({...config, llm_base_url: e.target.value})}
            className="w-full p-2.5 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
            placeholder="https://api.openai.com/v1"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">API Key</label>
          <input 
            type="password"
            value={config.llm_api_key || ''}
            onChange={e => setConfig({...config, llm_api_key: e.target.value})}
            className="w-full p-2.5 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
            placeholder="Leave blank to keep existing key"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Model</label>
          <input 
            type="text"
            value={config.llm_model || ''}
            onChange={e => setConfig({...config, llm_model: e.target.value})}
            className="w-full p-2.5 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
            placeholder="gpt-4o"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">VLM Model (For image reconstruction)</label>
          <input 
            type="text"
            value={config.vlm_model || ''}
            onChange={e => setConfig({...config, vlm_model: e.target.value})}
            className="w-full p-2.5 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
            placeholder="gpt-4o / claude-3-5-sonnet-20240620"
          />
        </div>

        <div className="flex gap-4 pt-4 border-t">
          <button 
            onClick={handleSave}
            disabled={loading}
            className="flex items-center gap-2 px-6 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition disabled:opacity-50"
          >
            <Save className="w-4 h-4" />
            {loading ? 'Saving...' : 'Save Settings'}
          </button>
          <button 
            onClick={handleTestConnection}
            disabled={loading}
            className="flex items-center gap-2 px-6 py-2.5 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition disabled:opacity-50"
          >
            <Activity className="w-4 h-4" />
            Test Connection
          </button>
        </div>
      </div>
    </div>
  );
}
