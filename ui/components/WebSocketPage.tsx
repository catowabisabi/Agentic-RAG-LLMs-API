'use client';

import React, { useState, useRef, useEffect } from 'react';
import {
  Activity, Circle, Send, Trash2, Code, Zap,
  Brain, Clock, ChevronDown, ChevronRight,
  Filter, Columns, List, ArrowRight
} from 'lucide-react';
import { useWebSocket, WSEvent } from '../contexts/WebSocketContext';

type ViewMode = 'columns' | 'timeline' | 'json';

// ========== Event Card ==========

const EventCard = ({ event, compact }: { event: WSEvent; compact?: boolean }) => {
  const [expanded, setExpanded] = useState(false);

  const getTypeColor = (type: string) => {
    switch (type) {
      case 'task_assigned': case 'task_rerouted': return 'border-l-blue-500 bg-blue-900/10';
      case 'thinking': case 'llm_call_start': return 'border-l-purple-500 bg-purple-900/10';
      case 'plan_step': case 'planning_result': return 'border-l-yellow-500 bg-yellow-900/10';
      case 'task_completed': case 'agent_completed': return 'border-l-green-500 bg-green-900/10';
      case 'error': return 'border-l-red-500 bg-red-900/10';
      case 'rag_query': case 'rag_result': return 'border-l-cyan-500 bg-cyan-900/10';
      default: return 'border-l-gray-500 bg-gray-800/50';
    }
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'task_assigned': return '📋';
      case 'task_rerouted': return '🔀';
      case 'agent_started': return '🚀';
      case 'thinking': return '💭';
      case 'llm_call_start': return '🤖';
      case 'plan_step': return '📝';
      case 'planning_result': return '📊';
      case 'task_completed': return '✅';
      case 'agent_completed': return '🎯';
      case 'error': return '❌';
      case 'rag_query': return '🔍';
      case 'rag_result': return '📚';
      case 'entry_classification': return '🏷️';
      case 'agent_status_changed': return '🔄';
      case 'metacognition': return '🧠';
      case 'validation': return '✔️';
      default: return '▶️';
    }
  };

  const formatContent = (data: any): string => {
    if (!data) return '';
    if (typeof data === 'string') return data;
    const d = data.data || data.content || data;
    if (typeof d === 'string') return d;
    if (d.message) return d.message;
    if (d.query) return `Query: ${d.query}`;
    if (d.result) return typeof d.result === 'string' ? d.result : JSON.stringify(d.result).slice(0, 200);
    return JSON.stringify(d, null, 2).slice(0, 300);
  };

  if (compact) {
    return (
      <div className={`border-l-2 px-2 py-1.5 text-xs ${getTypeColor(event.type)} rounded-r`}>
        <div className="flex items-center gap-1.5">
          <span>{getTypeIcon(event.type)}</span>
          {event.agent && <span className="text-blue-400 font-medium truncate">{event.agent}</span>}
          <span className="text-gray-500 ml-auto flex-shrink-0">{event.timestamp.toLocaleTimeString()}</span>
        </div>
        <p className="text-gray-400 mt-0.5 line-clamp-2">{formatContent(event.data)}</p>
      </div>
    );
  }

  return (
    <div className={`border-l-2 px-3 py-2 rounded-r-lg ${getTypeColor(event.type)} transition-colors`}>
      <div className="flex items-center gap-2 cursor-pointer" onClick={() => setExpanded(!expanded)}>
        <span className="text-sm">{getTypeIcon(event.type)}</span>
        <span className="text-xs font-medium text-gray-300">{event.type}</span>
        {event.agent && (
          <>
            <ArrowRight className="w-3 h-3 text-gray-600" />
            <span className="text-xs text-blue-400">{event.agent}</span>
          </>
        )}
        <span className="text-xs text-gray-600 ml-auto">{event.timestamp.toLocaleTimeString()}</span>
        {expanded ? <ChevronDown className="w-3 h-3 text-gray-500" /> : <ChevronRight className="w-3 h-3 text-gray-500" />}
      </div>
      <p className="text-xs text-gray-400 mt-1 line-clamp-2">{formatContent(event.data)}</p>
      {expanded && (
        <pre className="text-xs text-gray-500 mt-2 p-2 bg-gray-900/50 rounded overflow-auto max-h-40 font-mono">
          {JSON.stringify(event.data, null, 2)}
        </pre>
      )}
    </div>
  );
};

