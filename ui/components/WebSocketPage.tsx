'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Activity, Circle, Send, Trash2, Code, Layout, User, Zap, Brain, Server, Clock, Database, ChevronDown, ChevronRight } from 'lucide-react';
import { createWebSocket } from '../lib/api';

interface WSMessage {
  id: string;
  type: 'sent' | 'received' | 'system';
  content: string;
  parsed?: any;
  timestamp: Date;
}

type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error';
type ViewMode = 'both' | 'json' | 'visual';

// --- Visual Components ---

const AgentStatusBadge = ({ status }: { status: string }) => {
  let color = 'bg-gray-700 text-gray-300 border-gray-600';
  let icon = <Circle className="w-3 h-3" />;
  
  switch(status?.toLowerCase()) {
    case 'idle':
      color = 'bg-gray-800 text-gray-400 border-gray-700';
      break;
    case 'working':
    case 'busy':
      color = 'bg-yellow-900/30 text-yellow-500 border-yellow-700/50';
      icon = <Zap className="w-3 h-3" />;
      break;
    case 'thinking':
      color = 'bg-purple-900/30 text-purple-400 border-purple-700/50';
      icon = <Brain className="w-3 h-3" />;
      break;
    case 'error':
      color = 'bg-red-900/30 text-red-400 border-red-700/50';
      icon = <Activity className="w-3 h-3" />;
      break;
  }
  
  return (
    <span className={`flex items-center gap-1.5 px-2 py-0.5 rounded text-xs border ${color}`}>
      {icon}
      <span className="capitalize">{status}</span>
    </span>
  );
};

