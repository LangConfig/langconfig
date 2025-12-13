/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useCallback } from 'react';
import { Node, Edge } from 'reactflow';
import apiClient from '@/lib/api-client';

interface ExecutionStatus {
  state: 'idle' | 'running' | 'completed' | 'failed';
  currentNode?: string;
  progress: number;
  startTime?: string;
  duration?: string;
}

interface ExecutionConfig {
  directive: string;
  query: string;
  task: string;
  classification: string;
  executor_type: string;
  max_retries: number;
  max_events?: number;
  timeout_seconds?: number;
}

interface UseExecutionHandlersOptions {
  nodes: Node[];
  edges: Edge[];
  currentWorkflowId: number | null;
  currentTaskId: number | null;
  executionStatus: ExecutionStatus;
  executionConfig: ExecutionConfig;
  additionalContext: string;
  checkpointerEnabled: boolean;
  globalRecursionLimit: number;
  contextDocuments: number[];
  activeProjectId: number | null;
  setCurrentWorkflowId: (id: number | null) => void;
  setCurrentTaskId: (id: number | null) => void;
  setExecutionStatus: React.Dispatch<React.SetStateAction<any>>;
  setShowExecutionDialog: (show: boolean) => void;
  setShowLiveExecutionPanel: (show: boolean) => void;
  setNodes: React.Dispatch<React.SetStateAction<Node[]>>;
  clearEvents: () => void;
  showWarning: (message: string) => void;
  logError: (title: string, message: string) => void;
  onExecutionStart?: () => void;
  onNodeSelect?: (nodeId: string | null, nodeData: any) => void;
}

interface UseExecutionHandlersReturn {
  handleRun: () => Promise<void>;
  handleStop: () => Promise<void>;
  executeWorkflow: () => Promise<void>;
}

/**
 * Hook for handling workflow execution (run, stop, execute)
 */
