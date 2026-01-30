/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * Workflow Types
 *
 * Centralized type definitions for workflows, nodes, edges, and related data structures.
 * Used across the application for type safety and consistency.
 */

/**
 * Node position in the canvas
 */
export interface NodePosition {
  x: number;
  y: number;
}

/**
 * Agent configuration for a workflow node
 */
export interface AgentConfig {
  model: string;
  fallback_models?: string[];
  temperature?: number;
  max_tokens?: number;
  max_retries?: number;
  recursion_limit?: number;
  system_prompt?: string;
  tools?: string[];
  native_tools?: string[];
  cli_tools?: string[];
  custom_tools?: string[];
  middleware?: Array<{
    type: string;
    config?: Record<string, unknown>;
  }>;
  timeout_seconds?: number;
  enable_model_routing?: boolean;
  enable_parallel_tools?: boolean;
  enable_memory?: boolean;
  enable_rag?: boolean;
  requires_human_approval?: boolean;
  condition?: string;
  max_iterations?: number;
  exit_condition?: string;
  name?: string;
}

/**
 * Node data structure
 */
export interface NodeData {
  id?: string;
  name?: string;
  label?: string;
  agentType?: string;
  type?: string;
  config?: AgentConfig;
  // Additional fields that may exist
  [key: string]: unknown;
}

/**
 * Workflow node
 */
export interface WorkflowNode {
  id: string;
  type?: string;
  position?: NodePosition;
  data?: NodeData;
  config?: AgentConfig;
}

/**
 * Edge data structure
 */
export interface EdgeData {
  condition?: string;
  label?: string;
  // Additional fields that may exist
  [key: string]: unknown;
}

/**
 * Workflow edge (connection between nodes)
 */
export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  type?: string;
  data?: EdgeData;
  animated?: boolean;
  label?: string;
}

/**
 * Workflow blueprint structure
 */
export interface WorkflowBlueprint {
  nodes?: WorkflowNode[];
  edges?: WorkflowEdge[];
}

/**
 * Workflow configuration
 */
export interface WorkflowConfiguration {
  /**
   * Canvas structure (Studio saves node/edge state here)
   * Note: some older workflows may store this under `blueprint` instead.
   */
  nodes?: WorkflowNode[];
  edges?: WorkflowEdge[];

  // LangGraph configuration
  checkpointer?: {
    type: string;
    config?: Record<string, unknown>;
  };

  // Execution settings
  max_iterations?: number;
  timeout?: number;

  // Memory settings
  memory_enabled?: boolean;
  memory_config?: {
    provider: string;
    config?: Record<string, unknown>;
  };

  // RAG settings
  rag_enabled?: boolean;
  rag_config?: {
    provider: string;
    config?: Record<string, unknown>;
  };

  // Additional settings
  [key: string]: unknown;
}

/**
 * Complete workflow data structure
 */
export interface Workflow {
  id: number;
  name: string;
  description?: string;
  created_at: string;
  updated_at: string;
  configuration: WorkflowConfiguration;
  blueprint?: WorkflowBlueprint;
  project_id?: number;
  status?: string;
  strategy_type?: string; // For predefined strategy workflows
}

/**
 * Project data structure
 */
export interface Project {
  id: number;
  name: string;
  description?: string;
  status: string;
  indexed_nodes_count?: number;
  created_at?: string;
  updated_at?: string;
}

/**
 * Cost metrics for a workflow
 */
export interface AgentCostMetric {
  name: string;
  cost: number;
  tokens: number;
}

export interface ToolUsageMetric {
  name: string;
  count: number;
}

export interface CostMetrics {
  totalCost: number;
  totalTokens: number;
  promptTokens: number;
  completionTokens: number;
  executionCount: number;
  agents: AgentCostMetric[];
  tools: ToolUsageMetric[];
}

/**
 * Workflow schedule for cron-based execution
 */
export interface WorkflowSchedule {
  id: number;
  workflow_id: number;
  name?: string;
  cron_expression: string;
  timezone: string;
  enabled: boolean;
  default_input_data: Record<string, unknown>;
  max_concurrent_runs: number;
  timeout_minutes: number;
  idempotency_key_template?: string;
  last_run_at?: string;
  next_run_at?: string;
  last_run_status?: 'SUCCESS' | 'FAILED' | 'SKIPPED';
  created_at?: string;
  updated_at?: string;
}

/**
 * Request to create a schedule
 */
export interface ScheduleCreateRequest {
  workflow_id: number;
  name?: string;
  cron_expression: string;
  timezone?: string;
  enabled?: boolean;
  default_input_data?: Record<string, unknown>;
  max_concurrent_runs?: number;
  timeout_minutes?: number;
  idempotency_key_template?: string;
}

/**
 * Request to update a schedule
 */
export interface ScheduleUpdateRequest {
  name?: string;
  cron_expression?: string;
  timezone?: string;
  enabled?: boolean;
  default_input_data?: Record<string, unknown>;
  max_concurrent_runs?: number;
  timeout_minutes?: number;
  idempotency_key_template?: string;
}

/**
 * Scheduled run log entry
 */
export interface ScheduledRunLog {
  id: number;
  schedule_id: number;
  scheduled_for: string;
  started_at?: string;
  completed_at?: string;
  status: 'PENDING' | 'RUNNING' | 'SUCCESS' | 'FAILED' | 'SKIPPED';
  task_id?: number;
  error_message?: string;
  idempotency_key?: string;
  duration?: number;
  created_at?: string;
}

/**
 * Cron validation response
 */
export interface CronValidationResult {
  valid: boolean;
  error?: string;
  next_runs: string[];
  human_readable?: string;
}

/**
 * Workflow trigger types
 */
export type TriggerType = 'webhook' | 'file_watch';

/**
 * Workflow trigger for event-based execution
 */
export interface WorkflowTrigger {
  id: number;
  workflow_id: number;
  trigger_type: TriggerType;
  name?: string;
  enabled: boolean;
  config: Record<string, unknown>;
  webhook_secret?: string;
  webhook_url?: string;
  last_triggered_at?: string;
  trigger_count: number;
  created_at?: string;
  updated_at?: string;
}

/**
 * Request to create a trigger
 */
export interface TriggerCreateRequest {
  workflow_id: number;
  trigger_type: TriggerType;
  name?: string;
  enabled?: boolean;
  config: Record<string, unknown>;
}

/**
 * Request to update a trigger
 */
export interface TriggerUpdateRequest {
  name?: string;
  enabled?: boolean;
  config?: Record<string, unknown>;
}

/**
 * Trigger execution log entry
 */
export interface TriggerLog {
  id: number;
  trigger_id: number;
  triggered_at: string;
  status: 'PENDING' | 'RUNNING' | 'SUCCESS' | 'FAILED' | 'SKIPPED';
  trigger_source?: string;
  trigger_payload?: Record<string, unknown>;
  task_id?: number;
  error_message?: string;
  completed_at?: string;
  duration?: number;
  created_at?: string;
}
