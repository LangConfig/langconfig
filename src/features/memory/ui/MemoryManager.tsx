/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * Memory Manager Component
 *
 * Manages workflow-scoped long-term memory (LangGraph Store).
 * Allows viewing, adding, and deleting memory items.
 */

import React, { useState, useEffect } from 'react';
import { X, Plus, Trash2, RefreshCw, Database } from 'lucide-react';
import apiClient from '../../../lib/api-client';

interface StoreItem {
  namespace: string[];
  key: string;
  value: any;
  created_at?: string;
  updated_at?: string;
}

interface MemoryManagerProps {
  workflowId: number;
  isOpen: boolean;
  onClose: () => void;
}

export const MemoryManager: React.FC<MemoryManagerProps> = ({
  workflowId,
  isOpen,
  onClose,
}) => {
  const [items, setItems] = useState<StoreItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Add item form state
  const [showAddForm, setShowAddForm] = useState(false);
  const [newKey, setNewKey] = useState('');
  const [newValue, setNewValue] = useState('');

  useEffect(() => {
    if (isOpen) {
      loadMemoryItems();
    }
  }, [isOpen, workflowId]);

  const loadMemoryItems = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.getWorkflowMemory(workflowId);
      setItems(response.data || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      console.error('Error loading memory:', err);
    } finally {
      setLoading(false);
    }
  };

  const addMemoryItem = async () => {
    if (!newKey.trim()) {
      setError('Key is required');
      return;
    }

    let parsedValue: any;
    try {
      // Try to parse as JSON, otherwise treat as string
      parsedValue = JSON.parse(newValue);
    } catch {
      parsedValue = newValue;
    }

    setLoading(true);
    setError(null);
    try {
      await apiClient.addWorkflowMemoryItem(workflowId, {
        namespace: ['workflow', String(workflowId)],
        key: newKey,
        value: parsedValue,
      });

      // Reset form and reload items
      setNewKey('');
      setNewValue('');
      setShowAddForm(false);
      await loadMemoryItems();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      console.error('Error adding memory:', err);
    } finally {
      setLoading(false);
    }
  };

  const deleteMemoryItem = async (key: string) => {
    if (!confirm(`Delete memory item "${key}"?`)) {
      return;
    }

    setLoading(true);
    setError(null);
    try {
      await apiClient.deleteWorkflowMemoryItem(workflowId, key);
      await loadMemoryItems();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      console.error('Error deleting memory:', err);
    } finally {
      setLoading(false);
    }
  };

  const clearAllMemory = async () => {
    if (!confirm('Clear ALL memory items for this workflow? This cannot be undone.')) {
      return;
    }

    setLoading(true);
    setError(null);
    try {
      await apiClient.clearWorkflowMemory(workflowId);
      await loadMemoryItems();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      console.error('Error clearing memory:', err);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-4xl max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2">
            <Database className="w-5 h-5 text-primary" />
            <h2 className="text-xl font-bold text-gray-900 dark:text-white">
              Workflow Memory
            </h2>
            <span className="text-sm text-gray-500 dark:text-gray-400">
              ({items.length} items)
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={loadMemoryItems}
              disabled={loading}
              className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
              title="Refresh"
            >
              <RefreshCw className={`w-4 h-4 text-gray-600 dark:text-gray-400 ${loading ? 'animate-spin' : ''}`} />
            </button>
            <button
              onClick={onClose}
              className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
            >
              <X className="w-5 h-5 text-gray-600 dark:text-gray-400" />
            </button>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mx-4 mt-4 p-3 bg-red-100 dark:bg-red-900/30 border border-red-300 dark:border-red-700 rounded-lg text-red-800 dark:text-red-400 text-sm">
            {error}
          </div>
        )}

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4">
          {/* Add Item Button */}
          {!showAddForm && (
            <button
              onClick={() => setShowAddForm(true)}
              className="w-full mb-4 p-3 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg hover:border-primary dark:hover:border-primary transition-colors flex items-center justify-center gap-2 text-gray-600 dark:text-gray-400 hover:text-primary"
            >
              <Plus className="w-4 h-4" />
              <span>Add Memory Item</span>
            </button>
          )}

          {/* Add Item Form */}
          {showAddForm && (
            <div className="mb-4 p-4 border border-primary dark:border-primary/50 rounded-lg bg-primary/5 dark:bg-primary/10">
              <h3 className="font-semibold text-gray-900 dark:text-white mb-3">Add Memory Item</h3>
              <div className="space-y-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Key
                  </label>
                  <input
                    type="text"
                    value={newKey}
                    onChange={(e) => setNewKey(e.target.value)}
                    placeholder="e.g., user_preferences, api_endpoint"
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Value (JSON or text)
                  </label>
                  <textarea
                    value={newValue}
                    onChange={(e) => setNewValue(e.target.value)}
                    placeholder='{"key": "value"} or plain text'
                    rows={4}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white font-mono text-sm"
                  />
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={addMemoryItem}
                    disabled={loading}
                    className="px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors disabled:opacity-50"
                  >
                    Add
                  </button>
                  <button
                    onClick={() => {
                      setShowAddForm(false);
                      setNewKey('');
                      setNewValue('');
                      setError(null);
                    }}
                    className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Memory Items List */}
          {items.length === 0 && !loading && (
            <div className="text-center py-12 text-gray-500 dark:text-gray-400">
              <Database className="w-12 h-12 mx-auto mb-3 opacity-30" />
              <p>No memory items yet</p>
              <p className="text-sm mt-1">Add items to provide context to your workflow</p>
            </div>
          )}

          {items.map((item, index) => (
            <div
              key={index}
              className="mb-3 p-4 border border-gray-200 dark:border-gray-700 rounded-lg hover:border-primary dark:hover:border-primary/50 transition-colors"
            >
              <div className="flex items-start justify-between mb-2">
                <div className="flex-1">
                  <div className="font-mono text-sm font-semibold text-primary mb-1">
                    {item.key}
                  </div>
                  {item.created_at && (
                    <div className="text-xs text-gray-500 dark:text-gray-400">
                      Created: {new Date(item.created_at).toLocaleString()}
                    </div>
                  )}
                </div>
                <button
                  onClick={() => deleteMemoryItem(item.key)}
                  disabled={loading}
                  className="p-2 hover:bg-red-100 dark:hover:bg-red-900/30 rounded-lg transition-colors"
                  title="Delete"
                >
                  <Trash2 className="w-4 h-4 text-red-600 dark:text-red-400" />
                </button>
              </div>
              <div className="mt-2 p-3 bg-gray-50 dark:bg-gray-900/50 rounded-lg">
                <pre className="text-xs text-gray-800 dark:text-gray-200 overflow-x-auto whitespace-pre-wrap">
                  {JSON.stringify(item.value, null, 2)}
                </pre>
              </div>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="border-t border-gray-200 dark:border-gray-700 p-4 flex justify-between items-center">
          <button
            onClick={clearAllMemory}
            disabled={loading || items.length === 0}
            className="px-4 py-2 text-red-600 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-900/30 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Clear All Memory
          </button>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-800 dark:text-gray-200 rounded-lg hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
