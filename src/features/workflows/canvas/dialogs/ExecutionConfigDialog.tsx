/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { memo } from 'react';

interface WorkflowExecutionContext {
  directive: string;
  query: string;
  task: string;
  classification: 'GENERAL' | 'BACKEND' | 'FRONTEND' | 'DEVOPS_IAC' | 'DATABASE' | 'API' | 'TESTING' | 'DOCUMENTATION' | 'CONFIGURATION';
  executor_type: 'default' | 'devops' | 'frontend' | 'database' | 'testing';
  max_retries: number;
  max_events?: number;
  timeout_seconds?: number;
}

interface Document {
  id: number;
  name: string;
  document_type: string;
}

interface ExecutionConfigDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onExecute: () => void;
  executionConfig: WorkflowExecutionContext;
  setExecutionConfig: React.Dispatch<React.SetStateAction<WorkflowExecutionContext>>;
  showAdvancedOptions: boolean;
  setShowAdvancedOptions: React.Dispatch<React.SetStateAction<boolean>>;
  additionalContext: string;
  setAdditionalContext: React.Dispatch<React.SetStateAction<string>>;
  contextDocuments: number[];
  setContextDocuments: React.Dispatch<React.SetStateAction<number[]>>;
  availableDocuments: Document[];
}

/**
 * Dialog for configuring workflow execution parameters
 */
