'use client';

import React, { useState, useEffect, useRef } from 'react';
import {
  Users, RefreshCw, Play, Pause, Send, AlertTriangle,
  CheckCircle, Clock, Zap, Activity, Eye, ChevronDown, ChevronUp,
  MessageSquare, Brain, ArrowRight, Wifi, WifiOff
} from 'lucide-react';
import { agentAPI, createWebSocket } from '../lib/api';

interface Agent {
  name: string;
  role: string;
  description: string;
  status: string;
  is_running: boolean;
}

interface ActivityItem {
  agent: string;
  type: string;
  source: string;
  target: string;
  content: any;
  timestamp: string;
  priority: number;
}

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [taskType, setTaskType] = useState('process_query');
  const [taskInput, setTaskInput] = useState('');
  const [taskResult, setTaskResult] = useState<any>(null);
  const [sending, setSending] = useState(false);
  
  // Activity state
  const [showActivity, setShowActivity] = useState(true);
  const [activity, setActivity] = useState<ActivityItem[]>([]);
  const [loadingActivity, setLoadingActivity] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [expandedActivities, setExpandedActivities] = useState<Set<number>>(new Set());
  const activityRef = useRef<HTMLDivElement>(null);
  
  // WebSocket state
  const [wsConnected, setWsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  
  // Agent detail
  const [agentDetail, setAgentDetail] = useState<any>(null);
  const [showAgentDetail, setShowAgentDetail] = useState(false);

  // Connect to WebSocket for real-time activity
  useEffect(() => {
    const connectWs = () => {
      try {
        const ws = createWebSocket('/ws');
        wsRef.current = ws;
        
        ws.onopen = () => {
          console.log('[AgentsPage] WebSocket connected');
          setWsConnected(true);
        };
        
        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            // Handle activity messages
            if (data.message_type === 'activity' || data.type?.includes('agent') || data.type?.includes('task') || data.type === 'thinking') {
              const newActivity: ActivityItem = {
                agent: data.agent || data.source_agent || 'unknown',
                type: data.type,
                source: data.source || data.source_agent || 'system',
                target: data.target || data.target_agent || 'system',
                content: data.content || data,
                timestamp: data.timestamp || new Date().toISOString(),
                priority: data.priority || 1
              };
              setActivity(prev => {
                // Dedupe
                const isDupe = prev.some(p => 
                  p.timestamp === newActivity.timestamp && 
                  p.type === newActivity.type && 
                  p.agent === newActivity.agent
                );
                if (isDupe) return prev;
                return [newActivity, ...prev].slice(0, 50);
              });
              
              // Update agent status based on activity
              const agentName = data.agent || data.source;
              if (agentName) {
                setAgents(prev => prev.map(agent => {
                  if (agent.name === agentName) {
                    let newStatus = agent.status;
                    if (data.type === 'agent_started' || data.type === 'task_assigned' || data.type === 'thinking') {
                      newStatus = 'busy';
                    } else if (data.type === 'agent_completed') {
                      newStatus = 'idle';
                    } else if (data.type === 'agent_error') {
                      newStatus = 'error';
                    }
                    return { ...agent, status: newStatus };
                  }
                  return agent;
                }));
              }
            }
          } catch (e) {
            console.error('[AgentsPage] Parse error:', e);
          }
        };
        
        ws.onclose = () => {
          console.log('[AgentsPage] WebSocket disconnected');
          setWsConnected(false);
          // Reconnect after delay
          setTimeout(connectWs, 3000);
        };
        
        ws.onerror = (err) => {
          console.error('[AgentsPage] WebSocket error:', err);
        };
      } catch (e) {
        console.error('[AgentsPage] Failed to connect:', e);
        setTimeout(connectWs, 3000);
      }
    };
    
    connectWs();
    
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  const fetchAgents = async () => {
    setLoading(true);
    try {
      const response = await agentAPI.listAgents();
      setAgents(response.data || []);
    } catch (err) {
      console.error('Failed to fetch agents:', err);
    }
    setLoading(false);
  };

  const fetchActivity = async () => {
    setLoadingActivity(true);
    try {
      const response = await agentAPI.getAllActivity(30);
      const apiActivity = response.data.activity || [];
      if (Array.isArray(apiActivity) && apiActivity.length > 0) {
        setActivity(prev => {
          const combined = [...apiActivity, ...prev];
          const unique = combined.filter((item, index, self) => 
            index === self.findIndex(t => t.timestamp === item.timestamp && t.type === item.type)
          );
          return unique.slice(0, 50);
        });
      }
    } catch (err) {
      console.error('Failed to fetch activity:', err);
    }
    setLoadingActivity(false);
  };

  const fetchAgentDetail = async (name: string) => {
    try {
      const response = await agentAPI.getAgentActivity(name, 50);
      setAgentDetail(response.data);
      setShowAgentDetail(true);
    } catch (err) {
      console.error('Failed to fetch agent detail:', err);
    }
  };

  useEffect(() => {
    fetchAgents();
    fetchActivity();
  }, []);

  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => {
      fetchActivity();
    }, 3000);
    return () => clearInterval(interval);
  }, [autoRefresh]);

  const sendTask = async () => {
    if (!selectedAgent || !taskInput) return;
    setSending(true);
    setTaskResult(null);
    try {
      const response = await agentAPI.sendTask({
        agent_name: selectedAgent,
        task_type: taskType,
        input_data: { query: taskInput },
        priority: 1,
      });
      setTaskResult(response.data);
      setTimeout(fetchActivity, 1000);
    } catch (err: any) {
      setTaskResult({ error: err.message || 'Failed to send task' });
    }
    setSending(false);
  };

  const handleInterrupt = async (agentName?: string) => {
    try {
      await agentAPI.interrupt({ agent_name: agentName, reason: 'User requested interrupt' });
      fetchAgents();
    } catch (err) {
      console.error('Failed to interrupt:', err);
    }
  };

  const getStatusIcon = (status: string, isRunning: boolean) => {
    if (!isRunning) return <Pause className="w-4 h-4 text-gray-500" />;
    switch (status) {
      case 'busy': return <Zap className="w-4 h-4 text-yellow-500" />;
      case 'idle': return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'error': return <AlertTriangle className="w-4 h-4 text-red-500" />;
      default: return <Clock className="w-4 h-4 text-blue-500" />;
    }
  };

  const getActivityTypeColor = (type: string) => {
    switch (type) {
      case 'task_assigned': return 'bg-blue-900/50 text-blue-400';
      case 'agent_completed': return 'bg-green-900/50 text-green-400';
      case 'agent_started': return 'bg-purple-900/50 text-purple-400';
      case 'error': return 'bg-red-900/50 text-red-400';
      case 'thinking': return 'bg-yellow-900/50 text-yellow-400';
      default: return 'bg-gray-700 text-gray-300';
    }
  };

  const toggleActivityExpand = (i: number) => {
    const n = new Set(expandedActivities);
    n.has(i) ? n.delete(i) : n.add(i);
    setExpandedActivities(n);
  };

  const formatContent = (content: any) => {
    if (typeof content === 'string') return content;
    return JSON.stringify(content, null, 2);
  };

  return (
    <div className="p-8 h-full overflow-y-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center gap-3">
            <Users className="w-8 h-8" />
            Agents Dashboard
          </h1>
          <div className="flex items-center gap-3 mt-1">
            <p className="text-gray-400">Manage agents and view Chain of Thought</p>
            <div className={`flex items-center gap-1 px-2 py-0.5 rounded text-xs ${wsConnected ? 'bg-green-900/50 text-green-400' : 'bg-red-900/50 text-red-400'}`}>
              {wsConnected ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
              {wsConnected ? 'Live' : 'Disconnected'}
            </div>
          </div>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => setShowActivity(!showActivity)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-white transition-colors ${showActivity ? 'bg-blue-600' : 'bg-gray-700 hover:bg-gray-600'}`}
          >
            <Activity className="w-4 h-4" />
            Activity Log
          </button>
          <button
            onClick={() => handleInterrupt()}
            className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-700 rounded-lg text-white transition-colors"
          >
            <Pause className="w-4 h-4" />
            Interrupt All
          </button>
          <button
            onClick={fetchAgents}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-white transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Agents List */}
        <div className="xl:col-span-1 bg-gray-800 rounded-xl border border-gray-700">
          <div className="p-6 border-b border-gray-700">
            <h2 className="text-xl font-semibold text-white">Agents ({agents.length})</h2>
          </div>
          <div className="p-4 max-h-[400px] overflow-y-auto">
            {loading ? (
              <div className="flex justify-center py-8"><div className="loading-spinner" /></div>
            ) : (
              <div className="space-y-2">
                {agents.map((agent) => (
                  <div
                    key={agent.name}
                    className={`p-3 rounded-lg cursor-pointer transition-colors ${
                      selectedAgent === agent.name
                        ? 'bg-blue-600/20 border-2 border-blue-500'
                        : 'bg-gray-700/50 border border-gray-600 hover:border-gray-500'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2" onClick={() => setSelectedAgent(agent.name)}>
                        {getStatusIcon(agent.status, agent.is_running)}
                        <div>
                          <h4 className="font-medium text-white text-sm">{agent.name}</h4>
                          <p className="text-xs text-gray-400">{agent.role}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => fetchAgentDetail(agent.name)}
                          className="p-1.5 hover:bg-gray-600 rounded text-gray-400 hover:text-white"
                          title="View Details"
                        >
                          <Eye className="w-3.5 h-3.5" />
                        </button>
                        <span className={`px-2 py-0.5 text-xs rounded-full ${agent.is_running ? 'bg-green-900/50 text-green-400' : 'bg-gray-600 text-gray-400'}`}>
                          {agent.status}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Task Panel */}
        <div className="xl:col-span-1 bg-gray-800 rounded-xl border border-gray-700">
          <div className="p-6 border-b border-gray-700">
            <h2 className="text-xl font-semibold text-white">Send Task</h2>
          </div>
          <div className="p-6 space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Target Agent</label>
              <select
                value={selectedAgent || ''}
                onChange={(e) => setSelectedAgent(e.target.value)}
                className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
              >
                <option value="">Select an agent</option>
                {agents.map((agent) => (
                  <option key={agent.name} value={agent.name}>{agent.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Task Type</label>
              <select
                value={taskType}
                onChange={(e) => setTaskType(e.target.value)}
                className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
              >
                <option value="process_query">Process Query</option>
                <option value="analyze">Analyze</option>
                <option value="summarize">Summarize</option>
                <option value="translate">Translate</option>
                <option value="calculate">Calculate</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Input</label>
              <textarea
                value={taskInput}
                onChange={(e) => setTaskInput(e.target.value)}
                rows={3}
                className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-blue-500 resize-none"
                placeholder="Enter task input..."
              />
            </div>
            <button
              onClick={sendTask}
              disabled={!selectedAgent || !taskInput || sending}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed rounded-lg text-white transition-colors"
            >
              {sending ? (<><div className="loading-spinner" />Sending...</>) : (<><Send className="w-4 h-4" />Send Task</>)}
            </button>
            {taskResult && (
              <div className={`p-4 rounded-lg ${taskResult.error ? 'bg-red-900/50 border border-red-700' : 'bg-green-900/50 border border-green-700'}`}>
                <pre className="text-xs overflow-auto text-white max-h-[150px]">{JSON.stringify(taskResult, null, 2)}</pre>
              </div>
            )}
          </div>
        </div>

        {/* Activity Log / COT */}
        <div className="xl:col-span-1 bg-gray-800 rounded-xl border border-gray-700">
          <div className="p-6 border-b border-gray-700 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Brain className="w-5 h-5 text-purple-400" />
              <h2 className="text-xl font-semibold text-white">Chain of Thought</h2>
            </div>
            <div className="flex items-center gap-2">
              <label className="flex items-center gap-2 cursor-pointer text-sm text-gray-400">
                <input type="checkbox" checked={autoRefresh} onChange={(e) => setAutoRefresh(e.target.checked)} className="w-4 h-4 rounded" />
                Auto
              </label>
              <button onClick={fetchActivity} disabled={loadingActivity} className="p-2 hover:bg-gray-700 rounded text-gray-400">
                <RefreshCw className={`w-4 h-4 ${loadingActivity ? 'animate-spin' : ''}`} />
              </button>
            </div>
          </div>
          <div ref={activityRef} className="p-4 max-h-[500px] overflow-y-auto">
            {activity.length === 0 ? (
              <p className="text-gray-500 text-center py-8">No activity yet. Send a task to see the chain of thought.</p>
            ) : (
              <div className="space-y-2">
                {activity.map((item, i) => (
                  <div key={i} className="bg-gray-700/50 rounded-lg border border-gray-600 overflow-hidden">
                    <div
                      onClick={() => toggleActivityExpand(i)}
                      className="p-3 cursor-pointer hover:bg-gray-700 transition-colors"
                    >
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-2">
                          <span className={`px-2 py-0.5 text-xs rounded ${getActivityTypeColor(item.type)}`}>{item.type}</span>
                          <span className="text-xs text-gray-400">{new Date(item.timestamp).toLocaleTimeString()}</span>
                        </div>
                        {expandedActivities.has(i) ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
                      </div>
                      <div className="flex items-center gap-2 text-sm">
                        <span className="text-blue-400 font-medium">{item.source}</span>
                        <ArrowRight className="w-3 h-3 text-gray-500" />
                        <span className="text-green-400 font-medium">{item.target}</span>
                      </div>
                    </div>
                    {expandedActivities.has(i) && (
                      <div className="p-3 border-t border-gray-600 bg-gray-800/50">
                        <h4 className="text-xs font-medium text-gray-400 mb-2">Content</h4>
                        <pre className="text-xs text-gray-300 whitespace-pre-wrap overflow-auto max-h-[200px]">{formatContent(item.content)}</pre>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Agent Detail Modal */}
      {showAgentDetail && agentDetail && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-gray-800 rounded-xl border border-gray-700 max-w-4xl w-full max-h-[80vh] overflow-hidden">
            <div className="p-6 border-b border-gray-700 flex items-center justify-between">
              <div>
                <h2 className="text-xl font-semibold text-white">{agentDetail.agent}</h2>
                <div className="flex items-center gap-3 mt-1">
                  <span className={`px-2 py-0.5 text-xs rounded ${agentDetail.is_running ? 'bg-green-900/50 text-green-400' : 'bg-gray-600 text-gray-400'}`}>
                    {agentDetail.status}
                  </span>
                  <span className="text-sm text-gray-400">{agentDetail.message_count} messages</span>
                </div>
              </div>
              <button onClick={() => setShowAgentDetail(false)} className="text-gray-400 hover:text-white text-2xl">&times;</button>
            </div>
            <div className="p-6 max-h-[60vh] overflow-y-auto">
              {agentDetail.current_task && (
                <div className="mb-6">
                  <h3 className="text-lg font-medium text-white mb-2">Current Task</h3>
                  <pre className="text-sm text-gray-300 bg-gray-900 p-4 rounded-lg overflow-auto">{JSON.stringify(agentDetail.current_task, null, 2)}</pre>
                </div>
              )}
              <h3 className="text-lg font-medium text-white mb-2">Message History</h3>
              <div className="space-y-2">
                {agentDetail.activity?.map((item: any, i: number) => (
                  <div key={i} className="bg-gray-700/50 rounded-lg p-3 border border-gray-600">
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <span className={`px-2 py-0.5 text-xs rounded ${getActivityTypeColor(item.type)}`}>{item.type}</span>
                        <span className="text-xs text-gray-400">{new Date(item.timestamp).toLocaleTimeString()}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 text-sm mb-2">
                      <span className="text-blue-400">{item.source}</span>
                      <ArrowRight className="w-3 h-3 text-gray-500" />
                      <span className="text-green-400">{item.target}</span>
                    </div>
                    <pre className="text-xs text-gray-300 whitespace-pre-wrap overflow-auto max-h-[150px]">{formatContent(item.content)}</pre>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
