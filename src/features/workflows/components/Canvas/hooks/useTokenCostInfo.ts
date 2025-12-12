/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useMemo, useEffect } from 'react';
import { calculateAndFormatCost } from '../../../../../utils/modelPricing';

interface NodeTokenCost {
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
  costString: string;
}

export interface TokenCostInfo {
  totalTokens: number;
  promptTokens: number;
  completionTokens: number;
  costString: string;
}

interface UseTokenCostInfoOptions {
  taskHistory: any[];
  selectedHistoryTask: any;
  currentModelName: string;
  workflowEvents: any[];
  nodeTokenCosts: Record<string, NodeTokenCost>;
  onTokenCostUpdate?: (info: TokenCostInfo) => void;
}

/**
 * Hook for calculating token cost information from various sources
 */
export function useTokenCostInfo({
  taskHistory,
  selectedHistoryTask,
  currentModelName,
  workflowEvents,
  nodeTokenCosts,
  onTokenCostUpdate,
}: UseTokenCostInfoOptions): TokenCostInfo {
  const tokenCostInfo = useMemo(() => {
    const displayTask = selectedHistoryTask || taskHistory[0];
    const taskOutput = displayTask?.result;

    // PRIORITY 1: Use workflow_summary from backend (most accurate, already calculated)
    if (taskOutput?.workflow_summary) {
      const summary = taskOutput.workflow_summary;
      if (summary.total_tokens > 0) {
        const costString = summary.total_cost_usd !== undefined
          ? `$${Number(summary.total_cost_usd).toFixed(4)}`
          : '$0.0000';
        return {
          totalTokens: summary.total_tokens,
          promptTokens: 0,
          completionTokens: 0,
          costString
        };
      }
    }

    // PRIORITY 2: Sum costs from per-node token costs (for live execution)
    const nodeCostValues = Object.values(nodeTokenCosts);
    if (nodeCostValues.length > 0) {
      let totalTokens = 0;
      let promptTokens = 0;
      let completionTokens = 0;
      let totalCostCents = 0;

      nodeCostValues.forEach(nodeCost => {
        totalTokens += nodeCost.totalTokens;
        promptTokens += nodeCost.promptTokens;
        completionTokens += nodeCost.completionTokens;

        const costMatch = nodeCost.costString.match(/\$(\d+\.?\d*)/);
        if (costMatch) {
          totalCostCents += Math.round(parseFloat(costMatch[1]) * 100);
        }
      });

      const costString = `$${(totalCostCents / 100).toFixed(4)}`;
      return { totalTokens, promptTokens, completionTokens, costString };
    }

    // Fallback for older workflows
    let totalTokens = 0;
    let promptTokens = 0;
    let completionTokens = 0;

    // Try to get tokens_used from task record first (if backend stored it)
    if (displayTask?.tokens_used) {
      totalTokens = displayTask.tokens_used;
    }
    // Fallback to token_usage in result
    else if (taskOutput?.token_usage) {
      totalTokens = taskOutput.token_usage.total_tokens || 0;
      promptTokens = taskOutput.token_usage.prompt_tokens || 0;
      completionTokens = taskOutput.token_usage.completion_tokens || 0;
    }

    // If not available, sum from all LLM events in workflowEvents with per-event model costs
    if (totalTokens === 0 && workflowEvents.length > 0) {
      let totalCostCents = 0;
      let hasModelInfo = false;

      workflowEvents.forEach(event => {
        if (event.type === 'on_llm_end') {
          let eventPrompt = 0;
          let eventCompletion = 0;

          if (event.data?.tokens_used) {
            const tokens = event.data.tokens_used;
            if (typeof tokens === 'number') {
              eventCompletion = tokens;  // Assume completion if just a number
            } else if (tokens.prompt_tokens || tokens.completion_tokens) {
              eventPrompt = tokens.prompt_tokens || 0;
              eventCompletion = tokens.completion_tokens || 0;
            }
          } else if (event.data?.prompt_tokens || event.data?.completion_tokens) {
            eventPrompt = event.data.prompt_tokens || 0;
            eventCompletion = event.data.completion_tokens || 0;
          }

          promptTokens += eventPrompt;
          completionTokens += eventCompletion;
          totalTokens += eventPrompt + eventCompletion;

          // Calculate cost for this event if model is available
          const modelName = event.data?.model || event.data?.model_name;
          if (modelName) {
            hasModelInfo = true;
            const eventCostString = calculateAndFormatCost(eventPrompt, eventCompletion, modelName);
            const costMatch = eventCostString.match(/\$(\d+\.?\d*)/);
            if (costMatch) {
              totalCostCents += Math.round(parseFloat(costMatch[1]) * 100);
            }
          }
        }
      });

      // If we calculated per-event costs, use that instead of single-model calculation
      if (hasModelInfo && totalCostCents > 0) {
        const costString = `$${(totalCostCents / 100).toFixed(4)}`;
        return { totalTokens, promptTokens, completionTokens, costString };
      }
    }

    // Final fallback: estimate from agent messages
    if (totalTokens === 0 && taskOutput?.agent_messages) {
      taskOutput.agent_messages.forEach((msg: any) => {
        if (msg.role === 'human' || msg.role === 'system') {
          const tokens = Math.ceil((msg.content?.length || 0) / 4);
          promptTokens += tokens;
        } else if (msg.role === 'ai') {
          const tokens = Math.ceil((msg.content?.length || 0) / 4);
          completionTokens += tokens;
        }
      });
      totalTokens = promptTokens + completionTokens;
    }

    const costString = calculateAndFormatCost(promptTokens, completionTokens, currentModelName);
    return { totalTokens, promptTokens, completionTokens, costString };
  }, [taskHistory, selectedHistoryTask, currentModelName, workflowEvents, nodeTokenCosts]);

  // Notify parent of token cost updates
  useEffect(() => {
    if (onTokenCostUpdate && tokenCostInfo.totalTokens > 0) {
      onTokenCostUpdate(tokenCostInfo);
    }
  }, [tokenCostInfo, onTokenCostUpdate]);

  return tokenCostInfo;
}
