/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { memo } from 'react';
import { X } from 'lucide-react';

interface WorkflowSettingsDialogProps {
  isOpen: boolean;
  onClose: () => void;
  checkpointerEnabled: boolean;
  onToggleCheckpointer: () => void;
  globalRecursionLimit: number;
  setGlobalRecursionLimit: (limit: number) => void;
}

/**
 * Modal for configuring workflow settings (checkpointer, recursion limit)
 */
const WorkflowSettingsDialog = memo(function WorkflowSettingsDialog({
  isOpen,
  onClose,
  checkpointerEnabled,
  onToggleCheckpointer,
  globalRecursionLimit,
  setGlobalRecursionLimit,
}: WorkflowSettingsDialogProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div
        className="w-full max-w-md rounded-xl shadow-2xl overflow-hidden"
        style={{
          backgroundColor: 'var(--color-panel-dark)',
          border: '1px solid var(--color-border-dark)'
        }}
      >
        <div className="px-6 py-4 border-b flex justify-between items-center" style={{ borderColor: 'var(--color-border-dark)' }}>
          <h3 className="text-lg font-semibold" style={{ color: 'var(--color-text-primary)' }}>
            Workflow Settings
          </h3>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-white/10 transition-colors"
            style={{ color: 'var(--color-text-muted)' }}
          >
            <X size={20} />
          </button>
        </div>

        <div className="p-6 space-y-6">
          {/* Checkpointer Setting */}
          <div className="flex items-start gap-3">
            <div className="flex-1">
              <label className="text-sm font-medium block mb-1" style={{ color: 'var(--color-text-primary)' }}>
                Enable Persistence (Checkpointer)
              </label>
              <p className="text-xs leading-relaxed" style={{ color: 'var(--color-text-muted)' }}>
                Saves conversation history between workflow runs. Required for Human-in-the-Loop (HITL) and resuming interrupted workflows.
              </p>
              {checkpointerEnabled && (
                <p className="text-xs leading-relaxed mt-2 p-2 rounded-md" style={{ backgroundColor: 'rgba(245, 158, 11, 0.15)', color: '#f59e0b' }}>
                  ⚠️ <strong>Warning:</strong> When enabled, agents will remember previous executions. The same prompt may produce different results as the agent may reference prior context. Use clear, specific instructions to avoid confusion.
                </p>
              )}
            </div>
            <div
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors cursor-pointer ${checkpointerEnabled ? 'bg-primary' : 'bg-gray-600'}`}
              onClick={onToggleCheckpointer}
            >
              <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${checkpointerEnabled ? 'translate-x-6' : 'translate-x-1'}`} />
            </div>
          </div>

          {/* Recursion Limit Setting */}
          <div>
            <label className="text-sm font-medium block mb-1" style={{ color: 'var(--color-text-primary)' }}>
              Global Recursion Limit
            </label>
            <p className="text-xs mb-3" style={{ color: 'var(--color-text-muted)' }}>
              Maximum number of steps the workflow can execute before stopping. Prevents infinite loops.
            </p>
            <div className="flex items-center gap-3">
              <input
                type="range"
                min="5"
                max="500"
                step="5"
                value={globalRecursionLimit}
                onChange={(e) => setGlobalRecursionLimit(parseInt(e.target.value))}
                className="flex-1 h-2 rounded-lg appearance-none cursor-pointer bg-gray-700"
              />
              <span className="text-sm font-mono w-12 text-right" style={{ color: 'var(--color-text-primary)' }}>
                {globalRecursionLimit}
              </span>
            </div>
          </div>
        </div>

        <div className="px-6 py-4 border-t flex justify-end" style={{ borderColor: 'var(--color-border-dark)', backgroundColor: 'var(--color-background-dark)' }}>
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-sm font-medium transition-colors bg-primary text-white hover:bg-primary/90"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
});

export default WorkflowSettingsDialog;
