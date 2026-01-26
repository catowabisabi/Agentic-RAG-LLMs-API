'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { MessageSquare, Send, Trash2, Plus, Edit2, Check, X, Database, Loader2, Brain, Wifi, WifiOff } from 'lucide-react';
import { chatAPI, createWebSocket } from '../lib/api';

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

export default function ChatPage() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [editingTitle, setEditingTitle] = useState<string | null>(null);
  const [editTitleValue, setEditTitleValue] = useState('');
  const [isHydrated, setIsHydrated] = useState(false);
  const [thinkingSteps, setThinkingSteps] = useState<ThinkingStep[]>([]);
  const [wsConnected, setWsConnected] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const pendingMessageRef = useRef<string | null>(null);

  const activeSession = sessions.find(s => s.id === activeSessionId);
  const messages = activeSession?.messages || [];

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
            // Capture thinking steps - dedupe by timestamp + type + agent
            if (data.type === 'thinking' || data.type === 'agent_started' || data.type === 'task_assigned') {
              const step: ThinkingStep = {
                type: data.type,
                agent: data.agent || data.source || 'system',
                content: data.content || data,
                timestamp: data.timestamp || new Date().toISOString()
              };
              setThinkingSteps(prev => {
                // Check for duplicates
                const isDupe = prev.some(s => 
                  s.timestamp === step.timestamp && 
                  s.type === step.type && 
                  s.agent === step.agent
                );
                if (isDupe) return prev;
                return [...prev, step];
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
    pendingMessageRef.current = currentSessionId;

    try {
      const response = await chatAPI.sendMessage({
        message: messageToSend,
        conversation_id: currentSessionId || undefined,
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
    } catch (err: any) {
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
    }

    setLoading(false);
    pendingMessageRef.current = null;
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
    if (content.status) return content.status;
    if (content.task) return content.task;
    if (content.query) return `Query: ${content.query}`;
    return JSON.stringify(content);
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
            <div className={`flex items-center gap-1 px-2 py-1 rounded text-xs ${wsConnected ? 'bg-green-900/50 text-green-400' : 'bg-red-900/50 text-red-400'}`}>
              {wsConnected ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
              {wsConnected ? 'Live' : 'Offline'}
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
                      </div>
                    </div>
                  </div>

                  {/* Show thinking steps for this message */}
                  {msg.thinking && msg.thinking.length > 0 && (
                    <div className="mt-2 ml-4 p-3 bg-purple-900/20 border border-purple-800/50 rounded-lg">
                      <div className="flex items-center gap-2 text-xs text-purple-400 mb-2">
                        <Brain className="w-3 h-3" />
                        <span>Chain of Thought</span>
                      </div>
                      <div className="space-y-1">
                        {msg.thinking.map((step, i) => (
                          <div key={i} className="text-xs text-gray-400">
                            <span className="text-purple-400">[{step.agent}]</span>
                            <span className="ml-2">{formatThinkingContent(step.content)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}
              
              {/* Active Thinking Indicator */}
              {loading && (
                <div className="space-y-2">
                  <div className="flex justify-start">
                    <div className="bg-gray-700 rounded-xl px-4 py-3 flex items-center gap-3">
                      <Loader2 className="w-5 h-5 text-blue-400 animate-spin" />
                      <div className="flex flex-col">
                        <span className="text-white text-sm">Thinking...</span>
                        <span className="text-gray-400 text-xs">Processing your request</span>
                      </div>
                    </div>
                  </div>
                  
                  {/* Live thinking steps */}
                  {thinkingSteps.length > 0 && (
                    <div className="ml-4 p-3 bg-purple-900/20 border border-purple-800/50 rounded-lg animate-pulse">
                      <div className="flex items-center gap-2 text-xs text-purple-400 mb-2">
                        <Brain className="w-3 h-3" />
                        <span>Live Chain of Thought</span>
                      </div>
                      <div className="space-y-1">
                        {thinkingSteps.map((step, i) => (
                          <div key={i} className="text-xs text-gray-400">
                            <span className="text-purple-400">[{step.agent}]</span>
                            <span className="ml-2">{formatThinkingContent(step.content)}</span>
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
            <div className="mt-2 flex justify-end">
              <button
                onClick={clearCurrentChat}
                className="text-xs text-gray-500 hover:text-red-400 flex items-center gap-1"
              >
                <Trash2 className="w-3 h-3" />
                Clear chat
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
