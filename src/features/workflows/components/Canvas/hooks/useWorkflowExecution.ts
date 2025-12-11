/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useCallback, useEffect } from 'react';
import type { Node, Edge } from 'reactflow';
import apiClient from '../../../../../lib/api-client';
import type { ExecutionStatus, ExecutionConfig, NodeData, NodeTokenCost } from '../types';

interface UseWorkflowExecutionOptions {
  currentWorkflowId: number | null;
  nodes: Node<NodeData>[];
  edges: Edge[];
  setNodes: React.Dispatch<React.SetStateAction<Node<NodeData>[]>>;
  activeProjectId: number | null;
  checkpointerEnabled: boolean;
  globalRecursionLimit: number;
  onExecutionStart?: () => void;
  onNodeSelect?: (nodeId: string | null, nodeData?: NodeData | null) => void;
  showWarning: (message: string) => void;
  logError: (title: string, message: string) => void;
  clearEvents: () => void;
}

interface UseWorkflowExecutionReturn {
  // State
  executionStatus: ExecutionStatus;
  setExecutionStatus: React.Dispatch<React.SetStateAction<ExecutionStatus>>;
  currentTaskId: number | null;
  setCurrentTaskId: React.Dispatch<React.SetStateAction<number | null>>;
  showExecutionDialog: boolean;
  setShowExecutionDialog: React.Dispatch<React.SetStateAction<boolean>>;
  showAdvancedOptions: boolean;
  setShowAdvancedOptions: React.Dispatch<React.SetStateAction<boolean>>;
  executionConfig: ExecutionConfig;
  setExecutionConfig: React.Dispatch<React.SetStateAction<ExecutionConfig>>;
  contextDocuments: number[];
  setContextDocuments: React.Dispatch<React.SetStateAction<number[]>>;
  availableDocuments: any[];
  additionalContext: string;
  setAdditionalContext: React.Dispatch<React.SetStateAction<string>>;
  showThinkingStream: boolean;
  showLiveExecutionPanel: boolean;
  nodeTokenCosts: Record<string, NodeTokenCost>;
  setNodeTokenCosts: React.Dispatch<React.SetStateAction<Record<string, NodeTokenCost>>>;

  // Handlers
  handleRun: () => Promise<void>;
  handleStop: () => Promise<void>;
  executeWorkflow: () => Promise<void>;
  handleToggleThinkingStream: () => void;
  handleToggleLiveExecutionPanel: () => void;
}

/**
 * Hook for managing workflow execution state and handlers
 */
