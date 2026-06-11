/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useCallback, useRef } from 'react';
import type { ChatMessage, ChatStreamEvent } from '../types/chat';
import type { ContentBlock } from '@/types/content-blocks';
import apiClient from '../../../lib/api-client';
import { normalizeChatStreamEvent } from '../stream/chatStreamAdapter';

interface UseChatStreamingResult {
  sendMessage: (
    message: string,
    onMessageAdd: (message: ChatMessage) => void,
    onMessageUpdate: (content: string, patch?: Partial<ChatMessage>) => void,
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
      onMessageUpdate: (content: string, patch?: Partial<ChatMessage>) => void,
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
        let accumulatedThinking = '';
        let assistantMessageAdded = false;
        let streamedArtifacts: ContentBlock[] = [];
        let streamedContentBlocks: ContentBlock[] = [];

        const ensureAssistantMessage = () => {
          if (assistantMessageAdded) return;

          const assistantMessage: ChatMessage = {
            role: 'assistant',
            content: accumulatedContent,
            timestamp: new Date().toISOString(),
            artifacts: streamedArtifacts,
            content_blocks: streamedContentBlocks,
            has_multimodal: streamedContentBlocks.length > 0,
          };
          onMessageAdd(assistantMessage);
          assistantMessageAdded = true;
        };

        const patchAssistantMessage = () => {
          ensureAssistantMessage();
          onMessageUpdate(accumulatedContent, {
            artifacts: streamedArtifacts,
            content_blocks: streamedContentBlocks,
            has_multimodal: streamedContentBlocks.length > 0,
          });
        };

        while (true) {
          const { done, value } = await reader.read();

          if (done) break;

          const chunk = decoder.decode(value, { stream: true });
          const lines = chunk.split('\n');

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data: ChatStreamEvent = JSON.parse(line.substring(6));
                const part = normalizeChatStreamEvent(data);

                if (!part) continue;

                if (part.type === 'thinking_delta') {
                  // Model reasoning (Anthropic adaptive thinking) — kept
                  // separate from content; surfaced via message.thinking
                  accumulatedThinking += part.text;
                  ensureAssistantMessage();
                  onMessageUpdate(accumulatedContent, { thinking: accumulatedThinking });
                } else if (part.type === 'text_delta') {
                  // Stream individual tokens as they arrive
                  accumulatedContent += part.text;

                  // Add assistant message on first chunk
                  ensureAssistantMessage();
                  onMessageUpdate(accumulatedContent, {
                    artifacts: streamedArtifacts,
                    content_blocks: streamedContentBlocks,
                    has_multimodal: streamedContentBlocks.length > 0,
                  });
                } else if (part.type === 'complete') {
                  // Final content - use accumulated or provided
                  const finalContent = part.text || accumulatedContent;
                  streamedArtifacts = part.artifacts.length > 0 ? part.artifacts : streamedArtifacts;
                  streamedContentBlocks = part.contentBlocks.length > 0 ? part.contentBlocks : streamedContentBlocks;
                  if (finalContent !== accumulatedContent) {
                    accumulatedContent = finalContent;
                  }
                  patchAssistantMessage();
                } else if (part.type === 'error') {
                  setError(part.message);
                } else if (part.type === 'tool_started' || part.type === 'tool_completed') {
                  // Pass tool events to callback
                  if (onToolEvent) {
                    onToolEvent(data);
                  }
                } else if (part.type === 'artifact') {
                  streamedArtifacts = [...streamedArtifacts, part.artifact];
                  if (part.artifact.type === 'image' || part.artifact.type === 'audio' || part.artifact.type === 'file' || part.artifact.type === 'resource') {
                    streamedContentBlocks = [...streamedContentBlocks, part.artifact];
                  }
                  patchAssistantMessage();
                } else if (part.type === 'custom') {
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
