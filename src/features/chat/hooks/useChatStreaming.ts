/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useCallback, useRef } from 'react';
import type { ChatMessage, ChatStreamEvent } from '../types/chat';
import apiClient from '../../../lib/api-client';

interface UseChatStreamingResult {
  sendMessage: (
    message: string,
    onMessageAdd: (message: ChatMessage) => void,
    onMessageUpdate: (content: string) => void,
    onComplete: () => void,
    onToolEvent?: (event: ChatStreamEvent) => void,
    onCustomEvent?: (event: ChatStreamEvent) => void
  ) => Promise<void>;
  isStreaming: boolean;
  error: string | null;
  clearError: () => void;
}

export function useChatStreaming(
  sessionId: string | null,
  hitlEnabled: boolean = false
): UseChatStreamingResult {
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const sendMessage = useCallback(
    async (
      message: string,
      onMessageAdd: (message: ChatMessage) => void,
      onMessageUpdate: (content: string) => void,
      onComplete: () => void,
      onToolEvent?: (event: ChatStreamEvent) => void,
      onCustomEvent?: (event: ChatStreamEvent) => void
    ) => {
      if (!sessionId || isStreaming) return;

      setError(null);
      setIsStreaming(true);

      // Create abort controller for cancellation
      abortControllerRef.current = new AbortController();

      // Add user message immediately
      const userMessage: ChatMessage = {
        role: 'user',
        content: message,
        timestamp: new Date().toISOString(),
      };
      onMessageAdd(userMessage);

      try {
        // Call streaming endpoint
        const response = await fetch(`${apiClient.baseURL}/api/chat/message/stream`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: sessionId,
            message: message,
            enable_hitl: hitlEnabled,
          }),
          signal: abortControllerRef.current.signal,
        });

        if (!response.ok) {
          throw new Error(`Failed to send message: ${response.statusText}`);
        }

        // Read stream
        const reader = response.body?.getReader();
        const decoder = new TextDecoder();

        if (!reader) {
          throw new Error('No reader available for response stream');
        }

        let accumulatedContent = '';
        let assistantMessageAdded = false;

        while (true) {
          const { done, value } = await reader.read();

          if (done) break;

          const chunk = decoder.decode(value, { stream: true });
          const lines = chunk.split('\n');

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data: ChatStreamEvent = JSON.parse(line.substring(6));

                if (data.type === 'chunk') {
                  // Stream individual tokens as they arrive
                  accumulatedContent += data.content;

                  // Add assistant message on first chunk
                  if (!assistantMessageAdded) {
                    const assistantMessage: ChatMessage = {
                      role: 'assistant',
                      content: accumulatedContent,
                      timestamp: new Date().toISOString(),
                    };
                    onMessageAdd(assistantMessage);
                    assistantMessageAdded = true;
                  } else {
                    onMessageUpdate(accumulatedContent);
                  }
                } else if (data.type === 'complete') {
                  // Final content - use accumulated or provided
                  const finalContent = data.content || accumulatedContent;
                  if (finalContent !== accumulatedContent) {
                    accumulatedContent = finalContent;
                    onMessageUpdate(finalContent);
                  }
                } else if (data.type === 'error') {
                  setError(data.message || 'An error occurred during streaming');
                } else if (data.type === 'tool_start' || data.type === 'tool_end') {
                  // Pass tool events to callback
                  if (onToolEvent) {
                    onToolEvent(data);
                  }
                } else if (data.type === 'custom_event') {
                  // Pass custom events to callback (LangGraph-style progress, status, etc.)
                  if (onCustomEvent) {
                    onCustomEvent(data);
                  }
                }
              } catch (parseError) {
                // Skip invalid JSON lines
                console.warn('Failed to parse SSE data:', line);
              }
            }
          }
        }

        // Streaming complete
        setIsStreaming(false);
        onComplete();
      } catch (err: any) {
        if (err.name === 'AbortError') {
          console.log('Stream aborted by user');
        } else {
          console.error('Failed to send message:', err);
          setError(err.message || 'Failed to send message');
        }
        setIsStreaming(false);
      }
    },
    [sessionId, hitlEnabled, isStreaming]
  );

  // Cleanup on unmount
  const cancel = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsStreaming(false);
  }, []);

  return {
    sendMessage,
    isStreaming,
    error,
    clearError,
  };
}
