'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { MessageSquare, Send, Trash2, Plus, Edit2, Check, X, ChevronLeft, ChevronRight, Database, ExternalLink } from 'lucide-react';
import { chatAPI } from '../lib/api';

interface Source {
  database: string;
  title: string;
  relevance: number;
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  agents_involved?: string[];
  sources?: Source[];
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
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Get active session
  const activeSession = sessions.find(s => s.id === activeSessionId);
  const messages = activeSession?.messages || [];

  // Load from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      try {
        const savedSessions: ChatSession[] = JSON.parse(saved);
        if (Array.isArray(savedSessions) && savedSessions.length > 0) {
          setSessions(savedSessions);
          setActiveSessionId(savedSessions[0].id);
          return;
        }
      } catch (e) {
        console.error('Failed to load chat sessions:', e);
      }
    }
    // Create initial session if none exist
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

  // Save to localStorage on change - always save
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
  }, [sessions]);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  // Create new session
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
    inputRef.current?.focus();
  };

  // Delete session
  const deleteSession = (sessionId: string) => {
    setSessions(prev => {
      const filtered = prev.filter(s => s.id !== sessionId);
      if (activeSessionId === sessionId) {
        setActiveSessionId(filtered[0]?.id || null);
      }
      if (filtered.length === 0) {
        localStorage.removeItem(STORAGE_KEY);
      }
      return filtered;
    });
  };

  // Update session title
  const startEditTitle = (session: ChatSession) => {
    setEditingTitle(session.id);
    setEditTitleValue(session.title);
  };

  const saveTitle = () => {
    if (editingTitle && editTitleValue.trim()) {
      setSessions(prev => prev.map(s => 
        s.id === editingTitle 
          ? { ...s, title: editTitleValue.trim(), updatedAt: new Date().toISOString() }
          : s
      ));
    }
    setEditingTitle(null);
    setEditTitleValue('');
  };

  const cancelEditTitle = () => {
    setEditingTitle(null);
    setEditTitleValue('');
  };

  // Auto-generate title from first message
  const autoGenerateTitle = (message: string): string => {
    const words = message.split(' ').slice(0, 5).join(' ');
    return words.length > 30 ? words.slice(0, 30) + '...' : words;
  };

  const sendMessage = async () => {
    if (!input.trim() || loading) return;

    // Create session if none exists
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

    // Add user message to session
    setSessions(prev => prev.map(s => {
      if (s.id === currentSessionId) {
        const isFirstMessage = s.messages.length === 0;
        return {
          ...s,
          messages: [...s.messages, userMessage],
          title: isFirstMessage ? autoGenerateTitle(input) : s.title,
          updatedAt: new Date().toISOString(),
        };
      }
      return s;
    }));

    setInput('');
    setLoading(true);

    try {
      const response = await chatAPI.sendMessage({
        message: input,
        conversation_id: currentSessionId || undefined,
      });

      const data = response.data;

      const assistantMessage: Message = {
        id: data.message_id || Date.now().toString() + '-a',
        role: 'assistant',
        content: data.response || 'No response received',
        timestamp: data.timestamp || new Date().toISOString(),
        agents_involved: data.agents_involved,
        sources: data.sources || [],
      };

      setSessions(prev => prev.map(s => {
        if (s.id === currentSessionId) {
          return {
            ...s,
            messages: [...s.messages, assistantMessage],
            updatedAt: new Date().toISOString(),
          };
        }
        return s;
      }));
    } catch (err: any) {
      const errorMessage: Message = {
        id: Date.now().toString() + '-err',
        role: 'assistant',
        content: `Error: ${err.response?.data?.detail || err.message || 'Failed to get response'}`,
        timestamp: new Date().toISOString(),
      };
      setSessions(prev => prev.map(s => {
        if (s.id === currentSessionId) {
          return {
            ...s,
            messages: [...s.messages, errorMessage],
            updatedAt: new Date().toISOString(),
          };
        }
        return s;
      }));
    }

    setLoading(false);
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
        s.id === activeSessionId 
          ? { ...s, messages: [], updatedAt: new Date().toISOString() }
          : s
      ));
    }
  };

  return (
    <div className="h-screen flex">
      {/* Sidebar */}
      <div className={`${sidebarOpen ? 'w-72' : 'w-0'} transition-all duration-300 bg-gray-900 border-r border-gray-700 flex flex-col overflow-hidden`}>
        {/* Sidebar Header */}
        <div className="p-4 border-b border-gray-700">
          <button
            onClick={createNewSession}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-blue-600 hover:bg-blue-700 rounded-lg text-white font-medium transition-colors"
          >
            <Plus className="w-5 h-5" />
            New Chat
          </button>
        </div>

        {/* Session List */}
        <div className="flex-1 overflow-y-auto">
          {sessions.length === 0 ? (
            <div className="p-4 text-center text-gray-500">
              <p className="text-sm">No conversations yet</p>
              <p className="text-xs mt-1">Start a new chat!</p>
            </div>
          ) : (
            sessions.map(session => (
              <div
                key={session.id}
                className={`group p-3 border-b border-gray-800 cursor-pointer hover:bg-gray-800 transition-colors ${
                  session.id === activeSessionId ? 'bg-gray-800' : ''
                }`}
                onClick={() => setActiveSessionId(session.id)}
              >
                {editingTitle === session.id ? (
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      value={editTitleValue}
                      onChange={(e) => setEditTitleValue(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') saveTitle();
                        if (e.key === 'Escape') cancelEditTitle();
                      }}
                      className="flex-1 px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-sm focus:outline-none focus:border-blue-500"
                      autoFocus
                      onClick={(e) => e.stopPropagation()}
                    />
                    <button
                      onClick={(e) => { e.stopPropagation(); saveTitle(); }}
                      className="p-1 text-green-400 hover:text-green-300"
                    >
                      <Check className="w-4 h-4" />
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); cancelEditTitle(); }}
                      className="p-1 text-red-400 hover:text-red-300"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center justify-between">
                    <div className="flex-1 min-w-0">
                      <p className="text-white text-sm font-medium truncate">{session.title}</p>
                      <p className="text-gray-500 text-xs mt-1">
                        {session.messages.length} messages • {new Date(session.updatedAt).toLocaleDateString()}
                      </p>
                    </div>
                    <div className="hidden group-hover:flex items-center gap-1 ml-2">
                      <button
                        onClick={(e) => { e.stopPropagation(); startEditTitle(session); }}
                        className="p-1 text-gray-400 hover:text-white transition-colors"
                        title="Edit title"
                      >
                        <Edit2 className="w-4 h-4" />
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); deleteSession(session.id); }}
                        className="p-1 text-gray-400 hover:text-red-400 transition-colors"
                        title="Delete"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>

      {/* Toggle Sidebar Button */}
      <button
        onClick={() => setSidebarOpen(!sidebarOpen)}
        className="absolute top-1/2 transform -translate-y-1/2 z-10 bg-gray-700 hover:bg-gray-600 p-1 rounded-r-lg transition-all"
        style={{ left: sidebarOpen ? '288px' : '0' }}
      >
        {sidebarOpen ? <ChevronLeft className="w-4 h-4 text-gray-300" /> : <ChevronRight className="w-4 h-4 text-gray-300" />}
      </button>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="p-6 border-b border-gray-700 bg-gray-800">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-white flex items-center gap-3">
                <MessageSquare className="w-7 h-7" />
                {activeSession?.title || 'Chat'}
              </h1>
              <p className="text-gray-400 text-sm mt-1">
                {activeSession 
                  ? `${activeSession.messages.length} messages • Started ${new Date(activeSession.createdAt).toLocaleDateString()}`
                  : 'Start a new conversation'
                }
              </p>
            </div>
            {activeSession && activeSession.messages.length > 0 && (
              <button
                onClick={clearCurrentChat}
                className="flex items-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-gray-300 transition-colors"
              >
                <Trash2 className="w-4 h-4" />
                Clear Messages
              </button>
            )}
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-gray-500">
              <MessageSquare className="w-16 h-16 mb-4 opacity-50" />
              <p className="text-lg">Start a conversation</p>
              <p className="text-sm">Send a message to interact with the AI assistant</p>
              <div className="mt-6 grid grid-cols-2 gap-3">
                {['Hello!', 'What can you do?', 'Help me with...', 'Tell me about...'].map((suggestion) => (
                  <button
                    key={suggestion}
                    onClick={() => setInput(suggestion)}
                    className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-gray-300 text-sm transition-colors"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((message) => (
              <div
                key={message.id}
                className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[70%] rounded-xl px-4 py-3 ${
                    message.role === 'user'
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-700 text-gray-100'
                  }`}
                >
                  <p className="whitespace-pre-wrap">{message.content}</p>
                  
                  {/* Sources from RAG */}
                  {message.sources && message.sources.length > 0 && (
                    <div className="mt-3 pt-2 border-t border-gray-600">
                      <div className="flex items-center gap-1 text-xs text-gray-400 mb-2">
                        <Database className="w-3 h-3" />
                        <span>Sources:</span>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {message.sources.map((source, idx) => (
                          <span
                            key={idx}
                            className="inline-flex items-center gap-1 px-2 py-1 bg-gray-600 rounded text-xs"
                            title={`Relevance: ${Math.round(source.relevance * 100)}%`}
                          >
                            <span className="text-blue-400">{source.database}</span>
                            <span className="text-gray-300">: {source.title}</span>
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  
                  <div className="flex items-center justify-between mt-2 text-xs opacity-70">
                    <span>{new Date(message.timestamp).toLocaleTimeString()}</span>
                    {message.agents_involved && message.agents_involved.length > 0 && (
                      <span className="ml-2">
                        Agents: {message.agents_involved.join(', ')}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))
          )}
          {loading && (
            <div className="flex justify-start">
              <div className="bg-gray-700 rounded-xl px-4 py-3 flex items-center gap-2">
                <div className="flex space-x-1">
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                </div>
                <span className="text-gray-400 ml-2">Thinking...</span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="p-6 border-t border-gray-700 bg-gray-800">
          <div className="flex gap-3">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              rows={1}
              className="flex-1 px-4 py-3 bg-gray-700 border border-gray-600 rounded-xl text-white placeholder-gray-400 focus:outline-none focus:border-blue-500 resize-none"
              placeholder="Type your message... (Press Enter to send)"
            />
            <button
              onClick={sendMessage}
              disabled={!input.trim() || loading}
              className="px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed rounded-xl text-white transition-colors"
            >
              <Send className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
