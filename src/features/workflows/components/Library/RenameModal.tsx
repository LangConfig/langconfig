/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useEffect, useRef } from 'react';

interface RenameModalProps {
  currentName: string;
  onRename: (newName: string) => void;
  onClose: () => void;
}

export default function RenameModal({ currentName, onRename, onClose }: RenameModalProps) {
  const [newName, setNewName] = useState(currentName);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    // Focus and select text on mount
    inputRef.current?.focus();
    inputRef.current?.select();
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (newName.trim() && newName !== currentName) {
      onRename(newName.trim());
      onClose();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-panel-dark rounded-lg max-w-md w-full p-6 shadow-2xl">
        <h3 className="text-lg font-bold mb-4" style={{ color: 'var(--color-text-primary)' }}>
          Rename Workflow
        </h3>

        <form onSubmit={handleSubmit}>
          <input
            ref={inputRef}
            type="text"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={handleKeyDown}
            className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-border-dark rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
            style={{
              backgroundColor: 'var(--color-input-background)',
              color: 'var(--color-text-primary)'
            }}
            placeholder="Enter workflow name..."
          />

          <div className="flex items-center justify-end gap-3 mt-6">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium border border-gray-300 dark:border-border-dark rounded-lg hover:bg-gray-100 dark:hover:bg-white/10 hover:border-gray-400 dark:hover:border-border-light transition-all"
              style={{ color: 'var(--color-text-primary)' }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!newName.trim() || newName === currentName}
              className="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:brightness-110 hover:shadow-lg transition-all disabled:opacity-50"
            >
              Rename
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
