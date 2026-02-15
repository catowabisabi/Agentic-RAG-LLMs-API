'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { MessageSquare, Send, Trash2, Plus, Edit2, Check, X, Database, Loader2, Brain, Wifi, WifiOff, StopCircle, Zap, Activity, Clock, AlertTriangle, CheckCircle2, Search, ChevronDown, ChevronRight } from 'lucide-react';
import { chatAPI, createWebSocket } from '../lib/api';
import { useWebSocket } from '../contexts/WebSocketContext';
import MarkdownRenderer from './MarkdownRenderer';

interface Source {
  database: string;
  title: string;
  relevance: number;
}

interface ThinkingStep {
  type: string;
  agent: string;
  content: any;
  timestamp: string;
  step?: number;
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
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  agents_involved?: string[];
  sources?: Source[];
  thinking?: ThinkingStep[];
}

interface ChatSession {
  id: string;
  title: string;
  messages: Message[];
  createdAt: string;
  updatedAt: string;
}

const STORAGE_KEY = 'agentic-rag-chat-sessions';
const PENDING_TASK_KEY = 'agentic-rag-pending-task';
const POLL_INTERVAL = 2000; // Poll every 2 seconds for async tasks

interface PendingTask {
  sessionId: string;
  taskId: string;
  message: string;
  startedAt: string;
}

// Agent state icons mapping
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
    default:
      return <Clock className="w-3 h-3 text-gray-500" />;
  }
};

