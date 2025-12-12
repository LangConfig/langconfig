/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import type { Node } from 'reactflow';
import type { NodeExecutionStatus } from '../../../../hooks/useNodeExecutionStatus';

/**
 * Agent definition from the agent library
 */
export interface Agent {
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

/**
 * Node configuration stored in each workflow node
 */
export interface NodeConfig {
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
  // Execution control
  recursion_limit?: number;
  pauseBefore?: boolean;
  pauseAfter?: boolean;
  // DeepAgent support
  use_deepagents?: boolean;
  subagents?: any[];
  middleware?: any[];
}

/**
 * Data structure for workflow nodes
 */
export interface NodeData {
  label: string;
  agentType: string;
  model: string;
  config: NodeConfig;
  executionStatus?: NodeExecutionStatus;
}

/**
 * Typed workflow node
 */
export type WorkflowNode = Node<NodeData>;

/**
 * Execution context for workflow runs
 */
export interface WorkflowExecutionContext {
  directive: string;
  query: string;
  task: string;
  classification: 'GENERAL' | 'BACKEND' | 'FRONTEND' | 'DEVOPS_IAC' | 'DATABASE' | 'API' | 'TESTING' | 'DOCUMENTATION' | 'CONFIGURATION';
  executor_type: 'default' | 'devops' | 'frontend' | 'database' | 'testing';
  max_retries: number;
  max_events?: number;
  timeout_seconds?: number;
}

/**
 * Ref interface for exposing methods to parent components
 */
export interface WorkflowCanvasRef {
  updateNodeConfig: (nodeId: string, fullConfig: any) => void;
  deleteNode: (nodeId: string) => void;
  saveWorkflow: (silent?: boolean) => Promise<void>;
  hasUnsavedChanges: () => boolean;
  clearCanvas: () => void;
}

/**
 * Recipe type for multi-node workflow templates
 */
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

/**
 * Props for the main WorkflowCanvas component
 */
export interface WorkflowCanvasProps {
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
  onTokenCostUpdate?: (tokenInfo: TokenCostInfo) => void;
}

/**
 * Token cost information for display
 */
export interface TokenCostInfo {
  totalTokens: number;
  promptTokens: number;
  completionTokens: number;
  costString: string;
}

/**
 * Execution status state
 */
export interface ExecutionStatus {
  state: 'idle' | 'running' | 'completed' | 'failed';
  currentNode?: string;
  progress?: number;
  startTime?: string;
  duration?: string;
}

/**
 * Execution configuration for running workflows
 */
export interface ExecutionConfig {
  prompt: string;
  directive?: string;
  task?: string;
  classification?: WorkflowExecutionContext['classification'];
  executor_type?: WorkflowExecutionContext['executor_type'];
  max_retries?: number;
  max_events?: number;
  timeout_seconds?: number;
  context_documents?: any[];
}

/**
 * Task history entry
 */
export interface TaskHistoryEntry {
  id: number;
  task_id: number;
  workflow_id?: number;
  status: string;
  created_at: string;
  completed_at?: string;
  duration_seconds?: number;
  user_input?: string;  // The user's prompt/directive
  input_data?: any;
  formatted_input?: string;
  result?: any;
  error?: string;
}

/**
 * Workflow version entry
 */
export interface WorkflowVersion {
  id: number;
  workflow_id: number;
  version_number: number;
  notes?: string;
  created_at: string;
  nodes: any[];
  edges: any[];
}

/**
 * Conflict data for merge conflicts
 */
export interface ConflictData {
  serverVersion: number;
  serverNodes: any[];
  serverEdges: any[];
  serverName: string;
  localNodes: any[];
  localEdges: any[];
  localName: string;
}

/**
 * File entry from workspace
 */
export interface WorkspaceFile {
  name: string;
  path: string;
  size: number;
  modified: string;
  type: 'file' | 'directory';
}

/**
 * Context value for sharing state with nested components
 */
export interface WorkflowCanvasContextValue {
  updateNodeConfig: (nodeId: string, config: any) => void;
  openNodeContextMenu: (nodeId: string, nodeData: NodeData, x: number, y: number) => void;
}

/**
 * Node token cost tracking
 */
export interface NodeTokenCost {
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
  costString?: string;
}

/**
 * Node warning state
 */
export interface NodeWarning {
  nodeId: string;
  message: string;
  type: 'error' | 'warning';
}
