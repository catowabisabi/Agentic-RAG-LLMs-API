'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { toolsAPI } from '../lib/api';
import {
  Calculator,
  FileText,
  FolderOpen,
  ScanLine,
  FileSpreadsheet,
  Plus,
  RefreshCw,
  Check,
  X,
  ArrowRightLeft,
  AlertTriangle,
  Download,
  Eye,
  Trash2,
} from 'lucide-react';

// ============================================================
// Types
// ============================================================

interface Account {
  id: number;
  name: string;
  type: string;
  currency: string;
  balance: number;
  balance_display?: number;
  description: string;
  created_at: string;
}

interface Transaction {
  id: number;
  account_id: number;
  type: string;
  amount: number;
  amount_display?: number;
  description: string;
  reference: string;
  counterparty: string;
  category: string;
  status: string;
  transaction_date: string;
  created_at: string;
}

interface OCRResult {
  result_id: string;
  filename: string;
  text: string;
  confidence: number;
  mock: boolean;
  timestamp: string;
}

interface Report {
  report_id: string;
  title: string;
  format: string;
  file_name: string;
  file_path: string;
  created_at: string;
}

// ============================================================
// Sub-tabs
// ============================================================

type TabKey = 'accounting' | 'ocr' | 'reports' | 'files';

const TABS: { key: TabKey; label: string; icon: React.ReactNode }[] = [
  { key: 'accounting', label: 'Accounting', icon: <Calculator className="w-4 h-4" /> },
  { key: 'ocr', label: 'OCR', icon: <ScanLine className="w-4 h-4" /> },
  { key: 'reports', label: 'Reports', icon: <FileText className="w-4 h-4" /> },
  { key: 'files', label: 'Files', icon: <FolderOpen className="w-4 h-4" /> },
];

// ============================================================
// Main component
// ============================================================

export default function ToolsPage() {
  const [activeTab, setActiveTab] = useState<TabKey>('accounting');

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-white flex items-center gap-2">
        <FileSpreadsheet className="w-7 h-7 text-blue-400" /> Tools &amp; Accounting
      </h1>

      {/* Tab bar */}
      <div className="flex gap-2 border-b border-gray-700 pb-2">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setActiveTab(t.key)}
            className={`flex items-center gap-2 px-4 py-2 rounded-t-lg text-sm font-medium transition-colors ${
              activeTab === t.key
                ? 'bg-gray-700 text-white border-b-2 border-blue-400'
                : 'text-gray-400 hover:text-white hover:bg-gray-800'
            }`}
          >
            {t.icon}
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div>
        {activeTab === 'accounting' && <AccountingTab />}
        {activeTab === 'ocr' && <OCRTab />}
        {activeTab === 'reports' && <ReportsTab />}
        {activeTab === 'files' && <FilesTab />}
      </div>
    </div>
  );
}

// ============================================================
// ACCOUNTING TAB
// ============================================================

