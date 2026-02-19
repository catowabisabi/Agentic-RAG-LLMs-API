'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { AlertTriangle, XCircle, X, Power } from 'lucide-react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:1130';

interface SystemAlert {
  level: 'warning' | 'error';
  code: string;
  message: string;
}

export default function SystemAlertBanner() {
  const [alerts, setAlerts] = useState<SystemAlert[]>([]);
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());
  const [showShutdown, setShowShutdown] = useState(false);

  const fetchAlerts = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/system/alerts`);
      if (res.ok) {
        const data = await res.json();
        setAlerts(data.alerts || []);
      }
    } catch {
      // Server unreachable — no alert needed (WebSocket will show disconnect)
    }
  }, []);

  useEffect(() => {
    fetchAlerts();
    const interval = setInterval(fetchAlerts, 30000); // Re-check every 30s

    // Listen for real-time system alerts via WebSocket CustomEvent
    const handleSystemAlert = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (detail && detail.code) {
        setAlerts((prev) => {
          // Avoid duplicates
          if (prev.some((a) => a.code === detail.code)) return prev;
          return [...prev, {
            level: detail.level || 'error',
            code: detail.code,
            message: detail.message || detail.error || 'System alert',
          }];
        });
      }
    };
    window.addEventListener('system-alert', handleSystemAlert);

    return () => {
      clearInterval(interval);
      window.removeEventListener('system-alert', handleSystemAlert);
    };
  }, [fetchAlerts]);

  const handleDismiss = (code: string) => {
    setDismissed((prev) => new Set(prev).add(code));
  };

  const handleShutdown = async () => {
    if (!confirm('Are you sure you want to shut down the API server?')) return;
    try {
      await fetch(`${API_URL}/system/shutdown`, { method: 'POST' });
    } catch {
      // Expected — server will die
    }
    setShowShutdown(false);
  };

  const visibleAlerts = alerts.filter((a) => !dismissed.has(a.code));
  if (visibleAlerts.length === 0) return null;

  return (
    <div className="w-full">
      {visibleAlerts.map((alert) => (
        <div
          key={alert.code}
          className={`flex items-center justify-between px-4 py-2.5 text-sm ${
            alert.level === 'error'
              ? 'bg-red-900/70 text-red-200 border-b border-red-800'
              : 'bg-yellow-900/70 text-yellow-200 border-b border-yellow-800'
          }`}
        >
          <div className="flex items-center gap-2">
            {alert.level === 'error' ? (
              <XCircle className="w-4 h-4 flex-shrink-0" />
            ) : (
              <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            )}
            <span>{alert.message}</span>
          </div>
          <div className="flex items-center gap-2">
            {alert.code === 'TASK_ERROR' && (
              <button
                onClick={() => setShowShutdown(true)}
                className="px-2 py-1 text-xs bg-red-700 hover:bg-red-600 rounded transition-colors flex items-center gap-1"
              >
                <Power className="w-3 h-3" /> Shutdown
              </button>
            )}
            <button
              onClick={() => handleDismiss(alert.code)}
              className="p-0.5 hover:bg-white/10 rounded transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      ))}

      {/* Shutdown confirmation dialog */}
      {showShutdown && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center">
          <div className="bg-gray-800 rounded-lg border border-gray-700 p-6 max-w-sm">
            <h3 className="text-white font-semibold mb-2">Shutdown Server?</h3>
            <p className="text-gray-400 text-sm mb-4">
              This will stop the API server and the UI will lose connection.
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setShowShutdown(false)}
                className="px-4 py-2 text-sm text-gray-300 hover:bg-gray-700 rounded"
              >
                Cancel
              </button>
              <button
                onClick={handleShutdown}
                className="px-4 py-2 text-sm bg-red-600 hover:bg-red-700 text-white rounded"
              >
                Shutdown
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