export default function ChatPage() {
  const globalWs = useWebSocket();
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [editingTitle, setEditingTitle] = useState<string | null>(null);
  const [editTitleValue, setEditTitleValue] = useState('');
  const [isHydrated, setIsHydrated] = useState(false);
  const [thinkingSteps, setThinkingSteps] = useState<ThinkingStep[]>([]);
  const [wsConnected, setWsConnected] = useState(false);
  const [pendingInfo, setPendingInfo] = useState<string | null>(null);
  const [useAsyncMode, setUseAsyncMode] = useState(true); // Enable async mode by default
  const [useRag, setUseRag] = useState(true); // Enable RAG by default
  const [useStreaming, setUseStreaming] = useState(true); // Enable streaming for faster UX
  const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);
  const [agentStatuses, setAgentStatuses] = useState<Record<string, AgentStatus>>({});
  // Track which messages have expanded thinking steps (collapsed by default)
  const [expandedThinking, setExpandedThinking] = useState<Set<string>>(new Set());
  const [isInterrupting, setIsInterrupting] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const pendingMessageRef = useRef<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const activeSession = sessions.find(s => s.id === activeSessionId);
  const messages = activeSession?.messages || [];
  
  // Merge agent statuses from local WS and global context
  const mergedAgentStatuses = { ...globalWs.agentStatuses, ...Object.fromEntries(
    Object.entries(agentStatuses).map(([k, v]) => [k, v])
  ) };
  
  // Check if any agent is currently working
  const hasWorkingAgents = Object.values(agentStatuses).some(
    a => ['working', 'thinking', 'calling_llm', 'querying_rag', 'processing'].includes(a.state?.toLowerCase())
  );
  
  // Use global WS status as fallback
  const effectiveWsConnected = wsConnected || globalWs.status === 'connected';

  // WebSocket connection for real-time thinking updates
  useEffect(() => {
    const connectWs = () => {
      try {
        const ws = createWebSocket('/ws');
        wsRef.current = ws;
        
        ws.onopen = () => {
          console.log('[Chat] WebSocket connected');
          setWsConnected(true);
        };
        
        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            
            // Handle heartbeat with agent statuses
            if (data.type === 'heartbeat' && data.agent_statuses) {
              setAgentStatuses(data.agent_statuses);
              return;
            }
            
            // Handle agent status changes
            if (data.type === 'agent_status_changed') {
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
            }
            
            // Capture thinking/plan steps (including planning_result from backend)
            if (data.type === 'thinking' || data.type === 'plan_step' || 
                data.type === 'agent_started' || data.type === 'task_assigned' ||
                data.type === 'rag_query' || data.type === 'rag_result' ||
                data.type === 'llm_call_start' || data.type === 'task_completed' ||
                data.type === 'planning_result' || data.type === 'task_rerouted') {
              const step: ThinkingStep = {
                type: data.type,
                agent: data.agent_name || data.agent || data.source || 'system',
                content: data.data || data.content || data,
                timestamp: data.timestamp || new Date().toISOString(),
                step: data.step
              };
              setThinkingSteps(prev => {
                // Check for duplicates
                const isDupe = prev.some(s => 
                  s.timestamp === step.timestamp && 
                  s.type === step.type && 
                  s.agent === step.agent
                );
                if (isDupe) return prev;
                // Keep last 50 steps for more visibility
                const updated = [...prev, step];
                return updated.slice(-50);
              });
            }
          } catch (e) {
            console.error('[Chat] Parse error:', e);
          }
        };
        
        ws.onclose = () => {
          console.log('[Chat] WebSocket disconnected');
          setWsConnected(false);
          setTimeout(connectWs, 3000);
        };
        
        ws.onerror = (err) => {
          console.error('[Chat] WebSocket error:', err);
        };
      } catch (e) {
        console.error('[Chat] Failed to connect:', e);
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

  // Warn user if leaving page with active request
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (loading) {
        e.preventDefault();
        e.returnValue = 'You have a request in progress. Leaving may interrupt it.';
        return e.returnValue;
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [loading]);

  // Load from localStorage
  useEffect(() => {
    setIsHydrated(true);
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const savedSessions: ChatSession[] = JSON.parse(saved);
        if (Array.isArray(savedSessions) && savedSessions.length > 0) {
          setSessions(savedSessions);
          setActiveSessionId(savedSessions[0].id);
          
          // Check for pending task from previous session
          const pendingTaskStr = localStorage.getItem(PENDING_TASK_KEY);
          if (pendingTaskStr) {
            try {
              const pendingTask: PendingTask = JSON.parse(pendingTaskStr);
              const startedAt = new Date(pendingTask.startedAt);
              const elapsed = (Date.now() - startedAt.getTime()) / 1000;
              
              if (elapsed < 300 && pendingTask.taskId) {
                // Task has a taskId - it's an async task, check its status
                setPendingInfo(`⏳ Checking previous task status...`);
                
                // Check task status in background
                (async () => {
                  try {
                    const statusResponse = await chatAPI.getTaskStatus(pendingTask.taskId);
                    const status = statusResponse.data;
                    
                    if (status.status === 'completed') {
                      // Get and apply result
                      const resultResponse = await chatAPI.getTaskResult(pendingTask.taskId);
                      const result = resultResponse.data.result;
                      
                      const assistantMessage: Message = {
                        id: pendingTask.taskId,
                        role: 'assistant',
                        content: result.response || 'Task completed',
                        timestamp: new Date().toISOString(),
                        agents_involved: result.agents_involved,
                        sources: result.sources || [],
                      };
                      
                      setSessions(prev => prev.map(s => {
                        if (s.id === pendingTask.sessionId) {
                          // Check if message already added
                          const exists = s.messages.some(m => m.id === pendingTask.taskId);
                          if (exists) return s;
                          return { ...s, messages: [...s.messages, assistantMessage], updatedAt: new Date().toISOString() };
                        }
                        return s;
                      }));
                      
                      setPendingInfo(`✅ Previous task completed! Response added.`);
                      localStorage.removeItem(PENDING_TASK_KEY);
                      setTimeout(() => setPendingInfo(null), 3000);
                      
                    } else if (status.status === 'running' || status.status === 'pending') {
                      setPendingInfo(`⏳ Previous task still running: ${status.current_step || 'Processing...'} (${Math.round(status.progress)}%)`);
                      // Keep polling
                      // TODO: Could resume polling here
                      setTimeout(() => {
                        localStorage.removeItem(PENDING_TASK_KEY);
                        setPendingInfo(null);
                      }, 10000);
                      
                    } else if (status.status === 'failed') {
                      setPendingInfo(`❌ Previous task failed: ${status.error}`);
                      localStorage.removeItem(PENDING_TASK_KEY);
                      setTimeout(() => setPendingInfo(null), 5000);
                      
                    } else {
                      localStorage.removeItem(PENDING_TASK_KEY);
                      setPendingInfo(null);
                    }
                  } catch (e) {
                    console.warn('[Chat] Could not check previous task:', e);
                    localStorage.removeItem(PENDING_TASK_KEY);
                    setPendingInfo(null);
                  }
                })();
                
              } else if (elapsed < 180) {
                // Old-style sync task - just show warning
                setPendingInfo(`⚠️ Previous task "${pendingTask.message.slice(0, 30)}..." may have been interrupted. Consider resending.`);
                setTimeout(() => {
                  localStorage.removeItem(PENDING_TASK_KEY);
                  setPendingInfo(null);
                }, 10000);
              } else {
                // Task is too old, clear it
                localStorage.removeItem(PENDING_TASK_KEY);
              }
            } catch (e) {
              localStorage.removeItem(PENDING_TASK_KEY);
            }
          }
          return;
        }
      }
    } catch (e) {
      console.error('Failed to load sessions:', e);
    }
    
    const initialSession: ChatSession = {
      id: `session_${Date.now()}`,
      title: 'New Chat',
      messages: [],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
    setSessions([initialSession]);
    setActiveSessionId(initialSession.id);
  }, []);

  // Save to localStorage
  useEffect(() => {
    if (!isHydrated) return;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
  }, [sessions, isHydrated]);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, thinkingSteps, scrollToBottom]);

  const createNewSession = () => {
    const newSession: ChatSession = {
      id: `session_${Date.now()}`,
      title: `Chat ${sessions.length + 1}`,
      messages: [],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
    setSessions(prev => [newSession, ...prev]);
    setActiveSessionId(newSession.id);
  };

  const deleteSession = (sessionId: string) => {
    setSessions(prev => {
      const filtered = prev.filter(s => s.id !== sessionId);
      if (activeSessionId === sessionId) {
        setActiveSessionId(filtered[0]?.id || null);
      }
      return filtered;
    });
  };

  const startEditTitle = (session: ChatSession, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingTitle(session.id);
    setEditTitleValue(session.title);
  };

  const saveTitle = () => {
    if (editingTitle && editTitleValue.trim()) {
      setSessions(prev => prev.map(s => 
        s.id === editingTitle ? { ...s, title: editTitleValue.trim() } : s
      ));
    }
    setEditingTitle(null);
  };

  const autoGenerateTitle = (msg: string): string => {
    const words = msg.split(' ').slice(0, 5).join(' ');
    return words.length > 25 ? words.slice(0, 25) + '...' : words;
  };

  // Interrupt current task
  const interruptTask = async () => {
    if (!currentTaskId || isInterrupting) return;
    
    setIsInterrupting(true);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:1130';
      const response = await fetch(`${apiUrl}/agents/interrupt/task/${currentTaskId}`, {
        method: 'POST'
      });
      
      if (response.ok) {
        setPendingInfo('⛔ Interrupt requested - waiting for agents to stop...');
        // The task will complete with interrupted status
      } else {
        console.error('[Chat] Interrupt failed');
      }
    } catch (e) {
      console.error('[Chat] Interrupt error:', e);
    } finally {
      setIsInterrupting(false);
    }
  };

  const sendMessage = async () => {
    if (!input.trim() || loading) return;

    let currentSessionId = activeSessionId;
    if (!currentSessionId) {
      const newSession: ChatSession = {
        id: `session_${Date.now()}`,
        title: autoGenerateTitle(input),
        messages: [],
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      };
      setSessions(prev => [newSession, ...prev]);
      currentSessionId = newSession.id;
      setActiveSessionId(newSession.id);
    }

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date().toISOString(),
    };

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
    pendingMessageRef.current = currentSessionId;

    try {
      if (useAsyncMode) {
        // ============================================
        // ASYNC MODE: Submit task and poll for result
        // Task runs in background even if user leaves page
        // ============================================
        setPendingInfo(`Submitting task... (async mode - runs in background)${useRag ? '' : ' [RAG disabled]'}`);
        
        const submitResponse = await chatAPI.sendMessage({
          message: messageToSend,
          conversation_id: currentSessionId || undefined,
          async_mode: true,
          use_rag: useRag
        });
        
        const { task_id } = submitResponse.data;
        
        // Track current task for interrupt functionality
        setCurrentTaskId(task_id);
        
        // Save pending task to localStorage for recovery
        const pendingTask: PendingTask = {
          sessionId: currentSessionId!,
          taskId: task_id,
          message: messageToSend,
          startedAt: new Date().toISOString()
        };
        localStorage.setItem(PENDING_TASK_KEY, JSON.stringify(pendingTask));
        
        setPendingInfo(`Task ${task_id.slice(0, 8)}... - agents are working`);
        
        // Poll for result
        let attempts = 0;
        const maxAttempts = 120; // 4 minutes max (120 * 2s)
        
        while (attempts < maxAttempts) {
          await new Promise(resolve => setTimeout(resolve, POLL_INTERVAL));
          attempts++;
          
          try {
            const statusResponse = await chatAPI.getTaskStatus(task_id);
            const status = statusResponse.data;
            
            // Update progress info
            setPendingInfo(`${status.current_step || 'Processing...'} (${Math.round(status.progress)}%)`);
            
            if (status.status === 'completed' || status.status === 'interrupted') {
              // Get full result
              const resultResponse = await chatAPI.getTaskResult(task_id);
              const result = resultResponse.data.result;
              
              const wasInterrupted = status.status === 'interrupted' || result.status === 'interrupted';
              
              const assistantMessage: Message = {
                id: task_id,
                role: 'assistant',
                content: wasInterrupted ? `⛔ Task interrupted. Partial result:\n\n${result.response || 'No response yet'}` : (result.response || 'No response'),
                timestamp: new Date().toISOString(),
                agents_involved: result.agents_involved || status.agents_involved,
                sources: result.sources || [],
                thinking: [...thinkingSteps],
              };
              
              setSessions(prev => prev.map(s => {
                if (s.id === currentSessionId) {
                  return { ...s, messages: [...s.messages, assistantMessage], updatedAt: new Date().toISOString() };
                }
                return s;
              }));
              
              localStorage.removeItem(PENDING_TASK_KEY);
              break;
            }
            
            if (status.status === 'failed') {
              throw new Error(status.error || 'Task failed');
            }
            
            if (status.status === 'cancelled') {
              throw new Error('Task was cancelled');
            }
            
          } catch (pollError: any) {
            // If polling fails, task might still be running - just continue
            console.warn('[Chat] Poll error:', pollError.message);
          }
        }
        
        if (attempts >= maxAttempts) {
          throw new Error('Task timed out after 4 minutes');
        }
        
      } else {
        // ============================================
        // SYNC MODE: Wait for response (original behavior)
        // Now with STREAMING support for faster UX!
        // ============================================
        
        if (useStreaming && !useAsyncMode) {
          // === STREAMING MODE ===
          setPendingInfo(`Processing with streaming... (faster response)`);
          
          // Save pending task
          const pendingTask: PendingTask = {
            sessionId: currentSessionId!,
            taskId: '',
            message: messageToSend,
            startedAt: new Date().toISOString()
          };
          localStorage.setItem(PENDING_TASK_KEY, JSON.stringify(pendingTask));
          
          // Create a placeholder message that will be updated
          const placeholderId = Date.now().toString() + '-streaming-a';
          const placeholderMessage: Message = {
            id: placeholderId,
            role: 'assistant',
            content: '',
            timestamp: new Date().toISOString(),
            thinking: [...thinkingSteps],
          };
          
          setSessions(prev => prev.map(s => {
            if (s.id === currentSessionId) {
              return { ...s, messages: [...s.messages, placeholderMessage], updatedAt: new Date().toISOString() };
            }
            return s;
          }));
          
          try {
            await chatAPI.sendMessageStream(
              {
                message: messageToSend,
                conversation_id: currentSessionId || undefined,
                use_rag: useRag
              },
              // onToken callback - updates message incrementally
              (token: string) => {
                setSessions(prev => prev.map(s => {
                  if (s.id === currentSessionId) {
                    return {
                      ...s,
                      messages: s.messages.map(m => 
                        m.id === placeholderId 
                          ? { ...m, content: m.content + token }
                          : m
                      )
                    };
                  }
                  return s;
                }));
              },
              // onMetadata callback
              (metadata) => {
                setSessions(prev => prev.map(s => {
                  if (s.id === currentSessionId) {
                    return {
                      ...s,
                      messages: s.messages.map(m => 
                        m.id === placeholderId 
                          ? { ...m, agents_involved: metadata.agents, sources: metadata.sources }
                          : m
                      )
                    };
                  }
                  return s;
                }));
              },
              // onError callback
              (error) => {
                console.error('[Streaming] Error:', error);
                setPendingInfo(`Error: ${error}`);
              }
            );
            
            // Clear pending task on success
            localStorage.removeItem(PENDING_TASK_KEY);
          } catch (err: any) {
            console.error('[Streaming] Failed, falling back to regular mode:', err);
            // Fallback: remove placeholder and use regular API
            setSessions(prev => prev.map(s => {
              if (s.id === currentSessionId) {
                return {
                  ...s,
                  messages: s.messages.filter(m => m.id !== placeholderId)
                };
              }
              return s;
            }));
            
            // Retry with regular mode
            const response = await chatAPI.sendMessage({
              message: messageToSend,
              conversation_id: currentSessionId || undefined,
              async_mode: false,
              use_rag: useRag
            });
            
            const data = response.data;
            const assistantMessage: Message = {
              id: data.message_id || Date.now().toString() + '-a',
              role: 'assistant',
              content: data.response || 'No response',
              timestamp: data.timestamp || new Date().toISOString(),
              agents_involved: data.agents_involved,
              sources: data.sources || [],
              thinking: [...thinkingSteps],
            };
            
            setSessions(prev => prev.map(s => {
              if (s.id === currentSessionId) {
                return { ...s, messages: [...s.messages, assistantMessage], updatedAt: new Date().toISOString() };
              }
              return s;
            }));
          }
        } else {
          // === REGULAR MODE (no streaming) ===
          setPendingInfo(`Processing "${messageToSend.slice(0, 30)}..." - please wait (may take 20-60 seconds)`);
          
          // Save pending task to localStorage so we can recover if page is left
          const pendingTask: PendingTask = {
            sessionId: currentSessionId!,
            taskId: '',
            message: messageToSend,
            startedAt: new Date().toISOString()
          };
          localStorage.setItem(PENDING_TASK_KEY, JSON.stringify(pendingTask));
          
          // Create abort controller for this request
          abortControllerRef.current = new AbortController();
          
          const response = await chatAPI.sendMessage({
            message: messageToSend,
            conversation_id: currentSessionId || undefined,
            async_mode: false,
            use_rag: useRag
          }, abortControllerRef.current.signal);

          const data = response.data;
          const assistantMessage: Message = {
            id: data.message_id || Date.now().toString() + '-a',
            role: 'assistant',
            content: data.response || 'No response',
            timestamp: data.timestamp || new Date().toISOString(),
            agents_involved: data.agents_involved,
            sources: data.sources || [],
            thinking: [...thinkingSteps],
          };

          setSessions(prev => prev.map(s => {
            if (s.id === currentSessionId) {
              return { ...s, messages: [...s.messages, assistantMessage], updatedAt: new Date().toISOString() };
            }
            return s;
          }));

          // Clear pending task on success
          localStorage.removeItem(PENDING_TASK_KEY);
        }
      }
    } catch (err: any) {
      // Check if request was cancelled (user left page)
      if (err.name === 'CanceledError' || err.code === 'ERR_CANCELED') {
        console.log('[Chat] Request was cancelled - task may still be processing on server');
        // Don't remove pending task - it might still complete
        setPendingInfo('Request cancelled. If you left and came back, the task may still complete.');
      } else {
        const errorMessage: Message = {
          id: Date.now().toString() + '-err',
          role: 'assistant',
          content: `Error: ${err.response?.data?.detail || err.message || 'Failed'}`,
          timestamp: new Date().toISOString(),
          thinking: [...thinkingSteps],
        };
        setSessions(prev => prev.map(s => {
          if (s.id === currentSessionId) {
            return { ...s, messages: [...s.messages, errorMessage] };
          }
          return s;
        }));
        // Clear pending task on error
        localStorage.removeItem(PENDING_TASK_KEY);
      }
    }

    setLoading(false);
    setPendingInfo(null);
    setCurrentTaskId(null);
    pendingMessageRef.current = null;
    abortControllerRef.current = null;
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const clearCurrentChat = () => {
    if (activeSessionId) {
      setSessions(prev => prev.map(s => 
        s.id === activeSessionId ? { ...s, messages: [] } : s
      ));
    }
  };

  const formatThinkingContent = (content: any): string => {
    if (typeof content === 'string') return content;
    // Defensive check: prevent agent info objects from being stringified incorrectly
    if (content && typeof content === 'object' && content.name && content.role && content.icon) {
      return `Agent: ${content.name} (${content.role})`;
    }
    if (content.thought) return content.thought;
    if (content.status) return content.status;
    if (content.task) return `Task: ${content.task}`;
    if (content.query) return `Query: ${content.query}`;
    if (content.sources_count !== undefined) return `Found ${content.sources_count} sources`;
    if (content.response_length) return `Generated ${content.response_length} char response`;
    if (content.message) return content.message;
    return JSON.stringify(content);
  };
  
  const getStepIcon = (type: string) => {
    switch (type) {
      case 'task_assigned': return '📋';
      case 'thinking': return '💭';
      case 'plan_step': return '📝';
      case 'planning_result': return '📊';
      case 'rag_query': return '🔍';
      case 'rag_result': return '📚';
      case 'llm_call_start': return '🤖';
      case 'task_completed': return '✅';
      case 'task_rerouted': return '🔀';
      case 'agent_started': return '🚀';
      default: return '▶️';
    }
  };

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
                  <span className="text-sm max-w-[100px] truncate">{session.title}</span>
                  <span className="text-xs text-gray-500">({session.messages.length})</span>
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

          {/* WebSocket Status */}
          <div className="flex-shrink-0 ml-auto">
            <div className={`flex items-center gap-1 px-2 py-1 rounded text-xs ${effectiveWsConnected ? 'bg-green-900/50 text-green-400' : 'bg-red-900/50 text-red-400'}`}>
              {effectiveWsConnected ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
              {effectiveWsConnected ? 'Live' : 'Offline'}
            </div>
          </div>
        </div>
      </div>

      {/* Chat Area */}
      <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 && !loading ? (
            <div className="flex flex-col items-center justify-center h-full text-gray-500">
              <MessageSquare className="w-16 h-16 mb-4 opacity-50" />
              <p className="text-lg">Start a conversation</p>
              <p className="text-sm mt-1">Send a message to chat with the AI</p>
              <div className="mt-6 grid grid-cols-2 gap-3">
                {['Hello!', 'What can you do?', 'Help me with...', 'Tell me about SolidWorks'].map(s => (
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
                      {msg.role === 'user' ? (
                        <p className="whitespace-pre-wrap">{msg.content}</p>
                      ) : (
                        <MarkdownRenderer content={msg.content} />
                      )}
                      
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
                      </div>
                    </div>
                  </div>

                  {/* Show thinking steps for this message (COLLAPSIBLE) */}
                  {msg.thinking && msg.thinking.length > 0 && (
                    <div className="mt-2 ml-4 p-3 bg-purple-900/20 border border-purple-800/50 rounded-lg">
                      <button 
                        onClick={() => {
                          setExpandedThinking(prev => {
                            const next = new Set(prev);
                            if (next.has(msg.id)) {
                              next.delete(msg.id);
                            } else {
                              next.add(msg.id);
                            }
                            return next;
                          });
                        }}
                        className="flex items-center gap-2 text-xs text-purple-400 hover:text-purple-300 w-full"
                      >
                        {expandedThinking.has(msg.id) ? (
                          <ChevronDown className="w-3 h-3" />
                        ) : (
                          <ChevronRight className="w-3 h-3" />
                        )}
                        <Brain className="w-3 h-3" />
                        <span>Chain of Thought ({msg.thinking.length} steps)</span>
                        <span className="ml-auto text-gray-500 text-xs">
                          {expandedThinking.has(msg.id) ? 'Click to collapse' : 'Click to expand'}
                        </span>
                      </button>
                      {expandedThinking.has(msg.id) && (
                        <div className="space-y-1 mt-2 pt-2 border-t border-purple-800/30">
                          {msg.thinking.map((step, i) => (
                            <div key={i} className="text-xs text-gray-400 flex items-start gap-2">
                              <span>{getStepIcon(step.type)}</span>
                              <span className="text-purple-400 flex-shrink-0">[{String(step.agent || 'system')}]</span>
                              <span className="flex-1">{formatThinkingContent(step.content)}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
              
              {/* Active Thinking Indicator */}
              {loading && (
                <div className="space-y-3">
                  {/* Main thinking card with interrupt button */}
                  <div className="flex justify-start">
                    <div className="bg-gray-700 rounded-xl px-4 py-3 flex items-center gap-3">
                      <Loader2 className="w-5 h-5 text-blue-400 animate-spin" />
                      <div className="flex flex-col flex-1">
                        <span className="text-white text-sm">Agents are working...</span>
                        <span className="text-gray-400 text-xs">{pendingInfo || 'Processing your request'}</span>
                      </div>
                      {currentTaskId && (
                        <button
                          onClick={interruptTask}
                          disabled={isInterrupting}
                          className="ml-3 flex items-center gap-1 px-3 py-1.5 bg-red-600 hover:bg-red-700 disabled:bg-gray-600 rounded-lg text-white text-xs transition-colors"
                          title="Stop the current task"
                        >
                          <StopCircle className="w-3 h-3" />
                          {isInterrupting ? 'Stopping...' : 'Stop'}
                        </button>
                      )}
                    </div>
                  </div>
                  
                  {/* Real-time Agent Status Panel */}
                  {hasWorkingAgents && (
                    <div className="ml-4 p-3 bg-blue-900/20 border border-blue-800/50 rounded-lg">
                      <div className="flex items-center gap-2 text-xs text-blue-400 mb-2">
                        <Activity className="w-3 h-3" />
                        <span>Active Agents</span>
                      </div>
                      <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                        {Object.values(agentStatuses)
                          .filter(a => ['working', 'thinking', 'calling_llm', 'querying_rag', 'processing'].includes(a.state?.toLowerCase()))
                          .map((agent, i) => (
                            <div key={i} className="flex items-center gap-2 p-2 bg-gray-800/50 rounded">
                              {getAgentStateIcon(agent.state)}
                              <div className="flex flex-col min-w-0">
                                <span className="text-xs text-white truncate">{String(agent.name || '')}</span>
                                <span className="text-xs text-gray-400 truncate">{String(agent.message || agent.state || '')}</span>
                              </div>
                            </div>
                          ))}
                      </div>
                    </div>
                  )}
                  
                  {/* Live thinking steps */}
                  {thinkingSteps.length > 0 && (
                    <div className="ml-4 p-3 bg-purple-900/20 border border-purple-800/50 rounded-lg">
                      <div className="flex items-center justify-between text-xs text-purple-400 mb-2">
                        <div className="flex items-center gap-2">
                          <Brain className="w-3 h-3 animate-pulse" />
                          <span>Live Chain of Thought</span>
                        </div>
                        <span className="text-gray-500">{thinkingSteps.length} steps</span>
                      </div>
                      <div className="space-y-1 max-h-48 overflow-y-auto">
                        {thinkingSteps.map((step, i) => (
                          <div key={i} className="text-xs text-gray-400 flex items-start gap-2">
                            <span>{getStepIcon(step.type)}</span>
                            <span className="text-purple-400 flex-shrink-0">[{String(step.agent || 'system')}]</span>
                            <span className="flex-1">{formatThinkingContent(step.content)}</span>
                          </div>
                        ))}
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
          {/* Pending Task Warning */}
          {pendingInfo && (
            <div className="mb-3 p-3 bg-yellow-900/30 border border-yellow-700/50 rounded-lg text-yellow-400 text-sm flex items-start gap-2">
              <Loader2 className="w-4 h-4 animate-spin mt-0.5 flex-shrink-0" />
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
              {/* Async mode toggle */}
              <button
                onClick={() => setUseAsyncMode(!useAsyncMode)}
                className={`text-xs flex items-center gap-1.5 px-2 py-1 rounded ${
                  useAsyncMode 
                    ? 'bg-green-900/50 text-green-400 hover:bg-green-900/70' 
                    : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
                }`}
                title={useAsyncMode 
                  ? "Async Mode: Tasks run in background - you can leave and come back" 
                  : "Sync Mode: Wait for response - leaving will cancel the request"
                }
              >
                <span className={`w-2 h-2 rounded-full ${useAsyncMode ? 'bg-green-400' : 'bg-gray-500'}`} />
                {useAsyncMode ? '🔄 Background Mode' : '⏳ Wait Mode'}
              </button>
              
              {/* Streaming toggle (NEW!) */}
              <button
                onClick={() => setUseStreaming(!useStreaming)}
                className={`text-xs flex items-center gap-1.5 px-2 py-1 rounded ${
                  useStreaming 
                    ? 'bg-purple-900/50 text-purple-400 hover:bg-purple-900/70' 
                    : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
                }`}
                title={useStreaming 
                  ? "Streaming On: See responses as they are generated (faster UX)" 
                  : "Streaming Off: Wait for full response before displaying"
                }
              >
                <Zap className={`w-3 h-3 ${useStreaming ? 'text-purple-400' : 'text-gray-500'}`} />
                {useStreaming ? '⚡ Stream On' : '📝 Stream Off'}
              </button>
              
              {/* RAG toggle */}
              <button
                onClick={() => setUseRag(!useRag)}
                className={`text-xs flex items-center gap-1.5 px-2 py-1 rounded ${
                  useRag 
                    ? 'bg-blue-900/50 text-blue-400 hover:bg-blue-900/70' 
                    : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
                }`}
                title={useRag 
                  ? "RAG Enabled: AI will search knowledge bases for relevant context" 
                  : "RAG Disabled: AI will respond without searching knowledge bases"
                }
              >
                <Search className={`w-3 h-3 ${useRag ? 'text-blue-400' : 'text-gray-500'}`} />
                {useRag ? '🔍 RAG On' : '💬 RAG Off'}
              </button>
              
              <button
                onClick={clearCurrentChat}
                className="text-xs text-gray-500 hover:text-red-400 flex items-center gap-1"
              >
                <Trash2 className="w-3 h-3" />
                Clear chat
              </button>
            </div>
          )}
          
          {/* Show mode info for empty chats */}
          {(!activeSession || messages.length === 0) && (
            <div className="mt-2 flex justify-start gap-2">
              <button
                onClick={() => setUseAsyncMode(!useAsyncMode)}
                className={`text-xs flex items-center gap-1.5 px-2 py-1 rounded ${
                  useAsyncMode 
                    ? 'bg-green-900/50 text-green-400 hover:bg-green-900/70' 
                    : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
                }`}
              >
                <span className={`w-2 h-2 rounded-full ${useAsyncMode ? 'bg-green-400' : 'bg-gray-500'}`} />
                {useAsyncMode ? '🔄 Background Mode (safe to leave)' : '⏳ Wait Mode (stay on page)'}
              </button>
              
              {/* RAG toggle for empty chats */}
              <button
                onClick={() => setUseRag(!useRag)}
                className={`text-xs flex items-center gap-1.5 px-2 py-1 rounded ${
                  useRag 
                    ? 'bg-blue-900/50 text-blue-400 hover:bg-blue-900/70' 
                    : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
                }`}
                title={useRag 
                  ? "RAG Enabled: AI will search knowledge bases" 
                  : "RAG Disabled: AI will respond without searching"
                }
              >
                <Search className={`w-3 h-3 ${useRag ? 'text-blue-400' : 'text-gray-500'}`} />
                {useRag ? '🔍 RAG On' : '💬 RAG Off'}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