function AccountingTab() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [selectedAccount, setSelectedAccount] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // --- forms ---
  const [showCreateAccount, setShowCreateAccount] = useState(false);
  const [newAcctName, setNewAcctName] = useState('');
  const [newAcctType, setNewAcctType] = useState('general');
  const [newAcctCurrency, setNewAcctCurrency] = useState('HKD');

  const [showAddTxn, setShowAddTxn] = useState(false);
  const [txnType, setTxnType] = useState('expense');
  const [txnAmount, setTxnAmount] = useState('');
  const [txnDesc, setTxnDesc] = useState('');
  const [txnRef, setTxnRef] = useState('');
  const [txnCounterparty, setTxnCounterparty] = useState('');
  const [txnCategory, setTxnCategory] = useState('');

  const [dashboard, setDashboard] = useState<any>(null);

  // selection for reconcile
  const [selectedTxns, setSelectedTxns] = useState<Set<number>>(new Set());

  const loadAccounts = useCallback(async () => {
    try {
      const res = await toolsAPI.listAccounts();
      setAccounts(res.data.accounts || []);
    } catch {
      /* ignore */
    }
  }, []);

  const loadDashboard = useCallback(async () => {
    try {
      const res = await toolsAPI.getDashboard();
      setDashboard(res.data);
    } catch {
      /* ignore */
    }
  }, []);

  const loadTransactions = useCallback(async (acctId?: number) => {
    setLoading(true);
    try {
      const res = await toolsAPI.listTransactions({
        account_id: acctId || undefined,
        limit: 200,
      });
      setTransactions(res.data.transactions || []);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAccounts();
    loadDashboard();
    loadTransactions();
  }, [loadAccounts, loadDashboard, loadTransactions]);

  const createAccount = async () => {
    if (!newAcctName.trim()) return;
    setError('');
    try {
      await toolsAPI.createAccount({
        name: newAcctName,
        account_type: newAcctType,
        currency: newAcctCurrency,
      });
      setNewAcctName('');
      setShowCreateAccount(false);
      await loadAccounts();
      await loadDashboard();
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Failed to create account');
    }
  };

  const addTransaction = async () => {
    if (!selectedAccount || !txnAmount) return;
    setError('');
    try {
      await toolsAPI.addTransaction({
        account_id: selectedAccount,
        type: txnType,
        amount: parseFloat(txnAmount),
        description: txnDesc,
        reference: txnRef,
        counterparty: txnCounterparty,
        category: txnCategory,
      });
      setTxnAmount('');
      setTxnDesc('');
      setTxnRef('');
      setTxnCounterparty('');
      setTxnCategory('');
      setShowAddTxn(false);
      await loadTransactions(selectedAccount);
      await loadAccounts();
      await loadDashboard();
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Failed to add transaction');
    }
  };

  const reconcileSelected = async () => {
    if (selectedTxns.size === 0) return;
    try {
      await toolsAPI.reconcileTransactions({
        transaction_ids: Array.from(selectedTxns),
      });
      setSelectedTxns(new Set());
      await loadTransactions(selectedAccount || undefined);
    } catch {
      /* ignore */
    }
  };

  const voidTxn = async (id: number) => {
    try {
      await toolsAPI.voidTransaction({ transaction_id: id });
      await loadTransactions(selectedAccount || undefined);
      await loadAccounts();
      await loadDashboard();
    } catch {
      /* ignore */
    }
  };

  const toggleTxnSelection = (id: number) => {
    setSelectedTxns((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div className="space-y-4">
      {error && (
        <div className="p-3 bg-red-900/50 border border-red-700 rounded text-red-300 text-sm flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" /> {error}
        </div>
      )}

      {/* Dashboard cards */}
      {dashboard && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard label="Accounts" value={dashboard.account_count} />
          <StatCard label="Total Txns" value={dashboard.total_transactions} />
          <StatCard label="Pending" value={dashboard.pending_transactions} color="yellow" />
          <StatCard label="Reconciled" value={dashboard.reconciled_transactions} color="green" />
        </div>
      )}

      {/* Accounts bar */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-sm text-gray-400 font-medium">Accounts:</span>
        <button
          onClick={() => {
            setSelectedAccount(null);
            loadTransactions();
          }}
          className={`px-3 py-1 rounded text-xs font-medium ${
            !selectedAccount ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
          }`}
        >
          All
        </button>
        {accounts.map((a) => (
          <button
            key={a.id}
            onClick={() => {
              setSelectedAccount(a.id);
              loadTransactions(a.id);
            }}
            className={`px-3 py-1 rounded text-xs font-medium ${
              selectedAccount === a.id ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
          >
            {a.name} (${((a.balance_display ?? a.balance / 100)).toFixed(2)})
          </button>
        ))}
        <button onClick={() => setShowCreateAccount(!showCreateAccount)} className="p-1 rounded hover:bg-gray-700 text-blue-400">
          <Plus className="w-4 h-4" />
        </button>
        <button onClick={() => { loadAccounts(); loadDashboard(); loadTransactions(selectedAccount || undefined); }} className="p-1 rounded hover:bg-gray-700 text-gray-400">
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Create account form */}
      {showCreateAccount && (
        <div className="bg-gray-800 p-4 rounded-lg space-y-3">
          <h3 className="text-white font-medium text-sm">New Account</h3>
          <div className="grid grid-cols-3 gap-3">
            <input value={newAcctName} onChange={(e) => setNewAcctName(e.target.value)} placeholder="Account name" className="bg-gray-700 text-white text-sm px-3 py-2 rounded" />
            <select value={newAcctType} onChange={(e) => setNewAcctType(e.target.value)} className="bg-gray-700 text-white text-sm px-3 py-2 rounded">
              <option value="general">General</option>
              <option value="bank">Bank</option>
              <option value="cash">Cash</option>
              <option value="receivable">Receivable</option>
              <option value="payable">Payable</option>
            </select>
            <select value={newAcctCurrency} onChange={(e) => setNewAcctCurrency(e.target.value)} className="bg-gray-700 text-white text-sm px-3 py-2 rounded">
              <option value="HKD">HKD</option>
              <option value="USD">USD</option>
              <option value="CNY">CNY</option>
              <option value="GBP">GBP</option>
              <option value="EUR">EUR</option>
            </select>
          </div>
          <button onClick={createAccount} className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700">Create</button>
        </div>
      )}

      {/* Action buttons */}
      <div className="flex gap-2">
        {selectedAccount && (
          <button onClick={() => setShowAddTxn(!showAddTxn)} className="px-3 py-1.5 bg-green-600 text-white rounded text-xs hover:bg-green-700 flex items-center gap-1">
            <Plus className="w-3 h-3" /> Add Transaction
          </button>
        )}
        {selectedTxns.size > 0 && (
          <button onClick={reconcileSelected} className="px-3 py-1.5 bg-blue-600 text-white rounded text-xs hover:bg-blue-700 flex items-center gap-1">
            <Check className="w-3 h-3" /> Reconcile ({selectedTxns.size})
          </button>
        )}
      </div>

      {/* Add transaction form */}
      {showAddTxn && selectedAccount && (
        <div className="bg-gray-800 p-4 rounded-lg space-y-3">
          <h3 className="text-white font-medium text-sm">New Transaction</h3>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            <select value={txnType} onChange={(e) => setTxnType(e.target.value)} className="bg-gray-700 text-white text-sm px-3 py-2 rounded">
              <option value="income">Income</option>
              <option value="expense">Expense</option>
              <option value="transfer">Transfer</option>
              <option value="adjustment">Adjustment</option>
            </select>
            <input value={txnAmount} onChange={(e) => setTxnAmount(e.target.value)} placeholder="Amount" type="number" step="0.01" className="bg-gray-700 text-white text-sm px-3 py-2 rounded" />
            <input value={txnDesc} onChange={(e) => setTxnDesc(e.target.value)} placeholder="Description" className="bg-gray-700 text-white text-sm px-3 py-2 rounded" />
            <input value={txnRef} onChange={(e) => setTxnRef(e.target.value)} placeholder="Reference #" className="bg-gray-700 text-white text-sm px-3 py-2 rounded" />
            <input value={txnCounterparty} onChange={(e) => setTxnCounterparty(e.target.value)} placeholder="Counterparty" className="bg-gray-700 text-white text-sm px-3 py-2 rounded" />
            <input value={txnCategory} onChange={(e) => setTxnCategory(e.target.value)} placeholder="Category" className="bg-gray-700 text-white text-sm px-3 py-2 rounded" />
          </div>
          <button onClick={addTransaction} className="px-4 py-2 bg-green-600 text-white rounded text-sm hover:bg-green-700">Add</button>
        </div>
      )}

      {/* Transactions table */}
      <div className="bg-gray-800 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-750 text-gray-400">
              <th className="px-3 py-2 text-left w-8"></th>
              <th className="px-3 py-2 text-left">ID</th>
              <th className="px-3 py-2 text-left">Date</th>
              <th className="px-3 py-2 text-left">Type</th>
              <th className="px-3 py-2 text-right">Amount</th>
              <th className="px-3 py-2 text-left">Description</th>
              <th className="px-3 py-2 text-left">Counterparty</th>
              <th className="px-3 py-2 text-center">Status</th>
              <th className="px-3 py-2 text-center">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={9} className="text-center py-8 text-gray-500">Loading...</td></tr>
            ) : transactions.length === 0 ? (
              <tr><td colSpan={9} className="text-center py-8 text-gray-500">No transactions yet</td></tr>
            ) : (
              transactions.map((txn) => {
                const amt = txn.amount_display ?? txn.amount / 100;
                return (
                  <tr key={txn.id} className="border-t border-gray-700 hover:bg-gray-750">
                    <td className="px-3 py-2">
                      {txn.status === 'pending' && (
                        <input
                          type="checkbox"
                          checked={selectedTxns.has(txn.id)}
                          onChange={() => toggleTxnSelection(txn.id)}
                          className="rounded"
                        />
                      )}
                    </td>
                    <td className="px-3 py-2 text-gray-400 font-mono">{txn.id}</td>
                    <td className="px-3 py-2 text-gray-300">{txn.transaction_date}</td>
                    <td className="px-3 py-2">
                      <span className={`px-2 py-0.5 rounded text-xs ${txn.type === 'income' ? 'bg-green-900/50 text-green-400' : txn.type === 'expense' ? 'bg-red-900/50 text-red-400' : 'bg-blue-900/50 text-blue-400'}`}>
                        {txn.type}
                      </span>
                    </td>
                    <td className={`px-3 py-2 text-right font-mono ${txn.type === 'income' ? 'text-green-400' : 'text-red-400'}`}>
                      {txn.type === 'income' ? '+' : '-'}${Math.abs(amt).toFixed(2)}
                    </td>
                    <td className="px-3 py-2 text-gray-300 truncate max-w-[200px]">{txn.description}</td>
                    <td className="px-3 py-2 text-gray-400 truncate max-w-[120px]">{txn.counterparty}</td>
                    <td className="px-3 py-2 text-center">
                      <span className={`px-2 py-0.5 rounded text-xs ${
                        txn.status === 'reconciled' ? 'bg-green-900/50 text-green-400'
                          : txn.status === 'voided' ? 'bg-gray-600 text-gray-300'
                          : 'bg-yellow-900/50 text-yellow-400'
                      }`}>
                        {txn.status}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-center">
                      {txn.status === 'pending' && (
                        <button onClick={() => voidTxn(txn.id)} className="text-red-400 hover:text-red-300" title="Void">
                          <X className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ============================================================
// OCR TAB
// ============================================================

function OCRTab() {
  const [filePath, setFilePath] = useState('');
  const [results, setResults] = useState<OCRResult[]>([]);
  const [currentResult, setCurrentResult] = useState<OCRResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const loadResults = async () => {
    try {
      const res = await toolsAPI.listOCRResults(20);
      setResults(res.data.results || []);
    } catch {
      /* ignore */
    }
  };

  useEffect(() => { loadResults(); }, []);

  const runOCR = async () => {
    if (!filePath.trim()) return;
    setLoading(true);
    setError('');
    try {
      const res = await toolsAPI.ocrFile({ file_path: filePath });
      setCurrentResult(res.data as OCRResult);
      await loadResults();
    } catch (e: any) {
      setError(e.response?.data?.detail || 'OCR failed');
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setLoading(true);
    setError('');
    try {
      const res = await toolsAPI.ocrUpload(file);
      setCurrentResult(res.data as OCRResult);
      await loadResults();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Upload failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      {error && (
        <div className="p-3 bg-red-900/50 border border-red-700 rounded text-red-300 text-sm">{error}</div>
      )}

      <div className="bg-gray-800 p-4 rounded-lg space-y-3">
        <h3 className="text-white font-medium text-sm">OCR — Extract text from images/PDFs</h3>
        <div className="flex gap-3 items-end">
          <div className="flex-1">
            <label className="text-xs text-gray-400 block mb-1">File path (on server)</label>
            <input value={filePath} onChange={(e) => setFilePath(e.target.value)} placeholder="/path/to/image.png" className="w-full bg-gray-700 text-white text-sm px-3 py-2 rounded" />
          </div>
          <button onClick={runOCR} disabled={loading} className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:opacity-50">
            {loading ? 'Processing...' : 'Run OCR'}
          </button>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500">or</span>
          <label className="px-3 py-1.5 bg-gray-700 text-gray-300 rounded text-xs cursor-pointer hover:bg-gray-600">
            Upload File
            <input type="file" accept="image/*,.pdf" className="hidden" onChange={handleUpload} />
          </label>
        </div>
      </div>

      {/* Current result */}
      {currentResult && (
        <div className="bg-gray-800 p-4 rounded-lg space-y-2">
          <div className="flex items-center justify-between">
            <h3 className="text-white font-medium text-sm">
              Result: {currentResult.filename}
              {currentResult.mock && <span className="ml-2 text-xs px-2 py-0.5 bg-yellow-900/50 text-yellow-400 rounded">MOCK</span>}
            </h3>
            <span className="text-xs text-gray-400">Confidence: {(currentResult.confidence * 100).toFixed(0)}%</span>
          </div>
          <pre className="bg-gray-900 text-gray-300 p-3 rounded text-xs max-h-64 overflow-auto whitespace-pre-wrap">{currentResult.text}</pre>
        </div>
      )}

      {/* History */}
      {results.length > 0 && (
        <div className="bg-gray-800 rounded-lg overflow-hidden">
          <h3 className="text-white font-medium text-sm px-4 py-3 border-b border-gray-700">Recent OCR Results</h3>
          <div className="divide-y divide-gray-700">
            {results.map((r) => (
              <div
                key={r.result_id}
                className="px-4 py-2 flex items-center justify-between hover:bg-gray-750 cursor-pointer"
                onClick={() => setCurrentResult(r)}
              >
                <div>
                  <span className="text-sm text-gray-300">{r.filename}</span>
                  {r.mock && <span className="ml-2 text-xs text-yellow-400">(mock)</span>}
                </div>
                <span className="text-xs text-gray-500">{new Date(r.timestamp).toLocaleString()}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ============================================================
// REPORTS TAB
// ============================================================

function ReportsTab() {
  const [reports, setReports] = useState<Report[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [title, setTitle] = useState('');
  const [mdContent, setMdContent] = useState('');
  const [selectedAcctForReport, setSelectedAcctForReport] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const loadReports = async () => {
    try {
      const res = await toolsAPI.listReports(20);
      setReports(res.data.reports || []);
    } catch {
      /* ignore */
    }
  };

  const loadAccounts = async () => {
    try {
      const res = await toolsAPI.listAccounts();
      setAccounts(res.data.accounts || []);
    } catch {
      /* ignore */
    }
  };

  useEffect(() => {
    loadReports();
    loadAccounts();
  }, []);

  const generateMdReport = async () => {
    if (!title.trim() || !mdContent.trim()) return;
    setLoading(true);
    setError('');
    setSuccess('');
    try {
      const res = await toolsAPI.generateReport({ title, markdown_content: mdContent });
      setSuccess(`Report generated: ${res.data.file_name}`);
      setTitle('');
      setMdContent('');
      await loadReports();
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Failed');
    } finally {
      setLoading(false);
    }
  };

  const generateAcctReport = async () => {
    if (!selectedAcctForReport) return;
    setLoading(true);
    setError('');
    setSuccess('');
    try {
      const res = await toolsAPI.generateAccountingReport({ account_id: selectedAcctForReport });
      setSuccess(`Report generated: ${res.data.file_name}`);
      await loadReports();
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      {error && <div className="p-3 bg-red-900/50 border border-red-700 rounded text-red-300 text-sm">{error}</div>}
      {success && <div className="p-3 bg-green-900/50 border border-green-700 rounded text-green-300 text-sm">{success}</div>}

      {/* Generate from Markdown */}
      <div className="bg-gray-800 p-4 rounded-lg space-y-3">
        <h3 className="text-white font-medium text-sm">Generate Report from Markdown</h3>
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Report title" className="w-full bg-gray-700 text-white text-sm px-3 py-2 rounded" />
        <textarea value={mdContent} onChange={(e) => setMdContent(e.target.value)} placeholder="# My Report\n\nMarkdown content here..." rows={6} className="w-full bg-gray-700 text-white text-sm px-3 py-2 rounded font-mono" />
        <button onClick={generateMdReport} disabled={loading} className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:opacity-50">
          {loading ? 'Generating...' : 'Generate Report'}
        </button>
      </div>

      {/* Generate Accounting Report */}
      {accounts.length > 0 && (
        <div className="bg-gray-800 p-4 rounded-lg space-y-3">
          <h3 className="text-white font-medium text-sm">Generate Accounting Report</h3>
          <div className="flex gap-3 items-end">
            <select
              value={selectedAcctForReport || ''}
              onChange={(e) => setSelectedAcctForReport(e.target.value ? parseInt(e.target.value) : null)}
              className="bg-gray-700 text-white text-sm px-3 py-2 rounded flex-1"
            >
              <option value="">Select account...</option>
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </select>
            <button onClick={generateAcctReport} disabled={loading || !selectedAcctForReport} className="px-4 py-2 bg-green-600 text-white rounded text-sm hover:bg-green-700 disabled:opacity-50">
              Generate
            </button>
          </div>
        </div>
      )}

      {/* Reports list */}
      {reports.length > 0 && (
        <div className="bg-gray-800 rounded-lg overflow-hidden">
          <h3 className="text-white font-medium text-sm px-4 py-3 border-b border-gray-700">Generated Reports</h3>
          <div className="divide-y divide-gray-700">
            {reports.map((r) => (
              <div key={r.report_id} className="px-4 py-3 flex items-center justify-between">
                <div>
                  <span className="text-sm text-gray-300">{r.title}</span>
                  <span className="ml-2 text-xs text-gray-500">{r.file_name}</span>
                  <span className="ml-2 text-xs px-1.5 py-0.5 bg-gray-700 text-gray-400 rounded">{r.format.toUpperCase()}</span>
                </div>
                <span className="text-xs text-gray-500">{new Date(r.created_at).toLocaleString()}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ============================================================
// FILES TAB
// ============================================================

function FilesTab() {
  const [currentPath, setCurrentPath] = useState('.');
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Move form
  const [showMove, setShowMove] = useState(false);
  const [moveSrc, setMoveSrc] = useState('');
  const [moveDest, setMoveDest] = useState('');

  // Mkdir form
  const [showMkdir, setShowMkdir] = useState(false);
  const [mkdirPath, setMkdirPath] = useState('');

  const loadDir = useCallback(async (path: string) => {
    setLoading(true);
    setError('');
    try {
      const res = await toolsAPI.listDirectory(path);
      setItems(res.data.items || []);
      setCurrentPath(res.data.path || path);
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Failed to list directory');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDir('.');
  }, [loadDir]);

  const navigate = (name: string, type: string) => {
    if (type === 'directory') {
      const newPath = currentPath.endsWith('/') || currentPath.endsWith('\\')
        ? currentPath + name
        : currentPath + '/' + name;
      loadDir(newPath);
    }
  };

  const goUp = () => {
    const parts = currentPath.replace(/\\/g, '/').split('/');
    parts.pop();
    const parent = parts.join('/') || '.';
    loadDir(parent);
  };

  const moveFile = async () => {
    if (!moveSrc || !moveDest) return;
    setError('');
    try {
      await toolsAPI.moveFile({ src: moveSrc, dest_folder: moveDest });
      setMoveSrc('');
      setMoveDest('');
      setShowMove(false);
      await loadDir(currentPath);
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Move failed');
    }
  };

  const mkdir = async () => {
    if (!mkdirPath) return;
    setError('');
    try {
      await toolsAPI.createDirectory({ path: mkdirPath });
      setMkdirPath('');
      setShowMkdir(false);
      await loadDir(currentPath);
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Mkdir failed');
    }
  };

  return (
    <div className="space-y-4">
      {error && <div className="p-3 bg-red-900/50 border border-red-700 rounded text-red-300 text-sm">{error}</div>}

      {/* Toolbar */}
      <div className="flex items-center gap-2">
        <button onClick={goUp} className="px-3 py-1.5 bg-gray-700 text-gray-300 rounded text-xs hover:bg-gray-600">↑ Up</button>
        <code className="text-xs text-gray-400 bg-gray-800 px-3 py-1.5 rounded flex-1 truncate">{currentPath}</code>
        <button onClick={() => loadDir(currentPath)} className="p-1.5 rounded hover:bg-gray-700 text-gray-400">
          <RefreshCw className="w-4 h-4" />
        </button>
        <button onClick={() => setShowMove(!showMove)} className="px-3 py-1.5 bg-gray-700 text-gray-300 rounded text-xs hover:bg-gray-600 flex items-center gap-1">
          <ArrowRightLeft className="w-3 h-3" /> Move
        </button>
        <button onClick={() => setShowMkdir(!showMkdir)} className="px-3 py-1.5 bg-gray-700 text-gray-300 rounded text-xs hover:bg-gray-600 flex items-center gap-1">
          <Plus className="w-3 h-3" /> New Folder
        </button>
      </div>

      {/* Move form */}
      {showMove && (
        <div className="bg-gray-800 p-4 rounded-lg space-y-3">
          <h3 className="text-white font-medium text-sm">Move File</h3>
          <div className="grid grid-cols-2 gap-3">
            <input value={moveSrc} onChange={(e) => setMoveSrc(e.target.value)} placeholder="Source file path" className="bg-gray-700 text-white text-sm px-3 py-2 rounded" />
            <input value={moveDest} onChange={(e) => setMoveDest(e.target.value)} placeholder="Destination folder" className="bg-gray-700 text-white text-sm px-3 py-2 rounded" />
          </div>
          <button onClick={moveFile} className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700">Move</button>
        </div>
      )}

      {/* Mkdir form */}
      {showMkdir && (
        <div className="bg-gray-800 p-4 rounded-lg space-y-3">
          <h3 className="text-white font-medium text-sm">Create Folder</h3>
          <input value={mkdirPath} onChange={(e) => setMkdirPath(e.target.value)} placeholder="Folder path" className="w-full bg-gray-700 text-white text-sm px-3 py-2 rounded" />
          <button onClick={mkdir} className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700">Create</button>
        </div>
      )}

      {/* File listing */}
      <div className="bg-gray-800 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-750 text-gray-400">
              <th className="px-3 py-2 text-left">Name</th>
              <th className="px-3 py-2 text-left">Type</th>
              <th className="px-3 py-2 text-right">Size</th>
              <th className="px-3 py-2 text-left">Modified</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={4} className="text-center py-8 text-gray-500">Loading...</td></tr>
            ) : items.length === 0 ? (
              <tr><td colSpan={4} className="text-center py-8 text-gray-500">Empty directory</td></tr>
            ) : (
              items.map((item, i) => (
                <tr
                  key={i}
                  className="border-t border-gray-700 hover:bg-gray-750 cursor-pointer"
                  onClick={() => navigate(item.name, item.type)}
                >
                  <td className="px-3 py-2 text-gray-300 flex items-center gap-2">
                    {item.type === 'directory' ? <FolderOpen className="w-4 h-4 text-yellow-400" /> : <FileText className="w-4 h-4 text-gray-400" />}
                    {item.name}
                  </td>
                  <td className="px-3 py-2 text-gray-500 text-xs">{item.type}</td>
                  <td className="px-3 py-2 text-gray-400 text-right text-xs font-mono">
                    {item.size != null ? formatBytes(item.size) : '-'}
                  </td>
                  <td className="px-3 py-2 text-gray-500 text-xs">{item.modified ? new Date(item.modified).toLocaleString() : ''}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ============================================================
// Helper components
// ============================================================

function StatCard({ label, value, color = 'blue' }: { label: string; value: number | string; color?: string }) {
  const colors: Record<string, string> = {
    blue: 'text-blue-400',
    green: 'text-green-400',
    yellow: 'text-yellow-400',
    red: 'text-red-400',
  };
  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <div className="text-xs text-gray-400">{label}</div>
      <div className={`text-2xl font-bold ${colors[color] || colors.blue}`}>{value}</div>
    </div>
  );
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}
