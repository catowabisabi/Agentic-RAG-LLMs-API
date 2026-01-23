'use client';

import React, { useState, useEffect } from 'react';
import { Settings, Save, RefreshCw, Server, Key, Database } from 'lucide-react';

interface SettingsState {
  apiUrl: string;
  wsUrl: string;
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<SettingsState>({
    apiUrl: 'http://localhost:1130',
    wsUrl: 'ws://localhost:1130',
  });
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    // Load settings from localStorage
    const savedApiUrl = localStorage.getItem('api_url');
    const savedWsUrl = localStorage.getItem('ws_url');

    if (savedApiUrl || savedWsUrl) {
      setSettings({
        apiUrl: savedApiUrl || settings.apiUrl,
        wsUrl: savedWsUrl || settings.wsUrl,
      });
    }
  }, []);

  const handleSave = () => {
    localStorage.setItem('api_url', settings.apiUrl);
    localStorage.setItem('ws_url', settings.wsUrl);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const handleReset = () => {
    const defaults = {
      apiUrl: 'http://localhost:1130',
      wsUrl: 'ws://localhost:1130',
    };
    setSettings(defaults);
    localStorage.setItem('api_url', defaults.apiUrl);
    localStorage.setItem('ws_url', defaults.wsUrl);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white flex items-center gap-3">
          <Settings className="w-8 h-8" />
          Settings
        </h1>
        <p className="text-gray-400 mt-1">Configure API connection and preferences</p>
      </div>

      <div className="max-w-2xl space-y-6">
        {/* Connection Settings */}
        <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
          <div className="p-6 border-b border-gray-700">
            <h2 className="text-xl font-semibold text-white flex items-center gap-2">
              <Server className="w-5 h-5" />
              Connection Settings
            </h2>
          </div>
          <div className="p-6 space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                API URL
              </label>
              <input
                type="text"
                value={settings.apiUrl}
                onChange={(e) => setSettings({ ...settings, apiUrl: e.target.value })}
                className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-blue-500"
                placeholder="http://localhost:1130"
              />
              <p className="text-xs text-gray-500 mt-1">
                The base URL for the FastAPI server
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                WebSocket URL
              </label>
              <input
                type="text"
                value={settings.wsUrl}
                onChange={(e) => setSettings({ ...settings, wsUrl: e.target.value })}
                className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-blue-500"
                placeholder="ws://localhost:1130"
              />
              <p className="text-xs text-gray-500 mt-1">
                The WebSocket URL for real-time communication
              </p>
            </div>
          </div>
        </div>

        {/* API Endpoints Info */}
        <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
          <div className="p-6 border-b border-gray-700">
            <h2 className="text-xl font-semibold text-white flex items-center gap-2">
              <Database className="w-5 h-5" />
              Available Endpoints
            </h2>
          </div>
          <div className="p-6">
            <div className="space-y-3 text-sm">
              {[
                { method: 'GET', path: '/', desc: 'API Info' },
                { method: 'GET', path: '/health', desc: 'Health Check' },
                { method: 'GET', path: '/agents/', desc: 'List Agents' },
                { method: 'GET', path: '/agents/health', desc: 'System Health' },
                { method: 'POST', path: '/agents/task', desc: 'Send Task' },
                { method: 'POST', path: '/chat/message', desc: 'Send Chat Message' },
                { method: 'POST', path: '/rag/query', desc: 'RAG Query' },
                { method: 'POST', path: '/rag/document', desc: 'Add Document' },
                { method: 'WS', path: '/ws', desc: 'WebSocket' },
              ].map((endpoint) => (
                <div key={endpoint.path} className="flex items-center justify-between py-2 border-b border-gray-700 last:border-0">
                  <div className="flex items-center gap-3">
                    <span
                      className={`px-2 py-1 rounded text-xs font-mono ${
                        endpoint.method === 'GET'
                          ? 'bg-green-900/50 text-green-400'
                          : endpoint.method === 'POST'
                          ? 'bg-blue-900/50 text-blue-400'
                          : 'bg-purple-900/50 text-purple-400'
                      }`}
                    >
                      {endpoint.method}
                    </span>
                    <code className="text-gray-300">{endpoint.path}</code>
                  </div>
                  <span className="text-gray-500">{endpoint.desc}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-3">
          <button
            onClick={handleSave}
            className="flex items-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-700 rounded-lg text-white transition-colors"
          >
            <Save className="w-4 h-4" />
            {saved ? 'Saved!' : 'Save Settings'}
          </button>
          <button
            onClick={handleReset}
            className="flex items-center gap-2 px-6 py-3 bg-gray-700 hover:bg-gray-600 rounded-lg text-white transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Reset to Defaults
          </button>
        </div>
      </div>
    </div>
  );
}
