'use client';

import React, { useState, useEffect } from 'react';
import {
  Database, Search, FileText, Plus, Trash2, RefreshCw,
  ChevronDown, ChevronUp, Eye, FolderOpen
} from 'lucide-react';
import { ragAPI } from '../lib/api';

interface QueryResult { content: string; metadata: Record<string, any>; score?: number; }
interface Document { id: string; content: string; preview: string; metadata: Record<string, any>; }
interface DatabaseInfo { name: string; description?: string; document_count?: number; category?: string; }

export default function RAGPage() {
  const [activeTab, setActiveTab] = useState<'query' | 'add' | 'databases' | 'documents'>('databases');
  const [queryText, setQueryText] = useState('');
  const [collection, setCollection] = useState('default');
  const [topK, setTopK] = useState(5);
  const [results, setResults] = useState<QueryResult[]>([]);
  const [querying, setQuerying] = useState(false);
  const [docContent, setDocContent] = useState('');
  const [docTitle, setDocTitle] = useState('');
  const [docCategory, setDocCategory] = useState('general');
  const [selectedDb, setSelectedDb] = useState('');
  const [adding, setAdding] = useState(false);
  const [addResult, setAddResult] = useState<any>(null);
  const [summarizeOnAdd, setSummarizeOnAdd] = useState(true);
  const [databases, setDatabases] = useState<DatabaseInfo[]>([]);
  const [loadingDatabases, setLoadingDatabases] = useState(false);
  const [newDbName, setNewDbName] = useState('');
  const [newDbDesc, setNewDbDesc] = useState('');
  const [creatingDb, setCreatingDb] = useState(false);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [viewingDb, setViewingDb] = useState('');
  const [expandedResults, setExpandedResults] = useState<Set<number>>(new Set());
  const [expandedDocs, setExpandedDocs] = useState<Set<string>>(new Set());

  useEffect(() => { fetchDatabases(); }, []);

  const fetchDatabases = async () => {
    setLoadingDatabases(true);
    try {
      const response = await ragAPI.listDatabases();
      setDatabases(response.data.databases || []);
    } catch (err) { console.error('Failed to fetch databases:', err); }
    setLoadingDatabases(false);
  };

  const handleQuery = async () => {
    if (!queryText.trim()) return;
    setQuerying(true); setResults([]);
    try {
      const response = await ragAPI.query({ query: queryText, collection, top_k: topK });
      setResults(response.data.results || []);
    } catch (err) { console.error('Query failed:', err); }
    setQuerying(false);
  };

  const handleAddDocument = async () => {
    if (!docContent.trim() || !selectedDb) return;
    setAdding(true); setAddResult(null);
    try {
      const response = await ragAPI.insertDocument({ database: selectedDb, content: docContent, title: docTitle, category: docCategory, summarize: summarizeOnAdd });
      setAddResult(response.data); setDocContent(''); setDocTitle(''); fetchDatabases();
    } catch (err: any) { setAddResult({ error: err.response?.data?.detail || err.message }); }
    setAdding(false);
  };

  const handleCreateDatabase = async () => {
    if (!newDbName.trim()) return;
    setCreatingDb(true);
    try { await ragAPI.createDatabase({ name: newDbName, description: newDbDesc }); setNewDbName(''); setNewDbDesc(''); fetchDatabases(); }
    catch (err) { console.error('Failed to create database:', err); }
    setCreatingDb(false);
  };

  const handleDeleteDatabase = async (dbName: string) => {
    if (!confirm(`Delete database "${dbName}"?`)) return;
    try { await ragAPI.deleteDatabase(dbName); fetchDatabases(); if (viewingDb === dbName) { setViewingDb(''); setDocuments([]); } }
    catch (err) { console.error('Failed to delete:', err); }
  };

  const fetchDocuments = async (dbName: string) => {
    setLoadingDocs(true); setViewingDb(dbName);
    try { const r = await ragAPI.listDocuments(dbName, 100); setDocuments(r.data.documents || []); setActiveTab('documents'); }
    catch (err) { console.error('Failed:', err); setDocuments([]); }
    setLoadingDocs(false);
  };

  const handleDeleteDocument = async (docId: string) => {
    if (!confirm('Delete this document?')) return;
    try { await ragAPI.deleteDocument(viewingDb, docId); setDocuments(documents.filter(d => d.id !== docId)); fetchDatabases(); }
    catch (err) { console.error('Failed:', err); }
  };

  const toggleResultExpand = (i: number) => { const n = new Set(expandedResults); n.has(i) ? n.delete(i) : n.add(i); setExpandedResults(n); };
  const toggleDocExpand = (id: string) => { const n = new Set(expandedDocs); n.has(id) ? n.delete(id) : n.add(id); setExpandedDocs(n); };

  return (
    <div className="p-8 h-full overflow-y-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white flex items-center gap-3"><Database className="w-8 h-8" />RAG Vector Database</h1>
        <p className="text-gray-400 mt-1">Manage vector databases, documents, and queries</p>
      </div>

      <div className="flex gap-2 mb-6 flex-wrap">
        {[{ id: 'databases', label: 'Databases', icon: FolderOpen }, { id: 'documents', label: 'Documents', icon: FileText }, { id: 'query', label: 'Query', icon: Search }, { id: 'add', label: 'Add Document', icon: Plus }].map(({ id, label, icon: Icon }) => (
          <button key={id} onClick={() => setActiveTab(id as any)} className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${activeTab === id ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}>
            <Icon className="w-4 h-4" />{label}
          </button>
        ))}
      </div>

      {activeTab === 'databases' && (
        <div className="space-y-6">
          <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
            <h2 className="text-xl font-semibold text-white mb-4">Create New Database</h2>
            <div className="flex gap-4 flex-wrap">
              <input type="text" value={newDbName} onChange={(e) => setNewDbName(e.target.value)} placeholder="Database name" className="flex-1 min-w-[200px] px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500" />
              <input type="text" value={newDbDesc} onChange={(e) => setNewDbDesc(e.target.value)} placeholder="Description" className="flex-1 min-w-[200px] px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500" />
              <button onClick={handleCreateDatabase} disabled={!newDbName.trim() || creatingDb} className="flex items-center gap-2 px-6 py-3 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 rounded-lg text-white">{creatingDb ? <div className="loading-spinner" /> : <Plus className="w-4 h-4" />}Create</button>
            </div>
          </div>
          <div className="bg-gray-800 rounded-xl border border-gray-700">
            <div className="p-6 border-b border-gray-700 flex items-center justify-between">
              <h2 className="text-xl font-semibold text-white">Databases ({databases.length})</h2>
              <button onClick={fetchDatabases} disabled={loadingDatabases} className="flex items-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-white"><RefreshCw className={`w-4 h-4 ${loadingDatabases ? 'animate-spin' : ''}`} />Refresh</button>
            </div>
            <div className="p-6">
              {loadingDatabases ? <div className="flex justify-center py-8"><div className="loading-spinner" /></div> : databases.length === 0 ? <p className="text-gray-500 text-center py-8">No databases found.</p> : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {databases.map((db) => (
                    <div key={db.name} className="bg-gray-700/50 rounded-lg p-4 border border-gray-600">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-3"><Database className="w-5 h-5 text-blue-400" /><span className="text-white font-medium">{db.name}</span></div>
                        <div className="flex gap-2">
                          <button onClick={() => fetchDocuments(db.name)} className="p-2 hover:bg-gray-600 rounded text-gray-400 hover:text-white"><Eye className="w-4 h-4" /></button>
                          <button onClick={() => handleDeleteDatabase(db.name)} className="p-2 hover:bg-red-600/20 rounded text-gray-400 hover:text-red-400"><Trash2 className="w-4 h-4" /></button>
                        </div>
                      </div>
                      {db.description && <p className="text-sm text-gray-400 mb-2">{db.description}</p>}
                      <div className="flex gap-2 text-xs">{db.document_count !== undefined && <span className="px-2 py-1 bg-blue-900/50 text-blue-400 rounded">{db.document_count} docs</span>}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {activeTab === 'documents' && (
        <div className="bg-gray-800 rounded-xl border border-gray-700">
          <div className="p-6 border-b border-gray-700 flex items-center justify-between">
            <div><h2 className="text-xl font-semibold text-white">Documents {viewingDb && <span className="text-blue-400">- {viewingDb}</span>}</h2><p className="text-sm text-gray-400 mt-1">{documents.length} documents</p></div>
            <div className="flex gap-2">
              <select value={viewingDb} onChange={(e) => e.target.value && fetchDocuments(e.target.value)} className="px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white"><option value="">Select Database</option>{databases.map(db => <option key={db.name} value={db.name}>{db.name}</option>)}</select>
              <button onClick={() => viewingDb && fetchDocuments(viewingDb)} disabled={loadingDocs || !viewingDb} className="flex items-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-white"><RefreshCw className={`w-4 h-4 ${loadingDocs ? 'animate-spin' : ''}`} /></button>
            </div>
          </div>
          <div className="p-6 max-h-[600px] overflow-y-auto">
            {loadingDocs ? <div className="flex justify-center py-8"><div className="loading-spinner" /></div> : !viewingDb ? <p className="text-gray-500 text-center py-8">Select a database</p> : documents.length === 0 ? <p className="text-gray-500 text-center py-8">No documents</p> : (
              <div className="space-y-3">
                {documents.map((doc) => (
                  <div key={doc.id} className="bg-gray-700/50 rounded-lg border border-gray-600 overflow-hidden">
                    <div onClick={() => toggleDocExpand(doc.id)} className="p-4 cursor-pointer hover:bg-gray-700">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3"><FileText className="w-4 h-4 text-gray-400" /><span className="text-xs text-gray-500 font-mono">{doc.id.slice(0, 12)}...</span>{doc.metadata?.title && <span className="text-white font-medium">{doc.metadata.title}</span>}</div>
                        <div className="flex items-center gap-2"><button onClick={(e) => { e.stopPropagation(); handleDeleteDocument(doc.id); }} className="p-2 hover:bg-red-600/20 rounded text-gray-400 hover:text-red-400"><Trash2 className="w-4 h-4" /></button>{expandedDocs.has(doc.id) ? <ChevronUp className="w-5 h-5 text-gray-400" /> : <ChevronDown className="w-5 h-5 text-gray-400" />}</div>
                      </div>
                      <p className="text-gray-300 mt-2 text-sm line-clamp-2">{doc.preview}</p>
                    </div>
                    {expandedDocs.has(doc.id) && <div className="p-4 border-t border-gray-600 bg-gray-800/50"><h4 className="text-sm font-medium text-gray-400 mb-2">Full Content</h4><p className="text-gray-300 whitespace-pre-wrap text-sm max-h-[300px] overflow-y-auto">{doc.content}</p>{Object.keys(doc.metadata || {}).length > 0 && <><h4 className="text-sm font-medium text-gray-400 mt-4 mb-2">Metadata</h4><pre className="text-xs text-gray-400 bg-gray-900 p-3 rounded overflow-auto">{JSON.stringify(doc.metadata, null, 2)}</pre></>}</div>}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'query' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
            <h2 className="text-xl font-semibold text-white mb-4">Query Documents</h2>
            <div className="space-y-4">
              <div><label className="block text-sm font-medium text-gray-300 mb-2">Query</label><textarea value={queryText} onChange={(e) => setQueryText(e.target.value)} rows={4} className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white resize-none" placeholder="Enter query..." /></div>
              <div className="grid grid-cols-2 gap-4">
                <div><label className="block text-sm font-medium text-gray-300 mb-2">Collection</label><input type="text" value={collection} onChange={(e) => setCollection(e.target.value)} className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white" /></div>
                <div><label className="block text-sm font-medium text-gray-300 mb-2">Top K</label><input type="number" value={topK} onChange={(e) => setTopK(parseInt(e.target.value) || 5)} min={1} max={20} className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white" /></div>
              </div>
              <button onClick={handleQuery} disabled={!queryText.trim() || querying} className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 rounded-lg text-white">{querying ? <><div className="loading-spinner" />Searching...</> : <><Search className="w-4 h-4" />Search</>}</button>
            </div>
          </div>
          <div className="lg:col-span-2 bg-gray-800 rounded-xl border border-gray-700">
            <div className="p-6 border-b border-gray-700"><h2 className="text-xl font-semibold text-white">Results ({results.length})</h2></div>
            <div className="p-6 max-h-[600px] overflow-y-auto">
              {querying ? <div className="flex justify-center py-8"><div className="loading-spinner" /></div> : results.length === 0 ? <p className="text-gray-500 text-center py-8">No results</p> : (
                <div className="space-y-4">
                  {results.map((result, i) => (
                    <div key={i} className="bg-gray-700/50 rounded-lg border border-gray-600 overflow-hidden">
                      <div onClick={() => toggleResultExpand(i)} className="p-4 cursor-pointer hover:bg-gray-700">
                        <div className="flex items-center justify-between"><div className="flex items-center gap-3"><span className="text-blue-400 font-medium">#{i + 1}</span>{result.score && <span className="px-2 py-1 bg-green-900/50 text-green-400 text-xs rounded">Score: {result.score.toFixed(3)}</span>}</div>{expandedResults.has(i) ? <ChevronUp className="w-5 h-5 text-gray-400" /> : <ChevronDown className="w-5 h-5 text-gray-400" />}</div>
                        <p className="text-gray-300 mt-2 line-clamp-2">{result.content}</p>
                      </div>
                      {expandedResults.has(i) && <div className="p-4 border-t border-gray-600 bg-gray-800/50"><h4 className="text-sm font-medium text-gray-400 mb-2">Full Content</h4><p className="text-gray-300 whitespace-pre-wrap text-sm">{result.content}</p>{Object.keys(result.metadata || {}).length > 0 && <><h4 className="text-sm font-medium text-gray-400 mt-4 mb-2">Metadata</h4><pre className="text-xs text-gray-400 bg-gray-900 p-3 rounded overflow-auto">{JSON.stringify(result.metadata, null, 2)}</pre></>}</div>}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {activeTab === 'add' && (
        <div className="max-w-2xl">
          <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
            <h2 className="text-xl font-semibold text-white mb-4">Add Document</h2>
            <div className="space-y-4">
              <div><label className="block text-sm font-medium text-gray-300 mb-2">Target Database</label><select value={selectedDb} onChange={(e) => setSelectedDb(e.target.value)} className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white"><option value="">Select database</option>{databases.map(db => <option key={db.name} value={db.name}>{db.name}</option>)}</select></div>
              <div><label className="block text-sm font-medium text-gray-300 mb-2">Title</label><input type="text" value={docTitle} onChange={(e) => setDocTitle(e.target.value)} className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white" placeholder="Document title" /></div>
              <div><label className="block text-sm font-medium text-gray-300 mb-2">Content</label><textarea value={docContent} onChange={(e) => setDocContent(e.target.value)} rows={10} className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white resize-none" placeholder="Enter content..." /></div>
              <div className="grid grid-cols-2 gap-4">
                <div><label className="block text-sm font-medium text-gray-300 mb-2">Category</label><input type="text" value={docCategory} onChange={(e) => setDocCategory(e.target.value)} className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white" /></div>
                <div className="flex items-center pt-8"><label className="flex items-center gap-2 cursor-pointer"><input type="checkbox" checked={summarizeOnAdd} onChange={(e) => setSummarizeOnAdd(e.target.checked)} className="w-4 h-4 rounded" /><span className="text-gray-300">Summarize</span></label></div>
              </div>
              <button onClick={handleAddDocument} disabled={!docContent.trim() || !selectedDb || adding} className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 rounded-lg text-white">{adding ? <><div className="loading-spinner" />Adding...</> : <><Plus className="w-4 h-4" />Add Document</>}</button>
              {addResult && <div className={`p-4 rounded-lg ${addResult.error ? 'bg-red-900/50 border border-red-700' : 'bg-green-900/50 border border-green-700'}`}><pre className="text-sm overflow-auto text-white">{JSON.stringify(addResult, null, 2)}</pre></div>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
