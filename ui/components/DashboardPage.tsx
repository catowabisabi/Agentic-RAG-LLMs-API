'use client';

import React, { useState, useEffect } from 'react';
import { Activity, CheckCircle, XCircle, RefreshCw } from 'lucide-react';
import { healthAPI, agentAPI } from '../lib/api';

interface HealthStatus {
  status: string;
  agents?: Record<string, any>;
}

interface ApiInfo {
  name: string;
  version: string;
  status: string;
}

export default function DashboardPage() {
  const [apiInfo, setApiInfo] = useState<ApiInfo | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [agents, setAgents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchData = async () => {
    setLoading(true);
    setError('');

    try {
      const [rootRes, healthRes, agentsRes] = await Promise.all([
        healthAPI.root().catch(() => ({ data: null })),
        healthAPI.check().catch(() => ({ data: null })),
        agentAPI.listAgents().catch(() => ({ data: [] })),
      ]);

      setApiInfo(rootRes.data);
      setHealth(healthRes.data);
      setAgents(agentsRes.data || []);
    } catch (err: any) {
      setError('Failed to connect to API. Make sure the server is running on port 1130.');
    }

    setLoading(false);
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="p-8 h-full overflow-y-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-white">Dashboard</h1>
          <p className="text-gray-400 mt-1">System overview and status</p>
        </div>
        <button
          onClick={fetchData}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-white transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="mb-6 p-4 bg-red-900/50 border border-red-700 rounded-lg text-red-300">
          {error}
        </div>
      )}

      {/* Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        {/* API Status */}
        <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-gray-400 font-medium">API Status</h3>
            {apiInfo?.status === 'running' ? (
              <CheckCircle className="w-6 h-6 text-green-500" />
            ) : (
              <XCircle className="w-6 h-6 text-red-500" />
            )}
          </div>
          <p className="text-2xl font-bold text-white">
            {apiInfo?.status === 'running' ? 'Online' : 'Offline'}
          </p>
          <p className="text-sm text-gray-500 mt-1">
            {apiInfo?.name} v{apiInfo?.version}
          </p>
        </div>

        {/* Health Status */}
        <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-gray-400 font-medium">Health Check</h3>
            <Activity className="w-6 h-6 text-blue-500" />
          </div>
          <p className="text-2xl font-bold text-white capitalize">
            {health?.status || 'Unknown'}
          </p>
          <p className="text-sm text-gray-500 mt-1">
            System health status
          </p>
        </div>

        {/* Agents */}
        <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-gray-400 font-medium">Active Agents</h3>
            <span className="text-2xl">🤖</span>
          </div>
          <p className="text-2xl font-bold text-white">{agents.length}</p>
          <p className="text-sm text-gray-500 mt-1">
            Registered agents
          </p>
        </div>
      </div>

      {/* Agents List */}
      <div className="bg-gray-800 rounded-xl border border-gray-700">
        <div className="p-6 border-b border-gray-700">
          <h2 className="text-xl font-semibold text-white">Registered Agents</h2>
        </div>
        <div className="p-6">
          {loading ? (
            <div className="flex justify-center py-8">
              <div className="loading-spinner" />
            </div>
          ) : agents.length === 0 ? (
            <p className="text-gray-500 text-center py-8">No agents registered</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {agents.map((agent) => (
                <div
                  key={agent.name}
                  className="bg-gray-700/50 rounded-lg p-4 border border-gray-600"
                >
                  <div className="flex items-center justify-between mb-2">
                    <h4 className="font-medium text-white">{agent.name}</h4>
                    <span
                      className={`px-2 py-1 text-xs rounded-full ${
                        agent.is_running
                          ? 'bg-green-900/50 text-green-400'
                          : 'bg-gray-600 text-gray-400'
                      }`}
                    >
                      {agent.status || 'unknown'}
                    </span>
                  </div>
                  <p className="text-sm text-gray-400">{agent.role}</p>
                  {agent.description && (
                    <p className="text-xs text-gray-500 mt-2">{agent.description}</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
