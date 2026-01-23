'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Activity, Circle, Send, Trash2 } from 'lucide-react';
import { createWebSocket } from '../lib/api';

interface WSMessage {
  id: string;
  type: 'sent' | 'received' | 'system';
  content: string;
  timestamp: Date;
}

type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error';

export default function WebSocketPage() {
  const [status, setStatus] = useState<ConnectionStatus>('disconnected');
  const [messages, setMessages] = useState<WSMessage[]>([]);
  const [input, setInput] = useState('');
  const wsRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const addMessage = (type: WSMessage['type'], content: string) => {
    setMessages((prev) => [
      ...prev,
      {
        id: Date.now().toString(),
        type,
        content,
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
      };

      wsRef.current.onmessage = (event) => {
        let content = event.data;
        try {
          const parsed = JSON.parse(event.data);
          content = JSON.stringify(parsed, null, 2);
        } catch (e) {
          // Not JSON, use as-is
        }
        addMessage('received', content);
      };

      wsRef.current.onclose = () => {
        setStatus('disconnected');
        addMessage('system', 'Disconnected from WebSocket');
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
      wsRef.current.close();
      wsRef.current = null;
    }
  };

  const sendMessage = () => {
    if (!input.trim() || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

    wsRef.current.send(input);
    addMessage('sent', input);
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
    <div className="h-screen flex flex-col">
      {/* Header */}
      <div className="p-6 border-b border-gray-700 bg-gray-800">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-3">
              <Activity className="w-7 h-7" />
              WebSocket
            </h1>
            <div className="flex items-center gap-2 mt-1">
              <Circle className={`w-3 h-3 fill-current ${getStatusColor()}`} />
              <span className="text-gray-400 text-sm capitalize">{status}</span>
            </div>
          </div>
          <div className="flex gap-3">
            {status !== 'connected' ? (
              <button
                onClick={connect}
                disabled={status === 'connecting'}
                className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 rounded-lg text-white transition-colors"
              >
                Connect
              </button>
            ) : (
              <button
                onClick={disconnect}
                className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-700 rounded-lg text-white transition-colors"
              >
                Disconnect
              </button>
            )}
            <button
              onClick={clearMessages}
              className="flex items-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-gray-300 transition-colors"
            >
              <Trash2 className="w-4 h-4" />
              Clear
            </button>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-3 bg-gray-900">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-500">
            <Activity className="w-16 h-16 mb-4 opacity-50" />
            <p className="text-lg">WebSocket Test</p>
            <p className="text-sm">Connect to start sending and receiving messages</p>
          </div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${
                msg.type === 'sent' ? 'justify-end' : msg.type === 'system' ? 'justify-center' : 'justify-start'
              }`}
            >
              {msg.type === 'system' ? (
                <div className="px-4 py-2 bg-gray-800 rounded-full text-gray-400 text-sm">
                  {msg.content}
                </div>
              ) : (
                <div
                  className={`max-w-[70%] rounded-xl px-4 py-3 ${
                    msg.type === 'sent'
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-700 text-gray-100'
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1 text-xs opacity-70">
                    <span>{msg.type === 'sent' ? '↑ Sent' : '↓ Received'}</span>
                    <span>{msg.timestamp.toLocaleTimeString()}</span>
                  </div>
                  <pre className="whitespace-pre-wrap text-sm font-mono">{msg.content}</pre>
                </div>
              )}
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-6 border-t border-gray-700 bg-gray-800">
        <div className="flex gap-3">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            rows={1}
            disabled={status !== 'connected'}
            className="flex-1 px-4 py-3 bg-gray-700 border border-gray-600 rounded-xl text-white placeholder-gray-400 focus:outline-none focus:border-blue-500 resize-none disabled:opacity-50 disabled:cursor-not-allowed"
            placeholder={status === 'connected' ? 'Type message... (Press Enter to send)' : 'Connect to send messages'}
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || status !== 'connected'}
            className="px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed rounded-xl text-white transition-colors"
          >
            <Send className="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  );
}
