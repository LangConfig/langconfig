/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { memo } from 'react';

interface SaveToLibraryModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: () => void;
  agentName: string;
  setAgentName: (name: string) => void;
  agentDescription: string;
  setAgentDescription: (description: string) => void;
}

/**
 * Modal for saving a node/agent to the Agent Library
 */
const SaveToLibraryModal = memo(function SaveToLibraryModal({
  isOpen,
  onClose,
  onSave,
  agentName,
  setAgentName,
  agentDescription,
  setAgentDescription,
}: SaveToLibraryModalProps) {
  if (!isOpen) return null;

  const handleClose = () => {
    onClose();
    setAgentName('');
    setAgentDescription('');
  };

  const handleSave = () => {
    if (agentName.trim()) {
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
          Save to Agent Library
        </h2>

        <div className="space-y-4">
          <div>
            <label
              className="block text-sm font-medium mb-2"
              style={{ color: 'var(--color-text-primary)' }}
            >
              Agent Name
            </label>
            <input
              type="text"
              value={agentName}
              onChange={(e) => setAgentName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && agentName.trim()) {
                  handleSave();
                } else if (e.key === 'Escape') {
                  handleClose();
                }
              }}
              placeholder="Enter agent name..."
              autoFocus
              className="w-full px-3 py-2 rounded-lg border focus:outline-none focus:ring-2"
              style={{
                backgroundColor: 'var(--color-input-background)',
                borderColor: 'var(--color-border-dark)',
                color: 'var(--color-text-primary)',
              }}
            />
          </div>

          <div>
            <label
              className="block text-sm font-medium mb-2"
              style={{ color: 'var(--color-text-primary)' }}
            >
              Description (optional)
            </label>
            <textarea
              value={agentDescription}
              onChange={(e) => setAgentDescription(e.target.value)}
              placeholder="Describe what this agent does..."
              rows={3}
              className="w-full px-3 py-2 rounded-lg border focus:outline-none focus:ring-2 resize-none"
              style={{
                backgroundColor: 'var(--color-input-background)',
                borderColor: 'var(--color-border-dark)',
                color: 'var(--color-text-primary)',
              }}
            />
          </div>
        </div>

        <div className="flex gap-2 justify-end mt-6">
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
            disabled={!agentName.trim()}
            className="px-4 py-2 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            style={{
              backgroundColor: 'var(--color-primary)',
              color: 'white',
            }}
          >
            Save to Library
          </button>
        </div>
      </div>
    </div>
  );
});

export default SaveToLibraryModal;
