'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { 
  MessageSquare, Send, Trash2, Plus, Edit2, Check, X, Database, Loader2, 
  Brain, Wifi, WifiOff, StopCircle, Zap, Activity, Clock, AlertTriangle, 
  CheckCircle2, RefreshCw, Users, List
} from 'lucide-react';
import { chatAPI, sessionAPI, createWebSocket } from '../lib/api';

// ============== Type Definitions ==============

interface Source {
  database: string;
  title: string;
  relevance: number;
}

interface ThinkingStep {
  id?: string;
  step_type: string;
  agent_name: string;
  content: any;
  timestamp: string;
  duration_ms?: number;
  task_uid?: string;
}

interface AgentStatus {
  name: string;
  state: string;
  message?: string;
  progress?: number;
  task_id?: string;
}

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  agents_involved?: string[];
  sources?: Source[];
  thinking?: ThinkingStep[];
  task_uid?: string;
}

interface TaskInfo {
  task_uid: string;
  agent_name: string;
  task_type: string;
  status: string;
  input_data?: any;
  result?: any;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  steps?: ThinkingStep[];
}

interface SessionState {
  session: {
    session_id: string;
    title: string;
    status: string;
    created_at: string;
    updated_at: string;
    metadata: any;
  };
  messages: Message[];
  tasks: TaskInfo[];
  running_tasks: TaskInfo[];
  task_stats: {
    total: number;
    running: number;
    completed: number;
    failed: number;
  };
  agents_involved: string[];
  is_processing: boolean;
}

interface ChatSession {
  id: string;
  title: string;
  messages: Message[];
  createdAt: string;
  updatedAt: string;
  status: string;
  isLoaded: boolean;
  runningTasks: TaskInfo[];
  taskStats: { total: number; running: number; completed: number; failed: number };
}

// ============== Constants ==============

const POLL_INTERVAL = 2000;
const SESSION_RECOVERY_KEY = 'agentic-rag-session-ids';

// ============== Helper Functions ==============

const generateSessionId = (): string => {
  return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
};

const getAgentStateIcon = (state: string) => {
  switch (state?.toLowerCase()) {
    case 'working':
    case 'calling_llm':
    case 'querying_rag':
      return <Zap className="w-3 h-3 text-yellow-400 animate-pulse" />;
    case 'thinking':
      return <Brain className="w-3 h-3 text-purple-400 animate-pulse" />;
    case 'processing':
      return <Activity className="w-3 h-3 text-blue-400 animate-pulse" />;
    case 'error':
      return <AlertTriangle className="w-3 h-3 text-red-400" />;
    case 'completed':
      return <CheckCircle2 className="w-3 h-3 text-green-400" />;
    default:
      return <Clock className="w-3 h-3 text-gray-500" />;
  }
};

const getStepIcon = (type: string) => {
  switch (type) {
    case 'task_assigned': return '📋';
    case 'THINKING': return '💭';
    case 'PLANNING': return '📝';
    case 'RAG_QUERY': return '🔍';
    case 'RAG_RESULT': return '📚';
    case 'LLM_CALL': return '🤖';
    case 'AGENT_MESSAGE': return '💬';
    case 'COORDINATION': return '🔗';
    case 'RESULT': return '✅';
    case 'ERROR': return '❌';
    default: return '▶️';
  }
};

const formatThinkingContent = (content: any): string => {
  if (typeof content === 'string') return content;
  if (content.thought) return content.thought;
  if (content.status) return content.status;
  if (content.task) return `Task: ${content.task}`;
  if (content.query) return `Query: ${content.query}`;
  if (content.sources_count !== undefined) return `Found ${content.sources_count} sources`;
  if (content.response_length) return `Generated ${content.response_length} char response`;
  if (content.message) return content.message;
  if (content.workflow) return `Workflow: ${content.workflow}`;
  if (content.reasoning) return content.reasoning;
  // Skip verbose data
  if (typeof content === 'object') {
    const keys = Object.keys(content);
    if (keys.length === 0) return '';
    // Just show first meaningful value
    for (const key of ['status', 'message', 'task', 'workflow', 'query']) {
      if (content[key]) return String(content[key]);
    }
  }
  return '';
};

