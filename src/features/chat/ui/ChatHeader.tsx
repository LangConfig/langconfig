/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { X } from 'lucide-react';
import { useChat } from '../state/ChatContext';
import AgentSelector from './AgentSelector';
import SessionSelector from './SessionSelector';
import ChatSettingsMenu from './ChatSettingsMenu';

interface ChatHeaderProps {
  sessionId: string | null;
  agentName: string;
  messages: any[];
  metrics: any;
  toolCalls: any[];
  subagentActivity: any[];
  onStartSession: (agentId: number) => Promise<void>;
  onNewSession: () => void;
  onClearHistory: () => void;
  onEndSession: () => void;
}

export default function ChatHeader({
  sessionId,
  agentName,
  messages,
  metrics,
  toolCalls,
  subagentActivity,
  onStartSession,
  onNewSession,
  onClearHistory,
  onEndSession
}: ChatHeaderProps) {
  const { closeChat, selectedAgentId, setSelectedAgent } = useChat();

  const handleSelectAgent = async (agentId: number) => {
    setSelectedAgent(agentId);
    await onStartSession(agentId);
  };

  return (
    <div
      className="flex items-center justify-between px-6 py-3 border-b"
      style={{
        borderColor: 'var(--color-border-dark)',
        backgroundColor: 'white',
      }}
    >
      <div className="flex items-center gap-3">
        {/* Current Agent Display and Agent Selector */}
        {sessionId ? (
          <div className="flex items-center gap-3">
            <div>
              <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                Chatting with
              </div>
              <h2
                className="text-base font-semibold"
                style={{ color: 'var(--color-primary)' }}
              >
                {agentName}
              </h2>
            </div>
            <div className="h-8 w-px" style={{ backgroundColor: 'var(--color-border-dark)' }} />
            <AgentSelector
              selectedAgentId={selectedAgentId}
              onSelectAgent={handleSelectAgent}
            />
          </div>
        ) : (
          <AgentSelector
            selectedAgentId={selectedAgentId}
            onSelectAgent={handleSelectAgent}
          />
        )}
      </div>

      <div className="flex items-center gap-2">
        {/* Session Selector */}
        {sessionId && (
          <SessionSelector onNewSession={onNewSession} />
        )}

        {/* Settings Menu */}
        <ChatSettingsMenu
          sessionId={sessionId}
          messages={messages}
          metrics={metrics}
          toolCalls={toolCalls}
          subagentActivity={subagentActivity}
          agentName={agentName}
          onClearHistory={onClearHistory}
          onEndSession={onEndSession}
        />

        {/* Close Button */}
        <button
          onClick={closeChat}
          className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
          style={{ color: 'var(--color-text-muted)' }}
          title="Close (ESC)"
        >
          <X className="w-5 h-5" />
        </button>
      </div>
    </div>
  );
}