const DataVisualizer = ({ data }: { data: any }) => {
  // 1. Connection / System Status
  if (data.type === 'connected' || data.type === 'status_update') {
    const activeAgents = data.agents?.total_agents || 0;
    const idleAgents = data.agents?.status_breakdown?.idle || 0;
    const healthy = data.agents?.healthy;
    
    return (
      <div className="bg-gray-800 border border-gray-700 rounded-lg p-3 mb-2 w-full max-w-sm">
        <div className="flex items-center gap-2 mb-2 pb-2 border-b border-gray-700">
          <Server className="w-4 h-4 text-blue-400" />
          <span className="font-semibold text-blue-100">System Status</span>
        </div>
        <div className="grid grid-cols-2 gap-2 text-sm">
          <div className="flex flex-col bg-gray-900/50 p-2 rounded">
            <span className="text-gray-500 text-xs">Health</span>
            <span className={healthy ? 'text-green-400' : 'text-red-400'}>
              {healthy ? 'Operational' : 'Issues Detected'}
            </span>
          </div>
          <div className="flex flex-col bg-gray-900/50 p-2 rounded">
            <span className="text-gray-500 text-xs">Agents</span>
            <div className="flex gap-2">
              <span className="text-gray-300">{activeAgents} Total</span>
              <span className="text-gray-500">({idleAgents} Idle)</span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // 2. Agent Status Update (Single or Batch)
  if (data.type === 'agent_statuses' || data.type === 'heartbeat') {
    const statuses = data.statuses || data.agent_statuses || {};
    const activeAgents = Object.entries(statuses).filter(([_, s]: [string, any]) => s !== 'idle');
    
    if (activeAgents.length === 0) return (
      <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-2 mb-2 w-full max-w-xs opacity-75">
        <div className="flex items-center gap-2 text-gray-400 text-sm">
          <Clock className="w-4 h-4" />
          <span>No Active Agents</span>
        </div>
      </div>
    );

    return (
      <div className="bg-gray-800 border border-gray-700 rounded-lg p-3 mb-2 w-full">
        <div className="flex items-center gap-2 mb-2 pb-2 border-b border-gray-700">
          <Activity className="w-4 h-4 text-purple-400" />
          <span className="font-semibold text-purple-100">Agent Activity</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {activeAgents.map(([name, status]: [string, any]) => (
            <div key={name} className="flex items-center justify-between bg-gray-900/50 p-2 rounded border-l-2 border-purple-500">
              <span className="text-gray-300 text-sm truncate mr-2">{name.replace('_agent', '')}</span>
              <AgentStatusBadge status={status as string} />
            </div>
          ))}
        </div>
      </div>
    );
  }

  // 3. Pong / Ping
  if (data.type === 'pong' || data.type === 'ping') {
    return (
       <div className="inline-flex items-center gap-2 px-3 py-1 bg-gray-800 rounded-full border border-gray-700 text-xs text-gray-500 mb-2">
         <Activity className="w-3 h-3" />
         <span>Heartbeat ({data.type})</span>
       </div>
    );
  }

  // Fallback for unknown types
  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-2 mb-2 w-full">
         <div className="flex items-center gap-2 text-gray-400 text-sm">
            <Code className="w-4 h-4" />
            <span>Raw Data ({data.type || 'unknown'})</span>
         </div>
    </div>
  );
};

export default function WebSocketPage() {
  const [status, setStatus] = useState<ConnectionStatus>('disconnected');
  const [messages, setMessages] = useState<WSMessage[]>([]);
  const [input, setInput] = useState('');
  const [viewMode, setViewMode] = useState<ViewMode>('both');
  const wsRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const addMessage = (type: WSMessage['type'], content: string, parsed?: any) => {
    setMessages((prev) => [
      ...prev,
      {
        id: Date.now().toString(),
        type,
        content,
        parsed,
        timestamp: new Date(),
      },
    ]);
  };

  const connect = () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    setStatus('connecting');
    addMessage('system', 'Connecting to WebSocket...');

    try {
      wsRef.current = createWebSocket('/ws');

      wsRef.current.onopen = () => {
        setStatus('connected');
        addMessage('system', 'Connected to WebSocket');
        
        // Start Ping Interval
        const pingInterval = setInterval(() => {
            if (wsRef.current?.readyState === WebSocket.OPEN) {
                wsRef.current.send(JSON.stringify({ type: 'ping' }));
            }
        }, 30000);
        
        // Store interval ID on the socket element itself for cleanup (hacky but works for ref)
        (wsRef.current as any).pingInterval = pingInterval;
      };

      wsRef.current.onmessage = (event) => {
        let content = event.data;
        let parsed = undefined;
        try {
          parsed = JSON.parse(event.data);
          content = JSON.stringify(parsed, null, 2);
        } catch (e) {
          // Not JSON, use as-is
        }
        addMessage('received', content, parsed);
      };

      wsRef.current.onclose = () => {
        setStatus('disconnected');
        addMessage('system', 'Disconnected from WebSocket');
        if ((wsRef.current as any)?.pingInterval) clearInterval((wsRef.current as any).pingInterval);
      };

      wsRef.current.onerror = (error) => {
        setStatus('error');
        addMessage('system', 'WebSocket error occurred');
        console.error('WebSocket error:', error);
      };
    } catch (err) {
      setStatus('error');
      addMessage('system', 'Failed to create WebSocket connection');
    }
  };

  const disconnect = () => {
    if (wsRef.current) {
      if ((wsRef.current as any)?.pingInterval) clearInterval((wsRef.current as any).pingInterval);
      wsRef.current.close();
      wsRef.current = null;
    }
  };

  const sendMessage = () => {
    if (!input.trim() || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

    wsRef.current.send(input);
    // Try to parse sent message too for visualization
    let parsed = undefined;
    try { parsed = JSON.parse(input); } catch {}
    
    addMessage('sent', input, parsed);
    setInput('');
  };

  const clearMessages = () => {
    setMessages([]);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const getStatusColor = () => {
    switch (status) {
      case 'connected':
        return 'text-green-500';
      case 'connecting':
        return 'text-yellow-500 animate-pulse';
      case 'error':
        return 'text-red-500';
      default:
        return 'text-gray-500';
    }
  };

  return (
    <div className="h-screen flex flex-col bg-[#1e1e1e] text-[#d4d4d4]">
      {/* Header */}
      <div className="p-4 border-b border-[#3e3e3e] bg-[#252526]">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold flex items-center gap-3">
              <Activity className="w-6 h-6 text-[#007acc]" />
              WebSocket Debugger
            </h1>
            <div className="flex items-center gap-2 mt-1">
              <Circle className={`w-2 h-2 fill-current ${getStatusColor()}`} />
              <span className="text-[#cccccc] text-xs capitalize">{status}</span>
            </div>
          </div>
          
          <div className="flex items-center gap-4">
             {/* View Mode Toggle */}
             <div className="flex bg-[#333333] rounded-lg p-1">
                <button 
                  onClick={() => setViewMode('both')}
                  className={`p-1.5 rounded ${viewMode === 'both' ? 'bg-[#007acc] text-white' : 'text-gray-400 hover:text-white'}`}
                  title="Split View"
                >
                  <Layout className="w-4 h-4" />
                </button>
                <button 
                  onClick={() => setViewMode('visual')}
                  className={`p-1.5 rounded ${viewMode === 'visual' ? 'bg-[#007acc] text-white' : 'text-gray-400 hover:text-white'}`}
                  title="Visual Only"
                >
                  <User className="w-4 h-4" />
                </button>
                <button 
                  onClick={() => setViewMode('json')}
                  className={`p-1.5 rounded ${viewMode === 'json' ? 'bg-[#007acc] text-white' : 'text-gray-400 hover:text-white'}`}
                  title="JSON Only"
                >
                  <Code className="w-4 h-4" />
                </button>
             </div>

            <div className="flex gap-2">
              {status !== 'connected' ? (
                <button
                  onClick={connect}
                  disabled={status === 'connecting'}
                  className="flex items-center gap-2 px-3 py-1.5 bg-[#0e639c] hover:bg-[#1177bb] disabled:bg-gray-600 rounded text-white text-sm transition-colors"
                >
                  Connect
                </button>
              ) : (
                <button
                  onClick={disconnect}
                  className="flex items-center gap-2 px-3 py-1.5 bg-red-700 hover:bg-red-600 rounded text-white text-sm transition-colors"
                >
                  Disconnect
                </button>
              )}
              <button
                onClick={clearMessages}
                className="flex items-center gap-2 px-3 py-1.5 bg-[#3e3e3e] hover:bg-[#4e4e4e] rounded text-white text-sm transition-colors"
              >
                <Trash2 className="w-4 h-4" />
                Clear
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-[#1e1e1e]">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-[#6b6b6b]">
            <Activity className="w-16 h-16 mb-4 opacity-50" />
            <p className="text-lg font-semibold">Ready to Connect</p>
            <p className="text-sm">Click connect to start monitoring real-time agent events</p>
          </div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex flex-col ${
                msg.type === 'sent' ? 'items-end' : msg.type === 'system' ? 'items-center' : 'items-start'
              }`}
            >
              {msg.type === 'system' ? (
                <div className="px-3 py-1 bg-[#333333] rounded-full text-[#cccccc] text-xs my-2">
                  {msg.content}
                </div>
              ) : (
                <div
                  className={`max-w-[85%] rounded-lg p-3 ${
                    msg.type === 'sent'
                      ? 'bg-[#264f78] border border-[#007acc]' // VS Code active selection color
                      : 'bg-[#252526] border border-[#3e3e3e]' // VS Code sidebar color
                  }`}
                >
                  <div className="flex items-center justify-between gap-4 mb-2 text-xs opacity-70 border-b border-white/10 pb-1">
                    <span className="font-semibold uppercase tracking-wider">{msg.type === 'sent' ? 'Client' : 'Server'}</span>
                    <span className="font-mono">{msg.timestamp.toLocaleTimeString()}</span>
                  </div>
                  
                  {/* Visual Layer */}
                  {(viewMode !== 'json' && msg.parsed) && (
                    <div className="mb-2">
                      <DataVisualizer data={msg.parsed} />
                    </div>
                  )}

                  {/* Code Layer */}
                  {(viewMode !== 'visual') && (
                    <div className="relative group">
                        <pre className="whitespace-pre-wrap text-xs font-mono text-[#9cdcfe] overflow-x-auto bg-[#1e1e1e] p-2 rounded border border-[#3e3e3e]">
                            {msg.content}
                        </pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-4 border-t border-[#3e3e3e] bg-[#252526]">
        <div className="flex gap-3">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            rows={1}
            disabled={status !== 'connected'}
            className="flex-1 px-3 py-2 bg-[#3c3c3c] border border-[#3e3e3e] rounded text-[#d4d4d4] placeholder-[#a6a6a6] focus:outline-none focus:border-[#007acc] resize-none disabled:opacity-50"
            placeholder={status === 'connected' ? 'Send JSON command...' : 'Connect to send messages'}
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || status !== 'connected'}
            className="px-4 py-2 bg-[#0e639c] hover:bg-[#1177bb] disabled:bg-[#4d4d4d] rounded text-white transition-colors"
          >
            <Send className="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  );
}