export function useExecutionHandlers({
  nodes,
  edges,
  currentWorkflowId,
  currentTaskId,
  executionStatus,
  executionConfig,
  additionalContext,
  checkpointerEnabled,
  globalRecursionLimit,
  contextDocuments,
  activeProjectId,
  setCurrentWorkflowId,
  setCurrentTaskId,
  setExecutionStatus,
  setShowExecutionDialog,
  setShowLiveExecutionPanel,
  setNodes,
  clearEvents,
  showWarning,
  logError,
  onExecutionStart,
  onNodeSelect,
}: UseExecutionHandlersOptions): UseExecutionHandlersReturn {

  const handleStop = useCallback(async () => {
    if (!currentTaskId) {
      showWarning('No running workflow to stop.');
      return;
    }

    try {
      await apiClient.cancelTask(currentTaskId);

      // CRITICAL: Clear the task ID so events stop coming
      setCurrentTaskId(null);
      localStorage.removeItem('langconfig-current-task-id');

      // DON'T clear events - keep them visible for debugging
      // clearEvents(); // Removed to allow debugging of stopped workflows

      // Update execution status to stopped
      setExecutionStatus({
        state: 'idle',
        currentNode: '',
        progress: 0,
        startTime: '',
        duration: '0s',
      });

      // Force clear all node statuses
      setNodes((nds) =>
        nds.map((node) => ({
          ...node,
          data: {
            ...node.data,
            executionStatus: {
              state: 'idle',
              thinking: '',
              thinkingPreview: '',
            },
          },
        }))
      );
    } catch (error: any) {
      console.error('Failed to cancel workflow:', error);
      logError('Failed to cancel workflow', error.response?.data?.detail || error.message);
    }
  }, [currentTaskId, setCurrentTaskId, setExecutionStatus, setNodes, showWarning, logError]);

  const handleRun = useCallback(async () => {
    if (nodes.length === 0) {
      showWarning('Please add at least one agent to the workflow before running.');
      return;
    }

    // Check if workflow is already running
    if (executionStatus.state === 'running') {
      const shouldCancel = window.confirm(
        'A workflow is already running. Do you want to cancel it and start a new execution?'
      );

      if (shouldCancel) {
        await handleStop();
        // Wait a moment for cleanup
        await new Promise(resolve => setTimeout(resolve, 500));
      } else {
        return; // User chose to wait
      }
    }

    // Show execution dialog immediately
    setShowExecutionDialog(true);
  }, [nodes.length, executionStatus.state, handleStop, showWarning, setShowExecutionDialog]);

  const executeWorkflow = useCallback(async () => {
    setShowExecutionDialog(false);

    // Find the START node or the first node with no incoming edges
    const startNode = nodes.find(n => n.data.agentType === 'START_NODE') ||
      nodes.find(n => !edges.some(e => e.target === n.id)) ||
      nodes[0];

    setExecutionStatus({
      state: 'running',
      currentNode: startNode?.data.label,
      progress: 0,
      startTime: new Date().toLocaleTimeString(),
      duration: '0s',
    });

    if (onExecutionStart) {
      onExecutionStart();
    }

    try {
      // Make sure we have a workflow ID - always save/update before executing
      let workflowIdToExecute = currentWorkflowId;

      const configuration = {
        nodes: nodes.map(n => ({
          id: n.id,
          type: n.data.label.toLowerCase().replace(/\s+/g, '_'),
          config: {
            model: n.data.config?.model || 'gpt-4o-mini',
            temperature: n.data.config?.temperature ?? 0.7,
            system_prompt: n.data.config?.system_prompt || '',
            // Legacy tools field
            tools: n.data.config?.tools || [],
            // CRITICAL: Propagate native_tools and custom_tools for agent factory
            native_tools: n.data.config?.native_tools || [],
            cli_tools: n.data.config?.cli_tools || [],
            custom_tools: n.data.config?.custom_tools || [],
            enable_model_routing: n.data.config?.enable_model_routing ?? false,
            enable_parallel_tools: n.data.config?.enable_parallel_tools ?? true,
            enable_memory: n.data.config?.enable_memory ?? false,
            enable_rag: n.data.config?.enable_rag ?? false,
            // Ensure recursion limit is passed if set
            recursion_limit: n.data.config?.recursion_limit,
            // Pass pause settings
            pauseBefore: n.data.config?.pauseBefore ?? false,
            pauseAfter: n.data.config?.pauseAfter ?? false,
            // DeepAgent support: pass use_deepagents flag and subagent configs
            use_deepagents: n.data.config?.use_deepagents ?? false,
            subagents: n.data.config?.subagents || []
          }
        })),
        edges: edges.map(e => ({
          source: e.source,
          target: e.target
        }))
      };

      if (workflowIdToExecute) {
        // UPDATE existing workflow
        await apiClient.updateWorkflow(workflowIdToExecute, {
          configuration
        });
      } else {
        // CREATE new workflow
        const workflowData = {
          name: `Workflow ${Date.now()}`,
          configuration
        };

        const saveResponse = await apiClient.createWorkflow(workflowData);
        workflowIdToExecute = saveResponse.data.id;
        setCurrentWorkflowId(workflowIdToExecute);
      }

      // Clear previous execution events to prepare for new run
      // SSE connection stays alive across executions
      clearEvents();

      // Execute workflow with user-provided context
      const response = await apiClient.executeWorkflow({
        workflow_id: workflowIdToExecute as number,
        project_id: activeProjectId || 0, // Use active project if available, 0 for standalone
        input_data: {
          query: executionConfig.directive,
          task: executionConfig.task || executionConfig.directive,
          additional_context: additionalContext || '',
          checkpointer_enabled: checkpointerEnabled,
          recursion_limit: globalRecursionLimit,
          // Configurable execution limits (use defaults if not set, backend enforces bounds)
          max_events: executionConfig.max_events || 10000,  // Default: 10k events
          timeout_seconds: executionConfig.timeout_seconds || 600  // Default: 10 minutes
        },
        context_documents: contextDocuments,
      });

      // Save task ID for monitoring and persist to localStorage
      setCurrentTaskId(response.data.task_id);
      localStorage.setItem('langconfig-current-task-id', response.data.task_id.toString());

      // Set execution to running state
      setExecutionStatus((prev: ExecutionStatus) => ({
        ...prev,
        state: 'running',
        startTime: new Date().toISOString(),
      }));

      // Auto-open live execution panel when workflow runs
      setShowLiveExecutionPanel(true);

      // Close node config panel by deselecting all nodes
      onNodeSelect?.(null, null);

    } catch (error: any) {
      console.error('Workflow execution error:', error);

      // Extract detailed error information (preserved for future error handling)
      let _errorMessage = 'Unknown error';
      let _errorDetails = '';

      if (error.response?.data) {
        // API error response
        const errData = error.response.data;
        _errorMessage = errData.detail || errData.message || 'Execution failed';
        if (errData.error) _errorDetails = errData.error;
        if (errData.traceback) _errorDetails += `\n\nTraceback:\n${errData.traceback}`;
      } else if (error.message) {
        _errorMessage = error.message;
      }

      void _errorMessage; // Reserved for future error UI
      void _errorDetails;

      setExecutionStatus((prev: ExecutionStatus) => ({
        ...prev,
        state: 'failed',
      }));
    } finally {
      // Execution complete
    }
  }, [
    nodes,
    edges,
    currentWorkflowId,
    executionConfig,
    additionalContext,
    checkpointerEnabled,
    globalRecursionLimit,
    contextDocuments,
    activeProjectId,
    setCurrentWorkflowId,
    setCurrentTaskId,
    setExecutionStatus,
    setShowExecutionDialog,
    setShowLiveExecutionPanel,
    clearEvents,
    onExecutionStart,
    onNodeSelect,
  ]);

  return {
    handleRun,
    handleStop,
    executeWorkflow,
  };
}
