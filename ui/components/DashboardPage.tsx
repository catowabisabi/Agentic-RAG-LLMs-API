'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Activity, CheckCircle, XCircle, RefreshCw, Wifi, WifiOff, Zap, Clock, AlertTriangle, Brain } from 'lucide-react';
import { healthAPI, agentAPI, createWebSocket } from '../lib/api';

interface HealthStatus {
  status: string;
  agents?: Record<string, any>;
}

interface ApiInfo {
  name: string;
  version: string;
  status: string;
}

interface AgentStatus {
  agent_name: string;
  state: string;
  current_task: string | null;
  current_step: string | null;
  progress: number;
  message: string | null;
  error: string | null;
  last_activity: string | null;
}

interface RecentEvent {
  event_id: string;
  event_type: string;
  agent_name: string;
  timestamp: string;
  data: any;
}

export default function DashboardPage() {
  const [apiInfo, setApiInfo] = useState<ApiInfo | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [agents, setAgents] = useState<any[]>([]);
  const [agentStatuses, setAgentStatuses] = useState<Record<string, AgentStatus>>({});
  const [recentEvents, setRecentEvents] = useState<RecentEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [wsConnected, setWsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  // Initial data fetch
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

  // WebSocket connection for real-time updates
  useEffect(() => {
    const connectWs = () => {
      try {
        const ws = createWebSocket('/ws');
        wsRef.current = ws;

        ws.onopen = () => {
          console.log('[Dashboard] WebSocket connected');
          setWsConnected(true);
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            
            // Handle different event types
            if (data.event_type === 'agent_status_changed' || data.type === 'agent_status_update') {
              const agentData = data.data || data;
              setAgentStatuses(prev => ({
                ...prev,
                [agentData.agent_name]: agentData
              }));
              
              setAgents(prev => prev.map(agent => {
                if (agent.name === agentData.agent_name) {
                  return {
                    ...agent,
                    status: agentData.state || agentData.status,
                    current_task: agentData.current_task
                  };
                }
                return agent;
              }));
            }
            
            // Handle heartbeat with all agent statuses
            if (data.event_type === 'heartbeat' && data.agents) {
              setAgentStatuses(data.agents);
            }
            
            // Handle activity events for recent events feed
            if (data.event_type || data.message_type === 'activity') {
              const newEvent: RecentEvent = {
                event_id: data.event_id || Date.now().toString(),
                event_type: data.event_type || data.type,
                agent_name: data.agent_name || data.agent || 'system',
                timestamp: data.timestamp || new Date().toISOString(),
                data: data.data || data.content || {}
              };
              
              setRecentEvents(prev => {
                const exists = prev.some(e => e.event_id === newEvent.event_id);
                if (exists) return prev;
                return [newEvent, ...prev].slice(0, 20);
              });
            }
          } catch (e) {
            console.error('[Dashboard] Parse error:', e);
          }
        };

        ws.onclose = () => {
          console.log('[Dashboard] WebSocket disconnected');
          setWsConnected(false);
          setTimeout(connectWs, 3000);
        };

        ws.onerror = (err) => {
          console.error('[Dashboard] WebSocket error:', err);
        };
      } catch (e) {
        console.error('[Dashboard] Failed to connect:', e);
        setTimeout(connectWs, 3000);
      }
    };

    connectWs();
    fetchData();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  const getStatusIcon = (state: string) => {
    switch (state) {
      case 'working':
      case 'busy':
        return <Zap className="w-4 h-4 text-yellow-500 animate-pulse" />;
      case 'thinking':
      case 'calling_llm':
        return <Brain className="w-4 h-4 text-purple-500 animate-pulse" />;
      case 'querying_rag':
        return <Activity className="w-4 h-4 text-blue-500 animate-pulse" />;
      case 'waiting':
        return <Clock className="w-4 h-4 text-orange-500" />;
      case 'error':
        return <AlertTriangle className="w-4 h-4 text-red-500" />;
      default:
        return <CheckCircle className="w-4 h-4 text-green-500" />;
    }
  };

  const getStatusColor = (state: string) => {
    switch (state) {
      case 'working':
      case 'busy':
        return 'bg-yellow-900/50 text-yellow-400 border-yellow-700';
      case 'thinking':
      case 'calling_llm':
        return 'bg-purple-900/50 text-purple-400 border-purple-700';
      case 'querying_rag':
        return 'bg-blue-900/50 text-blue-400 border-blue-700';
      case 'waiting':
        return 'bg-orange-900/50 text-orange-400 border-orange-700';
      case 'error':
        return 'bg-red-900/50 text-red-400 border-red-700';
      default:
        return 'bg-green-900/50 text-green-400 border-green-700';
    }
  };

  const getEventTypeColor = (type: string) => {
    if (type.includes('started') || type.includes('assigned')) return 'bg-blue-900/50 text-blue-400';
    if (type.includes('completed')) return 'bg-green-900/50 text-green-400';
    if (type.includes('failed') || type.includes('error')) return 'bg-red-900/50 text-red-400';
    if (type.includes('thinking') || type.includes('progress')) return 'bg-purple-900/50 text-purple-400';
    return 'bg-gray-700 text-gray-300';
  };

  const formatTimestamp = (ts: string) => {
    try {
      return new Date(ts).toLocaleTimeString();
    } catch {
      return ts;
    }
  };

  const activeAgents = Object.values(agentStatuses).filter(
    s => s.state === 'working' || s.state === 'thinking' || s.state === 'calling_llm'
  ).length;

  return (
    <div className="p-8 h-full overflow-y-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-white">Dashboard</h1>
          <div className="flex items-center gap-3 mt-1">
            <p className="text-gray-400">Real-time system overview</p>
            <div className={`flex items-center gap-1 px-2 py-0.5 rounded text-xs ${wsConnected ? 'bg-green-900/50 text-green-400' : 'bg-red-900/50 text-red-400'}`}>
              {wsConnected ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
              {wsConnected ? 'Live' : 'Disconnected'}
            </div>
          </div>
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
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
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

        {/* WebSocket Status */}
        <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-gray-400 font-medium">WebSocket</h3>
            {wsConnected ? (
              <Wifi className="w-6 h-6 text-green-500" />
            ) : (
              <WifiOff className="w-6 h-6 text-red-500" />
            )}
          </div>
          <p className="text-2xl font-bold text-white">
            {wsConnected ? 'Connected' : 'Disconnected'}
          </p>
          <p className="text-sm text-gray-500 mt-1">
            Real-time updates
          </p>
        </div>

        {/* Active Agents */}
        <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-gray-400 font-medium">Active Agents</h3>
            <Zap className={`w-6 h-6 ${activeAgents > 0 ? 'text-yellow-500 animate-pulse' : 'text-gray-500'}`} />
          </div>
          <p className="text-2xl font-bold text-white">{activeAgents}</p>
          <p className="text-sm text-gray-500 mt-1">
            of {agents.length} total
          </p>
        </div>

        {/* Total Agents */}
        <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-gray-400 font-medium">Total Agents</h3>
            <span className="text-2xl">🤖</span>
          </div>
          <p className="text-2xl font-bold text-white">{agents.length}</p>
          <p className="text-sm text-gray-500 mt-1">
            Registered agents
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Agent Status Grid */}
        <div className="bg-gray-800 rounded-xl border border-gray-700">
          <div className="p-6 border-b border-gray-700">
            <h2 className="text-xl font-semibold text-white">Agent Status (Real-time)</h2>
          </div>
          <div className="p-6">
            {loading && agents.length === 0 ? (
              <div className="flex justify-center py-8">
                <div className="loading-spinner" />
              </div>
            ) : agents.length === 0 ? (
              <p className="text-gray-500 text-center py-8">No agents registered</p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {agents.map((agent) => {
                  const status = agentStatuses[agent.name];
                  const state = status?.state || agent.status || 'idle';
                  const message = status?.message;
                  const progress = status?.progress || 0;
                  
                  return (
                    <div
                      key={agent.name}
                      className={`rounded-lg p-4 border transition-all ${getStatusColor(state)}`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          {getStatusIcon(state)}
                          <h4 className="font-medium text-white text-sm">{agent.name}</h4>
                        </div>
                        <span className="text-xs uppercase font-medium">
                          {state}
                        </span>
                      </div>
                      <p className="text-xs text-gray-400 mb-1">{agent.role}</p>
                      
                      {(state === 'working' || state === 'thinking') && (
                        <div className="mt-2">
                          {message && (
                            <p className="text-xs text-white/80 mb-1 truncate">{message}</p>
                          )}
                          {progress > 0 && (
                            <div className="w-full bg-gray-700 rounded-full h-1.5 mt-1">
                              <div 
                                className="bg-yellow-500 h-1.5 rounded-full transition-all duration-300"
                                style={{ width: `${progress}%` }}
                              />
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Recent Events Feed */}
        <div className="bg-gray-800 rounded-xl border border-gray-700">
          <div className="p-6 border-b border-gray-700">
            <h2 className="text-xl font-semibold text-white">Recent Events</h2>
          </div>
          <div className="p-4 max-h-[400px] overflow-y-auto">
            {recentEvents.length === 0 ? (
              <p className="text-gray-500 text-center py-8">
                {wsConnected ? 'Waiting for events...' : 'Connect WebSocket to see events'}
              </p>
            ) : (
              <div className="space-y-2">
                {recentEvents.map((event) => (
                  <div
                    key={event.event_id}
                    className="flex items-start gap-3 p-3 bg-gray-700/30 rounded-lg"
                  >
                    <span className={`px-2 py-0.5 text-xs rounded ${getEventTypeColor(event.event_type)}`}>
                      {event.event_type}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-white">{event.agent_name}</span>
                        <span className="text-xs text-gray-500">{formatTimestamp(event.timestamp)}</span>
                      </div>
                      {event.data && Object.keys(event.data).length > 0 && (
                        <p className="text-xs text-gray-400 mt-1 truncate">
                          {typeof event.data === 'string' 
                            ? event.data 
                            : event.data.message || event.data.thought || event.data.step || JSON.stringify(event.data).slice(0, 100)
                          }
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
