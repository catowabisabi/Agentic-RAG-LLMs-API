'use client';

import React, { useState, useCallback } from 'react';
import { experimentAPI, chatAPI } from '../lib/api';

interface Source {
  title?: string;
  database?: string;
  similarity?: number;
  rerank_score?: number;
  fusion_score?: number;
  vector_score?: number;
  bm25_score?: number;
  snippet?: string;
}

interface StrategyResult {
  strategy: string;
  answer: string;
  sources: Source[];
  timing_ms: number;
  llm_calls: number;
  metadata: Record<string, any>;
  error?: string;
}

interface CompareResult {
  query: string;
  timestamp: string;
  strategies: Record<string, StrategyResult>;
  summary: Record<string, { timing_ms: number; sources_count: number; llm_calls: number; has_answer: boolean }>;
}

export default function ExperimentPage() {
  const [query, setQuery] = useState('');
  const [topK, setTopK] = useState(5);
  const [alpha, setAlpha] = useState(0.7);
  const [loading, setLoading] = useState<Record<string, boolean>>({});
  const [results, setResults] = useState<Record<string, StrategyResult>>({});
  const [agenticResult, setAgenticResult] = useState<{ response: string; timing_ms: number } | null>(null);
  const [compareResult, setCompareResult] = useState<CompareResult | null>(null);
  const [activeTab, setActiveTab] = useState<'individual' | 'compare'>('compare');

  // Run Fast RAG
  const runFastRAG = useCallback(async () => {
    if (!query.trim()) return;
    setLoading(prev => ({ ...prev, fast_rag: true }));
    try {
      const res = await experimentAPI.fastRAG({ query, top_k: topK });
      setResults(prev => ({ ...prev, fast_rag: res.data }));
    } catch (err: any) {
      setResults(prev => ({ ...prev, fast_rag: { strategy: 'fast_rag', answer: '', sources: [], timing_ms: 0, llm_calls: 0, metadata: {}, error: err.message } }));
    }
    setLoading(prev => ({ ...prev, fast_rag: false }));
  }, [query, topK]);

  // Run Hybrid Search
  const runHybrid = useCallback(async () => {
    if (!query.trim()) return;
    setLoading(prev => ({ ...prev, hybrid: true }));
    try {
      const res = await experimentAPI.hybridSearch({ query, top_k: topK, alpha });
      setResults(prev => ({ ...prev, hybrid: res.data }));
    } catch (err: any) {
      setResults(prev => ({ ...prev, hybrid: { strategy: 'hybrid', answer: '', sources: [], timing_ms: 0, llm_calls: 0, metadata: {}, error: err.message } }));
    }
    setLoading(prev => ({ ...prev, hybrid: false }));
  }, [query, topK, alpha]);

  // Run Full Agentic (via existing chat API)
  const runAgentic = useCallback(async () => {
    if (!query.trim()) return;
    setLoading(prev => ({ ...prev, agentic: true }));
    setAgenticResult(null);
    try {
      const start = performance.now();
      const res = await chatAPI.sendMessage({ message: query, use_rag: true });
      const elapsed = Math.round(performance.now() - start);
      setAgenticResult({
        response: res.data?.response || res.data?.result?.response || JSON.stringify(res.data),
        timing_ms: elapsed
      });
    } catch (err: any) {
      setAgenticResult({ response: `Error: ${err.message}`, timing_ms: 0 });
    }
    setLoading(prev => ({ ...prev, agentic: false }));
  }, [query]);

  // Compare all strategies
  const runCompare = useCallback(async () => {
    if (!query.trim()) return;
    setLoading(prev => ({ ...prev, compare: true }));
    setCompareResult(null);
    try {
      const res = await experimentAPI.compare({ query, top_k: topK });
      setCompareResult(res.data);
    } catch (err: any) {
      console.error('Compare failed:', err);
    }
    setLoading(prev => ({ ...prev, compare: false }));
  }, [query, topK]);

  // Run all individually
  const runAll = useCallback(async () => {
    await Promise.all([runFastRAG(), runHybrid(), runAgentic()]);
  }, [runFastRAG, runHybrid, runAgentic]);

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white mb-2">🧪 RAG Strategy Experiment Lab</h1>
        <p className="text-gray-400 text-sm">
          Compare different retrieval strategies side-by-side. These endpoints are isolated from the main pipeline.
        </p>
      </div>

      {/* Query Input */}
      <div className="bg-gray-800 rounded-lg p-4 mb-6">
        <div className="flex gap-4 items-end">
          <div className="flex-1">
            <label className="block text-sm text-gray-400 mb-1">Query</label>
            <input
              type="text"
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Enter your test query..."
              className="w-full bg-gray-700 text-white rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              onKeyDown={e => { if (e.key === 'Enter') activeTab === 'compare' ? runCompare() : runAll(); }}
            />
          </div>
          <div className="w-20">
            <label className="block text-sm text-gray-400 mb-1">Top K</label>
            <input
              type="number"
              value={topK}
              onChange={e => setTopK(Number(e.target.value))}
              min={1} max={20}
              className="w-full bg-gray-700 text-white rounded px-3 py-2 text-sm"
            />
          </div>
          <div className="w-24">
            <label className="block text-sm text-gray-400 mb-1">Alpha (BM25)</label>
            <input
              type="number"
              value={alpha}
              onChange={e => setAlpha(Number(e.target.value))}
              min={0} max={1} step={0.1}
              className="w-full bg-gray-700 text-white rounded px-3 py-2 text-sm"
            />
          </div>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-2 mb-4">
        <button
          onClick={() => setActiveTab('compare')}
          className={`px-4 py-2 rounded text-sm font-medium ${activeTab === 'compare' ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}
        >
          📊 Compare All
        </button>
        <button
          onClick={() => setActiveTab('individual')}
          className={`px-4 py-2 rounded text-sm font-medium ${activeTab === 'individual' ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}
        >
          🔬 Individual Tests
        </button>
      </div>

      {/* Compare Tab */}
      {activeTab === 'compare' && (
        <div>
          <button
            onClick={runCompare}
            disabled={loading.compare || !query.trim()}
            className="mb-4 px-6 py-2 bg-blue-600 text-white rounded font-medium hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading.compare ? '⏳ Running comparison...' : '▶ Run Comparison (Fast RAG + Hybrid + Vector)'}
          </button>

          {compareResult && (
            <div className="space-y-4">
              {/* Summary Table */}
              <div className="bg-gray-800 rounded-lg p-4">
                <h3 className="text-white font-semibold mb-3">📊 Performance Summary</h3>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-gray-400 border-b border-gray-700">
                      <th className="text-left py-2">Strategy</th>
                      <th className="text-right py-2">Time (ms)</th>
                      <th className="text-right py-2">Sources</th>
                      <th className="text-right py-2">LLM Calls</th>
                      <th className="text-right py-2">Has Answer</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(compareResult.summary).map(([name, s]) => (
                      <tr key={name} className="border-b border-gray-700/50 text-gray-300">
                        <td className="py-2 font-medium">{name}</td>
                        <td className="py-2 text-right">
                          <span className={`font-mono ${s.timing_ms < 2000 ? 'text-green-400' : s.timing_ms < 5000 ? 'text-yellow-400' : 'text-red-400'}`}>
                            {s.timing_ms}ms
                          </span>
                        </td>
                        <td className="py-2 text-right">{s.sources_count}</td>
                        <td className="py-2 text-right">{s.llm_calls}</td>
                        <td className="py-2 text-right">{s.has_answer ? '✅' : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Strategy Details */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                {Object.entries(compareResult.strategies).map(([name, strategy]) => (
                  <StrategyCard key={name} name={name} result={strategy} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Individual Tab */}
      {activeTab === 'individual' && (
        <div className="space-y-6">
          {/* Action Buttons */}
          <div className="flex gap-2 flex-wrap">
            <button
              onClick={runFastRAG}
              disabled={loading.fast_rag || !query.trim()}
              className="px-4 py-2 bg-emerald-600 text-white rounded text-sm font-medium hover:bg-emerald-500 disabled:opacity-50"
            >
              {loading.fast_rag ? '⏳...' : '⚡ Fast RAG (2 LLM calls)'}
            </button>
            <button
              onClick={runHybrid}
              disabled={loading.hybrid || !query.trim()}
              className="px-4 py-2 bg-purple-600 text-white rounded text-sm font-medium hover:bg-purple-500 disabled:opacity-50"
            >
              {loading.hybrid ? '⏳...' : '🔀 Hybrid BM25+Vector'}
            </button>
            <button
              onClick={runAgentic}
              disabled={loading.agentic || !query.trim()}
              className="px-4 py-2 bg-orange-600 text-white rounded text-sm font-medium hover:bg-orange-500 disabled:opacity-50"
            >
              {loading.agentic ? '⏳...' : '🤖 Full Agentic (ReAct Loop)'}
            </button>
            <button
              onClick={runAll}
              disabled={Object.values(loading).some(Boolean) || !query.trim()}
              className="px-4 py-2 bg-blue-600 text-white rounded text-sm font-medium hover:bg-blue-500 disabled:opacity-50"
            >
              ▶ Run All
            </button>
          </div>

          {/* Results Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Fast RAG */}
            {results.fast_rag && (
              <StrategyCard name="Fast RAG" result={results.fast_rag} />
            )}

            {/* Hybrid */}
            {results.hybrid && (
              <StrategyCard name="Hybrid BM25+Vector" result={results.hybrid} />
            )}

            {/* Agentic */}
            {agenticResult && (
              <div className="bg-gray-800 rounded-lg p-4">
                <div className="flex justify-between items-center mb-3">
                  <h3 className="text-white font-semibold">🤖 Full Agentic</h3>
                  <span className={`text-xs font-mono px-2 py-0.5 rounded ${agenticResult.timing_ms < 5000 ? 'bg-green-900 text-green-300' : agenticResult.timing_ms < 15000 ? 'bg-yellow-900 text-yellow-300' : 'bg-red-900 text-red-300'}`}>
                    {agenticResult.timing_ms}ms
                  </span>
                </div>
                <div className="text-gray-300 text-sm whitespace-pre-wrap max-h-80 overflow-y-auto">
                  {agenticResult.response}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function StrategyCard({ name, result }: { name: string; result: StrategyResult }) {
  const [expanded, setExpanded] = useState(false);

  if (result.error) {
    return (
      <div className="bg-gray-800 rounded-lg p-4 border border-red-800">
        <h3 className="text-white font-semibold mb-2">{name}</h3>
        <p className="text-red-400 text-sm">Error: {result.error}</p>
      </div>
    );
  }

  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <div className="flex justify-between items-center mb-3">
        <h3 className="text-white font-semibold text-sm">{name}</h3>
        <div className="flex gap-2">
          <span className={`text-xs font-mono px-2 py-0.5 rounded ${result.timing_ms < 2000 ? 'bg-green-900 text-green-300' : result.timing_ms < 5000 ? 'bg-yellow-900 text-yellow-300' : 'bg-red-900 text-red-300'}`}>
            {result.timing_ms}ms
          </span>
          {result.llm_calls > 0 && (
            <span className="text-xs font-mono px-2 py-0.5 rounded bg-blue-900 text-blue-300">
              {result.llm_calls} LLM
            </span>
          )}
        </div>
      </div>

      {/* Answer */}
      {result.answer && (
        <div className="mb-3">
          <p className="text-xs text-gray-500 mb-1">Answer:</p>
          <div className="text-gray-300 text-sm whitespace-pre-wrap max-h-40 overflow-y-auto bg-gray-900 rounded p-2">
            {result.answer}
          </div>
        </div>
      )}

      {/* Sources */}
      {result.sources.length > 0 && (
        <div>
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-xs text-blue-400 hover:text-blue-300 mb-2"
          >
            {expanded ? '▼' : '▶'} {result.sources.length} sources
          </button>
          
          {expanded && (
            <div className="space-y-2 max-h-60 overflow-y-auto">
              {result.sources.map((source, i) => (
                <div key={i} className="bg-gray-900 rounded p-2 text-xs">
                  <div className="flex justify-between text-gray-400 mb-1">
                    <span className="font-medium text-gray-300">{source.title || `Source ${i + 1}`}</span>
                    <span className="text-gray-500">{source.database}</span>
                  </div>
                  <div className="flex gap-2 text-gray-500 mb-1">
                    {source.similarity !== undefined && <span>sim: {source.similarity}</span>}
                    {source.rerank_score !== undefined && source.rerank_score !== null && <span>rerank: {source.rerank_score}</span>}
                    {source.fusion_score !== undefined && <span>fusion: {source.fusion_score}</span>}
                    {source.vector_score !== undefined && <span>vec: {source.vector_score}</span>}
                    {source.bm25_score !== undefined && <span>bm25: {source.bm25_score}</span>}
                  </div>
                  {source.snippet && (
                    <p className="text-gray-400 line-clamp-3">{source.snippet}</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Metadata */}
      {Object.keys(result.metadata).length > 0 && (
        <div className="mt-2 text-xs text-gray-600">
          {result.metadata.dbs_searched && (
            <span>DBs: {Array.isArray(result.metadata.dbs_searched) ? result.metadata.dbs_searched.join(', ') : result.metadata.dbs_searched}</span>
          )}
        </div>
      )}
    </div>
  );
}
