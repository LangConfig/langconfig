/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { memo } from 'react';

interface ChatWarningModalProps {
  isOpen: boolean;
  onClose: () => void;
}

/**
 * Warning modal shown when trying to chat with an agent not saved to the library
 */
const ChatWarningModal = memo(function ChatWarningModal({
  isOpen,
  onClose,
}: ChatWarningModalProps) {
  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      onClick={onClose}
    >
      <div
        className="rounded-lg shadow-xl p-6 max-w-md w-full mx-4"
        style={{
          backgroundColor: 'var(--color-panel-dark)',
          border: '1px solid var(--color-border-dark)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start gap-3 mb-4">
          <div
            className="flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center"
            style={{ backgroundColor: 'rgba(251, 191, 36, 0.1)' }}
          >
            <span
              className="material-symbols-outlined"
              style={{ color: '#f59e0b', fontSize: '24px' }}
            >
              warning
            </span>
          </div>
          <div>
            <h2
              className="text-lg font-semibold mb-2"
              style={{ color: 'var(--color-text-primary)' }}
            >
              Agent Not Saved to Library
            </h2>
            <p
              className="text-sm"
              style={{ color: 'var(--color-text-primary)' }}
            >
              To chat with this agent, you need to save it to the Agent Library first. This allows you to have persistent conversations with the agent.
            </p>
          </div>
        </div>

        <div className="flex gap-2 justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg transition-colors"
            style={{
              backgroundColor: 'var(--color-primary)',
              color: 'white',
            }}
          >
            Got it
          </button>
        </div>
      </div>
    </div>
  );
});

export default ChatWarningModal;
