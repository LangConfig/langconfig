/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState } from 'react';
import type { MouseEvent } from 'react';
import { ChevronDown, Plus, History, Trash2 } from 'lucide-react';
import type { ChatSession } from '../types/chat';
import { useChat } from '../state/ChatContext';

interface SessionSelectorProps {
  onNewSession: () => void;
}

export default function SessionSelector({ onNewSession }: SessionSelectorProps) {
  const { sessions, currentSessionId, switchSession, deleteSession } = useChat();
  const [isOpen, setIsOpen] = useState(false);
  const [hoveredSession, setHoveredSession] = useState<string | null>(null);
  const [deletingSession, setDeletingSession] = useState<string | null>(null);

  const currentSession = sessions.find((s: ChatSession) => s.session_id === currentSessionId);

  // Show conversations with messages OR the current active session
  const conversationsWithMessages = sessions.filter((s: ChatSession) =>
    s.message_count > 0 || s.session_id === currentSessionId
  );

  const handleSelectSession = (sessionId: string) => {
    switchSession(sessionId);
    setIsOpen(false);
  };

  const handleNewSession = () => {
    onNewSession();
    setIsOpen(false);
  };

  const handleDeleteSession = async (event: MouseEvent, session: ChatSession) => {
    event.stopPropagation();
    if (!window.confirm(`Delete the ${session.agent_name} conversation?`)) {
      return;
    }
    setDeletingSession(session.session_id);
    try {
      await deleteSession(session.session_id);
    } finally {
      setDeletingSession(null);
    }
  };

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMinutes = Math.floor((now.getTime() - date.getTime()) / (1000 * 60));

    if (diffMinutes < 1) return 'just now';
    if (diffMinutes < 60) return `${diffMinutes}m ago`;
    if (diffMinutes < 1440) return `${Math.floor(diffMinutes / 60)}h ago`;
    return `${Math.floor(diffMinutes / 1440)}d ago`;
  };

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 border-2 px-3 py-2 font-mono text-xs font-semibold uppercase tracking-[0.12em] transition-[transform,box-shadow,background-color] hover:translate-x-0.5 hover:translate-y-0.5"
        style={{
          borderColor: 'var(--color-border-dark)',
          backgroundColor: 'white',
          color: 'var(--color-text-primary)',
          boxShadow: '3px 3px 0 var(--color-border-dark)',
        }}
        title="View conversation history"
      >
        <History className="w-4 h-4" />
        <span>Conversations</span>
        <ChevronDown className="w-4 h-4" />
      </button>

      {isOpen && (
        <>
          <div
            className="fixed inset-0 z-40"
            onClick={() => setIsOpen(false)}
          />
          <div
            className="absolute right-0 z-50 mt-2 flex max-h-96 w-80 flex-col overflow-hidden border-2 shadow-[4px_4px_0_var(--color-border-dark)]"
            style={{
              backgroundColor: 'white',
              borderColor: 'var(--color-border-dark)',
            }}
          >
            {/* New Conversation Button */}
            <button
              onClick={handleNewSession}
              onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--color-primary)'}
              onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
              className="flex items-center gap-2 border-b-2 px-4 py-3 font-mono text-xs font-semibold uppercase tracking-[0.12em] transition-colors"
              style={{ borderColor: 'var(--color-border-dark)' }}
            >
              <Plus
                className="w-4 h-4 transition-colors"
                onMouseEnter={(e) => e.currentTarget.style.color = 'white'}
                onMouseLeave={(e) => e.currentTarget.style.color = 'var(--color-primary)'}
                style={{ color: 'var(--color-primary)' }}
              />
              <span
                className="transition-colors"
                onMouseEnter={(e) => e.currentTarget.style.color = 'white'}
                onMouseLeave={(e) => e.currentTarget.style.color = 'var(--color-primary)'}
                style={{ color: 'var(--color-primary)' }}
              >
                New Conversation
              </span>
            </button>

            {/* Conversation List */}
            <div className="overflow-y-auto">
              {conversationsWithMessages.length === 0 ? (
                <div
                  className="p-4 text-center text-sm"
                  style={{ color: 'var(--color-text-muted)' }}
                >
                  No conversations yet
                </div>
              ) : (
                conversationsWithMessages.map((session: ChatSession) => (
                  <div
                    key={session.session_id}
                    onClick={() => handleSelectSession(session.session_id)}
                    onMouseEnter={() => setHoveredSession(session.session_id)}
                    onMouseLeave={() => setHoveredSession(null)}
                    className="w-full cursor-pointer border-b px-4 py-3 text-left transition-colors"
                    style={{
                      borderColor: 'var(--color-border-dark)',
                      backgroundColor: hoveredSession === session.session_id ? 'var(--color-primary)' : 'transparent',
                    }}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-2 mb-1">
                          <div
                            className="text-sm font-medium truncate"
                            style={{
                              color: hoveredSession === session.session_id
                                ? 'white'
                                : currentSessionId === session.session_id
                                ? 'var(--color-primary)'
                                : 'var(--color-text-primary)',
                            }}
                          >
                            {session.agent_name}
                          </div>
                          <span
                            className="text-xs whitespace-nowrap"
                            style={{ color: hoveredSession === session.session_id ? 'white' : 'var(--color-text-muted)' }}
                          >
                            {formatTimestamp(session.updated_at)}
                          </span>
                        </div>
                        {session.last_message_preview && (
                          <div
                            className="text-xs truncate"
                            style={{ color: hoveredSession === session.session_id ? 'rgba(255,255,255,0.8)' : 'var(--color-text-muted)' }}
                          >
                            {session.last_message_preview}
                          </div>
                        )}
                      </div>
                      {currentSessionId === session.session_id && (
                        <span
                          className="material-symbols-outlined text-base flex-shrink-0"
                          style={{ color: hoveredSession === session.session_id ? 'white' : 'var(--color-primary)' }}
                        >
                          check
                        </span>
                      )}
                      <button
                        type="button"
                        onClick={(event) => handleDeleteSession(event, session)}
                        disabled={deletingSession === session.session_id}
                        className="flex h-7 w-7 flex-shrink-0 items-center justify-center border transition-[transform,box-shadow,opacity] hover:translate-x-0.5 hover:translate-y-0.5 disabled:cursor-wait disabled:opacity-50"
                        style={{
                          borderColor: hoveredSession === session.session_id ? 'white' : 'var(--color-border-dark)',
                          color: hoveredSession === session.session_id ? 'white' : 'var(--color-text-muted)',
                          boxShadow: hoveredSession === session.session_id ? '2px 2px 0 white' : '2px 2px 0 var(--color-border-dark)',
                          backgroundColor: 'transparent',
                        }}
                        title="Delete conversation"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
