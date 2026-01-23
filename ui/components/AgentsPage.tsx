'use client';

import React, { useState, useEffect } from 'react';
import {
  Users,
  RefreshCw,
  Play,
  Pause,
  Send,
  AlertTriangle,
  CheckCircle,
  Clock,
  Zap
} from 'lucide-react';
import { agentAPI } from '../lib/api';

interface Agent {
  name: string;
  role: string;
  description: string;
  status: string;
  is_running: boolean;
}

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [taskType, setTaskType] = useState('process_query');
  const [taskInput, setTaskInput] = useState('');
  const [taskResult, setTaskResult] = useState<any>(null);
  const [sending, setSending] = useState(false);

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

  useEffect(() => {
    fetchAgents();
  }, []);

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
    } catch (err: any) {
      setTaskResult({ error: err.message || 'Failed to send task' });
    }

    setSending(false);
  };

  const handleInterrupt = async (agentName?: string) => {
    try {
      await agentAPI.interrupt({
        agent_name: agentName,
        reason: 'User requested interrupt',
      });
      fetchAgents();
    } catch (err) {
      console.error('Failed to interrupt:', err);
    }
  };

  const getStatusIcon = (status: string, isRunning: boolean) => {
    if (!isRunning) return <Pause className="w-4 h-4 text-gray-500" />;
    switch (status) {
      case 'busy':
        return <Zap className="w-4 h-4 text-yellow-500" />;
      case 'idle':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'error':
        return <AlertTriangle className="w-4 h-4 text-red-500" />;
      default:
        return <Clock className="w-4 h-4 text-blue-500" />;
    }
  };

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center gap-3">
            <Users className="w-8 h-8" />
            Agents
          </h1>
          <p className="text-gray-400 mt-1">Manage and interact with AI agents</p>
        </div>
        <div className="flex gap-3">
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

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Agents List */}
        <div className="lg:col-span-2 bg-gray-800 rounded-xl border border-gray-700">
          <div className="p-6 border-b border-gray-700">
            <h2 className="text-xl font-semibold text-white">Registered Agents ({agents.length})</h2>
          </div>
          <div className="p-6">
            {loading ? (
              <div className="flex justify-center py-8">
                <div className="loading-spinner" />
              </div>
            ) : (
              <div className="space-y-3">
                {agents.map((agent) => (
                  <div
                    key={agent.name}
                    onClick={() => setSelectedAgent(agent.name)}
                    className={`p-4 rounded-lg cursor-pointer transition-colors ${
                      selectedAgent === agent.name
                        ? 'bg-blue-600/20 border-2 border-blue-500'
                        : 'bg-gray-700/50 border border-gray-600 hover:border-gray-500'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        {getStatusIcon(agent.status, agent.is_running)}
                        <div>
                          <h4 className="font-medium text-white">{agent.name}</h4>
                          <p className="text-sm text-gray-400">{agent.role}</p>
                        </div>
                      </div>
                      <span
                        className={`px-3 py-1 text-xs rounded-full ${
                          agent.is_running
                            ? 'bg-green-900/50 text-green-400'
                            : 'bg-gray-600 text-gray-400'
                        }`}
                      >
                        {agent.status}
                      </span>
                    </div>
                    {agent.description && (
                      <p className="text-sm text-gray-500 mt-2 ml-7">{agent.description}</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Task Panel */}
        <div className="bg-gray-800 rounded-xl border border-gray-700">
          <div className="p-6 border-b border-gray-700">
            <h2 className="text-xl font-semibold text-white">Send Task</h2>
          </div>
          <div className="p-6 space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Target Agent
              </label>
              <select
                value={selectedAgent || ''}
                onChange={(e) => setSelectedAgent(e.target.value)}
                className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
              >
                <option value="">Select an agent</option>
                {agents.map((agent) => (
                  <option key={agent.name} value={agent.name}>
                    {agent.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Task Type
              </label>
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
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Input
              </label>
              <textarea
                value={taskInput}
                onChange={(e) => setTaskInput(e.target.value)}
                rows={4}
                className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-blue-500 resize-none"
                placeholder="Enter task input..."
              />
            </div>

            <button
              onClick={sendTask}
              disabled={!selectedAgent || !taskInput || sending}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed rounded-lg text-white transition-colors"
            >
              {sending ? (
                <>
                  <div className="loading-spinner" />
                  Sending...
                </>
              ) : (
                <>
                  <Send className="w-4 h-4" />
                  Send Task
                </>
              )}
            </button>

            {/* Result */}
            {taskResult && (
              <div className="mt-4 p-4 bg-gray-700/50 rounded-lg">
                <h4 className="text-sm font-medium text-gray-300 mb-2">Result</h4>
                <pre className="text-sm text-gray-400 overflow-auto max-h-40">
                  {JSON.stringify(taskResult, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
