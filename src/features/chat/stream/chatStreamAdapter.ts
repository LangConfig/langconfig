/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import type { ContentBlock } from '@/types/content-blocks';
import type { ChatStreamEvent } from '../types/chat';

export type NormalizedChatStreamPart =
  | { type: 'text_delta'; text: string }
  | { type: 'complete'; text: string; artifacts: ContentBlock[]; contentBlocks: ContentBlock[] }
  | { type: 'error'; message: string }
  | { type: 'tool_started' | 'tool_completed'; toolName?: string; data?: any }
  | { type: 'artifact'; toolName?: string; artifact: ContentBlock }
  | { type: 'custom'; data: any };

export function normalizeChatStreamEvent(event: ChatStreamEvent): NormalizedChatStreamPart | null {
  switch (event.type) {
    case 'chunk':
      return { type: 'text_delta', text: event.content || '' };
    case 'complete':
      return {
        type: 'complete',
        text: event.content || '',
        artifacts: event.artifacts || [],
        contentBlocks: event.content_blocks || [],
      };
    case 'error':
      return { type: 'error', message: event.message || 'An error occurred during streaming' };
    case 'tool_start':
      return { type: 'tool_started', toolName: event.tool_name, data: event.data };
    case 'tool_end':
      return { type: 'tool_completed', toolName: event.tool_name, data: event.data };
    case 'tool_artifact':
      return event.artifact ? { type: 'artifact', toolName: event.tool_name, artifact: event.artifact } : null;
    case 'custom_event':
      return { type: 'custom', data: event };
    default:
      return null;
  }
}
