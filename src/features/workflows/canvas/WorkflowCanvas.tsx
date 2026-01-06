/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useCallback, useState, useEffect, useRef, useMemo, forwardRef, useImperativeHandle } from 'react';
import ReactFlow, {
  Node,
  Edge,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
  BackgroundVariant,
  MiniMap,
} from 'reactflow';
import 'reactflow/dist/style.css';
import apiClient from '@/lib/api-client';
import ConflictDialog from '../ui/ConflictDialog';
import RealtimeExecutionPanel from '@/features/workflows/execution/RealtimeExecutionPanel';
import InlineFilePreview from '@/features/workflows/execution/InlineFilePreview';
import { getFileIcon } from '../utils/fileHelpers';
import { validateNodePosition } from '@/utils/validation';
import { useWorkflowStream } from '@/hooks/useWorkflowStream';
import { useNodeExecutionStatus, NodeExecutionStatus } from '@/hooks/useNodeExecutionStatus';
import { useProject } from '@/contexts/ProjectContext';
import { useNotification } from '@/hooks/useNotification';
import { useChat } from '@/features/chat/state/ChatContext';
import CustomNode from './nodes/CustomNode';
import { WorkflowCanvasContext } from './context';
import { ErrorBoundary } from '@/components/common/ErrorBoundary';
import ExecutionConfigDialog from './dialogs/ExecutionConfigDialog';
import { Attachment } from '@/components/common/AttachmentUploader';
import SaveWorkflowModal from './dialogs/SaveWorkflowModal';
import SaveToLibraryModal from './dialogs/SaveToLibraryModal';
import SaveVersionDialog from './dialogs/SaveVersionDialog';
import DebugWorkflowDialog from './dialogs/DebugWorkflowDialog';
import CreateWorkflowDialog from './dialogs/CreateWorkflowDialog';
import WorkflowSettingsDialog from './dialogs/WorkflowSettingsDialog';
import ChatWarningModal from './dialogs/ChatWarningModal';
import PresentationDialog from './dialogs/PresentationDialog';
import WorkflowResults from './results/WorkflowResults';
import ArtifactsTab from './results/ArtifactsTab';
import FilesTab from './results/FilesTab';
import { SelectionProvider, useSelectionOptional } from './context/SelectionContext';
import WorkflowToolbar from './toolbar/WorkflowToolbar';
import NodeContextMenu from './menus/NodeContextMenu';
import TaskContextMenu from './menus/TaskContextMenu';
import EmptyCanvasState from './EmptyCanvasState';
import CanvasControlPanel from './panels/CanvasControlPanel';
import TotalCostPanel from './panels/TotalCostPanel';
import ThinkingToastRenderer from './panels/ThinkingToastRenderer';
import { useWorkflowMetrics } from './hooks/useWorkflowMetrics';
import { useContextMenus } from './hooks/useContextMenus';
import { useWorkflowCompletion } from './hooks/useWorkflowCompletion';
import { useToolsAndActions } from './hooks/useToolsAndActions';
import { useTokenCostInfo } from './hooks/useTokenCostInfo';
import { useExecutionHandlers } from './hooks/useExecutionHandlers';
import { useSaveToLibrary } from './hooks/useSaveToLibrary';
import { useUIToggles } from './hooks/useUIToggles';
import { useFileHandling } from './hooks/useFileHandling';
import { useWorkflowPersistence } from './hooks/useWorkflowPersistence';
import { useVersionManagement } from './hooks/useVersionManagement';
import { useResultsState } from './hooks/useResultsState';
import { useNodeManagement } from './hooks/useNodeManagement';
import { useWorkflowEventProcessing } from './hooks/useWorkflowEventProcessing';
import { useTaskManagement } from './hooks/useTaskManagement';
import { TaskHistoryEntry } from './types';

interface Agent {
  id: string;
  name: string;
  description: string;
  icon: string;
  model: string;
  fallback_models?: string[];
  temperature: number;
  max_tokens?: number;
  system_prompt: string;
  native_tools: string[];
  cli_tools?: string[];
  custom_tools?: string[];
  timeout_seconds: number;
  max_retries: number;
  enable_model_routing: boolean;
  enable_parallel_tools: boolean;
  enable_memory: boolean;
  enable_rag?: boolean;
  requires_human_approval?: boolean;
  tags?: string[];
}

interface NodeData {
  label: string;
  agentType: string;
  model: string;
  config: {
    model: string;
    fallback_models?: string[];
    temperature: number;
    max_tokens?: number;
    system_prompt: string;
    tools: string[];
    native_tools: string[];
    cli_tools?: string[];
    custom_tools?: string[];
    timeout_seconds: number;
    max_retries: number;
    enable_model_routing: boolean;
    enable_parallel_tools: boolean;
    enable_memory: boolean;
    enable_rag?: boolean;
    requires_human_approval?: boolean;
    // Conversation context fields
    enable_conversation_context?: boolean;
    deep_agent_template_id?: number | null;
    context_mode?: 'recent' | 'smart' | 'full';
    context_window_size?: number;
    banked_message_ids?: string[];
    // DeepAgent support
    subagents?: any[];
    middleware?: any[];
  };
  executionStatus?: NodeExecutionStatus;
}

interface WorkflowExecutionContext {
  directive: string;
  query: string;
  task: string;
  classification: 'GENERAL' | 'BACKEND' | 'FRONTEND' | 'DEVOPS_IAC' | 'DATABASE' | 'API' | 'TESTING' | 'DOCUMENTATION' | 'CONFIGURATION';
  executor_type: 'default' | 'devops' | 'frontend' | 'database' | 'testing';
  max_retries: number;
  max_events?: number;  // Configurable event limit (default: 10k)
  timeout_seconds?: number;  // Configurable timeout (default: 10 min)
}

// Ref interface for exposing methods to parent components
export interface WorkflowCanvasRef {
  updateNodeConfig: (nodeId: string, fullConfig: any) => void;
  deleteNode: (nodeId: string) => void;
  saveWorkflow: (silent?: boolean) => Promise<void>;
  hasUnsavedChanges: () => boolean;
  clearCanvas: () => void;
}

// Recipe type for multi-node workflow templates
export interface WorkflowRecipe {
  recipe_id: string;
  name: string;
  description: string;
  category: string;
  icon: string;
  tags: string[];
  nodes: any[];
  edges: any[];
  node_count: number;
  edge_count: number;
}

interface WorkflowCanvasProps {
  selectedAgent: Agent | null;
  selectedRecipe?: WorkflowRecipe | null;
  onWorkflowSelect?: (workflowId: number) => void;
  onNodeSelect?: (nodeId: string | null, nodeData?: NodeData | null) => void;
  onNodeDelete?: (nodeId: string) => void;
  onExecutionStart?: () => void;
  onAgentAdded?: () => void;
  onRecipeInserted?: () => void;
  workflowId?: number | null;
  onTabChange?: (tab: 'studio' | 'results') => void;
  initialTab?: 'studio' | 'results';
  onTokenCostUpdate?: (tokenInfo: { totalTokens: number; promptTokens: number; completionTokens: number; costString: string; }) => void;
  // Task history callbacks for left sidebar
  onTaskHistoryUpdate?: (tasks: TaskHistoryEntry[]) => void;
  onSelectedTaskChange?: (task: TaskHistoryEntry | null) => void;
  externalSelectedTask?: TaskHistoryEntry | null;
}

const initialNodes: Node[] = [];
const initialEdges: Edge[] = [];

// Custom Node Component is imported from ./nodes/CustomNode.tsx
// WorkflowCanvasContext is imported from ./context.ts
// TaskFile type is imported from ./hooks/useFileHandling

// nodeTypes will be memoized inside the component using imported CustomNode

