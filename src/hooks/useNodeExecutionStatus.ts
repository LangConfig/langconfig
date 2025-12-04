/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * useNodeExecutionStatus Hook
 *
 * Maps SSE workflow execution events to node-specific execution status.
 * Enables real-time visualization of agent thinking and execution state on canvas nodes.
 *
 * Features:
 * - Tracks execution state per node (idle, running, completed, error)
 * - Captures agent thinking/reasoning from on_agent_action events
 * - Provides abbreviated and full thinking text
 * - Auto-clears thinking when node completes
 * - Performance-optimized with throttling
 *
 * Usage:
 *   const nodeStatuses = useNodeExecutionStatus(workflowId, {
 *     taskId: currentTaskId,
 *     throttleMs: 200
 *   });
 *
 *   // In CustomNode component:
 *   const status = nodeStatuses[data.label];
 *   if (status?.state === 'running') {
 *     // Show thinking visualization
 *   }
 */

import { useMemo, useState, useEffect, useCallback, useRef } from 'react';
import { useWorkflowStream } from './useWorkflowStream';
import { WorkflowEvent } from '../types/events';
import { calculateAndFormatCost } from '../utils/modelPricing';

export type NodeExecutionState = 'idle' | 'running' | 'thinking' | 'completed' | 'error';

export interface NodeExecutionStatus {
  /** Current execution state */
  state: NodeExecutionState;

  /** Full agent thinking/reasoning text */
  thinking: string;

  /** Abbreviated thinking for compact display (first 50 chars) */
  thinkingPreview: string;

  /** Start timestamp */
  startTime?: string;

  /** End timestamp */
  endTime?: string;

  /** Duration in milliseconds */
  durationMs?: number;

  /** Error message if state is 'error' */
  error?: string;

  /** Latest event that updated this node */
  latestEvent?: WorkflowEvent;

  /** Tool being executed (if in tool execution) */
  activeTool?: string;

  /** Recently completed tool */
  toolCompleted?: string;

  /** Time when tool completed */
  toolCompletedTime?: number;

  /** Progress indicator (0-100) */
  progress?: number;

  /** Token cost information */
  tokenCost?: {
    promptTokens: number;
    completionTokens: number;
    totalTokens: number;
    costString: string;
  };

  /** Diagnostics/warnings for this node */
  warnings?: Array<{
    type: string;
    severity: 'warning' | 'error';
    message: string;
  }>;

  /** Internal tracking: are we accumulating thinking content */
  _accumulatingThinking?: boolean;

  /** Internal tracking: are we generating output */
  _generatingOutput?: boolean;

  /** Internal tracking: accumulated stream tokens */
  _streamAccumulator?: string;
}

export interface UseNodeExecutionStatusOptions {
  /** Task ID for loading historical events */
  taskId?: number | null;

  /** Maximum length of thinking text to keep in memory (default: 5000 chars) */
  maxThinkingLength?: number;
}

export type NodeExecutionStatusMap = Record<string, NodeExecutionStatus>;

/**
 * Hook to track execution status for all nodes in a workflow
 */
