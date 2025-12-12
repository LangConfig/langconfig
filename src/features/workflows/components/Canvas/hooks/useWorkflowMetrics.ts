/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useMemo, useEffect } from 'react';

export interface WorkflowMetrics {
  totalEvents: number;
  chainEnds: number;
  toolCalls: number;
  agentActions: number;
  llmCalls: number;
  totalTokens: number;
  errors: number;
  duration: string;
}

interface UseWorkflowMetricsOptions {
  workflowEvents: any[];
  enableLogging?: boolean;
}

/**
 * Hook for calculating workflow execution metrics from events
 */
export function useWorkflowMetrics({
  workflowEvents,
  enableLogging = false,
}: UseWorkflowMetricsOptions): WorkflowMetrics {
  const workflowMetrics = useMemo(() => {
    const chainEnds = workflowEvents.filter(e => e.type === 'on_chain_end').length;
    const toolCalls = workflowEvents.filter(e => e.type === 'on_tool_start').length;
    const agentActions = workflowEvents.filter(e => e.type === 'on_agent_action').length;
    const llmCalls = workflowEvents.filter(e => e.type === 'on_llm_end').length;
    const errors = workflowEvents.filter(e => e.type === 'error').length;

    let totalTokens = 0;
    workflowEvents.filter(e => e.type === 'on_llm_end').forEach(e => {
      if (e.data?.tokens_used) {
        totalTokens += e.data.tokens_used;
      }
    });

    const firstEvent = workflowEvents[0];
    const lastEvent = workflowEvents[workflowEvents.length - 1];
    let duration = '0s';
    if (firstEvent && lastEvent && firstEvent.timestamp && lastEvent.timestamp) {
      const start = new Date(firstEvent.timestamp).getTime();
      const end = new Date(lastEvent.timestamp).getTime();
      const durationMs = end - start;
      const seconds = Math.floor(durationMs / 1000);
      const minutes = Math.floor(seconds / 60);
      if (minutes > 0) {
        duration = `${minutes}m ${seconds % 60}s`;
      } else {
        duration = `${seconds}s`;
      }
    }

    return {
      totalEvents: workflowEvents.length,
      chainEnds,
      toolCalls,
      agentActions,
      llmCalls,
      totalTokens,
      errors,
      duration
    };
  }, [workflowEvents]);

  // Log workflow metrics for debugging/analytics
  useEffect(() => {
    if (enableLogging && workflowMetrics.totalEvents > 0) {
      console.log('[useWorkflowMetrics] Workflow Metrics Updated:', workflowMetrics);
    }
  }, [workflowMetrics, enableLogging]);

  return workflowMetrics;
}
