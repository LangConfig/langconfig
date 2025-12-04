/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useEffect, useCallback } from 'react';
import type { ChatMessage } from '../types/chat';
import apiClient from '../../../lib/api-client';

interface UseChatSessionResult {
  sessionId: string | null;
  messages: ChatMessage[];
  isLoading: boolean;
  error: string | null;
  loadHistory: (sessionId: string) => Promise<void>;
  addMessage: (message: ChatMessage) => void;
  updateLastMessage: (content: string) => void;
  clearHistory: () => void;
  setError: (error: string | null) => void;
}

export function useChatSession(currentSessionId: string | null): UseChatSessionResult {
  const [sessionId, setSessionId] = useState<string | null>(currentSessionId);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Update sessionId when currentSessionId changes
  useEffect(() => {
    setSessionId(currentSessionId);
  }, [currentSessionId]);

  // Load history when sessionId changes
  useEffect(() => {
    if (sessionId) {
      loadHistory(sessionId);
    } else {
      setMessages([]);
    }
  }, [sessionId]);

  const loadHistory = useCallback(async (sid: string) => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await apiClient.getChatHistory(sid);
      const data = response.data;

      if (data.messages && Array.isArray(data.messages)) {
        setMessages(data.messages);
      } else {
        setMessages([]);
      }
    } catch (err: any) {
      console.error('Failed to load chat history:', err);
      setError('Failed to load chat history');
      setMessages([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const addMessage = useCallback((message: ChatMessage) => {
    setMessages(prev => [...prev, message]);
  }, []);

  const updateLastMessage = useCallback((content: string) => {
    setMessages(prev => {
      if (prev.length === 0) return prev;

      const newMessages = [...prev];
      const lastMessage = newMessages[newMessages.length - 1];
      lastMessage.content = content;

      return newMessages;
    });
  }, []);

  const clearHistory = useCallback(() => {
    setMessages([]);
    setError(null);
  }, []);

  return {
    sessionId,
    messages,
    isLoading,
    error,
    loadHistory,
    addMessage,
    updateLastMessage,
    clearHistory,
    setError,
  };
}