// ========== Column ==========

const EventColumn = ({ title, icon, events, color }: { title: string; icon: React.ReactNode; events: WSEvent[]; color: string }) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [events.length]);

  return (
    <div className="flex flex-col h-full min-w-0">
      <div className={`flex items-center gap-2 px-3 py-2 border-b ${color} bg-gray-800/80`}>
        {icon}
        <span className="font-semibold text-sm text-gray-200">{title}</span>
        <span className="ml-auto text-xs text-gray-500 bg-gray-700 px-2 py-0.5 rounded-full">{events.length}</span>
      </div>
      <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
        {events.length === 0 ? (
          <div className="flex items-center justify-center h-full text-gray-600 text-xs">
            Waiting for events...
          </div>
        ) : (
          events.slice(-50).map(evt => <EventCard key={evt.id} event={evt} compact />)
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
};

// ========== Main Page ==========

export default function WebSocketPage() {
  const {
    status, events, agentStatuses, connect, disconnect, sendMessage, clearEvents,
    classifyingEvents, thinkingEvents, planningEvents, resultEvents
  } = useWebSocket();
  const [input, setInput] = useState('');
  const [viewMode, setViewMode] = useState<ViewMode>('columns');
  const [filterType, setFilterType] = useState<string>('');
  const timelineRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    timelineRef.current?.scrollTo({ top: timelineRef.current.scrollHeight, behavior: 'smooth' });
  }, [events.length, viewMode]);

  const handleSend = () => {
    if (!input.trim()) return;
    sendMessage(input);
    setInput('');
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

  const getStatusColor = () => {
    switch (status) {
      case 'connected': return 'text-green-500';
      case 'connecting': return 'text-yellow-500 animate-pulse';
      case 'error': return 'text-red-500';
      default: return 'text-gray-500';
    }
  };

  const filteredEvents = filterType
    ? events.filter(e => e.type === filterType || e.type.includes(filterType))
    : events.filter(e => !['heartbeat', 'pong', 'ping', 'system'].includes(e.type));

  const eventTypes = Array.from(new Set(events.map(e => e.type))).sort();

  return (
    <div className="h-screen flex flex-col bg-[#1e1e1e] text-[#d4d4d4]">
      {/* Header */}
      <div className="p-3 border-b border-[#3e3e3e] bg-[#252526] flex-shrink-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Activity className="w-5 h-5 text-[#007acc]" />
            <h1 className="text-lg font-bold">WebSocket Monitor</h1>
            <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-gray-800 text-xs">
              <Circle className={`w-2 h-2 fill-current ${getStatusColor()}`} />
              <span className="capitalize">{status}</span>
            </div>
            {Object.keys(agentStatuses).length > 0 && (
              <div className="flex items-center gap-1 text-xs text-gray-500">
                <span>{Object.values(agentStatuses).filter(s => s !== 'idle').length} active</span>
                <span>/</span>
                <span>{Object.keys(agentStatuses).length} total</span>
              </div>
            )}
          </div>

          <div className="flex items-center gap-3">
            <div className="flex bg-[#333333] rounded-lg p-0.5">
              <button onClick={() => setViewMode('columns')} className={`p-1.5 rounded ${viewMode === 'columns' ? 'bg-[#007acc] text-white' : 'text-gray-400 hover:text-white'}`} title="4-Column View">
                <Columns className="w-4 h-4" />
              </button>
              <button onClick={() => setViewMode('timeline')} className={`p-1.5 rounded ${viewMode === 'timeline' ? 'bg-[#007acc] text-white' : 'text-gray-400 hover:text-white'}`} title="Timeline View">
                <List className="w-4 h-4" />
              </button>
              <button onClick={() => setViewMode('json')} className={`p-1.5 rounded ${viewMode === 'json' ? 'bg-[#007acc] text-white' : 'text-gray-400 hover:text-white'}`} title="Raw JSON">
                <Code className="w-4 h-4" />
              </button>
            </div>

            {viewMode === 'timeline' && (
              <select value={filterType} onChange={e => setFilterType(e.target.value)} className="px-2 py-1.5 bg-[#333333] border border-[#3e3e3e] rounded text-xs text-gray-300">
                <option value="">All Events</option>
                {eventTypes.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            )}

            <div className="flex gap-1.5">
              {status !== 'connected' ? (
                <button onClick={connect} disabled={status === 'connecting'} className="px-3 py-1.5 bg-[#0e639c] hover:bg-[#1177bb] disabled:bg-gray-600 rounded text-white text-xs">Connect</button>
              ) : (
                <button onClick={disconnect} className="px-3 py-1.5 bg-red-700 hover:bg-red-600 rounded text-white text-xs">Disconnect</button>
              )}
              <button onClick={clearEvents} className="flex items-center gap-1 px-3 py-1.5 bg-[#3e3e3e] hover:bg-[#4e4e4e] rounded text-white text-xs">
                <Trash2 className="w-3 h-3" />Clear
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden">
        {events.length === 0 && status !== 'connected' ? (
          <div className="flex flex-col items-center justify-center h-full text-[#6b6b6b]">
            <Activity className="w-16 h-16 mb-4 opacity-50" />
            <p className="text-lg font-semibold">Ready to Connect</p>
            <p className="text-sm">Click connect to start monitoring real-time agent events</p>
          </div>
        ) : viewMode === 'columns' ? (
          <div className="grid grid-cols-4 h-full divide-x divide-[#3e3e3e]">
            <EventColumn title="Classifying" icon={<Filter className="w-4 h-4 text-blue-400" />} events={classifyingEvents} color="border-blue-500/50" />
            <EventColumn title="Thinking" icon={<Brain className="w-4 h-4 text-purple-400" />} events={thinkingEvents} color="border-purple-500/50" />
            <EventColumn title="Planning" icon={<Clock className="w-4 h-4 text-yellow-400" />} events={planningEvents} color="border-yellow-500/50" />
            <EventColumn title="Results" icon={<Zap className="w-4 h-4 text-green-400" />} events={resultEvents} color="border-green-500/50" />
          </div>
        ) : viewMode === 'timeline' ? (
          <div ref={timelineRef} className="h-full overflow-y-auto p-4 space-y-2">
            {filteredEvents.slice(-100).map(evt => (
              <EventCard key={evt.id} event={evt} />
            ))}
          </div>
        ) : (
          <div ref={timelineRef} className="h-full overflow-y-auto p-4 space-y-2">
            {events.slice(-100).map(evt => (
              <div key={evt.id} className="bg-[#252526] border border-[#3e3e3e] rounded-lg p-3">
                <div className="flex items-center gap-2 mb-2 text-xs opacity-70 border-b border-white/10 pb-1">
                  <span className="font-semibold uppercase tracking-wider text-blue-400">{evt.type}</span>
                  {evt.agent && <span className="text-gray-500">from {evt.agent}</span>}
                  <span className="font-mono ml-auto">{evt.timestamp.toLocaleTimeString()}</span>
                </div>
                <pre className="whitespace-pre-wrap text-xs font-mono text-[#9cdcfe] overflow-x-auto bg-[#1e1e1e] p-2 rounded border border-[#3e3e3e]">
                  {evt.raw}
                </pre>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Input */}
      <div className="p-3 border-t border-[#3e3e3e] bg-[#252526] flex-shrink-0">
        <div className="flex gap-2">
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            rows={1}
            disabled={status !== 'connected'}
            className="flex-1 px-3 py-2 bg-[#3c3c3c] border border-[#3e3e3e] rounded text-[#d4d4d4] placeholder-[#a6a6a6] focus:outline-none focus:border-[#007acc] resize-none disabled:opacity-50 text-sm"
            placeholder={status === 'connected' ? 'Send JSON command...' : 'Connect to send messages'}
          />
          <button onClick={handleSend} disabled={!input.trim() || status !== 'connected'} className="px-4 py-2 bg-[#0e639c] hover:bg-[#1177bb] disabled:bg-[#4d4d4d] rounded text-white transition-colors">
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
