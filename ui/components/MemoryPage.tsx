'use client';

import React, { useState, useEffect } from 'react';
import {
  Brain, RefreshCw, Trash2, Edit3, Save, X, Plus, Eye,
  AlertTriangle, ChevronDown, ChevronUp, Search, BarChart3
} from 'lucide-react';
import { memoryAPI } from '../lib/api';
import { useAuth } from '../contexts/AuthContext';

interface Observation {
  id: string;
  user_id: string;
  content: string;
  importance: string;
  memory_type: string;
  facts?: string[];
  narrative?: string;
  concepts?: string[];
  confidence?: number;
  created_at: string;
  updated_at?: string;
}

interface MemoryStats {
  total_observations: number;
  by_type: Record<string, number>;
  by_importance: Record<string, number>;
}

export default function MemoryPage() {
  const { isAdmin, username } = useAuth();
  const [userId, setUserId] = useState(username || 'default');
  const [observations, setObservations] = useState<Observation[]>([]);
  const [stats, setStats] = useState<MemoryStats | null>(null);
  const [promptContext, setPromptContext] = useState<{ length: number; content: string } | null>(null);
  const [profile, setProfile] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<'dashboard' | 'observations' | 'context' | 'add'>('dashboard');

  // Edit state
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editContent, setEditContent] = useState('');
  const [editImportance, setEditImportance] = useState('medium');
  const [editType, setEditType] = useState('general');

  // Add state
  const [newContent, setNewContent] = useState('');
  const [newImportance, setNewImportance] = useState('medium');
  const [newType, setNewType] = useState('general');
  const [adding, setAdding] = useState(false);
  const [addResult, setAddResult] = useState<any>(null);

  // Expand state
  const [expandedObs, setExpandedObs] = useState<Set<string>>(new Set());
  const [showPromptContext, setShowPromptContext] = useState(false);

  const fetchDashboard = async () => {
    if (!userId.trim()) return;
    setLoading(true);
    try {
      const response = await memoryAPI.getDashboard(userId);
      const data = response.data;
      setObservations(data.observations || []);
      setStats(data.memory_stats || null);
      setPromptContext(data.prompt_context || null);
      setProfile(data.profile || null);
    } catch (err) {
      console.error('Failed to fetch memory dashboard:', err);
      setObservations([]);
      setStats(null);
    }
    setLoading(false);
  };

  useEffect(() => { fetchDashboard(); }, []);

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this memory observation?')) return;
    try {
      await memoryAPI.deleteObservation(id);
      setObservations(prev => prev.filter(o => o.id !== id));
      if (stats) setStats({ ...stats, total_observations: stats.total_observations - 1 });
    } catch (err) { console.error('Failed to delete:', err); }
  };

  const handleDeleteAll = async () => {
    if (!confirm(`⚠️ Delete ALL memory for user "${userId}"? This cannot be undone!`)) return;
    try {
      await memoryAPI.deleteAllObservations(userId);
      setObservations([]);
      setStats({ total_observations: 0, by_type: {}, by_importance: {} });
    } catch (err) { console.error('Failed to delete all:', err); }
  };

  const startEdit = (obs: Observation) => {
    setEditingId(obs.id);
    setEditContent(obs.content);
    setEditImportance(obs.importance || 'medium');
    setEditType(obs.memory_type || 'general');
  };

  const handleUpdate = async () => {
    if (!editingId || !editContent.trim()) return;
    try {
      const response = await memoryAPI.updateObservation(editingId, {
        content: editContent,
        importance: editImportance,
        memory_type: editType,
      });
      setObservations(prev => prev.map(o => o.id === editingId ? { ...o, content: editContent, importance: editImportance, memory_type: editType } : o));
      setEditingId(null);
    } catch (err) { console.error('Failed to update:', err); }
  };

  const handleAdd = async () => {
    if (!newContent.trim()) return;
    setAdding(true); setAddResult(null);
    try {
      const response = await memoryAPI.addObservation({ user_id: userId, content: newContent, importance: newImportance, memory_type: newType });
      setAddResult({ success: true, message: 'Observation added' });
      setNewContent('');
      await fetchDashboard();
    } catch (err: any) {
      setAddResult({ error: err.response?.data?.detail || err.message });
    }
    setAdding(false);
  };

  const toggleExpand = (id: string) => {
    const next = new Set(expandedObs);
    next.has(id) ? next.delete(id) : next.add(id);
    setExpandedObs(next);
  };

  const importanceColor = (imp: string) => {
    switch (imp) {
      case 'critical': return 'bg-red-900/50 text-red-400 border-red-700';
      case 'high': return 'bg-orange-900/50 text-orange-400 border-orange-700';
      case 'medium': return 'bg-yellow-900/50 text-yellow-400 border-yellow-700';
      case 'low': return 'bg-gray-700 text-gray-400 border-gray-600';
      default: return 'bg-gray-700 text-gray-400 border-gray-600';
    }
  };

  const typeIcon = (type: string) => {
    switch (type) {
      case 'preference': return '⚙️';
      case 'skill': return '🛠️';
      case 'fact': return '📌';
      case 'interaction': return '💬';
      case 'context': return '📎';
      default: return '📝';
    }
  };

  return (
    <div className="p-8 h-full overflow-y-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white flex items-center gap-3">
          <Brain className="w-8 h-8" />Memory Dashboard
        </h1>
        <p className="text-gray-400 mt-1">View and manage what the system remembers about users</p>
      </div>

      {/* User selector */}
      <div className="flex gap-3 mb-6 items-center">
        <div className="flex items-center gap-2 flex-1 max-w-md">
          <label className="text-sm text-gray-400 whitespace-nowrap">User ID:</label>
          <input type="text" value={userId} onChange={(e) => setUserId(e.target.value)} className="flex-1 px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500" placeholder="Enter user ID" />
          <button onClick={fetchDashboard} disabled={loading} className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white">
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />Load
          </button>
        </div>
      </div>

      {/* Tab buttons */}
      <div className="flex gap-2 mb-6 flex-wrap">
        <button onClick={() => setActiveTab('dashboard')} className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${activeTab === 'dashboard' ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}>
          <BarChart3 className="w-4 h-4" />Overview
        </button>
        <button onClick={() => setActiveTab('observations')} className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${activeTab === 'observations' ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}>
          <Eye className="w-4 h-4" />Observations
        </button>
        <button onClick={() => setActiveTab('context')} className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${activeTab === 'context' ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}>
          <Brain className="w-4 h-4" />Prompt Context
        </button>
        <button onClick={() => setActiveTab('add')} className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${activeTab === 'add' ? 'bg-green-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}>
          <Plus className="w-4 h-4" />Add Memory
        </button>
      </div>

      {/* ===== Dashboard Overview ===== */}
      {activeTab === 'dashboard' && (
        <div className="space-y-6">
          {loading ? (
            <div className="flex justify-center py-12"><div className="loading-spinner" /></div>
          ) : (
            <>
              {/* Stats cards */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="bg-gray-800 rounded-xl border border-gray-700 p-5">
                  <div className="text-sm text-gray-400">Total Memories</div>
                  <div className="text-3xl font-bold text-white mt-1">{stats?.total_observations ?? 0}</div>
                </div>
                <div className="bg-gray-800 rounded-xl border border-gray-700 p-5">
                  <div className="text-sm text-gray-400">Memory Types</div>
                  <div className="text-3xl font-bold text-white mt-1">{Object.keys(stats?.by_type || {}).length}</div>
                </div>
                <div className="bg-gray-800 rounded-xl border border-gray-700 p-5">
                  <div className="text-sm text-gray-400">Critical/High</div>
                  <div className="text-3xl font-bold text-orange-400 mt-1">
                    {(stats?.by_importance?.critical || 0) + (stats?.by_importance?.high || 0)}
                  </div>
                </div>
                <div className="bg-gray-800 rounded-xl border border-gray-700 p-5">
                  <div className="text-sm text-gray-400">Context Length</div>
                  <div className="text-3xl font-bold text-blue-400 mt-1">{promptContext?.length ?? 0}</div>
                  <div className="text-xs text-gray-500">chars injected</div>
                </div>
              </div>

              {/* By Type Breakdown */}
              {stats && Object.keys(stats.by_type).length > 0 && (
                <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
                  <h3 className="text-lg font-semibold text-white mb-4">By Type</h3>
                  <div className="flex flex-wrap gap-3">
                    {Object.entries(stats.by_type).map(([type, count]) => (
                      <div key={type} className="flex items-center gap-2 bg-gray-700/50 rounded-lg px-4 py-2 border border-gray-600">
                        <span className="text-lg">{typeIcon(type)}</span>
                        <span className="text-white font-medium">{type}</span>
                        <span className="px-2 py-0.5 bg-blue-900/50 text-blue-400 text-xs rounded-full">{count}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* By Importance Breakdown */}
              {stats && Object.keys(stats.by_importance).length > 0 && (
                <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
                  <h3 className="text-lg font-semibold text-white mb-4">By Importance</h3>
                  <div className="flex flex-wrap gap-3">
                    {Object.entries(stats.by_importance).map(([imp, count]) => (
                      <div key={imp} className={`flex items-center gap-2 rounded-lg px-4 py-2 border ${importanceColor(imp)}`}>
                        <span className="font-medium capitalize">{imp}</span>
                        <span className="text-xs opacity-75">{count}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              
              {/* Profile */}
              {profile && (
                <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
                  <h3 className="text-lg font-semibold text-white mb-4">User Profile</h3>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div><span className="text-gray-400">User ID:</span> <span className="text-white">{profile.user_id}</span></div>
                    <div><span className="text-gray-400">Display Name:</span> <span className="text-white">{profile.display_name || '-'}</span></div>
                    <div><span className="text-gray-400">Observations:</span> <span className="text-white">{profile.observation_count ?? 0}</span></div>
                    <div><span className="text-gray-400">Created:</span> <span className="text-white">{profile.created_at ? new Date(profile.created_at).toLocaleDateString() : '-'}</span></div>
                  </div>
                  {profile.preferences && Object.keys(profile.preferences).length > 0 && (
                    <div className="mt-4">
                      <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">Preferences</span>
                      <pre className="text-xs text-gray-400 bg-gray-900 p-3 rounded mt-1 overflow-auto max-h-40">{JSON.stringify(profile.preferences, null, 2)}</pre>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* ===== Observations List ===== */}
      {activeTab === 'observations' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold text-white">All Observations ({observations.length})</h2>
            <button onClick={handleDeleteAll} disabled={observations.length === 0 || !isAdmin} className="flex items-center gap-2 px-4 py-2 bg-red-600/20 hover:bg-red-600/40 border border-red-700 rounded-lg text-red-400 text-sm">
              <Trash2 className="w-4 h-4" />Delete All
            </button>
          </div>

          {loading ? (
            <div className="flex justify-center py-8"><div className="loading-spinner" /></div>
          ) : observations.length === 0 ? (
            <div className="bg-gray-800 rounded-xl border border-gray-700 p-12 text-center">
              <Brain className="w-12 h-12 text-gray-600 mx-auto mb-4" />
              <p className="text-gray-400">No memory observations for this user</p>
              <p className="text-gray-500 text-sm mt-1">Memories are captured automatically from conversations</p>
            </div>
          ) : (
            <div className="space-y-3">
              {observations.map((obs) => (
                <div key={obs.id} className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
                  {editingId === obs.id ? (
                    /* Edit mode */
                    <div className="p-5 space-y-3">
                      <textarea value={editContent} onChange={(e) => setEditContent(e.target.value)} rows={3} className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white resize-none focus:outline-none focus:border-blue-500" />
                      <div className="flex gap-3">
                        <select value={editImportance} onChange={(e) => setEditImportance(e.target.value)} className="px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white text-sm">
                          <option value="low">Low</option>
                          <option value="medium">Medium</option>
                          <option value="high">High</option>
                          <option value="critical">Critical</option>
                        </select>
                        <select value={editType} onChange={(e) => setEditType(e.target.value)} className="px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white text-sm">
                          <option value="general">General</option>
                          <option value="preference">Preference</option>
                          <option value="skill">Skill</option>
                          <option value="fact">Fact</option>
                          <option value="interaction">Interaction</option>
                          <option value="context">Context</option>
                        </select>
                        <div className="flex-1" />
                        <button onClick={handleUpdate} className="flex items-center gap-1 px-4 py-2 bg-green-600 hover:bg-green-700 rounded-lg text-white text-sm"><Save className="w-4 h-4" />Save</button>
                        <button onClick={() => setEditingId(null)} className="flex items-center gap-1 px-4 py-2 bg-gray-600 hover:bg-gray-500 rounded-lg text-white text-sm"><X className="w-4 h-4" />Cancel</button>
                      </div>
                    </div>
                  ) : (
                    /* View mode */
                    <div className="p-5">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-2 flex-wrap">
                            <span className="text-lg">{typeIcon(obs.memory_type)}</span>
                            <span className={`px-2 py-0.5 text-xs rounded border ${importanceColor(obs.importance)}`}>{obs.importance}</span>
                            <span className="px-2 py-0.5 bg-gray-700 text-gray-400 text-xs rounded">{obs.memory_type}</span>
                            <span className="text-xs text-gray-500 ml-auto">{obs.created_at ? new Date(obs.created_at).toLocaleString() : ''}</span>
                          </div>
                          <p className="text-gray-200 text-sm leading-relaxed cursor-pointer" onClick={() => toggleExpand(obs.id)}>
                            {expandedObs.has(obs.id) ? obs.content : obs.content.length > 200 ? obs.content.slice(0, 200) + '...' : obs.content}
                          </p>
                          {expandedObs.has(obs.id) && (
                            <div className="mt-3 space-y-2">
                              {obs.facts && obs.facts.length > 0 && (
                                <div><span className="text-xs text-gray-500">Facts:</span><div className="flex flex-wrap gap-1 mt-1">{obs.facts.map((f, i) => <span key={i} className="px-2 py-0.5 bg-blue-900/30 text-blue-300 text-xs rounded">{f}</span>)}</div></div>
                              )}
                              {obs.concepts && obs.concepts.length > 0 && (
                                <div><span className="text-xs text-gray-500">Concepts:</span><div className="flex flex-wrap gap-1 mt-1">{obs.concepts.map((c, i) => <span key={i} className="px-2 py-0.5 bg-purple-900/30 text-purple-300 text-xs rounded">{c}</span>)}</div></div>
                              )}
                              {obs.confidence !== undefined && obs.confidence !== null && (
                                <div className="text-xs text-gray-500">Confidence: <span className="text-white">{(obs.confidence * 100).toFixed(0)}%</span></div>
                              )}
                            </div>
                          )}
                        </div>
                        <div className="flex gap-1 shrink-0">
                          <button onClick={() => startEdit(obs)} className="p-2 hover:bg-gray-700 rounded text-gray-400 hover:text-white"><Edit3 className="w-4 h-4" /></button>
                          <button onClick={() => handleDelete(obs.id)} className="p-2 hover:bg-red-600/20 rounded text-gray-400 hover:text-red-400"><Trash2 className="w-4 h-4" /></button>
                          <button onClick={() => toggleExpand(obs.id)} className="p-2 hover:bg-gray-700 rounded text-gray-400">
                            {expandedObs.has(obs.id) ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ===== Prompt Context ===== */}
      {activeTab === 'context' && (
        <div className="space-y-6">
          <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-xl font-semibold text-white flex items-center gap-2">
                  <Brain className="w-5 h-5 text-blue-400" />Injected Prompt Context
                </h2>
                <p className="text-gray-400 text-sm mt-1">This text is injected into every agent's system prompt for this user</p>
              </div>
              {promptContext && <span className="text-sm text-gray-500">{promptContext.length} characters</span>}
            </div>
            {promptContext && promptContext.content ? (
              <div className="bg-gray-900 rounded-lg border border-gray-700 p-4 max-h-[500px] overflow-y-auto">
                <pre className="text-sm text-gray-300 whitespace-pre-wrap font-mono leading-relaxed">{promptContext.content}</pre>
              </div>
            ) : (
              <div className="text-center py-12">
                <Brain className="w-12 h-12 text-gray-600 mx-auto mb-4" />
                <p className="text-gray-400">No prompt context generated yet</p>
                <p className="text-gray-500 text-sm mt-1">Context builds automatically from stored memories</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ===== Add Memory ===== */}
      {activeTab === 'add' && (
        <div className="max-w-2xl">
          <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
            <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
              <Plus className="w-5 h-5 text-green-400" />Add Memory Observation
            </h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Content</label>
                <textarea value={newContent} onChange={(e) => setNewContent(e.target.value)} rows={4} className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white resize-none focus:outline-none focus:border-blue-500" placeholder="What should the system remember about this user?" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">Importance</label>
                  <select value={newImportance} onChange={(e) => setNewImportance(e.target.value)} className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white">
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="critical">Critical</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">Memory Type</label>
                  <select value={newType} onChange={(e) => setNewType(e.target.value)} className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white">
                    <option value="general">General</option>
                    <option value="preference">Preference</option>
                    <option value="skill">Skill</option>
                    <option value="fact">Fact</option>
                    <option value="interaction">Interaction</option>
                    <option value="context">Context</option>
                  </select>
                </div>
              </div>
              <button onClick={handleAdd} disabled={!newContent.trim() || adding} className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 rounded-lg text-white font-medium">
                {adding ? <><RefreshCw className="w-4 h-4 animate-spin" />Adding...</> : <><Plus className="w-4 h-4" />Add Observation</>}
              </button>
              {addResult && (
                <div className={`p-4 rounded-lg text-sm ${addResult.error ? 'bg-red-900/50 border border-red-700 text-red-300' : 'bg-green-900/50 border border-green-700 text-green-300'}`}>
                  {addResult.error ? `Error: ${addResult.error}` : 'Memory observation added successfully!'}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
