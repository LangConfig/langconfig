/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { memo } from 'react';

interface SaveWorkflowModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: () => void;
  workflowName: string;
  setWorkflowName: (name: string) => void;
}

/**
 * Modal for saving a new workflow with a name
 */
const SaveWorkflowModal = memo(function SaveWorkflowModal({
  isOpen,
  onClose,
  onSave,
  workflowName,
  setWorkflowName,
}: SaveWorkflowModalProps) {
  if (!isOpen) return null;

  const handleClose = () => {
    onClose();
    setWorkflowName('');
  };

  const handleSave = () => {
    if (workflowName.trim()) {
      onSave();
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      onClick={handleClose}
    >
      <div
        className="rounded-lg shadow-xl p-6 max-w-md w-full mx-4"
        style={{
          backgroundColor: 'var(--color-panel-dark)',
          border: '1px solid var(--color-border-dark)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <h2
          className="text-xl font-semibold mb-4"
          style={{ color: 'var(--color-text-primary)' }}
        >
          Save Workflow
        </h2>
        <p
          className="mb-4 text-sm"
          style={{ color: 'var(--color-text-muted)' }}
        >
          Enter a name for your workflow:
        </p>
        <input
          type="text"
          value={workflowName}
          onChange={(e) => setWorkflowName(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && workflowName.trim()) {
              handleSave();
            } else if (e.key === 'Escape') {
              handleClose();
            }
          }}
          placeholder="Enter workflow name..."
          autoFocus
          className="w-full px-3 py-2 rounded-lg mb-4 border focus:outline-none focus:ring-2"
          style={{
            backgroundColor: 'var(--color-input-background)',
            borderColor: 'var(--color-border-dark)',
            color: 'var(--color-text-primary)',
          }}
        />
        <div className="flex gap-2 justify-end">
          <button
            onClick={handleClose}
            className="px-4 py-2 rounded-lg border transition-colors"
            style={{
              borderColor: 'var(--color-border-dark)',
              color: 'var(--color-text-muted)',
            }}
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={!workflowName.trim()}
            className="px-4 py-2 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            style={{
              backgroundColor: 'var(--color-primary)',
              color: 'white',
            }}
          >
            Save
          </button>
        </div>
      </div>
    </div>
  );
});

export default SaveWorkflowModal;
