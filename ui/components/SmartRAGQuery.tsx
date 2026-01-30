'use client';

import React, { useState, useEffect } from 'react';
import { Search, Database, Zap, List, AlertCircle } from 'lucide-react';

interface QueryMode {
  value: string;
  label: string;
  description: string;
  icon: React.ReactNode;
}

interface SmartRAGQueryProps {
  onResults?: (results: any) => void;
  compact?: boolean; // For embedding in chat
}

export default function SmartRAGQuery({ onResults, compact = false }: SmartRAGQueryProps) {
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState<string>('auto');
  const [selectedDb, setSelectedDb] = useState<string>('');
  const [databases, setDatabases] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<any>(null);
  const [error, setError] = useState<string>('');

  const modes: QueryMode[] = [
    {
      value: 'auto',
      label: '智能路由',
      description: 'AI 自動選擇最佳數據庫',
      icon: <Zap className="w-4 h-4" />
    },
    {
      value: 'multi',
      label: '多數據庫',
      description: '搜索所有數據庫並合併結果',
      icon: <Database className="w-4 h-4" />
    },
    {
      value: 'manual',
      label: '手動選擇',
      description: '選擇特定數據庫搜索',
      icon: <List className="w-4 h-4" />
    }
  ];

  useEffect(() => {
    fetchDatabases();
  }, []);

  const fetchDatabases = async () => {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:1130';
      const response = await fetch(`${apiUrl}/rag/databases`);
      const data = await response.json();
      const dbList = Object.entries(data.databases || {})
        .map(([name, info]: [string, any]) => ({
          name,
          ...info
        }))
        .filter(db => db.document_count > 0);
      setDatabases(dbList);
      if (dbList.length > 0) {
        setSelectedDb(dbList[0].name);
      }
    } catch (err) {
      console.error('Failed to fetch databases:', err);
    }
  };

  const handleSearch = async () => {
    if (!query.trim()) return;
    
    setLoading(true);
    setError('');
    setResults(null);

    try {
      const requestMode = mode === 'manual' ? selectedDb : mode;
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:1130';
      
      const response = await fetch(`${apiUrl}/rag/smart-query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: query,
          mode: requestMode,
          top_k: 5,
          threshold: 0.0
        })
      });

      if (!response.ok) {
        throw new Error(`搜索失敗: ${response.statusText}`);
      }

      const data = await response.json();
      setResults(data);
      onResults?.(data);
    } catch (err: any) {
      setError(err.message || '搜索時發生錯誤');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={`${compact ? 'space-y-4' : 'max-w-6xl mx-auto p-6 space-y-6'}`}>
      {/* Header */}
      {!compact && (
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h1 className="text-2xl font-bold text-white mb-2">智能 RAG 搜索</h1>
          <p className="text-gray-400">選擇搜索模式，輸入問題，快速獲取答案</p>
        </div>
      )}

      {/* Mode Selection */}
      <div className={`bg-gray-800 rounded-lg ${compact ? 'p-4' : 'p-6'} border border-gray-700`}>
        <h2 className={`${compact ? 'text-base' : 'text-lg'} font-semibold text-white mb-4`}>選擇搜索模式</h2>
        <div className={`grid ${compact ? 'grid-cols-3 gap-2' : 'grid-cols-1 md:grid-cols-3 gap-4'}`}>
          {modes.map((m) => (
            <button
              key={m.value}
              onClick={() => setMode(m.value)}
              className={`${compact ? 'p-2' : 'p-4'} rounded-lg border-2 transition-all text-left ${
                mode === m.value
                  ? 'border-blue-500 bg-blue-900/30'
                  : 'border-gray-600 hover:border-gray-500 bg-gray-700/50'
              }`}
            >
              <div className="flex items-center space-x-2 mb-1">
                <div className={`${mode === m.value ? 'text-blue-400' : 'text-gray-400'}`}>
                  {m.icon}
                </div>
                <span className={`font-medium ${compact ? 'text-sm' : ''} ${mode === m.value ? 'text-blue-300' : 'text-white'}`}>
                  {m.label}
                </span>
              </div>
              {!compact && <p className="text-sm text-gray-400">{m.description}</p>}
            </button>
          ))}
        </div>
      </div>

      {/* Database Selection (for manual mode) */}
      {mode === 'manual' && (
        <div className={`bg-gray-800 rounded-lg ${compact ? 'p-4' : 'p-6'} border border-gray-700`}>
          <h2 className={`${compact ? 'text-base' : 'text-lg'} font-semibold text-white mb-4`}>選擇數據庫</h2>
          <select
            value={selectedDb}
            onChange={(e) => setSelectedDb(e.target.value)}
            className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            {databases.map((db) => (
              <option key={db.name} value={db.name}>
                {db.description || db.name} ({db.document_count} 文檔)
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Search Input */}
      <div className={`bg-gray-800 rounded-lg ${compact ? 'p-4' : 'p-6'} border border-gray-700`}>
        <h2 className={`${compact ? 'text-base' : 'text-lg'} font-semibold text-white mb-4`}>輸入問題</h2>
        <div className="flex space-x-3">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="例如：如何使用 SolidWorks API？"
            className="flex-1 px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
          <button
            onClick={handleSearch}
            disabled={loading || !query.trim()}
            className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed flex items-center space-x-2 transition-colors"
          >
            <Search className="w-5 h-5" />
            <span>{loading ? '搜索中...' : '搜索'}</span>
          </button>
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="bg-red-900/30 border border-red-700 rounded-lg p-4 flex items-start space-x-3">
          <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
          <div>
            <h3 className="font-medium text-red-300">搜索錯誤</h3>
            <p className="text-sm text-red-400 mt-1">{error}</p>
          </div>
        </div>
      )}

      {/* Results Display */}
      {results && (
        <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
          {/* Result Header */}
          <div className="bg-gradient-to-r from-blue-900/50 to-indigo-900/50 px-6 py-4 border-b border-gray-700">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-white">搜索結果</h2>
                <p className="text-sm text-gray-400 mt-1">
                  共找到 {results.count} 個相關結果
                  {results.mode === 'auto' && ` · 智能選擇: ${results.selected_databases?.join(', ')}`}
                  {results.mode === 'multi' && ` · 搜索了 ${results.searched_databases?.length} 個數據庫`}
                  {results.mode === 'single' && ` · 數據庫: ${results.selected_database}`}
                </p>
              </div>
              <div className="flex items-center space-x-2 text-sm">
                {results.mode === 'auto' && results.reasoning && (
                  <span className="px-3 py-1 bg-blue-900/50 text-blue-300 rounded-full">
                    AI 推理
                  </span>
                )}
              </div>
            </div>
            {results.mode === 'auto' && results.reasoning && (
              <div className="mt-3 text-sm text-gray-300 bg-gray-900/50 p-3 rounded-lg border border-gray-600">
                <span className="font-medium text-blue-400">選擇原因：</span> {results.reasoning}
              </div>
            )}
          </div>

          {/* Results List */}
          <div className="divide-y divide-gray-700">
            {results.results?.length > 0 ? (
              results.results.map((result: any, idx: number) => (
                <div key={idx} className="p-6 hover:bg-gray-700/50 transition-colors">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center space-x-2">
                      <span className="text-sm font-medium text-gray-400">#{idx + 1}</span>
                      {result.source_database && (
                        <span className="px-2 py-1 text-xs bg-purple-900/50 text-purple-300 rounded-full">
                          {result.source_database}
                        </span>
                      )}
                      {result.metadata?.category && (
                        <span className="px-2 py-1 text-xs bg-gray-700 text-gray-300 rounded-full">
                          {result.metadata.category}
                        </span>
                      )}
                    </div>
                    {result.score !== undefined && (
                      <span className="text-sm text-gray-400">
                        相關度: {(result.score * 100).toFixed(1)}%
                      </span>
                    )}
                  </div>
                  
                  <div className="prose prose-invert max-w-none">
                    <p className="text-gray-200 leading-relaxed whitespace-pre-wrap">
                      {result.content || result.text}
                    </p>
                  </div>
                  
                  {result.metadata?.title && (
                    <div className="mt-3 text-sm text-gray-500">
                      來源: {result.metadata.title}
                    </div>
                  )}
                </div>
              ))
            ) : (
              <div className="p-12 text-center text-gray-500">
                <Database className="w-12 h-12 mx-auto mb-3 text-gray-600" />
                <p>沒有找到相關結果</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