export function useWorkflowExecution({
  currentWorkflowId,
  nodes,
  edges,
  setNodes,
  activeProjectId,
  checkpointerEnabled,
  globalRecursionLimit,
  onExecutionStart,
  onNodeSelect,
  showWarning,
  logError,
  clearEvents,
}: UseWorkflowExecutionOptions): UseWorkflowExecutionReturn {
  // Task ID with localStorage persistence
  const [currentTaskId, setCurrentTaskId] = useState<number | null>(() => {
    const savedTaskId = localStorage.getItem('langconfig-current-task-id');
    return savedTaskId ? parseInt(savedTaskId, 10) : null;
  });

  // Execution status
  const [executionStatus, setExecutionStatus] = useState<ExecutionStatus>({
    state: 'idle',
    currentNode: undefined,
    progress: 0,
    startTime: undefined,
    duration: undefined,
  });

  // Dialog state
  const [showExecutionDialog, setShowExecutionDialog] = useState(false);
  const [showAdvancedOptions, setShowAdvancedOptions] = useState(false);

  // Execution configuration
  const [executionConfig, setExecutionConfig] = useState<ExecutionConfig>({
    prompt: '',
    directive: '',
    classification: 'GENERAL',
    executor_type: 'default',
    max_events: 10000,
    timeout_seconds: 600,
  });

  // Context documents
  const [contextDocuments, setContextDocuments] = useState<number[]>([]);
  const [availableDocuments, setAvailableDocuments] = useState<any[]>([]);
  const [additionalContext, setAdditionalContext] = useState('');

  // View toggles
  const [showThinkingStream, setShowThinkingStream] = useState(false);
  const [showLiveExecutionPanel, setShowLiveExecutionPanel] = useState(false);

  // Per-node token costs (persisted to localStorage)
  const [nodeTokenCosts, setNodeTokenCosts] = useState<Record<string, NodeTokenCost>>(() => {
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

  // Persist token costs to localStorage
  useEffect(() => {
    if (currentWorkflowId && Object.keys(nodeTokenCosts).length > 0) {
      localStorage.setItem(`workflow-${currentWorkflowId}-token-costs`, JSON.stringify(nodeTokenCosts));
    }
  }, [nodeTokenCosts, currentWorkflowId]);

  // Load available documents when dialog opens
  useEffect(() => {
    if (showExecutionDialog && activeProjectId) {
      apiClient.listDocuments({ project_id: activeProjectId })
        .then(response => {
          setAvailableDocuments(response.data || []);
        })
        .catch(error => {
          console.error('Failed to load documents:', error);
          setAvailableDocuments([]);
        });
    }
  }, [showExecutionDialog, activeProjectId]);

  // Handle Escape key to close dialog
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && showExecutionDialog) {
        setShowExecutionDialog(false);
      }
    };

    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [showExecutionDialog]);

  // Toggle handlers
  const handleToggleThinkingStream = useCallback(() => {
    setShowThinkingStream(prev => !prev);
  }, []);

  const handleToggleLiveExecutionPanel = useCallback(() => {
    setShowLiveExecutionPanel(prev => !prev);
  }, []);

  // Handle run button click - opens execution dialog
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
        await new Promise(resolve => setTimeout(resolve, 500));
      } else {
        return;
      }
    }

    setShowExecutionDialog(true);
  }, [nodes.length, executionStatus.state, showWarning]);

  // Handle stop button click
  const handleStop = useCallback(async () => {
    if (!currentTaskId) {
      showWarning('No running workflow to stop.');
      return;
    }

    try {
      await apiClient.cancelTask(currentTaskId);

      // Clear the task ID
      setCurrentTaskId(null);
      localStorage.removeItem('langconfig-current-task-id');

      // Update execution status
      setExecutionStatus({
        state: 'idle',
        currentNode: '',
        progress: 0,
        startTime: '',
        duration: '0s',
      });

      // Clear all node statuses
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
  }, [currentTaskId, showWarning, logError, setNodes]);

  // Execute workflow after configuration
  const executeWorkflow = useCallback(async () => {
    setShowExecutionDialog(false);

    // Find the START node or first node
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
      let workflowIdToExecute = currentWorkflowId;

      const configuration = {
        nodes: nodes.map(n => ({
          id: n.id,
          type: n.data.label.toLowerCase().replace(/\s+/g, '_'),
          config: {
            model: n.data.config?.model || 'gpt-4o-mini',
            temperature: n.data.config?.temperature ?? 0.7,
            system_prompt: n.data.config?.system_prompt || '',
            tools: n.data.config?.tools || [],
            native_tools: n.data.config?.native_tools || [],
            cli_tools: n.data.config?.cli_tools || [],
            custom_tools: n.data.config?.custom_tools || [],
            enable_model_routing: n.data.config?.enable_model_routing ?? false,
            enable_parallel_tools: n.data.config?.enable_parallel_tools ?? true,
            enable_memory: n.data.config?.enable_memory ?? false,
            enable_rag: n.data.config?.enable_rag ?? false,
            recursion_limit: n.data.config?.recursion_limit,
            pauseBefore: n.data.config?.pauseBefore ?? false,
            pauseAfter: n.data.config?.pauseAfter ?? false,
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
        await apiClient.updateWorkflow(workflowIdToExecute, { configuration });
      } else {
        const workflowData = {
          name: `Workflow ${Date.now()}`,
          configuration
        };
        const saveResponse = await apiClient.createWorkflow(workflowData);
        workflowIdToExecute = saveResponse.data.id;
      }

      clearEvents();

      const response = await apiClient.executeWorkflow({
        workflow_id: workflowIdToExecute as number,
        project_id: activeProjectId || 0,
        input_data: {
          query: executionConfig.directive || executionConfig.prompt,
          task: executionConfig.directive || executionConfig.prompt,
          additional_context: additionalContext || '',
          checkpointer_enabled: checkpointerEnabled,
          recursion_limit: globalRecursionLimit,
          max_events: executionConfig.max_events || 10000,
          timeout_seconds: executionConfig.timeout_seconds || 600
        },
        context_documents: contextDocuments,
      });

      setCurrentTaskId(response.data.task_id);
      localStorage.setItem('langconfig-current-task-id', response.data.task_id.toString());

      setExecutionStatus(prev => ({
        ...prev,
        state: 'running',
        startTime: new Date().toISOString(),
      }));

      setShowLiveExecutionPanel(true);
      onNodeSelect?.(null, null);

    } catch (error: any) {
      console.error('Workflow execution error:', error);

      // Extract error details for logging (even if not displayed to user)
      if (error.response?.data) {
        const errData = error.response.data;
        const message = errData.detail || errData.message || 'Execution failed';
        const details = errData.error || '';
        console.error('Execution failed:', message, details);
      }

      setExecutionStatus(prev => ({
        ...prev,
        state: 'failed',
      }));
    }
  }, [
    nodes,
    edges,
    currentWorkflowId,
    activeProjectId,
    executionConfig,
    additionalContext,
    contextDocuments,
    checkpointerEnabled,
    globalRecursionLimit,
    onExecutionStart,
    onNodeSelect,
    clearEvents,
  ]);

  return {
    // State
    executionStatus,
    setExecutionStatus,
    currentTaskId,
    setCurrentTaskId,
    showExecutionDialog,
    setShowExecutionDialog,
    showAdvancedOptions,
    setShowAdvancedOptions,
    executionConfig,
    setExecutionConfig,
    contextDocuments,
    setContextDocuments,
    availableDocuments,
    additionalContext,
    setAdditionalContext,
    showThinkingStream,
    showLiveExecutionPanel,
    nodeTokenCosts,
    setNodeTokenCosts,

    // Handlers
    handleRun,
    handleStop,
    executeWorkflow,
    handleToggleThinkingStream,
    handleToggleLiveExecutionPanel,
  };
}
