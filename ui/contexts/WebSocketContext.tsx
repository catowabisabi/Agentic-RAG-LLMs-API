'use client';

import React, { createContext, useContext, useState, useEffect, useRef, useCallback, ReactNode } from 'react';
import { createWebSocket } from '../lib/api';

// ========== Types ==========

export interface WSEvent {
  id: string;
  type: string;
  agent?: string;
  data: any;
  raw: string;
  timestamp: Date;
}

export interface AgentStatusMap {
  [agentName: string]: string; // e.g. "idle" | "working" | "thinking" | "error"
}

export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error';

interface WebSocketContextType {
  status: ConnectionStatus;
  events: WSEvent[];
  agentStatuses: AgentStatusMap;
  connect: () => void;
  disconnect: () => void;
  sendMessage: (msg: string) => void;
  clearEvents: () => void;
  // Categorized events for the 4-column view
  classifyingEvents: WSEvent[];
  thinkingEvents: WSEvent[];
  planningEvents: WSEvent[];
  resultEvents: WSEvent[];
}

const WebSocketContext = createContext<WebSocketContextType | undefined>(undefined);

// ========== Categorization helpers ==========

const CLASSIFY_TYPES = new Set(['task_assigned', 'task_rerouted', 'agent_started', 'entry_classification', 'intent_classification']);
const THINKING_TYPES = new Set(['thinking', 'llm_call_start', 'agent_status_changed', 'rag_query', 'rag_result']);
const PLANNING_TYPES = new Set(['plan_step', 'planning_result', 'metacognition', 'validation']);
const RESULT_TYPES = new Set(['task_completed', 'agent_completed', 'final_response', 'error']);

function categorize(type: string): 'classify' | 'thinking' | 'planning' | 'result' | 'system' {
  if (CLASSIFY_TYPES.has(type)) return 'classify';
  if (THINKING_TYPES.has(type)) return 'thinking';
  if (PLANNING_TYPES.has(type)) return 'planning';
  if (RESULT_TYPES.has(type)) return 'result';
  return 'system';
}

// ========== Provider ==========

const MAX_EVENTS = 200;

export function WebSocketProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<ConnectionStatus>('disconnected');
  const [events, setEvents] = useState<WSEvent[]>([]);
  const [agentStatuses, setAgentStatuses] = useState<AgentStatusMap>({});
  const wsRef = useRef<WebSocket | null>(null);
  const pingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const eventIdCounter = useRef(0);

  const addEvent = useCallback((type: string, data: any, raw: string, agent?: string) => {
    const evt: WSEvent = {
      id: `ws-${Date.now()}-${eventIdCounter.current++}`,
      type,
      agent,
      data,
      raw,
      timestamp: new Date(),
    };
    setEvents(prev => {
      const updated = [...prev, evt];
      return updated.length > MAX_EVENTS ? updated.slice(-MAX_EVENTS) : updated;
    });
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    setStatus('connecting');

    try {
      const ws = createWebSocket('/ws');
      wsRef.current = ws;

      ws.onopen = () => {
        setStatus('connected');
        addEvent('system', { message: 'Connected' }, '{"type":"system","message":"Connected"}');
        // Start ping
        pingRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }));
          }
        }, 30000);
      };

      ws.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data);
          const type = parsed.type || 'unknown';
          const agent = parsed.agent_name || parsed.agent || parsed.source || parsed.source_agent;

          addEvent(type, parsed, event.data, agent);

          // Update agent statuses from heartbeat
          if (type === 'heartbeat' && parsed.agent_statuses) {
            setAgentStatuses(parsed.agent_statuses);
          }
          if (type === 'agent_status_changed') {
            setAgentStatuses(prev => ({ ...prev, [parsed.agent_name]: parsed.state }));
          }
          if (type === 'agent_statuses' && parsed.statuses) {
            setAgentStatuses(prev => ({ ...prev, ...parsed.statuses }));
          }
        } catch {
          addEvent('raw', { text: event.data }, event.data);
        }
      };

      ws.onclose = () => {
        setStatus('disconnected');
        if (pingRef.current) clearInterval(pingRef.current);
        addEvent('system', { message: 'Disconnected' }, '{"type":"system","message":"Disconnected"}');
        // Auto-reconnect
        reconnectRef.current = setTimeout(connect, 3000);
      };

      ws.onerror = () => {
        setStatus('error');
      };
    } catch {
      setStatus('error');
      reconnectRef.current = setTimeout(connect, 5000);
    }
  }, [addEvent]);

  const disconnect = useCallback(() => {
    if (reconnectRef.current) clearTimeout(reconnectRef.current);
    if (pingRef.current) clearInterval(pingRef.current);
    if (wsRef.current) {
      wsRef.current.onclose = null; // prevent auto-reconnect
      wsRef.current.close();
      wsRef.current = null;
    }
    setStatus('disconnected');
  }, []);

  const sendMessage = useCallback((msg: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(msg);
      addEvent('sent', { text: msg }, msg);
    }
  }, [addEvent]);

  const clearEvents = useCallback(() => {
    setEvents([]);
  }, []);

  // Auto-connect on mount
  useEffect(() => {
    connect();
    return () => {
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      if (pingRef.current) clearInterval(pingRef.current);
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Derived categorized events
  const classifyingEvents = events.filter(e => categorize(e.type) === 'classify');
  const thinkingEvents = events.filter(e => categorize(e.type) === 'thinking');
  const planningEvents = events.filter(e => categorize(e.type) === 'planning');
  const resultEvents = events.filter(e => categorize(e.type) === 'result');

  return (
    <WebSocketContext.Provider
      value={{
        status,
        events,
        agentStatuses,
        connect,
        disconnect,
        sendMessage,
        clearEvents,
        classifyingEvents,
        thinkingEvents,
        planningEvents,
        resultEvents,
      }}
    >
      {children}
    </WebSocketContext.Provider>
  );
}

export function useWebSocket() {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocket must be used within a WebSocketProvider');
  }
  return context;
}
