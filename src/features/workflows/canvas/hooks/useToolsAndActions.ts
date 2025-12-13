/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useMemo } from 'react';

interface ToolCall {
  name: string;
  agent: string;
  args: string;
  result: any;
}

interface ToolsAndActions {
  tools: ToolCall[];
  actions: string[];
  toolCount: number;
  actionCount: number;
}

interface UseToolsAndActionsOptions {
  taskHistory: any[];
  selectedHistoryTask: any;
}

/**
 * Hook for extracting tools and actions from task history for results display
 */
export function useToolsAndActions({
  taskHistory,
  selectedHistoryTask,
}: UseToolsAndActionsOptions): ToolsAndActions {
  return useMemo(() => {
    const displayTask = selectedHistoryTask || taskHistory[0];
    const taskOutput = displayTask?.result;
    const tools: ToolCall[] = [];
    const actions: string[] = [];

    if (taskOutput?.agent_messages) {
      for (let i = 0; i < taskOutput.agent_messages.length; i++) {
        const msg = taskOutput.agent_messages[i];

        if (msg.tool_calls && Array.isArray(msg.tool_calls)) {
          msg.tool_calls.forEach((tc: any) => {
            const toolName = tc.function?.name || tc.name || 'unknown_tool';
            const toolArgs = tc.function?.arguments || tc.args || '{}';

            let toolResult = null;
            for (let j = i + 1; j < taskOutput.agent_messages.length; j++) {
              const nextMsg = taskOutput.agent_messages[j];
              if (nextMsg.role === 'tool' && nextMsg.name === toolName) {
                toolResult = nextMsg.content;
                break;
              }
            }

            tools.push({
              name: toolName,
              agent: msg.name || 'Agent',
              args: toolArgs,
              result: toolResult
            });
          });
        }

        if (taskOutput.agent_messages[i].role === 'ai' && taskOutput.agent_messages[i].content) {
          const msg = taskOutput.agent_messages[i];
          const content = typeof msg.content === 'string' ? msg.content : '';
          const cleanContent = content.replace(/<thinking>[\s\S]*?<\/thinking>/gi, '');

          const lowerContent = cleanContent.toLowerCase();
          if (lowerContent.includes('role definition') ||
            lowerContent.includes('agent framework') ||
            lowerContent.includes('react methodology') ||
            lowerContent.includes('instruction to complete')) {
            continue;
          }

          const lines = cleanContent.split('\n');
          lines.forEach((line: string) => {
            const trimmed = line.trim();
            const lowerLine = trimmed.toLowerCase();

            if (lowerLine.includes('role definition') ||
              lowerLine.includes('agent framework') ||
              lowerLine.includes('research findings') ||
              lowerLine.includes('source materials') ||
              lowerLine.includes('empty context')) {
              return;
            }

            if (trimmed.length > 15 && trimmed.length < 150 &&
              (trimmed.match(/^[-*•]\s+/) ||
                trimmed.match(/^\d+\.\s+/) ||
                trimmed.match(/^(Analyzed|Found|Created|Generated|Retrieved|Completed|Processed|Searched|Fetched|Identified|Discovered):/i))) {
              actions.push(trimmed.replace(/^[-*•\d.]+\s*/, '').substring(0, 100));
            }
          });
        }
      }
    }

    return { tools, actions, toolCount: tools.length, actionCount: actions.length };
  }, [taskHistory, selectedHistoryTask]);
}