const ExecutionConfigDialog = memo(function ExecutionConfigDialog({
  isOpen,
  onClose,
  onExecute,
  executionConfig,
  setExecutionConfig,
  showAdvancedOptions,
  setShowAdvancedOptions,
  additionalContext,
  setAdditionalContext,
  contextDocuments,
  setContextDocuments,
  availableDocuments,
}: ExecutionConfigDialogProps) {
  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 flex items-center justify-center z-50 cursor-pointer"
      style={{ backgroundColor: 'rgba(0, 0, 0, 0.5)' }}
      onClick={onClose}
    >
      <div
        className="rounded-lg shadow-xl p-6 max-w-lg w-full mx-4 max-h-[90vh] overflow-y-auto"
        style={{ backgroundColor: 'var(--color-panel-dark)' }}
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-xl font-bold mb-4" style={{ color: 'var(--color-text-primary)' }}>
          Run Workflow
        </h3>

        <div className="space-y-4">
          {/* Prompt Input */}
          <div>
            <label className="block text-sm font-medium mb-2" style={{ color: 'var(--color-text-primary)' }}>
              What should this workflow do?
            </label>
            <textarea
              className="w-full px-3 py-2 border rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all"
              style={{
                backgroundColor: 'white',
                color: '#1f2937',
                borderColor: 'var(--color-border-dark)'
              }}
              rows={5}
              placeholder="Enter your task or prompt here..."
              value={executionConfig.directive}
              onChange={(e) => setExecutionConfig({
                ...executionConfig,
                directive: e.target.value,
                query: e.target.value,
                task: e.target.value,
              })}
              autoFocus
            />
          </div>

          {/* Advanced Options Toggle */}
          <button
            onClick={() => setShowAdvancedOptions(!showAdvancedOptions)}
            className="text-sm hover:underline flex items-center gap-1"
            style={{ color: 'var(--color-primary)' }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: '16px' }}>
              {showAdvancedOptions ? 'expand_less' : 'expand_more'}
            </span>
            {showAdvancedOptions ? 'Hide' : 'Show'} Advanced Options
          </button>

          {/* Advanced Options */}
          {showAdvancedOptions && (
            <div className="space-y-4 pt-2 border-t" style={{ borderColor: 'var(--color-border-dark)' }}>
              {/* Additional Context */}
              <div>
                <label className="block text-sm font-medium mb-2" style={{ color: 'var(--color-text-primary)' }}>
                  Additional Context (Optional)
                </label>
                <textarea
                  className="w-full px-3 py-2 border rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all"
                  style={{
                    backgroundColor: 'white',
                    color: '#1f2937',
                    borderColor: 'var(--color-border-dark)'
                  }}
                  rows={3}
                  placeholder="Add any background information, constraints, or context..."
                  value={additionalContext}
                  onChange={(e) => setAdditionalContext(e.target.value)}
                />
              </div>

              {/* Context Documents (RAG) */}
              <div>
                <label className="block text-sm font-medium mb-2" style={{ color: 'var(--color-text-primary)' }}>
                  Context Documents (RAG)
                </label>
                {availableDocuments.length > 0 ? (
                  <div className="max-h-40 overflow-y-auto border rounded-md p-2" style={{
                    borderColor: 'var(--color-border-dark)',
                    backgroundColor: 'var(--color-background-dark)'
                  }}>
                    {availableDocuments.map((doc) => (
                      <label
                        key={doc.id}
                        className="flex items-center gap-2 py-1.5 px-2 rounded cursor-pointer hover:bg-white/5"
                      >
                        <input
                          type="checkbox"
                          checked={contextDocuments.includes(doc.id)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setContextDocuments([...contextDocuments, doc.id]);
                            } else {
                              setContextDocuments(contextDocuments.filter(id => id !== doc.id));
                            }
                          }}
                          className="rounded"
                          style={{ accentColor: 'var(--color-primary)' }}
                        />
                        <span className="text-sm flex-1 truncate" style={{ color: 'var(--color-text-primary)' }}>
                          {doc.name}
                        </span>
                        <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                          {doc.document_type}
                        </span>
                      </label>
                    ))}
                  </div>
                ) : (
                  <div className="text-sm italic py-2" style={{ color: 'var(--color-text-muted)' }}>
                    No documents available. Upload documents in the Knowledge Base first.
                  </div>
                )}
                <p className="mt-1 text-xs" style={{ color: 'var(--color-text-muted)' }}>
                  Select documents from the Knowledge Base to use as context
                </p>
              </div>

              {/* Max Retries */}
              <div>
                <label className="block text-sm font-medium mb-2" style={{ color: 'var(--color-text-primary)' }}>
                  Max Retries
                </label>
                <input
                  type="number"
                  min="0"
                  max="10"
                  className="w-full px-3 py-2 border rounded-md focus:ring-2 focus:border-transparent"
                  style={{
                    backgroundColor: 'var(--color-background-dark)',
                    color: 'var(--color-text-primary)',
                    borderColor: 'var(--color-border-dark)'
                  }}
                  value={executionConfig.max_retries}
                  onChange={(e) => setExecutionConfig({
                    ...executionConfig,
                    max_retries: parseInt(e.target.value) || 0,
                  })}
                />
                <p className="mt-1 text-xs" style={{ color: 'var(--color-text-muted)' }}>
                  Number of times to retry failed steps
                </p>
              </div>

              {/* Max Events */}
              <div>
                <label className="block text-sm font-medium mb-2" style={{ color: 'var(--color-text-primary)' }}>
                  Max Events
                </label>
                <input
                  type="number"
                  min="1000"
                  max="100000"
                  step="1000"
                  className="w-full px-3 py-2 border rounded-md focus:ring-2 focus:border-transparent"
                  style={{
                    backgroundColor: 'var(--color-background-dark)',
                    color: 'var(--color-text-primary)',
                    borderColor: 'var(--color-border-dark)'
                  }}
                  value={executionConfig.max_events || 10000}
                  onChange={(e) => setExecutionConfig({
                    ...executionConfig,
                    max_events: parseInt(e.target.value) || 10000,
                  })}
                />
                <p className="mt-1 text-xs" style={{ color: 'var(--color-text-muted)' }}>
                  Maximum events before stopping (1k-100k). Increase for longer workflows.
                </p>
              </div>

              {/* Timeout */}
              <div>
                <label className="block text-sm font-medium mb-2" style={{ color: 'var(--color-text-primary)' }}>
                  Timeout (minutes)
                </label>
                <input
                  type="number"
                  min="1"
                  max="60"
                  className="w-full px-3 py-2 border rounded-md focus:ring-2 focus:border-transparent"
                  style={{
                    backgroundColor: 'var(--color-background-dark)',
                    color: 'var(--color-text-primary)',
                    borderColor: 'var(--color-border-dark)'
                  }}
                  value={Math.round((executionConfig.timeout_seconds || 600) / 60)}
                  onChange={(e) => setExecutionConfig({
                    ...executionConfig,
                    timeout_seconds: (parseInt(e.target.value) || 10) * 60,
                  })}
                />
                <p className="mt-1 text-xs" style={{ color: 'var(--color-text-muted)' }}>
                  Maximum runtime in minutes (1-60). Default is 10 minutes.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Action Buttons */}
        <div className="flex gap-3 mt-6">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2 border rounded-md transition-colors"
            style={{
              borderColor: 'var(--color-border-dark)',
              color: 'var(--color-text-primary)'
            }}
          >
            Cancel
          </button>
          <button
            onClick={onExecute}
            disabled={!executionConfig.directive.trim()}
            className="flex-1 px-4 py-2 rounded-md transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
            style={{
              backgroundColor: 'var(--color-primary)',
              color: '#ffffff'
            }}
          >
            Run Workflow
          </button>
        </div>
      </div>
    </div>
  );
});

export default ExecutionConfigDialog;