export function useNodeExecutionStatus(
  workflowId: number | null,
  options: UseNodeExecutionStatusOptions = {}
): NodeExecutionStatusMap {
  const {
    taskId = null,
    maxThinkingLength = 5000,
  } = options;

  // Get workflow events stream
  const { events } = useWorkflowStream(workflowId, {
    autoConnect: true,
    taskId,
    loadHistorical: true,
  });

  // State for node statuses
  const [nodeStatuses, setNodeStatuses] = useState<NodeExecutionStatusMap>({});

  // Track last processed event index to avoid reprocessing
  const lastProcessedIndexRef = useRef<number>(-1);

  // Track streaming rate for throttling
  const streamingRateRef = useRef<{ [nodeLabel: string]: {
    lastUpdate: number;
    updateCount: number;
    buffer: string;
    paragraphBuffer: string[];
    lastParagraphSwitch: number;
  } }>({});

  /**
   * Extract node label from event data
   */
  const getNodeLabelFromEvent = useCallback((event: WorkflowEvent): string | null => {
    // Try different field names based on event type
    const data = event.data;

    if (!data) return null;

    // Backend sends agent_label for all events including tools (see execution_events.py)
    const label = data.agent_label || data.name || null;

    // FILTER OUT infrastructure/system nodes that aren't real agents
    if (label) {
      const lowerLabel = label.toLowerCase();
      const systemNodes = [
        'build_graph',
        'langgraph',
        'node-',  // Matches node-1, node-15, etc
        '__start__',
        '__end__',
        'ping',
        'runnablelambda',
        'runnablesequence',
      ];

      // Check if this is a system node
      if (systemNodes.some(sysNode => lowerLabel.includes(sysNode))) {
        return null; // Ignore this node
      }
    }

    return label;
  }, []);

  /**
   * Truncate thinking text for preview - preserve word boundaries
   */
  const getTruncatedThinking = useCallback((fullText: string, maxLength: number = 50): string => {
    if (fullText.length <= maxLength) {
      return fullText;
    }

    // Find the last space before maxLength to avoid cutting words
    let truncateAt = maxLength;
    const lastSpace = fullText.lastIndexOf(' ', maxLength);
    if (lastSpace > maxLength * 0.8) { // Only use space if it's not too far back
      truncateAt = lastSpace;
    }

    return fullText.substring(0, truncateAt).trim() + '...';
  }, []);

  /**
   * Process events and update node statuses
   */
  useEffect(() => {
    if (events.length === 0) return;

    // Only process NEW events since last update
    const newEvents = events.slice(lastProcessedIndexRef.current + 1);
    if (newEvents.length === 0) return;

    // Build status updates from new events only
    setNodeStatuses((prevStatuses) => {
      const newStatuses = { ...prevStatuses };

      newEvents.forEach((event) => {
        const nodeLabel = getNodeLabelFromEvent(event);

        if (!nodeLabel) return;

        // Get or initialize node status
        const currentStatus = newStatuses[nodeLabel] || {
          state: 'idle' as const,
          thinking: '',
          thinkingPreview: '',
        };

        let updatedStatus: NodeExecutionStatus = { ...currentStatus };

      switch (event.type) {
        case 'on_chain_start':
          // Skip ping events - they shouldn't trigger any UI updates
          if (event.data?.name === 'ping' || event.data?.agent_label === 'ping') {
            return; // Skip this event entirely
          }

          // IMPORTANT: Do NOT reset token costs on chain_start!
          // LangChain emits multiple chain_start events during execution:
          // - Outer chain starts
          // - Inner chains/subchains start
          // - Each recursion/retry emits chain_start
          // Resetting token costs on every chain_start destroys the accumulation.
          // Token costs should only be reset at workflow start or task change.
          updatedStatus = {
            ...updatedStatus,
            state: 'running',
            thinking: '', // Empty until streaming tokens arrive
            thinkingPreview: '',
            startTime: currentStatus.startTime || event.timestamp, // Keep original start time if already set
            latestEvent: event,
            progress: 10,
            // DO NOT reset tokenCost here - preserve accumulated tokens
            tokenCost: currentStatus.tokenCost, // Keep existing token costs
          };
          break;

        case 'on_agent_action':
          // Agent is thinking/reasoning
          const reasoning = event.data?.reasoning ||
                           event.data?.thought ||
                           event.data?.thinking ||
                           event.data?.message || '';

          // Capture any reasoning text
          if (reasoning && reasoning.length > 0) {
            const truncatedThinking = getTruncatedThinking(reasoning, 50);

            updatedStatus = {
              ...updatedStatus,
              state: 'thinking',
              thinking: reasoning.substring(0, maxThinkingLength), // Limit memory usage
              thinkingPreview: truncatedThinking,
              latestEvent: event,
              progress: 50,
              _accumulatingThinking: true, // Mark as thinking
            };

          }
          break;

        case 'on_tool_start':
        case 'tool_start':  // Support both event types
          // Tool execution starting
          const toolName = event.data?.tool_name || event.data?.tool || event.data?.name || 'unknown';
          const toolInputs = event.data?.inputs || {};

          // Log to help debug what tool names we're getting

          // Extract relevant info from tool inputs to show user what's happening
          let toolContext = '';

          // Check for enhanced file_write info from backend
          if (event.data?.file_action && event.data?.filename) {
            // Use the backend's smart "Creating" or "Working on" message
            toolContext = `${event.data.file_action} ${event.data.filename}`;
          } else if (toolName === 'memory_store' && toolInputs.key) {
            const preview = toolInputs.value?.substring(0, 100) || '';
            toolContext = `Storing: "${toolInputs.key}" - ${preview}${preview.length >= 100 ? '...' : ''}`;
          } else if (toolName === 'web_search' && toolInputs.query) {
            toolContext = `Searching: "${toolInputs.query}"`;
          } else if (toolName === 'web_fetch' && toolInputs.url) {
            toolContext = `Fetching: ${toolInputs.url}`;
          } else if (toolName === 'file_write' && toolInputs.file_path) {
            toolContext = `Writing to: ${toolInputs.file_path}`;
          } else if (toolName === 'file_read' && toolInputs.file_path) {
            toolContext = `Reading: ${toolInputs.file_path}`;
          } else if (event.data?.input_preview) {
            toolContext = event.data.input_preview.substring(0, 150);
          }

          // Format tool name for display
          let displayToolName = toolName;
          if (toolName === 'web_search' || toolName === 'search_web') {
            displayToolName = 'Searching web';
          } else if (toolName === 'web_fetch') {
            displayToolName = 'Fetching webpage';
          } else if (toolName === 'browser' || toolName === 'browser_navigate') {
            displayToolName = 'Browser automation';
          } else if (toolName === 'file_read') {
            displayToolName = 'Reading file';
          } else if (toolName === 'file_write') {
            displayToolName = 'Writing file';
          } else if (toolName === 'file_list') {
            displayToolName = 'Listing files';
          } else if (toolName === 'memory_store') {
            displayToolName = 'Storing memory';
          } else if (toolName === 'memory_recall') {
            displayToolName = 'Recalling memory';
          } else if (toolName === 'reasoning_chain' || toolName === 'sequential_thinking') {
            displayToolName = 'Reasoning';
          } else if (toolName === 'create_agent') {
            displayToolName = 'Creating agent';
          }

          updatedStatus = {
            ...updatedStatus,
            state: 'running',
            // Show tool context as thinking text if available
            thinking: toolContext || updatedStatus.thinking,
            thinkingPreview: toolContext ? getTruncatedThinking(toolContext, 150) : updatedStatus.thinkingPreview,
            activeTool: displayToolName + '...', // Show tool with static dots
            toolCompleted: undefined, // Clear any previous completed tool
            latestEvent: event,
            progress: 60,
            _accumulatingThinking: true, // KEEP accumulating thinking during tool call
          };
          break;

        case 'on_tool_end':
          // Tool execution completed
          const completedToolName = event.data?.tool_name || updatedStatus.activeTool;

          updatedStatus = {
            ...updatedStatus,
            state: 'running',
            activeTool: undefined,
            toolCompleted: completedToolName ? completedToolName.replace(/\.{3}$/, '') : undefined, // Remove dots from completed tool
            toolCompletedTime: Date.now(),
            latestEvent: event,
            progress: 80,
            // DON'T clear thinking - let it persist
            _accumulatingThinking: true, // Continue accumulating thinking after tool
          };

          // Clear tool completed after 2 seconds
          setTimeout(() => {
            setNodeStatuses(prev => {
              const nodeStatus = prev[nodeLabel];
              if (nodeStatus && nodeStatus.toolCompletedTime === updatedStatus.toolCompletedTime) {
                return {
                  ...prev,
                  [nodeLabel]: {
                    ...nodeStatus,
                    toolCompleted: undefined,
                  }
                };
              }
              return prev;
            });
          }, 2000);
          break;

        case 'on_chat_model_stream':
        case 'on_llm_stream':
        case 'token':
          // Capture LLM streaming tokens and display as thinking text
          // Check both 'content' (new) and 'token' (old) for backward compatibility
          const chunk = event.data?.content || event.data?.token || '';
          if (!chunk) break;

          // Initialize rate tracking for this node if needed
          if (!streamingRateRef.current[nodeLabel]) {
            streamingRateRef.current[nodeLabel] = {
              lastUpdate: 0,
              updateCount: 0,
              buffer: '',
              paragraphBuffer: [],
              lastParagraphSwitch: Date.now()
            };
          }

          const rateInfo = streamingRateRef.current[nodeLabel];
          const now = Date.now();
          const timeSinceLastUpdate = now - rateInfo.lastUpdate;

          // Buffer the incoming chunks
          rateInfo.buffer += chunk;
          rateInfo.updateCount++;

          // Update only on time threshold or when buffer is full
          // AGGRESSIVE updates to show thinking text immediately
          const shouldUpdate =
            timeSinceLastUpdate > 100 || // Update every 100ms (10 updates per second)
            rateInfo.buffer.length > 20; // Accumulate 20 chars before forcing update

          if (shouldUpdate) {
            const bufferedContent = rateInfo.buffer;
            rateInfo.buffer = ''; // Clear buffer
            rateInfo.lastUpdate = now;

            // Build up the accumulated stream content
            const currentText = updatedStatus._streamAccumulator || '';
            const newText = currentText + bufferedContent;

            // Aggressive sanitization for agent thinking text
            const cleanedText = newText
              // Remove XML/HTML tags
              .replace(/<thinking[^>]*>|<\/thinking>/gi, '')
              .replace(/<tool_call[^>]*>|<\/tool_call>/gi, '')
              .replace(/<[^>]+>/g, '')
              // Remove JSON artifacts
              .replace(/\{\s*"[^"]+"\s*:\s*"[^"]*"\s*\}/g, '')
              .replace(/[\[\]{}]/g, '')
              // Remove escaped characters
              .replace(/\\n/g, ' ')
              .replace(/\\t/g, ' ')
              .replace(/\\r/g, '')
              .replace(/\\"/g, '"')
              // Collapse whitespace
              .replace(/\n{2,}/g, ' ')       // Replace 2+ newlines with single space
              .replace(/[ \t]{2,}/g, ' ')    // Collapse multiple spaces to single space
              .trim();                        // Remove leading/trailing whitespace

            // Show the most recent 2000 characters (no "..." prefix to avoid word breaks)
            const displayText = cleanedText.length > 2000
              ? cleanedText.slice(-2000)
              : cleanedText;

            updatedStatus = {
              ...updatedStatus,
              state: 'thinking',
              thinking: displayText,
              thinkingPreview: getTruncatedThinking(displayText, 150),
              latestEvent: event,
              progress: 50,
              _streamAccumulator: newText, // Store full stream
            };

          }
          break;

        case 'on_chain_end':
          // Node completed successfully - check if this is the final workflow completion
          const isWorkflowCompletion = event.data?.name === 'workflow_execution';

          if (isWorkflowCompletion) {
            // Clear the node status entirely for workflow completion
            updatedStatus = {
              state: 'idle',
              thinking: '',
              thinkingPreview: '',
              progress: 0,
            };
          } else {
            updatedStatus = {
              ...updatedStatus,
              state: 'completed',
              thinking: '', // Clear thinking on completion
              thinkingPreview: '',
              endTime: event.timestamp,
              durationMs: updatedStatus.startTime
                ? new Date(event.timestamp!).getTime() - new Date(updatedStatus.startTime).getTime()
                : undefined,
              latestEvent: event,
              activeTool: undefined,
              progress: 100,
              _streamAccumulator: '', // Clear accumulated stream
            };
          }

          // Also clear streaming buffer for this node
          if (streamingRateRef.current[nodeLabel]) {
            streamingRateRef.current[nodeLabel].buffer = '';
          }
          break;

        case 'error':
          // Node encountered an error
          const errorMsg = event.data?.error || event.data?.message || 'Unknown error';

          // Check if this is a cancellation
          if (errorMsg.includes('cancelled') || errorMsg.includes('TaskCancelled')) {
            // Clear ALL node statuses on cancellation
            // We'll handle this by returning an empty status map
            Object.keys(newStatuses).forEach(key => {
              newStatuses[key] = {
                state: 'idle',
                thinking: '',
                thinkingPreview: '',
                activeTool: undefined,
                toolCompleted: undefined,
                progress: 0,
              };
            });
          } else {
            updatedStatus = {
              ...updatedStatus,
              state: 'error',
              error: errorMsg,
              endTime: event.timestamp,
              latestEvent: event,
              thinking: '',
              thinkingPreview: '',
              progress: 0,
            };
          }
          break;

        case 'on_llm_end':
          // LLM call completed - extract token usage and calculate cost
          const tokenUsage = event.data?.token_usage || event.data?.usage;
          if (tokenUsage) {
            const promptTokens = tokenUsage.prompt_tokens || 0;
            const completionTokens = tokenUsage.completion_tokens || 0;
            const totalTokens = tokenUsage.total_tokens || (promptTokens + completionTokens);

            // Get model name from event data or use default
            const modelName = event.data?.model || event.data?.model_name || 'gpt-4o';

            // ACCUMULATE token costs instead of replacing them
            const existingCost = updatedStatus.tokenCost || { promptTokens: 0, completionTokens: 0, totalTokens: 0, costString: '$0.00' };
            const accumulatedPromptTokens = existingCost.promptTokens + promptTokens;
            const accumulatedCompletionTokens = existingCost.completionTokens + completionTokens;
            const accumulatedTotalTokens = existingCost.totalTokens + totalTokens;

            // Calculate accumulated cost
            const costString = calculateAndFormatCost(accumulatedPromptTokens, accumulatedCompletionTokens, modelName);

            updatedStatus = {
              ...updatedStatus,
              tokenCost: {
                promptTokens: accumulatedPromptTokens,
                completionTokens: accumulatedCompletionTokens,
                totalTokens: accumulatedTotalTokens,
                costString,
              },
              latestEvent: event,
            };
          }
          break;

        case 'complete':
          // Workflow completed - clear this node's status immediately
          updatedStatus = {
            state: 'idle',
            thinking: '',
            thinkingPreview: '',
            progress: 0,
          };
          break;

        case 'status':
        case 'node_status':
          // Backend status events that might contain thinking or tool info
          const statusData = event.data;
          if (statusData) {
            const statusThinking = statusData.thinking || statusData.message || statusData.status_message || '';
            const statusTool = statusData.tool || statusData.active_tool || statusData.current_tool;

            if (statusThinking || statusTool) {
              updatedStatus = {
                ...updatedStatus,
                state: statusData.state || 'running',
                thinking: statusThinking ? statusThinking.substring(0, maxThinkingLength) : updatedStatus.thinking,
                thinkingPreview: statusThinking ? getTruncatedThinking(statusThinking, 50) : updatedStatus.thinkingPreview,
                activeTool: statusTool || updatedStatus.activeTool,
                latestEvent: event,
              };
            }
          }
          break;

        default:
          // Log unknown event types for debugging in development
          if (event.type && !event.type.startsWith('on_') && event.data?.agent_label === nodeLabel) {
          }
          break;
      }

        newStatuses[nodeLabel] = updatedStatus;
      });

      return newStatuses;
    });

    // Mark events as processed
    lastProcessedIndexRef.current = events.length - 1;
  }, [events, getNodeLabelFromEvent, getTruncatedThinking, maxThinkingLength]);

  // Clear node statuses when workflow completes or errors
  useEffect(() => {
    const completeEvent = events.find((e) => e.type === 'complete' || e.type === 'error');
    if (completeEvent) {
      // After a brief delay, reset all nodes to idle for next execution
      const timeout = setTimeout(() => {
        setNodeStatuses((prev) => {
          const resetStatuses: NodeExecutionStatusMap = {};
          Object.keys(prev).forEach((nodeLabel) => {
            resetStatuses[nodeLabel] = {
              state: 'idle',
              thinking: '',
              thinkingPreview: '',
            };
          });
          return resetStatuses;
        });
        // Reset processed event index for next run
        lastProcessedIndexRef.current = -1;
      }, 3000); // 3 second delay to let user see final completed states

      return () => clearTimeout(timeout);
    }
  }, [events]);

  return nodeStatuses;
}

/**
 * Helper hook to get status for a specific node
 */
export function useNodeStatus(
  workflowId: number | null,
  nodeLabel: string,
  options?: UseNodeExecutionStatusOptions
): NodeExecutionStatus | null {
  const allStatuses = useNodeExecutionStatus(workflowId, options);
  return allStatuses[nodeLabel] || null;
}

/**
 * Helper hook to get active (non-idle) nodes
 */
export function useActiveNodes(
  workflowId: number | null,
  options?: UseNodeExecutionStatusOptions
): string[] {
  const allStatuses = useNodeExecutionStatus(workflowId, options);

  return useMemo(() => {
    return Object.entries(allStatuses)
      .filter(([_, status]) => status.state !== 'idle' && status.state !== 'completed')
      .map(([nodeLabel]) => nodeLabel);
  }, [allStatuses]);
}

/**
 * Helper hook to get the currently executing node
 */
export function useCurrentNode(
  workflowId: number | null,
  options?: UseNodeExecutionStatusOptions
): string | null {
  const allStatuses = useNodeExecutionStatus(workflowId, options);

  return useMemo(() => {
    // Find the node that was most recently updated and is running/thinking
    let latestNode: string | null = null;
    let latestTime = 0;

    Object.entries(allStatuses).forEach(([nodeLabel, status]) => {
      if (status.state === 'running' || status.state === 'thinking') {
        const eventTime = status.latestEvent?.timestamp
          ? new Date(status.latestEvent.timestamp).getTime()
          : 0;

        if (eventTime > latestTime) {
          latestTime = eventTime;
          latestNode = nodeLabel;
        }
      }
    });

    return latestNode;
  }, [allStatuses]);
}
