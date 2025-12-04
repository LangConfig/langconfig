/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState } from 'react';
import { Settings, Download, Trash2, LogOut, Check } from 'lucide-react';
import { useChat } from '../context/ChatContext';

interface ChatSettingsMenuProps {
  sessionId: string | null;
  messages: any[];
  metrics: any;
  toolCalls: any[];
  subagentActivity: any[];
  agentName: string;
  onClearHistory: () => void;
  onEndSession: () => void;
}

export default function ChatSettingsMenu({
  sessionId,
  messages,
  metrics,
  toolCalls,
  subagentActivity,
  agentName,
  onClearHistory,
  onEndSession
}: ChatSettingsMenuProps) {
  const { hitlEnabled, toggleHitl } = useChat();
  const [isOpen, setIsOpen] = useState(false);
  const [hoveredItem, setHoveredItem] = useState<string | null>(null);

  const downloadHistory = () => {
    const history = JSON.stringify({
      agent: agentName,
      session_id: sessionId,
      messages,
      tool_calls: toolCalls,
      subagent_activity: subagentActivity,
      metrics
    }, null, 2);

    const blob = new Blob([history], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `chat_history_${sessionId}.json`;
    a.click();
    URL.revokeObjectURL(url);
    setIsOpen(false);
  };

  const handleClearHistory = () => {
    if (window.confirm('Are you sure you want to clear the chat history? This cannot be undone.')) {
      onClearHistory();
      setIsOpen(false);
    }
  };

  const handleEndSession = () => {
    if (window.confirm('Are you sure you want to end this session? The session will be closed.')) {
      onEndSession();
      setIsOpen(false);
    }
  };

  const handleToggleHitl = () => {
    toggleHitl();
  };

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="p-2 rounded-lg transition-colors hover:bg-gray-100"
        style={{ color: 'var(--color-text-muted)' }}
        title="Settings"
      >
        <Settings className="w-5 h-5" />
      </button>

      {isOpen && (
        <>
          <div
            className="fixed inset-0 z-40"
            onClick={() => setIsOpen(false)}
          />
          <div
            className="absolute right-0 mt-2 w-64 rounded-lg shadow-lg border z-50"
            style={{
              backgroundColor: 'white',
              borderColor: 'var(--color-border-dark)',
            }}
          >
            {/* HITL Toggle */}
            <button
              onClick={handleToggleHitl}
              onMouseEnter={() => setHoveredItem('hitl')}
              onMouseLeave={() => setHoveredItem(null)}
              className="w-full px-4 py-3 flex items-center justify-between transition-colors border-b"
              style={{
                borderColor: 'var(--color-border-dark)',
                backgroundColor: hoveredItem === 'hitl' ? 'var(--color-primary)' : 'transparent',
              }}
            >
              <div className="flex items-center gap-2">
                <span
                  className="text-sm"
                  style={{ color: hoveredItem === 'hitl' ? 'white' : 'var(--color-text-primary)' }}
                >
                  Human-in-the-Loop
                </span>
              </div>
              <div
                className="flex items-center gap-2"
                style={{
                  color: hoveredItem === 'hitl'
                    ? 'white'
                    : hitlEnabled
                    ? 'var(--color-primary)'
                    : 'var(--color-text-muted)',
                }}
              >
                {hitlEnabled && <Check className="w-4 h-4" />}
                <span className="text-xs">{hitlEnabled ? 'ON' : 'OFF'}</span>
              </div>
            </button>

            {/* Download History */}
            <button
              onClick={downloadHistory}
              disabled={!sessionId}
              onMouseEnter={() => !sessionId || setHoveredItem('download')}
              onMouseLeave={() => setHoveredItem(null)}
              className="w-full px-4 py-3 flex items-center gap-2 transition-colors border-b disabled:opacity-50 disabled:cursor-not-allowed"
              style={{
                borderColor: 'var(--color-border-dark)',
                backgroundColor: hoveredItem === 'download' ? 'var(--color-primary)' : 'transparent',
              }}
            >
              <Download
                className="w-4 h-4"
                style={{ color: hoveredItem === 'download' ? 'white' : 'var(--color-text-muted)' }}
              />
              <span
                className="text-sm"
                style={{ color: hoveredItem === 'download' ? 'white' : 'var(--color-text-primary)' }}
              >
                Download History
              </span>
            </button>

            {/* Clear History */}
            <button
              onClick={handleClearHistory}
              disabled={!sessionId}
              onMouseEnter={() => !sessionId || setHoveredItem('clear')}
              onMouseLeave={() => setHoveredItem(null)}
              className="w-full px-4 py-3 flex items-center gap-2 transition-colors border-b disabled:opacity-50 disabled:cursor-not-allowed"
              style={{
                borderColor: 'var(--color-border-dark)',
                backgroundColor: hoveredItem === 'clear' ? 'var(--color-primary)' : 'transparent',
              }}
            >
              <Trash2
                className="w-4 h-4"
                style={{ color: hoveredItem === 'clear' ? 'white' : 'var(--color-text-muted)' }}
              />
              <span
                className="text-sm"
                style={{ color: hoveredItem === 'clear' ? 'white' : 'var(--color-text-primary)' }}
              >
                Clear History
              </span>
            </button>

            {/* End Session */}
            <button
              onClick={handleEndSession}
              disabled={!sessionId}
              onMouseEnter={() => !sessionId || setHoveredItem('end')}
              onMouseLeave={() => setHoveredItem(null)}
              className="w-full px-4 py-3 flex items-center gap-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              style={{
                borderColor: 'var(--color-border-dark)',
                backgroundColor: hoveredItem === 'end' ? 'var(--color-primary)' : 'transparent',
              }}
            >
              <LogOut
                className="w-4 h-4"
                style={{ color: hoveredItem === 'end' ? 'white' : 'rgb(239, 68, 68)' }}
              />
              <span
                className="text-sm"
                style={{ color: hoveredItem === 'end' ? 'white' : 'rgb(239, 68, 68)' }}
              >
                End Session
              </span>
            </button>
          </div>
        </>
      )}
    </div>
  );
}
