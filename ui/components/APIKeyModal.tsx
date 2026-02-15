'use client';

import React, { useState, useEffect } from 'react';
import { X, Key, AlertCircle, Save, Loader2 } from 'lucide-react';

interface APIKeyModalProps {
  isOpen: boolean;
  onClose: () => void;
  provider?: string;
  errorDetails?: string;
}

export default function APIKeyModal({
  isOpen,
  onClose,
  provider = 'openai',
  errorDetails = ''
}: APIKeyModalProps) {
  const [apiKey, setApiKey] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    if (!isOpen) {
      // Reset state when modal closes
      setApiKey('');
      setError(null);
      setSuccess(false);
    }
  }, [isOpen]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!apiKey.trim()) {
      setError('Please enter an API key');
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const apiUrl = localStorage.getItem('api_url') || 'http://localhost:1130';
      
      const response = await fetch(`${apiUrl}/config/api-key`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          provider: provider.toLowerCase(),
          api_key: apiKey
        })
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Failed to update API key');
      }

      setSuccess(true);
      
      // Close modal after a short delay
      setTimeout(() => {
        onClose();
      }, 1500);

    } catch (err: any) {
      setError(err.message || 'Failed to update API key');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isOpen) return null;

  const providerNames: Record<string, string> = {
    openai: 'OpenAI',
    anthropic: 'Anthropic',
    google: 'Google'
  };

  const providerName = providerNames[provider.toLowerCase()] || provider;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-2xl max-w-md w-full">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-red-100 dark:bg-red-900 rounded-lg">
              <AlertCircle className="w-6 h-6 text-red-600 dark:text-red-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-gray-900 dark:text-white">
                API Key Required
              </h2>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                {providerName} API Key
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {/* Error Details */}
          {errorDetails && (
            <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3">
              <p className="text-sm text-red-800 dark:text-red-300">
                <strong>Error:</strong> Invalid or missing API key
              </p>
              <p className="text-xs text-red-600 dark:text-red-400 mt-1 font-mono">
                {errorDetails.substring(0, 150)}...
              </p>
            </div>
          )}

          {/* Instructions */}
          <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-3">
            <p className="text-sm text-blue-800 dark:text-blue-300">
              Please enter your {providerName} API key to continue. 
              {provider.toLowerCase() === 'openai' && (
                <span className="block mt-1">
                  Get your key from{' '}
                  <a 
                    href="https://platform.openai.com/api-keys" 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="underline hover:text-blue-600"
                  >
                    platform.openai.com
                  </a>
                </span>
              )}
            </p>
          </div>

          {/* API Key Input */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              <Key className="w-4 h-4 inline mr-2" />
              API Key
            </label>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={`sk-proj-...`}
              className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg 
                focus:ring-2 focus:ring-blue-500 focus:border-transparent
                bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                placeholder-gray-400 dark:placeholder-gray-500"
              disabled={isSubmitting || success}
              autoFocus
            />
          </div>

          {/* Error Message */}
          {error && (
            <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3">
              <p className="text-sm text-red-800 dark:text-red-300">
                {error}
              </p>
            </div>
          )}

          {/* Success Message */}
          {success && (
            <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-3">
              <p className="text-sm text-green-800 dark:text-green-300">
                ✓ API key updated successfully!
              </p>
            </div>
          )}

          {/* Actions */}
          <div className="flex space-x-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
                text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700
                transition-colors disabled:opacity-50"
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || success}
              className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg
                transition-colors disabled:opacity-50 disabled:cursor-not-allowed
                flex items-center justify-center space-x-2"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Saving...</span>
                </>
              ) : success ? (
                <>
                  <span>✓ Saved</span>
                </>
              ) : (
                <>
                  <Save className="w-4 h-4" />
                  <span>Save API Key</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
