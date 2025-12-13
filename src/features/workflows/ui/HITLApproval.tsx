/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * HITL (Human-in-the-Loop) Approval Component
 *
 * Displays when a workflow is paused at an interrupt point.
 * Allows user to:
 * - Review current workflow state
 * - Inject memory before continuing
 * - Approve or reject the continuation
 */

import React, { useState } from 'react';
import { CheckCircle, XCircle, Database, Plus, X, AlertCircle } from 'lucide-react';
import apiClient from '@/lib/api-client';

interface MemoryItem {
  key: string;
  value: string;
}

interface HITLApprovalProps {
  workflowId: number;
  threadId: string;
  checkpointId: string;
  currentState: any;
  interruptReason?: string;
  onApprove: (injectedMemory?: MemoryItem[]) => void;
  onReject: () => void;
  isOpen: boolean;
}

export const HITLApproval: React.FC<HITLApprovalProps> = ({
  workflowId,
  threadId,
  checkpointId,
  currentState,
  interruptReason,
  onApprove,
  onReject,
  isOpen,
}) => {
  const [memoryItems, setMemoryItems] = useState<MemoryItem[]>([]);
  const [showMemoryForm, setShowMemoryForm] = useState(false);
  const [newKey, setNewKey] = useState('');
  const [newValue, setNewValue] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const addMemoryItem = () => {
    if (!newKey.trim()) {
      setError('Key is required');
      return;
    }

    setMemoryItems([...memoryItems, { key: newKey, value: newValue }]);
    setNewKey('');
    setNewValue('');
    setShowMemoryForm(false);
    setError(null);
  };

  const removeMemoryItem = (index: number) => {
    setMemoryItems(memoryItems.filter((_, i) => i !== index));
  };

  const handleApprove = async () => {
    setIsSubmitting(true);
    setError(null);

    try {
      // If memory items exist, inject them before approving
      if (memoryItems.length > 0) {
        const memoryBatch = {
          items: memoryItems.map(item => {
            let parsedValue: any;
            try {
              parsedValue = JSON.parse(item.value);
            } catch {
              parsedValue = item.value;
            }

            return {
              namespace: ['workflow', String(workflowId)],
              key: item.key,
              value: parsedValue,
            };
          }),
        };

        // Inject memory via batch API
        // Inject memory via batch API
        await apiClient.batchUpdateWorkflowMemory(workflowId, memoryBatch.items);
      }

      // Call the approval handler
      onApprove(memoryItems);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      setIsSubmitting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-2xl max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="p-6 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-3">
            <AlertCircle className="w-6 h-6 text-yellow-500" />
            <div>
              <h2 className="text-xl font-bold text-gray-900 dark:text-white">
                Workflow Paused - Approval Required
              </h2>
              {interruptReason && (
                <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                  {interruptReason}
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mx-6 mt-4 p-3 bg-red-100 dark:bg-red-900/30 border border-red-300 dark:border-red-700 rounded-lg text-red-800 dark:text-red-400 text-sm">
            {error}
          </div>
        )}

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {/* Current State Preview */}
          <div className="mb-6">
            <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
              Current State
            </h3>
            <div className="p-3 bg-gray-50 dark:bg-gray-900/50 rounded-lg">
              <pre className="text-xs text-gray-800 dark:text-gray-200 overflow-x-auto whitespace-pre-wrap max-h-40">
                {JSON.stringify(currentState, null, 2)}
              </pre>
            </div>
          </div>

          {/* Memory Injection Section */}
          <div className="mb-6">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Database className="w-4 h-4 text-primary" />
                <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
                  Inject Memory (Optional)
                </h3>
              </div>
              {!showMemoryForm && (
                <button
                  onClick={() => setShowMemoryForm(true)}
                  className="text-xs text-primary hover:text-primary/80 flex items-center gap-1"
                >
                  <Plus className="w-3 h-3" />
                  Add Item
                </button>
              )}
            </div>

            <p className="text-xs text-gray-600 dark:text-gray-400 mb-3">
              Add context or instructions that will be available to the workflow when it continues.
            </p>

            {/* Memory Items List */}
            {memoryItems.map((item, index) => (
              <div
                key={index}
                className="mb-2 p-3 border border-gray-200 dark:border-gray-700 rounded-lg flex items-start justify-between"
              >
                <div className="flex-1 min-w-0">
                  <div className="font-mono text-xs font-semibold text-primary mb-1 truncate">
                    {item.key}
                  </div>
                  <div className="text-xs text-gray-600 dark:text-gray-400 truncate">
                    {item.value}
                  </div>
                </div>
                <button
                  onClick={() => removeMemoryItem(index)}
                  className="ml-2 p-1 hover:bg-red-100 dark:hover:bg-red-900/30 rounded"
                >
                  <X className="w-4 h-4 text-red-600 dark:text-red-400" />
                </button>
              </div>
            ))}

            {/* Add Memory Form */}
            {showMemoryForm && (
              <div className="p-3 border border-primary dark:border-primary/50 rounded-lg bg-primary/5 dark:bg-primary/10">
                <div className="space-y-2">
                  <input
                    type="text"
                    value={newKey}
                    onChange={(e) => setNewKey(e.target.value)}
                    placeholder="Key (e.g., instructions, context)"
                    className="w-full px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  />
                  <textarea
                    value={newValue}
                    onChange={(e) => setNewValue(e.target.value)}
                    placeholder="Value (text or JSON)"
                    rows={2}
                    className="w-full px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={addMemoryItem}
                      className="px-3 py-1 text-sm bg-primary text-white rounded hover:bg-primary/90"
                    >
                      Add
                    </button>
                    <button
                      onClick={() => {
                        setShowMemoryForm(false);
                        setNewKey('');
                        setNewValue('');
                        setError(null);
                      }}
                      className="px-3 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded hover:bg-gray-100 dark:hover:bg-gray-700"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Footer Actions */}
        <div className="border-t border-gray-200 dark:border-gray-700 p-6 flex justify-end gap-3">
          <button
            onClick={onReject}
            disabled={isSubmitting}
            className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors disabled:opacity-50 flex items-center gap-2"
          >
            <XCircle className="w-4 h-4" />
            Reject
          </button>
          <button
            onClick={handleApprove}
            disabled={isSubmitting}
            className="px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors disabled:opacity-50 flex items-center gap-2"
          >
            <CheckCircle className="w-4 h-4" />
            {isSubmitting ? 'Approving...' : 'Approve & Continue'}
          </button>
        </div>
      </div>
    </div>
  );
};
