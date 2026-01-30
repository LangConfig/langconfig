/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useEffect, useRef, useState } from 'react';
import { useChat } from '../state/ChatContext';
import { useChatSession } from '../hooks/useChatSession';
import { useChatStreaming } from '../hooks/useChatStreaming';
import { useChatMetrics } from '../hooks/useChatMetrics';
import ChatHeader from './ChatHeader';
import MessagesPanel from './MessagesPanel';
import MetricsPanel from './MetricsPanel';
import type { ChatMessage, ChatSession, ChatStreamEvent, CustomEventPayload } from '../types/chat';

export default function GlobalChatModal() {
  const {
    isOpen,
    closeChat,
    currentSessionId,
    selectedAgentId,
    hitlEnabled,
    startSession,
    switchSession,
    endSession,
    sessions
  } = useChat();

  const modalRef = useRef<HTMLDivElement>(null);
  const [activeToolCalls, setActiveToolCalls] = useState<string[]>([]);
  const [customEvents, setCustomEvents] = useState<Map<string, CustomEventPayload>>(new Map());

  // Session management hook
  const {
    messages,
    isLoading: isLoadingSession,
    error: sessionError,
    addMessage,
    updateLastMessage,
    clearHistory,
    setError: setSessionError
  } = useChatSession(currentSessionId);

  // Streaming hook
  const {
    sendMessage,
    isStreaming,
    error: streamingError,
    clearError: clearStreamingError
  } = useChatStreaming(currentSessionId, hitlEnabled);

  // Metrics hook
  const {
    metrics,
    toolCalls,
    subagentActivity,
    isLoading: isLoadingMetrics,
    refresh: refreshMetrics
  } = useChatMetrics(currentSessionId);

  // Get current session details
  const currentSession = sessions.find((s: ChatSession) => s.session_id === currentSessionId);
  const agentName = currentSession?.agent_name || 'Agent';

  // Handle ESC key
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        closeChat();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, closeChat]);

  // Auto-start session when modal opens with pre-selected agent
  useEffect(() => {
    if (isOpen && selectedAgentId && !currentSessionId) {
      // Automatically start a session with the pre-selected agent
      handleStartSession(selectedAgentId);
    }
  }, [isOpen, selectedAgentId, currentSessionId]);

  // Prevent body scroll when modal is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }

    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  // Handle click outside
  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      closeChat();
    }
  };

  // Handle starting a new session
  const handleStartSession = async (agentId: number) => {
    try {
      await startSession(agentId);
    } catch (error) {
      console.error('Failed to start session:', error);
      setSessionError('Failed to start chat session');
    }
  };

  // Handle starting a new session (from session selector)
  const handleNewSession = async () => {
    if (selectedAgentId) {
      await handleStartSession(selectedAgentId);
    }
  };

  // Handle sending a message
  const handleSendMessage = async (message: string) => {
    if (!currentSessionId) return;

    await sendMessage(
      message,
      addMessage,
      updateLastMessage,
      async () => {
        // On complete: refresh metrics, clear active tools and custom events
        await refreshMetrics();
        setActiveToolCalls([]);
        setCustomEvents(new Map());
      },
      (event: ChatStreamEvent) => {
        // Handle tool events
        if (event.type === 'tool_start' && event.tool_name) {
          setActiveToolCalls(prev => [...prev, event.tool_name!]);
        } else if (event.type === 'tool_end' && event.tool_name) {
          setActiveToolCalls(prev => prev.filter(t => t !== event.tool_name));
        }
      },
      (event: ChatStreamEvent) => {
        // Handle custom events (LangGraph-style progress, status, etc.)
        if (event.type === 'custom_event' && event.data) {
          const payload = event.data as CustomEventPayload;
          const eventId = payload.event_id || `${payload.event_type}-${Date.now()}`;
          setCustomEvents(prev => {
            const next = new Map(prev);
            next.set(eventId, payload);
            return next;
          });
        }
      }
    );
  };

  // Handle ending the session
  const handleEndSession = async () => {
    if (!currentSessionId) return;

    try {
      await endSession(currentSessionId);
      // Context will handle clearing currentSessionId
    } catch (error) {
      console.error('Failed to end session:', error);
      setSessionError('Failed to end session');
    }
  };

  const error = sessionError || streamingError;
  const clearError = () => {
    setSessionError(null);
    clearStreamingError();
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4"
      onClick={handleBackdropClick}
    >
      <div
        ref={modalRef}
        className="rounded-xl shadow-2xl w-full max-w-7xl h-[90vh] flex flex-col overflow-hidden"
        style={{
          backgroundColor: 'white',
          border: '1px solid var(--color-border-dark)',
        }}
      >
        {/* Header with Title */}
        <div
          className="px-6 py-3 border-b"
          style={{
            backgroundColor: 'var(--color-primary)',
            color: 'white',
            borderColor: 'var(--color-border-dark)',
          }}
        >
          <h2 className="text-lg font-semibold">Agent Chat Interface</h2>
        </div>

        {/* Header */}
        <ChatHeader
          sessionId={currentSessionId}
          agentName={agentName}
          messages={messages}
          metrics={metrics}
          toolCalls={toolCalls}
          subagentActivity={subagentActivity}
          onStartSession={handleStartSession}
          onNewSession={handleNewSession}
          onClearHistory={clearHistory}
          onEndSession={handleEndSession}
        />

        {/* Main Content */}
        <div className="flex flex-1 overflow-hidden">
          {/* Messages Panel - Left/Center */}
          <MessagesPanel
            messages={messages}
            isStreaming={isStreaming}
            error={error}
            onSendMessage={handleSendMessage}
            onClearError={clearError}
            disabled={!currentSessionId}
            sessionId={currentSessionId}
            activeToolCalls={activeToolCalls}
            customEvents={customEvents}
          />

          {/* Metrics Panel - Right Sidebar */}
          <MetricsPanel
            metrics={metrics}
            toolCalls={toolCalls}
            subagentActivity={subagentActivity}
            isLoading={isLoadingMetrics}
            agentName={agentName}
            sessionId={currentSessionId}
          />
        </div>
      </div>
    </div>
  );
}