const WorkflowCanvas = forwardRef<WorkflowCanvasRef, WorkflowCanvasProps>(({
  selectedAgent,
  selectedRecipe,
  onNodeSelect,
  onNodeDelete,
  onExecutionStart,
  onAgentAdded,
  onRecipeInserted,
  workflowId,
  onTabChange,
  initialTab,
  onTokenCostUpdate,
  onTaskHistoryUpdate,
  onSelectedTaskChange,
  externalSelectedTask,
}, ref) => {
  const { showSuccess, logError, showWarning, NotificationModal } = useNotification();
  const { openChat } = useChat();
  const [nodes, setNodes, onNodesChangeBase] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Wrap onNodesChange with position validation
  const onNodesChange = useCallback((changes: any[]) => {
    const validatedChanges = changes.map((change) => {
      // Validate position changes
      if (change.type === 'position' && change.position) {
        const validation = validateNodePosition(change.position.x, change.position.y);
        if (!validation.isValid) {
          console.warn(`Invalid position change for node ${change.id}: ${validation.error}. Ignoring change.`);
          return null; // Skip this change
        }
      }
      return change;
    }).filter(Boolean); // Remove null changes

    onNodesChangeBase(validatedChanges);
  }, [onNodesChangeBase]);

  const [nodeIdCounter, setNodeIdCounter] = useState(1);
  const [currentWorkflowId, setCurrentWorkflowId] = useState<number | null>(workflowId || null);
  const [currentTaskId, setCurrentTaskId] = useState<number | null>(() => {
    // Restore task ID from localStorage on load
    const savedTaskId = localStorage.getItem('langconfig-current-task-id');
    return savedTaskId ? parseInt(savedTaskId, 10) : null;
  });

  const [reactFlowInstance, setReactFlowInstance] = useState<any>(null);
  const [currentZoom, setCurrentZoom] = useState(1); // Track zoom level for toasts
  const [activeTab, setActiveTab] = useState<'studio' | 'results' | 'files' | 'artifacts'>(() => {
    // Initialize from URL hash if present
    const hash = window.location.hash.replace('#', '');
    if (hash === 'results') return 'results';
    if (hash === 'files') return 'files';
    if (hash === 'artifacts') return 'artifacts';
    return 'studio';
  });
  const [executionStatus, setExecutionStatus] = useState<{
    state: 'idle' | 'running' | 'completed' | 'failed';
    currentNode?: string;
    progress: number;
    startTime?: string;
    duration?: string;
  }>({
    state: 'idle',
    progress: 0,
  });
  const [showExecutionDialog, setShowExecutionDialog] = useState(false);
  const [showAdvancedOptions, setShowAdvancedOptions] = useState(false);
  const [executionConfig, setExecutionConfig] = useState<WorkflowExecutionContext>({
    directive: '',
    query: '',
    task: '',
    classification: 'GENERAL',
    executor_type: 'default',
    max_retries: 3,
    max_events: 10000,  // Default: 10k events
    timeout_seconds: 600,  // Default: 10 minutes (600 seconds)
  });
  const [contextDocuments, setContextDocuments] = useState<number[]>([]);
  const [availableDocuments, setAvailableDocuments] = useState<any[]>([]);
  const [additionalContext, setAdditionalContext] = useState('');
  const [workflowAttachments, setWorkflowAttachments] = useState<Attachment[]>([]);
  const hasLoadedRef = useRef(false);
  const isDraggingRef = useRef(false); // Track if user is currently dragging a node
  const [workflowName, setWorkflowName] = useState('Untitled Workflow');
  const [editedName, setEditedName] = useState(workflowName);
  const [showCreateWorkflowModal, setShowCreateWorkflowModal] = useState(false);
  const [newWorkflowName, setNewWorkflowName] = useState('');

  // Use extracted hook for results tab state
  const {
    resultsSubTab: _resultsSubTab,
    setResultsSubTab: _setResultsSubTab,
    copiedToClipboard,
    setCopiedToClipboard,
    showRawOutput,
    setShowRawOutput,
    showAnimatedReveal,
    setShowAnimatedReveal,
    expandedToolCalls,
    setExpandedToolCalls,
  } = useResultsState();

  // Workflow Settings
  const [globalRecursionLimit, setGlobalRecursionLimit] = useState(300);

  // nodeTokenCosts is now managed by useWorkflowEventProcessing hook

  // Use extracted hook for task management (history, replay panel, selection)
  const {
    taskHistory,
    loadingHistory,
    selectedHistoryTask,
    setSelectedHistoryTask,
    isHistoryCollapsed,
    setIsHistoryCollapsed,
    fetchTaskHistory,
    handleDeleteTask,
    resetTaskHistory,
    showReplayPanel,
    setShowReplayPanel,
    replayTaskId,
    setReplayTaskId,
  } = useTaskManagement({
    currentWorkflowId,
    showSuccess,
    logError,
    onRunningTaskFound: useCallback((taskInfo: { id: number; created_at: string }) => {
      // Restore execution state when a running task is found
      setCurrentTaskId(taskInfo.id);
      setExecutionStatus({
        state: 'running',
        progress: 0,
        startTime: taskInfo.created_at,
      });
    }, []),
  });

  // Sync task history to parent component (for left sidebar)
  useEffect(() => {
    if (onTaskHistoryUpdate) {
      onTaskHistoryUpdate(taskHistory);
    }
  }, [taskHistory, onTaskHistoryUpdate]);

  // Track if the last selection change came from external source to prevent loops
  const isExternalSelectionRef = useRef(false);

  // Sync selected task changes to parent (only if change was internal)
  useEffect(() => {
    if (onSelectedTaskChange && selectedHistoryTask && !isExternalSelectionRef.current) {
      onSelectedTaskChange(selectedHistoryTask);
    }
    // Reset the flag after processing
    isExternalSelectionRef.current = false;
  }, [selectedHistoryTask, onSelectedTaskChange]);

  // Handle external task selection (from left sidebar)
  useEffect(() => {
    if (externalSelectedTask && externalSelectedTask.id !== selectedHistoryTask?.id) {
      isExternalSelectionRef.current = true; // Mark as external to prevent loop
      setSelectedHistoryTask(externalSelectedTask);
    }
  }, [externalSelectedTask, selectedHistoryTask?.id, setSelectedHistoryTask]);

  // Use extracted hook for context menu state management
  const {
    taskContextMenu,
    setTaskContextMenu,
    nodeContextMenu,
    setNodeContextMenu,
    openNodeContextMenu,
  } = useContextMenus();

  // Use extracted hook for node management (click, delete, config updates)
  // Note: setNodeTokenCosts is passed later after useWorkflowEventProcessing hook
  const {
    handleNodeClick,
    handleNodeDelete,
    updateNodeConfig,
  } = useNodeManagement({
    setNodes,
    setEdges,
    onNodeSelect,
    onNodeDelete,
  });

  // Use extracted hook for save to library functionality
  const {
    showSaveToLibraryModal,
    agentLibraryName,
    agentLibraryDescription,
    setAgentLibraryName,
    setAgentLibraryDescription,
    handleSaveToAgentLibrary,
    handleConfirmSaveToLibrary,
    handleCloseSaveToLibraryModal,
  } = useSaveToLibrary({
    setNodes,
    setNodeContextMenu,
    showWarning,
    showSuccess,
    logError,
  });

  // Use extracted hook for UI toggle states
  const {
    showWorkflowDropdown,
    setShowWorkflowDropdown,
    handleToggleWorkflowDropdown,
    handleCloseWorkflowDropdown,
    showSettingsModal,
    handleToggleSettingsModal,
    handleCloseSettingsModal,
    showThinkingStream,
    handleToggleThinkingStream,
    showLiveExecutionPanel,
    setShowLiveExecutionPanel,
    handleToggleLiveExecutionPanel,
    checkpointerEnabled,
    handleToggleCheckpointer,
    workflowSearchQuery,
    setWorkflowSearchQuery,
    handleWorkflowSearchChange,
    isEditingName,
    setIsEditingName,
    handleStartEditingName,
  } = useUIToggles();

  // Use extracted hook for file handling
  const {
    files,
    filesLoading,
    filesError,
    selectedPreviewFile,
    filePreviewContent,
    filePreviewLoading,
    fetchFiles,
    handleDownloadFile,
    handleFileSelect,
    closeFilePreview,
  } = useFileHandling({
    // Use selected history task when viewing results, otherwise use current running task
    // Note: API returns task ID as 'id', not 'task_id'
    currentTaskId: selectedHistoryTask?.id ?? currentTaskId,
    activeTab,
  });

  // Chat with unsaved agent warning modal
  const [showChatWarningModal, setShowChatWarningModal] = useState(false);

  // Project context
  const { activeProjectId } = useProject();
  const [availableWorkflows, setAvailableWorkflows] = useState<any[]>([]);
  const [showSaveModal, setShowSaveModal] = useState(false);
  const [saveWorkflowName, setSaveWorkflowName] = useState('');
  const [showPresentationDialog, setShowPresentationDialog] = useState(false);

  // Use extracted hook for workflow persistence (save, conflict resolution)
  const {
    currentLockVersion: _currentLockVersion, // Used internally by hook for optimistic locking
    hasUnsavedChanges,
    showConflictDialog,
    conflictData,
    setCurrentLockVersion: _setCurrentLockVersion, // Used internally
    setHasUnsavedChanges: _setHasUnsavedChanges, // Used internally
    handleSave,
    handleConflictResolve,
    handleWorkflowNameSave: updateWorkflowName, // Renamed to avoid conflict with local wrapper
    markAsSaved: _markAsSaved, // Used internally
    getWorkflowStateHash: _getWorkflowStateHash, // Used internally
  } = useWorkflowPersistence({
    nodes,
    edges,
    currentWorkflowId,
    setNodes,
    setEdges,
    setWorkflowName,
    setEditedName,
    showSuccess,
    logError,
    onShowSaveModal: () => setShowSaveModal(true),
  });

  // Debug modal state (separate from versioning)
  const [showDebugModal, setShowDebugModal] = useState(false);
  const [debugData, setDebugData] = useState<any>(null);

  // Use extracted hook for version management
  const {
    versions,
    currentVersion,
    loadingVersions,
    showVersionModal,
    versionNotes,
    showVersionDropdown,
    compareMode,
    compareVersion1,
    compareVersion2,
    versionComparison,
    loadingComparison,
    setVersionNotes,
    setShowVersionDropdown,
    setCompareMode,
    setCompareVersion1,
    setCompareVersion2,
    loadVersions: _loadVersions, // Used internally by hook
    handleSaveVersion,
    handleSaveVersionConfirm,
    handleLoadVersion,
    handleCompareVersions,
    handleCloseVersionModal,
  } = useVersionManagement({
    currentWorkflowId,
    nodes,
    edges,
    setNodes,
    setEdges,
    showSuccess,
    showWarning,
    logError,
  });

  // Memoize nodeTypes to prevent React Flow warnings about recreation
  const nodeTypes = useMemo(() => ({
    custom: CustomNode,
  }), []);

  // Validate nodes and edges before passing to ReactFlow to prevent NaN rendering errors
  const validatedNodes = useMemo(() => {
    return nodes.map((node, index) => {
      const hasValidPosition =
        node.position &&
        typeof node.position.x === 'number' &&
        typeof node.position.y === 'number' &&
        !isNaN(node.position.x) &&
        !isNaN(node.position.y) &&
        isFinite(node.position.x) &&
        isFinite(node.position.y);

      if (!hasValidPosition) {
        console.warn(`Node ${node.id} has invalid position:`, node.position, '- fixing to default position');
        // Fix the position instead of filtering out the node
        return {
          ...node,
          position: {
            x: 250 + (index * 300),
            y: 250
          }
        };
      }

      return node;
    });
  }, [nodes]);

  const validatedEdges = useMemo(() => {
    const validNodeIds = new Set(validatedNodes.map(n => n.id));
    return edges.filter(edge => {
      const isValid = validNodeIds.has(edge.source) && validNodeIds.has(edge.target);
      if (!isValid) {
        console.warn(`Edge ${edge.id} connects to invalid nodes:`, edge.source, edge.target);
      }
      return isValid;
    });
  }, [edges, validatedNodes]);

  // Use workflow stream hook to get events and formatted output
  // Only connect when there's an active task running
  const { events: workflowEvents, latestEvent, clearEvents } = useWorkflowStream(currentWorkflowId, {
    autoConnect: executionStatus.state === 'running' && currentTaskId !== null,
    maxEvents: 10000, // Increased to 10000 to handle very long workflows
    taskId: currentTaskId,
    loadHistorical: true,
    tokenBufferMs: 16 // Smooth 60fps streaming
  });

  // Separate hook for replay panel - loads historical events independently
  const { events: replayEvents, isLoadingHistorical: _replayLoading } = useWorkflowStream(currentWorkflowId, {
    autoConnect: false, // Never connect to live stream in replay
    maxEvents: 10000,
    taskId: replayTaskId,
    loadHistorical: true,
    tokenBufferMs: 16
  });

  // Use node execution status hook to track real-time execution state
  // Only track when there's an active task
  const nodeExecutionStatuses = useNodeExecutionStatus(
    executionStatus.state === 'running' ? currentWorkflowId : null,
    {
      taskId: executionStatus.state === 'running' ? currentTaskId : null,
    }
  );

  // Use extracted hook for workflow event processing (warnings, token costs, error handling)
  const {
    nodeWarnings,
    nodeTokenCosts,
  } = useWorkflowEventProcessing({
    workflowEvents,
    latestEvent,
    executionStatus,
    setExecutionStatus,
    currentWorkflowId,
    nodeExecutionStatuses,
  });

  // Update nodes with execution status whenever it changes - OPTIMIZED to only update changed nodes
  useEffect(() => {
    setNodes((nds) =>
      nds.map((node) => {
        const newStatus = nodeExecutionStatuses[node.data.label];

        // Get persisted token cost for this node label
        const persistedTokenCost = nodeTokenCosts[node.data.label];

        // Use token cost from status if available, otherwise use persisted
        const tokenCost = newStatus?.tokenCost || persistedTokenCost;

        // Attach warnings to the status if available
        const warnings = nodeWarnings[node.data.label] || nodeWarnings[node.id];
        const statusWithWarnings = newStatus && warnings ? { ...newStatus, warnings } : newStatus;

        // Only update if status, token cost, or warnings changed (prevents unnecessary re-renders)
        if (node.data.executionStatus === statusWithWarnings && node.data.tokenCost === tokenCost) {
          return node; // Return same object reference - React.memo will skip re-render
        }

        return {
          ...node,
          data: {
            ...node.data,
            executionStatus: statusWithWarnings,
            // Use persisted token cost by label (survives node deletion/recreation)
            tokenCost: tokenCost,
          },
        };
      })
    );
  }, [nodeExecutionStatuses, nodeTokenCosts, nodeWarnings, setNodes]);

  // Update URL when tab changes - delegate to parent component
  const handleTabChange = useCallback((newTab: 'studio' | 'results' | 'files' | 'artifacts') => {
    setActiveTab(newTab);
    if (newTab === 'studio' || newTab === 'results') {
      onTabChange?.(newTab);
    }
  }, [onTabChange]);

  // Re-center canvas when execution starts and animate edges
  useEffect(() => {
    if (executionStatus.state === 'running' && reactFlowInstance && nodes.length > 0) {
      // Delay slightly to ensure nodes are updated
      setTimeout(() => {
        reactFlowInstance.fitView({ padding: 0.5, maxZoom: 0.6, duration: 400 });
      }, 200);

      // Animate edges during execution
      setEdges((eds) =>
        eds.map((edge) => ({
          ...edge,
          animated: true,
        }))
      );
    } else if (executionStatus.state === 'idle' || executionStatus.state === 'completed' || executionStatus.state === 'failed') {
      // Stop animating edges when not executing
      setEdges((eds) =>
        eds.map((edge) => ({
          ...edge,
          animated: false,
        }))
      );
    }
  }, [executionStatus.state, reactFlowInstance, nodes.length, setEdges]);


  // Sync activeTab with initialTab prop from parent
  useEffect(() => {
    if (initialTab) {
      setActiveTab(initialTab);
    }
  }, [initialTab]);

  // Extract user prompt from latest execution
  const userPrompt = useMemo(() => {
    // First try to get from the latest task in history
    if (taskHistory.length > 0) {
      const latestTask = taskHistory[0];
      // Extract from agent_messages if available (first human message)
      if (latestTask.result?.agent_messages) {
        for (const msg of latestTask.result.agent_messages) {
          if (msg.role === 'human') {
            return msg.content;
          }
        }
      }
    }

    // Fallback: Try to get from workflow events (status event with input_data)
    for (const event of workflowEvents) {
      if (event.data?.input_data?.query) {
        return event.data.input_data.query;
      }
    }

    return null;
  }, [taskHistory, workflowEvents]);

  // Memoize model name extraction for performance
  const currentModelName = useMemo(() => {
    // Try to get from workflow configuration first
    if (currentWorkflowId && availableWorkflows.length > 0) {
      const workflow = availableWorkflows.find(w => w.id === currentWorkflowId);
      if (workflow?.configuration?.nodes?.[0]?.config?.model) {
        return workflow.configuration.nodes[0].config.model;
      }
    }
    // Fallback to nodes state
    if (nodes.length > 0 && nodes[0].data.config?.model) {
      return nodes[0].data.config.model;
    }
    return 'default';
  }, [currentWorkflowId, availableWorkflows, nodes]);

  // Use extracted hook for workflow metrics calculation
  const workflowMetrics = useWorkflowMetrics({
    workflowEvents,
    enableLogging: true,
  });

  // Callback to update status from monitoring panel
  // NOTE: fetchTaskHistory is already called by useTaskManagement when currentWorkflowId changes

  // Handle task deletion with confirmation
  const handleDeleteTaskWithConfirm = async (taskId: number) => {
    if (!confirm('Are you sure you want to delete this task? This action cannot be undone.')) {
      return;
    }

    // Close replay panel if viewing deleted task
    if (replayTaskId === taskId) {
      setShowReplayPanel(false);
      setReplayTaskId(null);
    }

    // Close context menu
    setTaskContextMenu(null);

    // Delete through hook (handles history update and notification)
    await handleDeleteTask(taskId);
  };

  // Handle duplicating a node
  const handleDuplicateNode = (nodeId: string, _nodeData: NodeData) => {
    const sourceNode = nodes.find(n => n.id === nodeId);
    if (!sourceNode) return;

    const newNodeId = `node-${Date.now()}`;
    const newNode = {
      ...sourceNode,
      id: newNodeId,
      position: {
        x: sourceNode.position.x + 50,
        y: sourceNode.position.y + 50,
      },
      data: {
        ...sourceNode.data,
        label: `${sourceNode.data.label} (Copy)`,
      },
    };

    setNodes((nds) => [...nds, newNode]);
    setNodeContextMenu(null);
    showSuccess('Node duplicated successfully');
  };

  // Handle opening chat with agent
  const handleChatWithAgent = (_nodeId: string, nodeData: NodeData) => {
    // Close context menu
    setNodeContextMenu(null);

    // Check if this node has a linked deep agent ID
    const deepAgentId = (nodeData as any).deepAgentId || (nodeData.config as any)?.deepAgentId;

    if (deepAgentId) {
      // Open chat with this specific agent
      openChat(deepAgentId);
    } else {
      // Show modal that this node needs to be saved to library first
      setShowChatWarningModal(true);
    }
  };

  // Handle deleting a node
  const handleDeleteNode = (nodeId: string) => {
    if (!confirm('Are you sure you want to delete this node?')) return;

    setNodes((nds) => nds.filter((n) => n.id !== nodeId));
    setEdges((eds) => eds.filter((e) => e.source !== nodeId && e.target !== nodeId));
    setNodeContextMenu(null);
    showSuccess('Node deleted');
  };

  // Handle opening node configuration
  const handleConfigureNode = (nodeId: string) => {
    const node = nodes.find(n => n.id === nodeId);
    if (node && onNodeSelect) {
      onNodeSelect(nodeId, node.data as NodeData);
    }
    setNodeContextMenu(null);
  };

  // Handle copying LangChain code for a node
  const handleCopyLangChainCode = async (_nodeId: string, nodeData: NodeData) => {
    try {
      // Generate Python code for this specific agent node
      const pythonCode = `from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

# Agent: ${nodeData.label}
# Model: ${nodeData.config.model}
# Temperature: ${nodeData.config.temperature}

# Initialize the model
${nodeData.config.model.includes('claude')
          ? `model = ChatAnthropic(
    model="${nodeData.config.model}",
    temperature=${nodeData.config.temperature},
    max_tokens=${nodeData.config.max_tokens || 4000}
)`
          : `model = ChatOpenAI(
    model="${nodeData.config.model}",
    temperature=${nodeData.config.temperature},
    max_tokens=${nodeData.config.max_tokens || 4000}
)`}

# System prompt
system_prompt = """${nodeData.config.system_prompt || 'You are a helpful AI assistant.'}"""

# Create the agent with tools
${nodeData.config.native_tools && nodeData.config.native_tools.length > 0
          ? `# Native tools: ${nodeData.config.native_tools.join(', ')}
tools = []  # Add your tools here
agent = create_react_agent(model, tools, state_modifier=system_prompt)`
          : `agent = create_react_agent(model, [], state_modifier=system_prompt)`}

# Run the agent
if __name__ == "__main__":
    result = agent.invoke({
        "messages": [HumanMessage(content="Your query here")]
    })
    print(result["messages"][-1].content)
`;

      await navigator.clipboard.writeText(pythonCode);
      showSuccess('LangChain code copied to clipboard!');
      setNodeContextMenu(null);
    } catch (error: any) {
      console.error('Failed to copy code:', error);
      logError('Failed to copy code', error.message);
    }
  };

  // Use extracted hook for workflow completion detection
  useWorkflowCompletion({
    workflowEvents,
    setExecutionStatus,
    fetchTaskHistory,
    onComplete: () => handleTabChange('results'),
    clearSelectedTask: () => setSelectedHistoryTask(null),
    expandHistory: () => setIsHistoryCollapsed(false),
  });

  // Fetch available documents for context
  useEffect(() => {
    const fetchDocuments = async () => {
      if (!activeProjectId) return;
      try {
        const projectId = typeof activeProjectId === 'string' ? parseInt(activeProjectId, 10) : activeProjectId;
        const response = await apiClient.listDocuments({ project_id: projectId });
        setAvailableDocuments(response.data || []);
      } catch (error) {
        console.error('Failed to fetch documents:', error);
      }
    };
    fetchDocuments();
  }, [activeProjectId]);

  // Fetch workflow list for dropdown
  const fetchWorkflows = async () => {
    try {
      const response = await apiClient.listWorkflows();
      setAvailableWorkflows(response.data || []); // Changed from setTaskHistory to setAvailableWorkflows
    } catch (error) {
      console.error('Failed to fetch workflows:', error);
    }
  };

  // Load workflow data
  // Fetch available workflows on mount
  useEffect(() => {
    fetchWorkflows();
  }, []);

  // Refresh workflow list when dropdown opens
  useEffect(() => {
    if (showWorkflowDropdown) {
      fetchWorkflows();
    }
  }, [showWorkflowDropdown]);

  // Workflow details (lock_version, name) are now fetched by useWorkflowPersistence hook

  // Use extracted hook for tool and action extraction
  const toolsAndActions = useToolsAndActions({
    taskHistory,
    selectedHistoryTask,
  });

  // Use extracted hook for token cost calculation
  const tokenCostInfo = useTokenCostInfo({
    taskHistory,
    selectedHistoryTask,
    currentModelName,
    workflowEvents,
    nodeTokenCosts,
    onTokenCostUpdate,
  });

  // Compute artifacts from task history content_blocks
  const artifacts = useMemo(() => {
    const artifactEntries: Array<{
      id: string;
      taskId: number;
      agentLabel?: string;
      timestamp: string;
      blocks: any[];
    }> = [];

    taskHistory.forEach((task) => {
      // Get content_blocks from task result
      const contentBlocks = task.result?.content_blocks || [];
      if (contentBlocks.length > 0) {
        artifactEntries.push({
          id: `task-${task.id}`,
          taskId: task.id,
          agentLabel: task.result?.agent_label,
          timestamp: task.created_at,
          blocks: contentBlocks,
        });
      }
    });

    return artifactEntries;
  }, [taskHistory]);

  // Count total artifact blocks
  const artifactsCount = useMemo(() => {
    return artifacts.reduce((count, entry) => count + entry.blocks.length, 0);
  }, [artifacts]);

  // Load workflow from localStorage on mount (only once)
  useEffect(() => {
    if (hasLoadedRef.current) return;
    hasLoadedRef.current = true;

    const savedWorkflow = localStorage.getItem('langconfig-workflow');
    if (savedWorkflow) {
      try {
        const { nodes: savedNodes, edges: savedEdges, counter, name, workflowId } = JSON.parse(savedWorkflow);
        let validatedNodes = []; // Declare outside the if block

        if (savedNodes && Array.isArray(savedNodes)) {
          // Validate and fix node positions with better defaults
          validatedNodes = savedNodes.map((node, index) => ({
            ...node,
            position: {
              x: typeof node.position?.x === 'number' && !isNaN(node.position.x)
                ? node.position.x
                : 250 + (index * 200), // Better horizontal spacing
              y: typeof node.position?.y === 'number' && !isNaN(node.position.y)
                ? node.position.y
                : 250
            },
            width: node.width || 200, // Ensure width is always set
            height: node.height || 100 // Ensure height is always set
          }));
          setNodes(validatedNodes);
        }

        if (savedEdges && Array.isArray(savedEdges) && validatedNodes.length > 0) {
          // Validate edges - only keep edges that reference existing nodes with valid positions
          const nodeIds = new Set(validatedNodes.map(n => n.id));
          const validatedEdges = savedEdges.filter(edge => {
            // Check if both source and target nodes exist
            if (!nodeIds.has(edge.source) || !nodeIds.has(edge.target)) {
              console.warn('Removing edge with invalid node reference:', edge);
              return false;
            }
            return true;
          });
          setEdges(validatedEdges);
        }
        if (counter) {
          setNodeIdCounter(counter);
        }
        if (name) {
          setWorkflowName(name);
          setEditedName(name);
        }
        if (workflowId) {
          setCurrentWorkflowId(workflowId);
        }

        // Always fit view to show all nodes after loading (ignore saved viewport)
        setTimeout(() => {
          if (reactFlowInstance && savedNodes && savedNodes.length > 0) {
            reactFlowInstance.fitView({ padding: 0.5, duration: 400, maxZoom: 0.6 });
          }
        }, 150);
      } catch (error) {
        console.error('Failed to load saved workflow:', error);
      }
    }
  }, [setNodes, setEdges, reactFlowInstance]);

  // Create a stable reference for nodes without runtime executionStatus
  // This prevents execution status changes from triggering auto-save
  const nodesForSave = useMemo(() =>
    nodes.map(n => ({
      ...n,
      data: {
        ...n.data,
        executionStatus: undefined // Strip runtime-only execution status
      }
    })),
    [nodes]
  );

  // Detect if nodes changed (excluding executionStatus) for auto-save
  const nodesSaveKey = useMemo(() =>
    JSON.stringify(nodesForSave.map(n => ({
      id: n.id,
      position: n.position,
      data: {
        label: n.data.label,
        config: n.data.config
      }
    }))),
    [nodesForSave]
  );

  // Auto-save workflow to localStorage on changes (debounced)
  useEffect(() => {
    if (!hasLoadedRef.current) return; // Don't save until we've loaded
    if (isDraggingRef.current) return; // Don't save while dragging nodes

    const saveWorkflow = setTimeout(() => {
      const workflowData = {
        nodes: nodesForSave, // Use nodes without execution status
        edges,
        counter: nodeIdCounter,
        viewport: reactFlowInstance ? reactFlowInstance.getViewport() : null,
        name: workflowName,
        workflowId: currentWorkflowId
      };
      // Silently save to localStorage
      localStorage.setItem('langconfig-workflow', JSON.stringify(workflowData));
    }, 500); // Reduced debounce since we're not saving during drag

    return () => clearTimeout(saveWorkflow);
  }, [nodesSaveKey, edges, nodeIdCounter, reactFlowInstance, workflowName, currentWorkflowId]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // Ctrl+S or Cmd+S - Quick save
      if ((event.ctrlKey || event.metaKey) && event.key === 's') {
        event.preventDefault();
        if (nodes.length > 0) {
          handleSave();
        }
      }

      // Escape - Deselect all
      if (event.key === 'Escape') {
        setNodes(nodes.map(node => ({ ...node, selected: false })));
        setEdges(edges.map(edge => ({ ...edge, selected: false })));
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [nodes, edges, setNodes, setEdges]);

  const onConnect = useCallback(
    (params: Connection) => {
      // Add edge with enhanced styling using theme colors
      const primaryColor = getComputedStyle(document.documentElement).getPropertyValue('--color-primary').trim();
      const newEdge = {
        ...params,
        type: 'smoothstep',
        animated: false, // Don't animate by default
        style: {
          stroke: primaryColor || '#6366f1',
          strokeWidth: 2.5,
        },
        markerEnd: {
          type: 'arrowclosed' as const,
          color: primaryColor || '#6366f1',
        },
      };
      setEdges((eds) => addEdge(newEdge, eds));
    },
    [setEdges]
  );

  // Handle node drag start - prevent auto-save during drag
  const onNodeDragStart = useCallback(() => {
    isDraggingRef.current = true;
  }, []);

  // Handle node drag stop - save workflow after drag completes
  const onNodeDragStop = useCallback(() => {
    isDraggingRef.current = false;

    // Validate and fix node positions before saving
    setNodes((currentNodes) =>
      currentNodes.map((node) => {
        const validation = validateNodePosition(node.position.x, node.position.y);
        if (!validation.isValid) {
          console.warn(`Invalid node position for ${node.id}: ${validation.error}. Resetting to (250, 250)`);
          return {
            ...node,
            position: { x: 250, y: 250 },
          };
        }
        return node;
      })
    );

    // Defer save to avoid blocking mouseup handler (causes violations)
    // Use setTimeout to push the work to the next event loop tick
    setTimeout(() => {
      // Strip execution status (runtime-only data) before saving
      const cleanNodes = nodes.map(n => ({
        ...n,
        data: {
          ...n.data,
          executionStatus: undefined
        }
      }));

      const workflowData = {
        nodes: cleanNodes,
        edges,
        counter: nodeIdCounter,
        viewport: reactFlowInstance ? reactFlowInstance.getViewport() : null,
        name: workflowName,
        workflowId: currentWorkflowId
      };
      localStorage.setItem('langconfig-workflow', JSON.stringify(workflowData));
    }, 0);
  }, [nodes, edges, nodeIdCounter, reactFlowInstance, workflowName, currentWorkflowId, setNodes]);

  // Add selected agent as a new node
  useEffect(() => {
    if (selectedAgent) {
      // Smart positioning: place near existing nodes or centered
      let newPosition = { x: 250, y: 250 };

      if (nodes.length > 0) {
        // Find the rightmost node with valid position
        const validNodes = nodes.filter(n =>
          typeof n.position?.x === 'number' &&
          typeof n.position?.y === 'number' &&
          !isNaN(n.position.x) &&
          !isNaN(n.position.y)
        );

        if (validNodes.length > 0) {
          const rightmostNode = validNodes.reduce((max, node) =>
            node.position.x > max.position.x ? node : max
            , validNodes[0]);

          newPosition = {
            x: rightmostNode.position.x + 350, // 350px to the right
            y: rightmostNode.position.y, // Same vertical position
          };
        } else {
          // Fallback if no nodes have valid positions
          newPosition = { x: 250, y: 250 };
        }
      } else if (reactFlowInstance) {
        // If first node, place it in the center of the viewport
        const viewport = reactFlowInstance.getViewport();
        // Validate viewport values to prevent NaN coordinates
        const viewportX = typeof viewport?.x === 'number' && !isNaN(viewport.x) ? viewport.x : 0;
        const viewportY = typeof viewport?.y === 'number' && !isNaN(viewport.y) ? viewport.y : 0;
        const viewportZoom = typeof viewport?.zoom === 'number' && !isNaN(viewport.zoom) && viewport.zoom > 0 ? viewport.zoom : 1;

        const centerX = (window.innerWidth / 2 - viewportX) / viewportZoom;
        const centerY = (window.innerHeight / 2 - viewportY) / viewportZoom;

        // Final validation: ensure calculated values are valid numbers
        const finalX = typeof centerX === 'number' && !isNaN(centerX) ? centerX - 100 : 250;
        const finalY = typeof centerY === 'number' && !isNaN(centerY) ? centerY - 50 : 250;

        newPosition = { x: finalX, y: finalY };
      }

      // Validate the calculated position
      const positionValidation = validateNodePosition(newPosition.x, newPosition.y);
      if (!positionValidation.isValid) {
        console.warn(`Invalid new node position: ${positionValidation.error}. Using default (250, 250)`);
        newPosition = { x: 250, y: 250 };
      }

      const newNode: Node = {
        id: `node-${nodeIdCounter}`,
        type: 'custom',
        position: newPosition,
        data: {
          label: selectedAgent.name,
          agentType: selectedAgent.id,
          model: selectedAgent.model,
          // Add full agent config as expected by backend (simple_executor.py line 178)
          config: {
            model: selectedAgent.model,
            fallback_models: selectedAgent.fallback_models || [],
            temperature: selectedAgent.temperature,
            max_tokens: selectedAgent.max_tokens,
            system_prompt: selectedAgent.system_prompt,
            // Built-in tools
            native_tools: selectedAgent.native_tools || [],
            tools: [], // legacy
            cli_tools: selectedAgent.cli_tools || [],
            custom_tools: selectedAgent.custom_tools || [],  // User-created custom tools
            timeout_seconds: selectedAgent.timeout_seconds,
            max_retries: selectedAgent.max_retries,
            enable_model_routing: selectedAgent.enable_model_routing,
            enable_parallel_tools: selectedAgent.enable_parallel_tools,
            enable_memory: selectedAgent.enable_memory,
            enable_rag: selectedAgent.enable_rag || false,
            requires_human_approval: selectedAgent.requires_human_approval || false,
            // DeepAgent configuration - check multiple sources for compatibility
            // Deep agents return use_deepagents at top-level AND in config
            use_deepagents: (selectedAgent as any).use_deepagents ||
              (selectedAgent as any).config?.use_deepagents ||
              ((selectedAgent as any).subagents?.length > 0) ||
              ((selectedAgent as any).subagents_config?.length > 0) ||
              false,
            subagents: (selectedAgent as any).subagents || (selectedAgent as any).subagents_config || [],
            // Track original library agent for updates (preserves chat context)
            deep_agent_template_id: (selectedAgent as any).id || null,
            // Tool Node configuration (instance-specific)
            tool_type: null,
            tool_id: null,
            tool_params: {}
          },
        },
      };

      setNodes((nds) => {
        return [...nds, newNode];
      });
      setNodeIdCounter(nodeIdCounter + 1);

      // Auto fit view to show all nodes after adding
      setTimeout(() => {
        if (reactFlowInstance) {
          reactFlowInstance.fitView({ padding: 0.2, duration: 400, maxZoom: 1.2 });
        }
      }, 100);

      // Notify parent that agent was added so it can clear the selection
      if (onAgentAdded) {
        onAgentAdded();
      }
    }
    // Only react to selectedAgent changes, not nodes changes to avoid re-running when we add a node
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedAgent, onAgentAdded, reactFlowInstance, nodeIdCounter]);

  // Insert workflow recipe as a set of connected nodes and edges
  useEffect(() => {
    if (selectedRecipe) {
      console.log('[WorkflowCanvas] Inserting recipe:', selectedRecipe.name);

      // Calculate offset based on existing nodes to avoid overlap
      let offsetX = 0;
      let offsetY = 0;

      if (nodes.length > 0) {
        // Find the rightmost and lowest positions of existing nodes
        const validNodes = nodes.filter(n =>
          typeof n.position?.x === 'number' &&
          typeof n.position?.y === 'number' &&
          !isNaN(n.position.x) &&
          !isNaN(n.position.y)
        );

        if (validNodes.length > 0) {
          const _maxX = Math.max(...validNodes.map(n => n.position.x));
          const maxY = Math.max(...validNodes.map(n => n.position.y));
          // Place recipe below and slightly to the right of existing content
          offsetX = 0; // Start at same X but offset Y
          offsetY = maxY + 250; // 250px gap below existing nodes
          void _maxX; // Future use for horizontal positioning
        }
      }

      // Create unique IDs for recipe nodes using current counter
      const idMap: Record<string, string> = {};
      let newCounter = nodeIdCounter;

      // Map old IDs to new unique IDs
      selectedRecipe.nodes.forEach((recipeNode: any) => {
        const newId = `node-${newCounter}`;
        idMap[recipeNode.id] = newId;
        newCounter++;
      });

      // Create new nodes with updated positions and IDs
      const newNodes: Node[] = selectedRecipe.nodes.map((recipeNode: any) => ({
        ...recipeNode,
        id: idMap[recipeNode.id],
        position: {
          x: recipeNode.position.x + offsetX,
          y: recipeNode.position.y + offsetY,
        },
      }));

      // Get primary color for edges
      const primaryColor = getComputedStyle(document.documentElement).getPropertyValue('--color-primary').trim() || '#6366f1';

      // Create new edges with updated source/target IDs and unique edge IDs
      const newEdges: Edge[] = selectedRecipe.edges.map((recipeEdge: any, idx: number) => ({
        ...recipeEdge,
        id: `recipe-edge-${nodeIdCounter}-${idx}`,
        source: idMap[recipeEdge.source] || recipeEdge.source,
        target: idMap[recipeEdge.target] || recipeEdge.target,
        type: recipeEdge.type || 'smoothstep',
        animated: false,
        style: {
          stroke: primaryColor,
          strokeWidth: 2.5,
        },
        markerEnd: {
          type: 'arrowclosed' as const,
          color: primaryColor,
        },
      }));

      // Add nodes and edges to canvas
      setNodes((nds) => [...nds, ...newNodes]);
      setEdges((eds) => [...eds, ...newEdges]);
      setNodeIdCounter(newCounter);

      // Auto fit view to show all nodes after adding
      setTimeout(() => {
        if (reactFlowInstance) {
          reactFlowInstance.fitView({ padding: 0.2, duration: 400, maxZoom: 1.2 });
        }
      }, 100);

      // Notify parent that recipe was inserted
      if (onRecipeInserted) {
        onRecipeInserted();
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedRecipe, onRecipeInserted, reactFlowInstance, nodeIdCounter]);

  // Node management (handleNodeClick, handleNodeDelete, updateNodeConfig) now provided by useNodeManagement hook

  // Load available documents when dialog opens
  useEffect(() => {
    if (showExecutionDialog && activeProjectId) {
      // Fetch documents from Knowledge Base using API client
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

  // Use extracted hook for execution handlers
  const { handleRun, handleStop, executeWorkflow } = useExecutionHandlers({
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
    workflowAttachments,
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
  });

  // Clear canvas for new workflow
  const clearCanvas = useCallback(() => {
    setNodes([]);
    setEdges([]);
    setCurrentWorkflowId(null);
    setWorkflowName('Untitled Workflow');
    setExecutionStatus({
      state: 'idle',
      currentNode: '',
      progress: 0,
      startTime: '',
      duration: '0s',
    });
    setCurrentTaskId(null);
    resetTaskHistory();
    localStorage.removeItem('langconfig-workflow-id');
    localStorage.removeItem('langconfig-current-task-id');
  }, [setNodes, setEdges]);

  // Expose methods to parent component via ref
  useImperativeHandle(ref, () => ({
    updateNodeConfig,
    deleteNode: handleNodeDelete,
    saveWorkflow: handleSave,
    hasUnsavedChanges: () => hasUnsavedChanges,
    clearCanvas
  }), [updateNodeConfig, handleNodeDelete, handleSave, hasUnsavedChanges, clearCanvas]);

  // ADDED: Debug workflow function
  const handleDebugWorkflow = useCallback(async () => {
    if (!currentWorkflowId) {
      showWarning('No workflow loaded');
      return;
    }

    try {
      const response = await apiClient.debugWorkflow(currentWorkflowId);
      setDebugData(response.data);
      setShowDebugModal(true);
    } catch (error) {
      console.error('Failed to fetch debug info:', error);
      logError('Debug failed', 'Unable to fetch workflow debug info');
    }
  }, [currentWorkflowId, showWarning, logError]);

  const handleSaveWorkflowConfirm = async () => {
    if (!saveWorkflowName.trim()) return;

    try {
      const configuration = {
        nodes: nodes.map(n => {
          const nativeTools = n.data.config?.native_tools || n.data.config?.nativeTools || [];
          const normalizedConfig = {
            ...n.data.config,
            native_tools: nativeTools,
            enable_memory: (n.data.config?.enable_memory ?? nativeTools.includes('enable_memory')) || false,
            enable_rag: (n.data.config?.enable_rag ?? nativeTools.includes('enable_rag')) || false,
          };
          return {
            id: n.id,
            type: n.data.agentType || 'default',
            data: n.data, // Save the full data object so we can restore it properly
            config: normalizedConfig,
            position: n.position
          };
        }),
        edges: edges.map(e => ({
          source: e.source,
          target: e.target
        }))
      };

      const response = await apiClient.createWorkflow({
        name: saveWorkflowName,
        configuration
      });

      setCurrentWorkflowId(response.data.id);
      setWorkflowName(saveWorkflowName); // Update the workflow name display
      setShowSaveModal(false);
      setSaveWorkflowName('');

      // Show success notification
      showSuccess('Workflow saved successfully!');
    } catch (error: any) {
      console.error('Failed to save workflow:', error);
      logError('Failed to save workflow', error.response?.data?.detail || error.message);
    }
  };

  // Version management functions are now provided by useVersionManagement hook

  const handleClear = () => {
    const confirmed = confirm('Are you sure you want to clear the entire workflow? This cannot be undone.');
    if (!confirmed) return;

    setNodes([]);
    setEdges([]);
    setNodeIdCounter(1);
    localStorage.removeItem('langconfig-workflow');
  };

  const handleWorkflowNameSave = async () => {
    if (!editedName.trim()) {
      setIsEditingName(false);
      return;
    }

    const newName = editedName.trim();
    setIsEditingName(false);

    // Use the hook's function for actual save
    await updateWorkflowName(newName);
  };

  const handleWorkflowSwitch = async (workflowId: number) => {
    try {
      const response = await apiClient.getWorkflow(workflowId);
      const workflow = response.data;

      // Load workflow into canvas
      // Backend stores data in 'configuration' field, which may contain nodes/edges
      const config = workflow.configuration || workflow.graph || {};
      const configNodes = config.nodes || [];

      // Validate and fix node positions and ensure type is set to 'custom'
      const validatedNodes = configNodes.map((node: any, index: number) => {
        // Backend saves nodes with: id, type (from agentType), config, position
        // Frontend needs: id, type='custom', data={label, agentType, model, config}, position

        // If node already has data field (from a previous save), use it
        // Otherwise, reconstruct it from the saved type and config
        const nodeData = node.data || {
          label: node.type ? node.type.replace(/_/g, ' ').replace(/\b\w/g, (l: string) => l.toUpperCase()) : `Node ${node.id}`,
          agentType: node.type || 'default',
          model: node.config?.model || 'gpt-4o-mini',
          config: node.config || {}
        };

        return {
          ...node,
          type: 'custom', // React Flow node type (always 'custom' for our CustomNode component)
          data: nodeData,
          position: {
            x: typeof node.position?.x === 'number' && !isNaN(node.position.x)
              ? node.position.x
              : 250 + (index * 200),
            y: typeof node.position?.y === 'number' && !isNaN(node.position.y)
              ? node.position.y
              : 250
          },
          width: node.width || 200, // Ensure width is always set
          height: node.height || 100 // Ensure height is always set
        };
      });

      // Always update the canvas state, even for empty workflows
      setNodes(validatedNodes);
      setEdges(config.edges || []);
      setWorkflowName(workflow.name || 'Untitled Workflow');
      setEditedName(workflow.name || 'Untitled Workflow');
      setCurrentWorkflowId(workflowId);
      // Clear task ID when switching workflows to get fresh events
      setCurrentTaskId(null);
      localStorage.removeItem('langconfig-current-task-id');
      localStorage.setItem('langconfig-workflow-id', String(workflowId));

      setShowWorkflowDropdown(false);
      setWorkflowSearchQuery('');
    } catch (error) {
      console.error('Failed to load workflow:', error);
      alert('Failed to switch workflow. Please try again.');
    }
  };

  const filteredWorkflows = availableWorkflows.filter(wf =>
    wf.name.toLowerCase().includes(workflowSearchQuery.toLowerCase())
  );

  // Status helpers (reserved for status indicator UI)
  const _getWorkflowStatus = (): 'draft' | 'saved' | 'running' | 'completed' | 'failed' => {
    if (executionStatus.state === 'running') return 'running';
    if (executionStatus.state === 'completed') return 'completed';
    if (executionStatus.state === 'failed') return 'failed';
    return currentWorkflowId ? 'saved' : 'draft';
  };

  const _statusConfig = {
    draft: { color: 'yellow', label: 'Draft' },
    saved: { color: 'blue', label: 'Saved' },
    running: { color: 'green', label: 'Running' },
    completed: { color: 'green', label: 'Completed' },
    failed: { color: 'red', label: 'Failed' }
  };
  void _getWorkflowStatus;
  void _statusConfig;

  // Handler to create new workflow from Studio dropdown
  const handleCreateNewWorkflow = useCallback(async () => {
    if (!newWorkflowName.trim()) {
      showWarning('Please enter a workflow name');
      return;
    }

    try {
      // Create new workflow in database
      const response = await apiClient.createWorkflow({
        name: newWorkflowName.trim(),
        configuration: {},
        blueprint: { nodes: [], edges: [] }
      });

      // Clear canvas and load the new workflow
      setNodes([]);
      setEdges([]);
      setCurrentWorkflowId(response.data.id);
      setWorkflowName(response.data.name);
      setExecutionStatus({
        state: 'idle',
        currentNode: '',
        progress: 0,
        startTime: '',
        duration: '0s',
      });
      setCurrentTaskId(null);
      resetTaskHistory();
      localStorage.setItem('langconfig-workflow-id', String(response.data.id));

      // Refresh workflow list
      apiClient.listWorkflows().then(res => {
        setAvailableWorkflows(res.data);
      });

      // Close modal and reset
      setShowCreateWorkflowModal(false);
      setNewWorkflowName('');
      showSuccess(`Created workflow "${response.data.name}"`);
    } catch (error: any) {
      console.error('Failed to create workflow:', error);
      showWarning(`Failed to create workflow: ${error.response?.data?.detail || error.message || 'Unknown error'}`);
    }
  }, [newWorkflowName, setNodes, setEdges, showSuccess, showWarning]);

  return (
    <SelectionProvider>
      <WorkflowCanvasContext.Provider value={{ updateNodeConfig, openNodeContextMenu }}>
        <div className="flex-1 flex flex-col overflow-hidden">
        {/* Workflow Toolbar - Always visible so users can select workflows even with empty canvas */}
        <WorkflowToolbar
          workflowName={workflowName}
          editedName={editedName}
          setEditedName={setEditedName}
          isEditingName={isEditingName}
          setIsEditingName={setIsEditingName}
          handleWorkflowNameSave={handleWorkflowNameSave}
          handleStartEditingName={handleStartEditingName}
          showWorkflowDropdown={showWorkflowDropdown}
          handleToggleWorkflowDropdown={handleToggleWorkflowDropdown}
          handleCloseWorkflowDropdown={handleCloseWorkflowDropdown}
          workflowSearchQuery={workflowSearchQuery}
          handleWorkflowSearchChange={handleWorkflowSearchChange}
          filteredWorkflows={filteredWorkflows}
          currentWorkflowId={currentWorkflowId}
          handleWorkflowSwitch={handleWorkflowSwitch}
          onShowCreateWorkflowModal={() => {
            setShowWorkflowDropdown(false);
            setShowCreateWorkflowModal(true);
          }}
          handleSave={handleSave}
          handleSaveVersion={handleSaveVersion}
          showVersionDropdown={showVersionDropdown}
          setShowVersionDropdown={setShowVersionDropdown}
          currentVersion={currentVersion}
          versions={versions}
          loadingVersions={loadingVersions}
          handleLoadVersion={handleLoadVersion}
          handleToggleSettingsModal={handleToggleSettingsModal}
          // Tab props (merged from TabNavigation)
          activeTab={activeTab}
          onTabChange={(tab) => {
            handleTabChange(tab);
            if (tab === 'results') {
              setShowExecutionDialog(false);
              // Auto-select the latest task to populate results
              if (taskHistory.length > 0 && !selectedHistoryTask) {
                const latestTask = taskHistory[0]; // taskHistory is sorted newest first
                setSelectedHistoryTask(latestTask);
                if (onSelectedTaskChange) {
                  onSelectedTaskChange(latestTask);
                }
              }
              if (executionStatus.state !== 'running') {
                setCurrentTaskId(null);
                localStorage.removeItem('langconfig-current-task-id');
              }
            } else if (tab === 'files') {
              setShowExecutionDialog(false);
              fetchFiles();
            }
          }}
          taskHistoryCount={taskHistory.length}
          filesCount={files.length}
          artifactsCount={artifactsCount}
          hasUnsavedChanges={hasUnsavedChanges}
        />

        {/* Canvas Area */}
        <div className="flex-1 bg-gray-50 dark:bg-background-dark relative overflow-hidden" id="workflow-canvas-container">
          {/* Studio Tab - Keep ReactFlow mounted to preserve node selection */}
          <div style={{ display: activeTab === 'studio' ? 'flex' : 'none', flexDirection: 'column', height: '100%' }}>
            {nodes.length === 0 ? (
              <EmptyCanvasState />
            ) : (
              <ErrorBoundary>
                <ReactFlow
                  nodes={validatedNodes}
                  edges={validatedEdges}
                  onNodesChange={onNodesChange}
                  onEdgesChange={onEdgesChange}
                  onConnect={onConnect}
                  onNodeClick={handleNodeClick}
                  onNodeDragStart={onNodeDragStart}
                  onNodeDragStop={onNodeDragStop}
                  onInit={(instance) => {
                    setReactFlowInstance(instance);
                    setCurrentZoom(instance.getZoom()); // Set initial zoom
                    // Fit view on initial load if nodes exist - more zoomed out for better visibility
                    if (nodes.length > 0) {
                      setTimeout(() => {
                        instance.fitView({ padding: 0.5, maxZoom: 0.6, minZoom: 0.3 });
                        setCurrentZoom(instance.getZoom()); // Update zoom after fit
                      }, 100);
                    }
                  }}
                  onMove={(_event, viewport) => {
                    // Update zoom level when viewport changes
                    if (viewport && viewport.zoom !== currentZoom) {
                      setCurrentZoom(viewport.zoom);
                    }
                  }}
                  nodeTypes={nodeTypes}
                  className="w-full h-full"
                  deleteKeyCode={["Backspace", "Delete"]}
                  multiSelectionKeyCode="Shift"
                  panOnScroll={true}
                  zoomOnScroll={true}
                  zoomOnPinch={true}
                  zoomOnDoubleClick={false}
                  fitView
                  fitViewOptions={{ padding: 0.5, maxZoom: 0.6, minZoom: 0.3 }}
                  defaultViewport={{ x: 0, y: 0, zoom: 0.5 }}
                >
                  <Background
                    variant={BackgroundVariant.Dots}
                    gap={16}
                    size={1}
                    className="bg-gray-50 dark:bg-background-dark"
                  />

                  {/* Controls - repositioned to top-left */}
                  <Controls
                    showInteractive={false}
                    position="top-left"
                    className="!bg-white dark:!bg-panel-dark !border-2 !border-gray-200 dark:!border-border-dark !rounded-lg !shadow-lg"
                  />

                  {/* Control Buttons - Top Right */}
                  <CanvasControlPanel
                    showLiveExecutionPanel={showLiveExecutionPanel}
                    showThinkingStream={showThinkingStream}
                    onToggleLiveExecutionPanel={handleToggleLiveExecutionPanel}
                    onToggleThinkingStream={handleToggleThinkingStream}
                    onDebugWorkflow={handleDebugWorkflow}
                    executionStatus={executionStatus}
                    currentTaskId={currentTaskId}
                    onRun={handleRun}
                    onStop={handleStop}
                    onClear={handleClear}
                  />

                  {/* Workflow Settings Modal */}
                  <WorkflowSettingsDialog
                    isOpen={showSettingsModal}
                    onClose={handleCloseSettingsModal}
                    checkpointerEnabled={checkpointerEnabled}
                    onToggleCheckpointer={handleToggleCheckpointer}
                    globalRecursionLimit={globalRecursionLimit}
                    setGlobalRecursionLimit={setGlobalRecursionLimit}
                  />

                  {/* MiniMap with enhanced styling - only show when nodes have valid positions */}
                  {validatedNodes.length > 0 && (
                    <MiniMap
                      nodeColor={() => 'var(--color-primary)'}
                      maskColor="rgba(0, 0, 0, 0.1)"
                      position="bottom-left"
                      className="!bg-white dark:!bg-panel-dark !border-2 !border-gray-200 dark:!border-border-dark !rounded-lg !shadow-lg"
                      style={{
                        backgroundColor: 'var(--color-panel-dark)',
                        width: '120px',
                        height: '80px'
                      }}
                    />
                  )}
                </ReactFlow>

                {/* Live Execution Panel - Slides in from left, independent from thinking toasts */}
                <RealtimeExecutionPanel
                  isVisible={showLiveExecutionPanel}
                  events={workflowEvents}
                  latestEvent={latestEvent}
                  onClose={() => setShowLiveExecutionPanel(false)}
                  executionStatus={executionStatus}
                  workflowMetrics={workflowMetrics}
                  userPrompt={userPrompt}
                  workflowName={workflowName}
                />

                {/* Thinking Toasts - Rendered outside ReactFlow with screen coordinates */}
                <ThinkingToastRenderer
                  nodes={nodes}
                  nodeExecutionStatuses={nodeExecutionStatuses}
                  reactFlowInstance={reactFlowInstance}
                  showThinkingStream={showThinkingStream}
                  currentZoom={currentZoom}
                />
              </ErrorBoundary>
            )}

            {/* Floating Total Cost Panel - Top Right */}
            {activeTab === 'studio' && (
              <TotalCostPanel
                nodeTokenCosts={nodeTokenCosts}
                isNodeConfigPanelOpen={!!onNodeSelect}
              />
            )}
          </div>

          {/* Results Tab - Extracted to WorkflowResults component */}
          {activeTab === 'results' && (
            <WorkflowResults
              currentWorkflowId={currentWorkflowId}
              workflowName={workflowName}
              taskHistory={taskHistory}
              loadingHistory={loadingHistory}
              selectedHistoryTask={selectedHistoryTask}
              setSelectedHistoryTask={setSelectedHistoryTask}
              isHistoryCollapsed={isHistoryCollapsed}
              setIsHistoryCollapsed={setIsHistoryCollapsed}
              taskContextMenu={taskContextMenu}
              setTaskContextMenu={setTaskContextMenu}
              handleDeleteTask={handleDeleteTaskWithConfirm}
              showReplayPanel={showReplayPanel}
              setShowReplayPanel={setShowReplayPanel}
              replayTaskId={replayTaskId}
              setReplayTaskId={setReplayTaskId}
              replayEvents={replayEvents}
              executionStatus={executionStatus}
              copiedToClipboard={copiedToClipboard}
              setCopiedToClipboard={setCopiedToClipboard}
              showRawOutput={showRawOutput}
              setShowRawOutput={setShowRawOutput}
              showAnimatedReveal={showAnimatedReveal}
              setShowAnimatedReveal={setShowAnimatedReveal}
              versions={versions}
              compareMode={compareMode}
              setCompareMode={setCompareMode}
              compareVersion1={compareVersion1}
              setCompareVersion1={setCompareVersion1}
              compareVersion2={compareVersion2}
              setCompareVersion2={setCompareVersion2}
              loadingComparison={loadingComparison}
              versionComparison={versionComparison}
              handleCompareVersions={handleCompareVersions}
              toolsAndActions={toolsAndActions}
              tokenCostInfo={tokenCostInfo}
              nodeTokenCosts={nodeTokenCosts}
              expandedToolCalls={expandedToolCalls}
              setExpandedToolCalls={setExpandedToolCalls}
            />
          )}

          {/* Files Tab */}
          {activeTab === 'files' && (
            <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
              <div className="w-full h-full flex flex-col">
                {/* Header */}
                <div className="flex items-center justify-between border-b px-4 py-2" style={{ borderColor: 'var(--color-border-dark)' }}>
                  <h2 className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                    Generated Files
                  </h2>
                </div>

                {/* Files Content with Selection Support */}
                <FilesTab
                  files={files}
                  filesLoading={filesLoading}
                  filesError={filesError}
                  selectedPreviewFile={selectedPreviewFile}
                  filePreviewContent={filePreviewContent}
                  filePreviewLoading={filePreviewLoading}
                  currentTaskId={selectedHistoryTask?.id ?? currentTaskId}
                  fetchFiles={fetchFiles}
                  handleDownloadFile={handleDownloadFile}
                  handleFileSelect={handleFileSelect}
                  closeFilePreview={closeFilePreview}
                  onCreatePresentation={() => setShowPresentationDialog(true)}
                />
              </div>
            </div>
          )}

          {/* Artifacts Tab */}
          {activeTab === 'artifacts' && (
            <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
              <ArtifactsTab
                artifacts={artifacts}
                loading={loadingHistory}
                onCreatePresentation={() => setShowPresentationDialog(true)}
              />
            </div>
          )}

          {/* Execution Configuration Dialog */}
          {activeTab === 'studio' && (
            <ExecutionConfigDialog
              isOpen={showExecutionDialog}
              onClose={() => setShowExecutionDialog(false)}
              onExecute={executeWorkflow}
              executionConfig={executionConfig}
              setExecutionConfig={setExecutionConfig}
              showAdvancedOptions={showAdvancedOptions}
              setShowAdvancedOptions={setShowAdvancedOptions}
              additionalContext={additionalContext}
              setAdditionalContext={setAdditionalContext}
              contextDocuments={contextDocuments}
              setContextDocuments={setContextDocuments}
              availableDocuments={availableDocuments}
              attachments={workflowAttachments}
              onAttachmentsChange={setWorkflowAttachments}
            />
          )}

          {/* Save Workflow Modal */}
          <SaveWorkflowModal
            isOpen={showSaveModal}
            onClose={() => setShowSaveModal(false)}
            onSave={handleSaveWorkflowConfirm}
            workflowName={saveWorkflowName}
            setWorkflowName={setSaveWorkflowName}
          />

          {/* Save to Agent Library Modal */}
          <SaveToLibraryModal
            isOpen={showSaveToLibraryModal}
            onClose={handleCloseSaveToLibraryModal}
            onSave={handleConfirmSaveToLibrary}
            agentName={agentLibraryName}
            setAgentName={setAgentLibraryName}
            agentDescription={agentLibraryDescription}
            setAgentDescription={setAgentLibraryDescription}
          />

          {/* Chat with Unsaved Agent Warning Modal */}
          <ChatWarningModal
            isOpen={showChatWarningModal}
            onClose={() => setShowChatWarningModal(false)}
          />

          {/* Presentation Dialog */}
          <PresentationDialog
            isOpen={showPresentationDialog}
            onClose={() => setShowPresentationDialog(false)}
            workflowId={currentWorkflowId ?? undefined}
            taskId={currentTaskId ?? undefined}
          />

          {/* Save Version Modal */}
          <SaveVersionDialog
            isOpen={showVersionModal}
            onClose={handleCloseVersionModal}
            onSave={handleSaveVersionConfirm}
            versionNotes={versionNotes}
            setVersionNotes={setVersionNotes}
          />

        </div>

        {/* Debug Workflow Modal */}
        <DebugWorkflowDialog
          isOpen={showDebugModal}
          onClose={() => setShowDebugModal(false)}
          debugData={debugData}
          onCopyJson={() => {
            if (debugData) {
              navigator.clipboard.writeText(JSON.stringify(debugData.raw_configuration, null, 2));
              showSuccess('Configuration copied to clipboard!');
            }
          }}
        />

        {/* Notification Modal */}
        <NotificationModal />

        {/* Task Context Menu */}
        {taskContextMenu && (
          <TaskContextMenu
            x={taskContextMenu.x}
            y={taskContextMenu.y}
            taskId={taskContextMenu.taskId}
            onDeleteTask={handleDeleteTaskWithConfirm}
          />
        )}

        {/* Node Context Menu */}
        {nodeContextMenu && (
          <NodeContextMenu
            x={nodeContextMenu.x}
            y={nodeContextMenu.y}
            nodeId={nodeContextMenu.nodeId}
            nodeData={nodeContextMenu.nodeData}
            onClose={() => setNodeContextMenu(null)}
            onChatWithAgent={handleChatWithAgent}
            onSaveToLibrary={handleSaveToAgentLibrary}
            onCopyLangChainCode={handleCopyLangChainCode}
            onDuplicateNode={handleDuplicateNode}
            onConfigureNode={handleConfigureNode}
            onDeleteNode={handleDeleteNode}
          />
        )}

        {/* Create New Workflow Modal */}
        <CreateWorkflowDialog
          isOpen={showCreateWorkflowModal}
          onClose={() => setShowCreateWorkflowModal(false)}
          onCreate={handleCreateNewWorkflow}
          workflowName={newWorkflowName}
          setWorkflowName={setNewWorkflowName}
        />

        {showConflictDialog && conflictData && (
          <ConflictDialog
            open={showConflictDialog}
            resourceType="Workflow"
            resourceName={workflowName}
            localData={conflictData.localData}
            remoteData={conflictData.remoteData}
            onResolve={handleConflictResolve}
            onClose={() => handleConflictResolve('cancel')}
          />
        )}
        </div>
      </WorkflowCanvasContext.Provider>
    </SelectionProvider>
  );
});

WorkflowCanvas.displayName = 'WorkflowCanvas';

export default WorkflowCanvas;