// Helper to summarize agent statuses
const getAgentSummary = (statuses: Record<string, AgentStatus>): { active: string[], idle: number, total: number } => {
  const active: string[] = [];
  let idle = 0;
  const entries = Object.entries(statuses);
  
  for (const [name, status] of entries) {
    const state = status.state?.toLowerCase() || 'idle';
    if (['working', 'thinking', 'calling_llm', 'querying_rag', 'processing'].includes(state)) {
      active.push(name.replace('_agent', ''));
    } else {
      idle++;
    }
  }
  
  return { active, idle, total: entries.length };
};

// ============== Main Component ==============

export default function ChatPageV2() {
  // Session state
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [sessionLoading, setSessionLoading] = useState<Record<string, boolean>>({});
  
  // Input state
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [editingTitle, setEditingTitle] = useState<string | null>(null);
  const [editTitleValue, setEditTitleValue] = useState('');
  
  // Thinking/Status state
  const [thinkingSteps, setThinkingSteps] = useState<ThinkingStep[]>([]);
  const [agentStatuses, setAgentStatuses] = useState<Record<string, AgentStatus>>({});
  const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);
  const [pendingInfo, setPendingInfo] = useState<string | null>(null);
  const [isInterrupting, setIsInterrupting] = useState(false);
  const [lastStatusUpdate, setLastStatusUpdate] = useState<string>('');
  
  // WebSocket state
  const [wsConnected, setWsConnected] = useState(false);
  const [subscribedSession, setSubscribedSession] = useState<string | null>(null);
  
  // UI state
  const [isHydrated, setIsHydrated] = useState(false);
  const [showTaskPanel, setShowTaskPanel] = useState(true);
  const [showThinking, setShowThinking] = useState(true);
  
  // Refs
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const activeSession = sessions.find(s => s.id === activeSessionId);
  const messages = activeSession?.messages || [];
  const runningTasks = activeSession?.runningTasks || [];
  
  // Computed values
  const agentSummary = getAgentSummary(agentStatuses);
  const hasWorkingAgents = agentSummary.active.length > 0;

  // ============== WebSocket Connection ==============

  useEffect(() => {
    const connectWs = () => {
      try {
        const ws = createWebSocket('/ws');
        wsRef.current = ws;
        
        ws.onopen = () => {
          console.log('[ChatV2] WebSocket connected');
          setWsConnected(true);
          
          // Re-subscribe to active session if we have one
          if (activeSessionId) {
            subscribeToSession(activeSessionId);
          }
        };
        
        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            handleWebSocketMessage(data);
          } catch (e) {
            console.error('[ChatV2] Parse error:', e);
          }
        };
        
        ws.onclose = () => {
          console.log('[ChatV2] WebSocket disconnected');
          setWsConnected(false);
          setSubscribedSession(null);
          setTimeout(connectWs, 3000);
        };
        
        ws.onerror = (err) => {
          console.error('[ChatV2] WebSocket error:', err);
        };
      } catch (e) {
        console.error('[ChatV2] Failed to connect:', e);
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

  const handleWebSocketMessage = useCallback((data: any) => {
    // Handle heartbeat with agent statuses - update quietly without re-rendering unless active agents change
    if (data.type === 'heartbeat' && data.agent_statuses) {
      const newSummary = getAgentSummary(data.agent_statuses);
      // Only update if active agents changed
      if (JSON.stringify(newSummary.active) !== JSON.stringify(agentSummary.active)) {
        setAgentStatuses(data.agent_statuses);
        setLastStatusUpdate(new Date().toLocaleTimeString());
      }
      return;
    }
    
    // Handle agent_statuses message (alternative format)
    if (data.type === 'agent_statuses' && data.statuses) {
      const formatted: Record<string, AgentStatus> = {};
      for (const [name, state] of Object.entries(data.statuses)) {
        formatted[name] = { name, state: state as string };
      }
      const newSummary = getAgentSummary(formatted);
      if (JSON.stringify(newSummary.active) !== JSON.stringify(agentSummary.active)) {
        setAgentStatuses(formatted);
        setLastStatusUpdate(new Date().toLocaleTimeString());
      }
      return;
    }
    
    // Handle subscription confirmation
    if (data.type === 'session_subscribed') {
      console.log('[ChatV2] Subscribed to session:', data.session_id);
      setSubscribedSession(data.session_id);
      return;
    }
    
    // Handle connected message - just log
    if (data.type === 'connected') {
      console.log('[ChatV2] Connected:', data.client_id);
      return;
    }
    
    // Handle session state response (from WebSocket)
    if (data.type === 'session_state') {
      handleSessionStateUpdate(data.state);
      return;
    }
    
    // Handle agent status changes - only for active changes
    if (data.type === 'agent_status_changed') {
      const state = data.state?.toLowerCase();
      // Only update UI if becoming active or completing
      if (['working', 'thinking', 'calling_llm', 'querying_rag', 'processing', 'idle', 'error'].includes(state)) {
        setAgentStatuses(prev => ({
          ...prev,
          [data.agent_name]: {
            name: data.agent_name,
            state: data.state,
            message: data.message,
            progress: data.progress,
            task_id: data.task_id
          }
        }));
        setLastStatusUpdate(new Date().toLocaleTimeString());
      }
      return;
    }
    
    // Filter messages by session_id if present
    if (data.session_id && data.session_id !== activeSessionId) {
      return;
    }
    
    // Capture only important thinking/plan steps (not every status update)
    if (data.type === 'thinking' || data.type === 'task_assigned' || 
        data.type === 'task_completed' || data.type === 'agent_step') {
      const content = formatThinkingContent(data.data || data.content || data);
      // Skip empty or redundant content
      if (!content || content.length < 3) return;
      
      const step: ThinkingStep = {
        step_type: data.type.toUpperCase(),
        agent_name: data.agent_name || data.agent || data.source || 'system',
        content: data.data || data.content || data,
        timestamp: data.timestamp || new Date().toISOString(),
        task_uid: data.task_uid
      };
      
      setThinkingSteps(prev => {
        const isDupe = prev.some(s => 
          s.timestamp === step.timestamp && 
          s.step_type === step.step_type && 
          s.agent_name === step.agent_name
        );
        if (isDupe) return prev;
        return [...prev, step].slice(-30);
      });
    }
    
    // Handle task completion - update session state
    if (data.type === 'task_completed' && data.session_id === activeSessionId && activeSessionId) {
      refreshSessionState(activeSessionId);
    }
  }, [activeSessionId, agentSummary.active]);

  const subscribeToSession = useCallback((sessionId: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'subscribe_session',
        session_id: sessionId
      }));
    }
  }, []);

  // ============== Session State Management ==============

  const handleSessionStateUpdate = useCallback((state: SessionState) => {
    if (!state?.session) return;
    
    const sessionId = state.session.session_id;
    
    setSessions(prev => prev.map(s => {
      if (s.id === sessionId) {
        return {
          ...s,
          title: state.session.title || s.title,
          messages: state.messages.map(m => ({
            id: m.id,
            role: m.role,
            content: m.content,
            timestamp: m.timestamp,
            agents_involved: m.agents_involved,
            sources: m.sources,
            task_uid: m.task_uid
          })),
          runningTasks: state.running_tasks || [],
          taskStats: state.task_stats || { total: 0, running: 0, completed: 0, failed: 0 },
          status: state.session.status,
          isLoaded: true,
          updatedAt: state.session.updated_at
        };
      }
      return s;
    }));
    
    // If this is for the active session, update loading state
    if (sessionId === activeSessionId) {
      setSessionLoading(prev => ({ ...prev, [sessionId]: false }));
      
      // If there are running tasks, start polling
      if (state.running_tasks && state.running_tasks.length > 0) {
        startPolling(sessionId);
        setLoading(true);
        setPendingInfo(`${state.running_tasks.length} task(s) in progress...`);
      }
    }
  }, [activeSessionId]);

  const refreshSessionState = useCallback(async (sessionId: string) => {
    if (!sessionId) return;
    
    try {
      const response = await sessionAPI.getSessionState(sessionId);
      handleSessionStateUpdate(response.data);
    } catch (e: any) {
      if (e.response?.status !== 404) {
        console.error('[ChatV2] Failed to refresh session:', e);
      }
    }
  }, [handleSessionStateUpdate]);

  const loadSessionState = useCallback(async (sessionId: string) => {
    setSessionLoading(prev => ({ ...prev, [sessionId]: true }));
    
    try {
      const response = await sessionAPI.getSessionState(sessionId);
      handleSessionStateUpdate(response.data);
    } catch (e: any) {
      if (e.response?.status === 404) {
        // Session doesn't exist in database yet - mark as loaded with default title
        console.log('[ChatV2] Session not in database yet:', sessionId);
        setSessions(prev => prev.map(s => {
          if (s.id === sessionId) {
            return {
              ...s,
              title: s.title === 'Loading...' ? 'New Chat' : s.title,
              isLoaded: true
            };
          }
          return s;
        }));
      } else {
        console.error('[ChatV2] Failed to load session:', e);
      }
      setSessionLoading(prev => ({ ...prev, [sessionId]: false }));
    }
  }, [handleSessionStateUpdate]);

  // ============== Polling for Running Tasks ==============

  const startPolling = useCallback((sessionId: string) => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
    }
    
    pollIntervalRef.current = setInterval(async () => {
      try {
        const response = await sessionAPI.getRunningTasks(sessionId);
        const { tasks, count } = response.data;
        
        setSessions(prev => prev.map(s => {
          if (s.id === sessionId) {
            return { ...s, runningTasks: tasks };
          }
          return s;
        }));
        
        if (count === 0) {
          // No more running tasks - stop polling and refresh full state
          stopPolling();
          setLoading(false);
          setPendingInfo(null);
          refreshSessionState(sessionId);
        } else {
          setPendingInfo(`${count} task(s) in progress...`);
        }
      } catch (e) {
        console.error('[ChatV2] Poll error:', e);
      }
    }, POLL_INTERVAL);
  }, [refreshSessionState]);

  const stopPolling = useCallback(() => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  }, []);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  // ============== Session Tab Switching ==============

  useEffect(() => {
    if (!activeSessionId || !isHydrated) return;
    
    // Subscribe to WebSocket for this session
    subscribeToSession(activeSessionId);
    
    // Load session state from database
    loadSessionState(activeSessionId);
    
    // Clear thinking steps when switching sessions
    setThinkingSteps([]);
    
  }, [activeSessionId, isHydrated, subscribeToSession, loadSessionState]);

  // ============== Initial Load ==============

  useEffect(() => {
    setIsHydrated(true);
    
    // Load saved session IDs from localStorage
    try {
      const savedIds = localStorage.getItem(SESSION_RECOVERY_KEY);
      if (savedIds) {
        const sessionIds: string[] = JSON.parse(savedIds);
        if (Array.isArray(sessionIds) && sessionIds.length > 0) {
          // Create placeholder sessions
          const placeholderSessions: ChatSession[] = sessionIds.map(id => ({
            id,
            title: 'Loading...',
            messages: [],
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
            status: 'active',
            isLoaded: false,
            runningTasks: [],
            taskStats: { total: 0, running: 0, completed: 0, failed: 0 }
          }));
          
          setSessions(placeholderSessions);
          setActiveSessionId(sessionIds[0]);
          return;
        }
      }
    } catch (e) {
      console.error('[ChatV2] Failed to load session IDs:', e);
    }
    
    // No saved sessions - create a new one
    const newSessionId = generateSessionId();
    const initialSession: ChatSession = {
      id: newSessionId,
      title: 'New Chat',
      messages: [],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      status: 'active',
      isLoaded: true,
      runningTasks: [],
      taskStats: { total: 0, running: 0, completed: 0, failed: 0 }
    };
    
    setSessions([initialSession]);
    setActiveSessionId(newSessionId);
  }, []);

  // Save session IDs to localStorage
  useEffect(() => {
    if (!isHydrated) return;
    const sessionIds = sessions.map(s => s.id);
    localStorage.setItem(SESSION_RECOVERY_KEY, JSON.stringify(sessionIds));
  }, [sessions, isHydrated]);

  // ============== Session CRUD ==============

  const createNewSession = async () => {
    const newSessionId = generateSessionId();
    const newSession: ChatSession = {
      id: newSessionId,
      title: `Chat ${sessions.length + 1}`,
      messages: [],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      status: 'active',
      isLoaded: true,
      runningTasks: [],
      taskStats: { total: 0, running: 0, completed: 0, failed: 0 }
    };
    
    setSessions(prev => [newSession, ...prev]);
    setActiveSessionId(newSessionId);
    setThinkingSteps([]);
    
    // Create session in backend
    try {
      await sessionAPI.createSession(newSessionId, newSession.title);
    } catch (e) {
      console.error('[ChatV2] Failed to create session in backend:', e);
    }
  };

  const deleteSession = async (sessionId: string) => {
    setSessions(prev => {
      const filtered = prev.filter(s => s.id !== sessionId);
      if (activeSessionId === sessionId) {
        setActiveSessionId(filtered[0]?.id || null);
      }
      return filtered;
    });
    
    // Delete from backend
    try {
      await sessionAPI.deleteSession(sessionId, false);
    } catch (e) {
      console.error('[ChatV2] Failed to delete session from backend:', e);
    }
  };

  const startEditTitle = (session: ChatSession, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingTitle(session.id);
    setEditTitleValue(session.title);
  };

  const saveTitle = async () => {
    if (editingTitle && editTitleValue.trim()) {
      setSessions(prev => prev.map(s => 
        s.id === editingTitle ? { ...s, title: editTitleValue.trim() } : s
      ));
      
      // Update in backend
      try {
        await sessionAPI.updateSession(editingTitle, { title: editTitleValue.trim() });
      } catch (e) {
        console.error('[ChatV2] Failed to update session title:', e);
      }
    }
    setEditingTitle(null);
  };

  const autoGenerateTitle = (msg: string): string => {
    const words = msg.split(' ').slice(0, 5).join(' ');
    return words.length > 25 ? words.slice(0, 25) + '...' : words;
  };

  // ============== Send Message ==============

  const sendMessage = async () => {
    if (!input.trim() || loading) return;

    let currentSessionId = activeSessionId;
    
    // Create session if needed
    if (!currentSessionId) {
      currentSessionId = generateSessionId();
      const newSession: ChatSession = {
        id: currentSessionId,
        title: autoGenerateTitle(input),
        messages: [],
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        status: 'active',
        isLoaded: true,
        runningTasks: [],
        taskStats: { total: 0, running: 0, completed: 0, failed: 0 }
      };
      setSessions(prev => [newSession, ...prev]);
      setActiveSessionId(currentSessionId);
    }

    const userMessage: Message = {
      id: `msg_${Date.now()}`,
      role: 'user',
      content: input,
      timestamp: new Date().toISOString(),
    };

    // Update local state immediately
    setSessions(prev => prev.map(s => {
      if (s.id === currentSessionId) {
        const isFirst = s.messages.length === 0;
        return {
          ...s,
          messages: [...s.messages, userMessage],
          title: isFirst ? autoGenerateTitle(input) : s.title,
          updatedAt: new Date().toISOString(),
        };
      }
      return s;
    }));

    const messageToSend = input;
    setInput('');
    setLoading(true);
    setThinkingSteps([]);
    setCurrentTaskId(null);

    try {
      setPendingInfo('Submitting task...');
      
      const submitResponse = await chatAPI.sendMessage({
        message: messageToSend,
        conversation_id: currentSessionId || undefined,
        async_mode: true // Always use async mode with session system
      });
      
      const { task_id, task_uid, session_id } = submitResponse.data;
      setCurrentTaskId(task_id || task_uid);
      setPendingInfo(`Task ${(task_id || task_uid)?.slice(0, 8)}... - agents working`);
      
      // Start polling for this session
      startPolling(currentSessionId!);
      
    } catch (err: any) {
      const errorMessage: Message = {
        id: `err_${Date.now()}`,
        role: 'assistant',
        content: `Error: ${err.response?.data?.detail || err.message || 'Failed'}`,
        timestamp: new Date().toISOString(),
      };
      
      setSessions(prev => prev.map(s => {
        if (s.id === currentSessionId) {
          return { ...s, messages: [...s.messages, errorMessage] };
        }
        return s;
      }));
      
      setLoading(false);
      setPendingInfo(null);
    }
  };

  // ============== Task Interrupt ==============

  const interruptTask = async () => {
    if (!currentTaskId || isInterrupting) return;
    
    setIsInterrupting(true);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:1130';
      const response = await fetch(`${apiUrl}/agents/interrupt/task/${currentTaskId}`, {
        method: 'POST'
      });
      
      if (response.ok) {
        setPendingInfo('⛔ Interrupt requested...');
      }
    } catch (e) {
      console.error('[ChatV2] Interrupt error:', e);
    } finally {
      setIsInterrupting(false);
    }
  };

  // ============== UI Helpers ==============

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, thinkingSteps, scrollToBottom]);

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const clearCurrentChat = async () => {
    if (activeSessionId) {
      setSessions(prev => prev.map(s => 
        s.id === activeSessionId ? { ...s, messages: [] } : s
      ));
      // Note: This just clears UI - messages are still in database
    }
  };

  // ============== Render ==============

  return (
    <div className="h-full flex flex-col">
      {/* Top Bar with Sessions */}
      <div className="bg-gray-800 border-b border-gray-700 p-3">
        <div className="flex items-center gap-2 overflow-x-auto">
          {/* New Chat Button */}
          <button
            onClick={createNewSession}
            className="flex-shrink-0 flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white text-sm font-medium transition-colors"
          >
            <Plus className="w-4 h-4" />
            New Chat
          </button>

          {/* Session Tabs */}
          {sessions.map(session => (
            <div
              key={session.id}
              onClick={() => setActiveSessionId(session.id)}
              className={`flex-shrink-0 group flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-colors ${
                session.id === activeSessionId
                  ? 'bg-gray-700 text-white'
                  : 'bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-white border border-gray-700'
              }`}
            >
              {editingTitle === session.id ? (
                <div className="flex items-center gap-1" onClick={e => e.stopPropagation()}>
                  <input
                    type="text"
                    value={editTitleValue}
                    onChange={e => setEditTitleValue(e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter') saveTitle(); if (e.key === 'Escape') setEditingTitle(null); }}
                    className="w-24 px-1 py-0.5 bg-gray-600 border border-gray-500 rounded text-white text-xs"
                    autoFocus
                  />
                  <button onClick={saveTitle} className="text-green-400 hover:text-green-300">
                    <Check className="w-3 h-3" />
                  </button>
                  <button onClick={() => setEditingTitle(null)} className="text-red-400 hover:text-red-300">
                    <X className="w-3 h-3" />
                  </button>
                </div>
              ) : (
                <>
                  <MessageSquare className="w-4 h-4" />
                  <span className="text-sm max-w-[100px] truncate">
                    {sessionLoading[session.id] ? 'Loading...' : session.title}
                  </span>
                  <span className="text-xs text-gray-500">({session.messages.length})</span>
                  
                  {/* Running task indicator */}
                  {session.runningTasks.length > 0 && (
                    <span className="flex items-center gap-1 text-xs text-yellow-400">
                      <Loader2 className="w-3 h-3 animate-spin" />
                      {session.runningTasks.length}
                    </span>
                  )}
                  
                  <div className="hidden group-hover:flex items-center gap-1 ml-1">
                    <button onClick={e => startEditTitle(session, e)} className="text-gray-400 hover:text-white">
                      <Edit2 className="w-3 h-3" />
                    </button>
                    <button onClick={e => { e.stopPropagation(); deleteSession(session.id); }} className="text-gray-400 hover:text-red-400">
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                </>
              )}
            </div>
          ))}

          {/* Status indicators */}
          <div className="flex-shrink-0 ml-auto flex items-center gap-2">
            {/* Agent Summary - compact display */}
            <div className="flex items-center gap-1 px-2 py-1 bg-gray-700 rounded text-xs">
              {agentSummary.active.length > 0 ? (
                <>
                  <Zap className="w-3 h-3 text-yellow-400 animate-pulse" />
                  <span className="text-yellow-400">{agentSummary.active.join(', ')}</span>
                </>
              ) : (
                <>
                  <span className="text-gray-400">Idle {agentSummary.idle}/{agentSummary.total}</span>
                </>
              )}
            </div>
            
            {/* Thinking toggle */}
            <button
              onClick={() => setShowThinking(!showThinking)}
              className={`flex items-center gap-1 px-2 py-1 rounded text-xs ${
                showThinking ? 'bg-purple-900/50 text-purple-400' : 'bg-gray-700 text-gray-400'
              }`}
            >
              <Brain className="w-3 h-3" />
              Think
            </button>
            
            {/* Task panel toggle */}
            <button
              onClick={() => setShowTaskPanel(!showTaskPanel)}
              className={`flex items-center gap-1 px-2 py-1 rounded text-xs ${
                showTaskPanel ? 'bg-blue-900/50 text-blue-400' : 'bg-gray-700 text-gray-400'
              }`}
            >
              <List className="w-3 h-3" />
              Tasks
            </button>
            
            {/* WebSocket Status */}
            <div className={`flex items-center gap-1 px-2 py-1 rounded text-xs ${wsConnected ? 'bg-green-900/50 text-green-400' : 'bg-red-900/50 text-red-400'}`}>
              {wsConnected ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
              {wsConnected ? 'Live' : 'Offline'}
            </div>
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex min-h-0 overflow-hidden">
        {/* Messages Panel */}
        <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.length === 0 && !loading ? (
              <div className="flex flex-col items-center justify-center h-full text-gray-500">
                <MessageSquare className="w-16 h-16 mb-4 opacity-50" />
                <p className="text-lg">Start a conversation</p>
                <p className="text-sm mt-1">Send a message to chat with the AI</p>
                <div className="mt-6 grid grid-cols-2 gap-3">
                  {['Hello!', 'What can you do?', 'Help me with...', 'Tell me about RAG'].map(s => (
                    <button
                      key={s}
                      onClick={() => setInput(s)}
                      className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-gray-300 text-sm"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <>
                {messages.map(msg => (
                  <div key={msg.id}>
                    <div className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                      <div className={`max-w-[75%] rounded-xl px-4 py-3 ${
                        msg.role === 'user' ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-100'
                      }`}>
                        <p className="whitespace-pre-wrap">{msg.content}</p>
                        
                        {msg.sources && msg.sources.length > 0 && (
                          <div className="mt-2 pt-2 border-t border-gray-600">
                            <div className="flex items-center gap-1 text-xs text-gray-400 mb-1">
                              <Database className="w-3 h-3" />
                              <span>Sources:</span>
                            </div>
                            <div className="flex flex-wrap gap-1">
                              {msg.sources.map((src, i) => (
                                <span key={i} className="px-2 py-0.5 bg-gray-600 rounded text-xs">
                                  {src.database}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                        
                        <div className="flex items-center justify-between mt-2 text-xs opacity-70">
                          <span>{new Date(msg.timestamp).toLocaleTimeString()}</span>
                          {msg.agents_involved && (
                            <span className="ml-2">via {msg.agents_involved.join(', ')}</span>
                          )}
                          {msg.task_uid && (
                            <span className="ml-2 text-gray-500">#{msg.task_uid.slice(-8)}</span>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
                
                {/* Active Thinking Indicator */}
                {loading && (
                  <div className="space-y-3">
                    <div className="flex justify-start">
                      <div className="bg-gray-700 rounded-xl px-4 py-3 flex items-center gap-3">
                        <Loader2 className="w-5 h-5 text-blue-400 animate-spin" />
                        <div className="flex flex-col flex-1">
                          <span className="text-white text-sm">
                            {agentSummary.active.length > 0 
                              ? `Active: ${agentSummary.active.join(' → ')}`
                              : 'Processing...'}
                          </span>
                          <span className="text-gray-400 text-xs">{pendingInfo || 'Please wait'}</span>
                        </div>
                        {currentTaskId && (
                          <button
                            onClick={interruptTask}
                            disabled={isInterrupting}
                            className="ml-3 flex items-center gap-1 px-3 py-1.5 bg-red-600 hover:bg-red-700 disabled:bg-gray-600 rounded-lg text-white text-xs transition-colors"
                          >
                            <StopCircle className="w-3 h-3" />
                            {isInterrupting ? 'Stopping...' : 'Stop'}
                          </button>
                        )}
                      </div>
                    </div>
                    
                    {/* Live thinking steps - only show if toggle is on */}
                    {showThinking && thinkingSteps.length > 0 && (
                      <div className="ml-4 p-3 bg-purple-900/20 border border-purple-800/50 rounded-lg max-h-48 overflow-y-auto">
                        <div className="space-y-1">
                          {thinkingSteps.slice(-10).map((step, i) => {
                            const content = formatThinkingContent(step.content);
                            if (!content) return null;
                            return (
                              <div key={i} className="text-xs text-gray-400 flex items-start gap-2">
                                <span>{getStepIcon(step.step_type)}</span>
                                <span className="text-purple-400 flex-shrink-0">{step.agent_name.replace('_agent', '')}</span>
                                <span className="flex-1 truncate">{content}</span>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Area */}
          <div className="border-t border-gray-700 bg-gray-800 p-4">
            {pendingInfo && !loading && (
              <div className="mb-3 p-3 bg-blue-900/30 border border-blue-700/50 rounded-lg text-blue-400 text-sm flex items-start gap-2">
                <RefreshCw className="w-4 h-4 mt-0.5 flex-shrink-0" />
                <span>{pendingInfo}</span>
              </div>
            )}
            
            <div className="flex gap-3">
              <textarea
                ref={inputRef}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyPress={handleKeyPress}
                rows={1}
                disabled={loading}
                className="flex-1 px-4 py-3 bg-gray-700 border border-gray-600 rounded-xl text-white placeholder-gray-400 focus:outline-none focus:border-blue-500 resize-none disabled:opacity-50"
                placeholder={loading ? "Waiting for response..." : "Type your message... (Enter to send)"}
              />
              <button
                onClick={sendMessage}
                disabled={!input.trim() || loading}
                className="px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed rounded-xl text-white transition-colors"
              >
                {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
              </button>
            </div>
            
            {activeSession && messages.length > 0 && (
              <div className="mt-2 flex justify-between items-center">
                <div className="flex items-center gap-2 text-xs text-gray-500">
                  <Users className="w-3 h-3" />
                  <span>Tasks: {activeSession.taskStats.completed} completed, {activeSession.taskStats.running} running</span>
                </div>
                <button
                  onClick={clearCurrentChat}
                  className="text-xs text-gray-500 hover:text-red-400 flex items-center gap-1"
                >
                  <Trash2 className="w-3 h-3" />
                  Clear UI
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Task Panel (collapsible) */}
        {showTaskPanel && activeSession && (
          <div className="w-72 border-l border-gray-700 bg-gray-850 flex flex-col">
            <div className="p-3 border-b border-gray-700">
              <h3 className="text-sm font-medium text-white flex items-center gap-2">
                <Activity className="w-4 h-4" />
                Task Status
              </h3>
            </div>
            
            <div className="flex-1 overflow-y-auto p-3 space-y-3">
              {/* Running Tasks */}
              {runningTasks.length > 0 && (
                <div>
                  <h4 className="text-xs text-yellow-400 mb-2 flex items-center gap-1">
                    <Loader2 className="w-3 h-3 animate-spin" />
                    Running ({runningTasks.length})
                  </h4>
                  <div className="space-y-2">
                    {runningTasks.map(task => (
                      <div key={task.task_uid} className="p-2 bg-yellow-900/20 border border-yellow-800/50 rounded text-xs">
                        <div className="flex items-center gap-2">
                          {getAgentStateIcon(task.status)}
                          <span className="text-white font-medium">{task.agent_name.replace('_agent', '')}</span>
                        </div>
                        <div className="text-gray-400 mt-1 truncate">{task.task_type}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              
              {/* Active Agents - compact list */}
              {hasWorkingAgents && (
                <div>
                  <h4 className="text-xs text-blue-400 mb-2 flex items-center gap-1">
                    <Activity className="w-3 h-3" />
                    Active ({agentSummary.active.length})
                  </h4>
                  <div className="flex flex-wrap gap-1">
                    {agentSummary.active.map((name, i) => (
                      <span key={i} className="px-2 py-1 bg-blue-900/30 text-blue-300 rounded text-xs">
                        {name}
                      </span>
                    ))}
                  </div>
                  {lastStatusUpdate && (
                    <div className="text-gray-500 text-xs mt-2">Updated: {lastStatusUpdate}</div>
                  )}
                </div>
              )}
              
              {/* Session Stats - compact */}
              <div>
                <h4 className="text-xs text-gray-400 mb-2">Stats</h4>
                <div className="flex gap-2 text-xs">
                  <span className="text-green-400">✓{activeSession.taskStats.completed}</span>
                  <span className="text-yellow-400">⟳{activeSession.taskStats.running}</span>
                  {activeSession.taskStats.failed > 0 && (
                    <span className="text-red-400">✗{activeSession.taskStats.failed}</span>
                  )}
                </div>
              </div>
              
              {/* No activity message */}
              {runningTasks.length === 0 && !hasWorkingAgents && (
                <div className="text-center text-gray-500 text-xs py-4">
                  Ready
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
