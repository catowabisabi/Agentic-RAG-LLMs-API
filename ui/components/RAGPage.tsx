'use client';

import React, { useState } from 'react';
import {
  Database,
  Search,
  FileText,
  Upload,
  Plus,
  Trash2,
  RefreshCw,
  ChevronDown,
  ChevronUp
} from 'lucide-react';
import { ragAPI } from '../lib/api';

interface QueryResult {
  content: string;
  metadata: Record<string, any>;
  score?: number;
}

export default function RAGPage() {
  const [activeTab, setActiveTab] = useState<'query' | 'add' | 'collections'>('query');

  // Query state
  const [queryText, setQueryText] = useState('');
  const [collection, setCollection] = useState('default');
  const [topK, setTopK] = useState(5);
  const [results, setResults] = useState<QueryResult[]>([]);
  const [querying, setQuerying] = useState(false);

  // Add document state
  const [docContent, setDocContent] = useState('');
  const [docMetadata, setDocMetadata] = useState('{}');
  const [docCollection, setDocCollection] = useState('default');
  const [adding, setAdding] = useState(false);
  const [addResult, setAddResult] = useState<any>(null);

  // Collections state
  const [collections, setCollections] = useState<string[]>([]);
  const [newCollectionName, setNewCollectionName] = useState('');
  const [loadingCollections, setLoadingCollections] = useState(false);

  // Expanded results
  const [expandedResults, setExpandedResults] = useState<Set<number>>(new Set());

  const handleQuery = async () => {
    if (!queryText.trim()) return;

    setQuerying(true);
    setResults([]);

    try {
      const response = await ragAPI.query({
        query: queryText,
        collection: collection,
        top_k: topK,
      });
      setResults(response.data.results || []);
    } catch (err: any) {
      console.error('Query failed:', err);
    }

    setQuerying(false);
  };

  const handleAddDocument = async () => {
    if (!docContent.trim()) return;

    setAdding(true);
    setAddResult(null);

    try {
      let metadata = {};
      try {
        metadata = JSON.parse(docMetadata);
      } catch (e) {
        // Invalid JSON, use empty object
      }

      const response = await ragAPI.addDocument({
        content: docContent,
        metadata,
        collection: docCollection,
      });
      setAddResult(response.data);
      setDocContent('');
      setDocMetadata('{}');
    } catch (err: any) {
      setAddResult({ error: err.message || 'Failed to add document' });
    }

    setAdding(false);
  };

  const fetchCollections = async () => {
    setLoadingCollections(true);
    try {
      const response = await ragAPI.listCollections();
      setCollections(response.data.collections || []);
    } catch (err) {
      console.error('Failed to fetch collections:', err);
    }
    setLoadingCollections(false);
  };

  const toggleResultExpand = (index: number) => {
    const newExpanded = new Set(expandedResults);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedResults(newExpanded);
  };

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white flex items-center gap-3">
          <Database className="w-8 h-8" />
          RAG Operations
        </h1>
        <p className="text-gray-400 mt-1">Query and manage vector database documents</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6">
        {[
          { id: 'query', label: 'Query', icon: Search },
          { id: 'add', label: 'Add Document', icon: FileText },
          { id: 'collections', label: 'Collections', icon: Database },
        ].map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => {
              setActiveTab(id as any);
              if (id === 'collections') fetchCollections();
            }}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
              activeTab === id
                ? 'bg-blue-600 text-white'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
          >
            <Icon className="w-4 h-4" />
            {label}
          </button>
        ))}
      </div>

      {/* Query Tab */}
      {activeTab === 'query' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
            <h2 className="text-xl font-semibold text-white mb-4">Query Documents</h2>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Query</label>
                <textarea
                  value={queryText}
                  onChange={(e) => setQueryText(e.target.value)}
                  rows={4}
                  className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-blue-500 resize-none"
                  placeholder="Enter your search query..."
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">Collection</label>
                  <input
                    type="text"
                    value={collection}
                    onChange={(e) => setCollection(e.target.value)}
                    className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">Top K</label>
                  <input
                    type="number"
                    value={topK}
                    onChange={(e) => setTopK(parseInt(e.target.value) || 5)}
                    min={1}
                    max={20}
                    className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
                  />
                </div>
              </div>

              <button
                onClick={handleQuery}
                disabled={!queryText.trim() || querying}
                className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed rounded-lg text-white transition-colors"
              >
                {querying ? (
                  <>
                    <div className="loading-spinner" />
                    Searching...
                  </>
                ) : (
                  <>
                    <Search className="w-4 h-4" />
                    Search
                  </>
                )}
              </button>
            </div>
          </div>

          <div className="lg:col-span-2 bg-gray-800 rounded-xl border border-gray-700">
            <div className="p-6 border-b border-gray-700">
              <h2 className="text-xl font-semibold text-white">
                Results ({results.length})
              </h2>
            </div>
            <div className="p-6 max-h-[600px] overflow-y-auto">
              {querying ? (
                <div className="flex justify-center py-8">
                  <div className="loading-spinner" />
                </div>
              ) : results.length === 0 ? (
                <p className="text-gray-500 text-center py-8">No results. Try a query above.</p>
              ) : (
                <div className="space-y-4">
                  {results.map((result, index) => (
                    <div
                      key={index}
                      className="bg-gray-700/50 rounded-lg border border-gray-600 overflow-hidden"
                    >
                      <div
                        onClick={() => toggleResultExpand(index)}
                        className="p-4 cursor-pointer hover:bg-gray-700 transition-colors"
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <span className="text-blue-400 font-medium">#{index + 1}</span>
                            {result.score && (
                              <span className="px-2 py-1 bg-green-900/50 text-green-400 text-xs rounded">
                                Score: {result.score.toFixed(3)}
                              </span>
                            )}
                          </div>
                          {expandedResults.has(index) ? (
                            <ChevronUp className="w-5 h-5 text-gray-400" />
                          ) : (
                            <ChevronDown className="w-5 h-5 text-gray-400" />
                          )}
                        </div>
                        <p className="text-gray-300 mt-2 line-clamp-2">{result.content}</p>
                      </div>
                      {expandedResults.has(index) && (
                        <div className="p-4 border-t border-gray-600 bg-gray-800/50">
                          <h4 className="text-sm font-medium text-gray-400 mb-2">Full Content</h4>
                          <p className="text-gray-300 whitespace-pre-wrap text-sm">{result.content}</p>
                          {Object.keys(result.metadata || {}).length > 0 && (
                            <>
                              <h4 className="text-sm font-medium text-gray-400 mt-4 mb-2">Metadata</h4>
                              <pre className="text-xs text-gray-400 bg-gray-900 p-3 rounded overflow-auto">
                                {JSON.stringify(result.metadata, null, 2)}
                              </pre>
                            </>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Add Document Tab */}
      {activeTab === 'add' && (
        <div className="max-w-2xl">
          <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
            <h2 className="text-xl font-semibold text-white mb-4">Add Document</h2>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Content</label>
                <textarea
                  value={docContent}
                  onChange={(e) => setDocContent(e.target.value)}
                  rows={8}
                  className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-blue-500 resize-none"
                  placeholder="Enter document content..."
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Metadata (JSON)
                </label>
                <textarea
                  value={docMetadata}
                  onChange={(e) => setDocMetadata(e.target.value)}
                  rows={3}
                  className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white font-mono text-sm placeholder-gray-400 focus:outline-none focus:border-blue-500 resize-none"
                  placeholder='{"source": "manual", "category": "example"}'
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Collection</label>
                <input
                  type="text"
                  value={docCollection}
                  onChange={(e) => setDocCollection(e.target.value)}
                  className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
                />
              </div>

              <button
                onClick={handleAddDocument}
                disabled={!docContent.trim() || adding}
                className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 disabled:cursor-not-allowed rounded-lg text-white transition-colors"
              >
                {adding ? (
                  <>
                    <div className="loading-spinner" />
                    Adding...
                  </>
                ) : (
                  <>
                    <Plus className="w-4 h-4" />
                    Add Document
                  </>
                )}
              </button>

              {addResult && (
                <div
                  className={`p-4 rounded-lg ${
                    addResult.error
                      ? 'bg-red-900/50 border border-red-700'
                      : 'bg-green-900/50 border border-green-700'
                  }`}
                >
                  <pre className="text-sm overflow-auto">
                    {JSON.stringify(addResult, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Collections Tab */}
      {activeTab === 'collections' && (
        <div className="bg-gray-800 rounded-xl border border-gray-700">
          <div className="p-6 border-b border-gray-700 flex items-center justify-between">
            <h2 className="text-xl font-semibold text-white">Collections</h2>
            <button
              onClick={fetchCollections}
              disabled={loadingCollections}
              className="flex items-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-white transition-colors"
            >
              <RefreshCw className={`w-4 h-4 ${loadingCollections ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
          <div className="p-6">
            {loadingCollections ? (
              <div className="flex justify-center py-8">
                <div className="loading-spinner" />
              </div>
            ) : collections.length === 0 ? (
              <p className="text-gray-500 text-center py-8">No collections found</p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {collections.map((col) => (
                  <div
                    key={col}
                    className="bg-gray-700/50 rounded-lg p-4 border border-gray-600 flex items-center justify-between"
                  >
                    <div className="flex items-center gap-3">
                      <Database className="w-5 h-5 text-blue-400" />
                      <span className="text-white font-medium">{col}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
