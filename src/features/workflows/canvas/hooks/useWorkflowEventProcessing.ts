/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useEffect, useState, SetStateAction, Dispatch } from 'react';
import { analyzeWorkflowEvents } from '@/utils/workflowErrorDetector';

interface NodeTokenCost {
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
  costString: string;
}

interface ExecutionStatus {
  state: 'idle' | 'running' | 'completed' | 'failed';
  currentNode?: string;
  progress: number;
  startTime?: string;
  duration?: string;
}

interface NodeWarning {
  type: string;
  severity: 'warning' | 'error';
  message: string;
}

interface UseWorkflowEventProcessingOptions {
  workflowEvents: any[];
  latestEvent: any;
  executionStatus: ExecutionStatus;
  setExecutionStatus: Dispatch<SetStateAction<ExecutionStatus>>;
  currentWorkflowId: number | null;
  nodeExecutionStatuses: Record<string, { tokenCost?: NodeTokenCost }>;
}

interface UseWorkflowEventProcessingReturn {
  nodeWarnings: Record<string, NodeWarning[]>;
  nodeTokenCosts: Record<string, NodeTokenCost>;
  setNodeTokenCosts: React.Dispatch<React.SetStateAction<Record<string, NodeTokenCost>>>;
}

/**
 * Hook for processing workflow events and extracting warnings, token costs, and errors
 */
export function useWorkflowEventProcessing({
  workflowEvents,
  latestEvent,
  executionStatus,
  setExecutionStatus,
  currentWorkflowId,
  nodeExecutionStatuses,
}: UseWorkflowEventProcessingOptions): UseWorkflowEventProcessingReturn {
  // Node warnings from event analysis
  const [nodeWarnings, setNodeWarnings] = useState<Record<string, NodeWarning[]>>({});

  // Per-node token costs stored by node label
  const [nodeTokenCosts, setNodeTokenCosts] = useState<Record<string, NodeTokenCost>>(() => {
    // Load from localStorage on mount
    if (currentWorkflowId) {
      const saved = localStorage.getItem(`workflow-${currentWorkflowId}-token-costs`);
      if (saved) {
        try {
          return JSON.parse(saved);
        } catch (e) {
          console.error('Failed to parse saved token costs:', e);
        }
      }
    }
    return {};
  });

  // Process workflow events
  useEffect(() => {
    if (workflowEvents.length > 0) {
      // Analyze workflow events for common issues
      const diagnoses = analyzeWorkflowEvents(workflowEvents);

      // Map diagnoses to nodes
      const warningsMap: Record<string, NodeWarning[]> = {};

      diagnoses.forEach(diagnosis => {
        const nodeId = diagnosis.nodeId || 'unknown';

        if (!warningsMap[nodeId]) {
          warningsMap[nodeId] = [];
        }

        warningsMap[nodeId].push({
          type: diagnosis.type,
          severity: diagnosis.severity,
          message: diagnosis.message
        });
      });

      setNodeWarnings(warningsMap);

      // Check for errors in the events (for logging only)
      const errorEvents = workflowEvents.filter(e => e.type === 'error');
      if (errorEvents.length > 0) {
        const latestError = errorEvents[errorEvents.length - 1];
        console.error('[useWorkflowEventProcessing] Workflow error detected:', latestError.data);
      }

      // Check for complete event with error status - stop execution spinner
      const completeEvent = workflowEvents.find(e => e.type === 'complete');
      if (completeEvent?.data?.status === 'error') {
        console.log('[useWorkflowEventProcessing] Workflow completed with error status:', completeEvent.data?.error);
        // Stop execution state if still running
        if (executionStatus.state === 'running') {
          setExecutionStatus({
            state: 'failed',
            currentNode: undefined,
            progress: 0,
            startTime: executionStatus.startTime,
            duration: executionStatus.duration,
          });
        }
      }

      // Process node_completed events to update token costs
      const nodeCompletedEvents = workflowEvents.filter(e => e.type === 'node_completed');
      if (nodeCompletedEvents.length > 0) {
        nodeCompletedEvents.forEach(event => {
          const agentLabel = event.data?.agent_label;
          const tokenCost = event.data?.tokenCost;

          if (agentLabel && tokenCost) {
            setNodeTokenCosts(prev => {
              // Only update if different to avoid unnecessary re-renders
              if (prev[agentLabel]?.totalTokens === tokenCost.totalTokens) {
                return prev;
              }
              return {
                ...prev,
                [agentLabel]: {
                  promptTokens: tokenCost.promptTokens || 0,
                  completionTokens: tokenCost.completionTokens || 0,
                  totalTokens: tokenCost.totalTokens || 0,
                  costString: tokenCost.costString || '$0.00'
                }
              };
            });
          }
        });
      }
    }
  }, [workflowEvents, latestEvent, executionStatus.state, executionStatus.startTime, executionStatus.duration, setExecutionStatus]);

  // Save nodeTokenCosts to localStorage whenever they change
  useEffect(() => {
    if (currentWorkflowId && Object.keys(nodeTokenCosts).length > 0) {
      localStorage.setItem(`workflow-${currentWorkflowId}-token-costs`, JSON.stringify(nodeTokenCosts));
    }
  }, [nodeTokenCosts, currentWorkflowId]);

  // Update nodeTokenCosts when execution status has token cost data
  useEffect(() => {
    Object.entries(nodeExecutionStatuses).forEach(([nodeLabel, status]) => {
      if (status.tokenCost) {
        setNodeTokenCosts(prev => {
          // Only update if different to avoid unnecessary re-renders
          if (prev[nodeLabel]?.totalTokens === status.tokenCost?.totalTokens) {
            return prev;
          }
          const newCosts = { ...prev };
          newCosts[nodeLabel] = status.tokenCost!;
          return newCosts;
        });
      }
    });
  }, [nodeExecutionStatuses]);

  return {
    nodeWarnings,
    nodeTokenCosts,
    setNodeTokenCosts,
  };
}
