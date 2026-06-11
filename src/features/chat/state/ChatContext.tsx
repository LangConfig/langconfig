/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react';
import type { ChatContextValue, ChatSession, CompletedExecutionSnapshot } from '../types/chat';
import apiClient from '../../../lib/api-client';
import { useProject } from '../../../contexts/ProjectContext';

const ChatContext = createContext<ChatContextValue | undefined>(undefined);

interface ChatProviderProps {
  children: ReactNode;
}

export function ChatProvider({ children }: ChatProviderProps) {
  const { activeProjectId } = useProject();
  const [isOpen, setIsOpen] = useState(false);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(() => {
    const stored = sessionStorage.getItem('chat_currentSessionId');
    return stored || null;
  });
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState<number | null>(() => {
    const stored = sessionStorage.getItem('chat_selectedAgentId');
    return stored ? parseInt(stored, 10) : null;
  });
  const [hitlEnabled, setHitlEnabled] = useState<boolean>(() => {
    const stored = sessionStorage.getItem('chat_hitlEnabled');
    return stored === 'true';
  });
  const [completedExecutions, setCompletedExecutions] = useState<Record<string, CompletedExecutionSnapshot[]>>(() => {
    try {
      const stored = sessionStorage.getItem('chat_completedExecutions');
      return stored ? JSON.parse(stored) : {};
    } catch {
      return {};
    }
  });

  useEffect(() => {
    try {
      sessionStorage.setItem('chat_completedExecutions', JSON.stringify(completedExecutions));
    } catch {
      // Ignore session storage quota or serialization failures.
    }
  }, [completedExecutions]);

  // Persist currentSessionId to sessionStorage
  useEffect(() => {
    if (currentSessionId) {
      sessionStorage.setItem('chat_currentSessionId', currentSessionId);
    } else {
      sessionStorage.removeItem('chat_currentSessionId');
    }
  }, [currentSessionId]);

  // Persist selectedAgentId to sessionStorage
  useEffect(() => {
    if (selectedAgentId !== null) {
      sessionStorage.setItem('chat_selectedAgentId', selectedAgentId.toString());
    } else {
      sessionStorage.removeItem('chat_selectedAgentId');
    }
  }, [selectedAgentId]);

  // Persist hitlEnabled to sessionStorage
  useEffect(() => {
    sessionStorage.setItem('chat_hitlEnabled', hitlEnabled.toString());
  }, [hitlEnabled]);

  // Keyboard shortcut listener (Ctrl/Cmd + K)
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key === 'k') {
        event.preventDefault();
        setIsOpen(true);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const refreshSessions = useCallback(async () => {
    try {
      const response = await apiClient.getChatSessions({ project_id: activeProjectId });
      console.log('[ChatContext] Fetched sessions:', response.data);
      const fetchedSessions = response.data || [];
      setSessions(fetchedSessions);

      // If we have a persisted currentSessionId, update selectedAgentId from the session
      const persistedSessionId = sessionStorage.getItem('chat_currentSessionId');
      if (persistedSessionId && fetchedSessions.length > 0) {
        const persistedSession = fetchedSessions.find((s: ChatSession) => s.session_id === persistedSessionId);
        if (persistedSession) {
          setSelectedAgentId(persistedSession.agent_id);
          console.log('[ChatContext] Restored session:', persistedSession.session_id, 'agent:', persistedSession.agent_name);
        } else if (currentSessionId === persistedSessionId) {
          setCurrentSessionId(null);
        }
      }
    } catch (error) {
      console.error('Failed to fetch sessions:', error);
      setSessions([]);
    }
  }, [activeProjectId, currentSessionId]);

  // Fetch all sessions on mount
  useEffect(() => {
    refreshSessions();
  }, [refreshSessions]);

  const openChat = useCallback((agentId?: number) => {
    if (agentId !== undefined) {
      setSelectedAgentId(agentId);
    }
    setIsOpen(true);

    // Dispatch custom event to notify other components
    window.dispatchEvent(new CustomEvent('chat:opened'));
  }, []);

  const closeChat = useCallback(() => {
    setIsOpen(false);
  }, []);

  const startSession = useCallback(async (agentId: number): Promise<string> => {
    try {
      const response = await apiClient.startChatSession(agentId, activeProjectId);
      const sessionId = response.data.session_id;

      // Refresh sessions list to include new session
      await refreshSessions();

      // Set as current session
      setCurrentSessionId(sessionId);

      return sessionId;
    } catch (error) {
      console.error('Failed to start session:', error);
      throw error;
    }
  }, [activeProjectId, refreshSessions]);

  const switchSession = useCallback((sessionId: string) => {
    setCurrentSessionId(sessionId);
  }, []);

  const clearCurrentSession = useCallback(() => {
    setCurrentSessionId(null);
  }, []);

  const endSession = useCallback(async (sessionId: string) => {
    try {
      await apiClient.endChatSession(sessionId);

      // Remove from sessions list
      setSessions(prev => prev.filter(s => s.session_id !== sessionId));

      // If this was the current session, clear it
      if (currentSessionId === sessionId) {
        setCurrentSessionId(null);
      }
    } catch (error) {
      console.error('Failed to end session:', error);
      throw error;
    }
  }, [currentSessionId]);

  const deleteSession = useCallback(async (sessionId: string) => {
    try {
      await apiClient.deleteChatSession(sessionId);
      setSessions(prev => prev.filter(s => s.session_id !== sessionId));

      if (currentSessionId === sessionId) {
        setCurrentSessionId(null);
      }
    } catch (error) {
      console.error('Failed to delete session:', error);
      throw error;
    }
  }, [currentSessionId]);

  const toggleHitl = useCallback(() => {
    setHitlEnabled(prev => !prev);
  }, []);

  const getCompletedExecutions = useCallback(
    (key: string) => completedExecutions[key] || [],
    [completedExecutions]
  );

  const appendCompletedExecution = useCallback((key: string, snapshot: CompletedExecutionSnapshot) => {
    setCompletedExecutions(prev => {
      const existing = prev[key] || [];
      if (snapshot.taskId && existing.some(item => item.taskId === snapshot.taskId)) {
        return prev;
      }
      return {
        ...prev,
        [key]: [...existing, snapshot].slice(-20),
      };
    });
  }, []);

  const clearCompletedExecutions = useCallback((key: string) => {
    setCompletedExecutions(prev => {
      if (!(key in prev)) return prev;
      const next = { ...prev };
      delete next[key];
      return next;
    });
  }, []);

  const value: ChatContextValue = {
    isOpen,
    currentSessionId,
    sessions,
    selectedAgentId,
    hitlEnabled,
    openChat,
    closeChat,
    startSession,
    switchSession,
    clearCurrentSession,
    endSession,
    deleteSession,
    setSelectedAgent: setSelectedAgentId,
    toggleHitl,
    refreshSessions,
    getCompletedExecutions,
    appendCompletedExecution,
    clearCompletedExecutions,
  };

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

export function useChat() {
  const context = useContext(ChatContext);
  if (context === undefined) {
    throw new Error('useChat must be used within a ChatProvider');
  }
  return context;
}
