/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { memo } from 'react';

interface CreateWorkflowDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onCreate: () => void;
  workflowName: string;
  setWorkflowName: (name: string) => void;
}

/**
 * Modal for creating a new workflow with a name
 */
const CreateWorkflowDialog = memo(function CreateWorkflowDialog({
  isOpen,
  onClose,
  onCreate,
  workflowName,
  setWorkflowName,
}: CreateWorkflowDialogProps) {
  if (!isOpen) return null;

  const handleClose = () => {
    onClose();
    setWorkflowName('');
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (workflowName.trim()) {
      onCreate();
    }
  };

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-panel-dark rounded-lg max-w-md w-full p-6 shadow-2xl">
        <h3 className="text-lg font-bold mb-4" style={{ color: 'var(--color-text-primary)' }}>
          Create New Workflow
        </h3>

        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label className="block text-sm font-medium mb-2" style={{ color: 'var(--color-text-primary)' }}>
              Workflow Name
            </label>
            <input
              type="text"
              value={workflowName}
              onChange={(e) => setWorkflowName(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-border-dark rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
              style={{
                backgroundColor: 'var(--color-input-background)',
                color: 'var(--color-text-primary)'
              }}
              placeholder="Enter workflow name..."
              autoFocus
            />
          </div>

          <div className="flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={handleClose}
              className="px-4 py-2 text-sm font-medium border border-gray-300 dark:border-border-dark rounded-lg hover:bg-gray-100 dark:hover:bg-white/10 hover:border-gray-400 dark:hover:border-border-light transition-all"
              style={{ color: 'var(--color-text-primary)' }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!workflowName.trim()}
              className="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:brightness-110 hover:shadow-lg transition-all disabled:opacity-50"
            >
              Create Workflow
            </button>
          </div>
        </form>
      </div>
    </div>
  );
});

export default CreateWorkflowDialog;
