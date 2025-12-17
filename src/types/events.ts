/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

export type WorkflowEventType =
  | 'connected'
  | 'on_chain_start'
  | 'on_chain_end'
  | 'on_tool_start'
  | 'tool_start'
  | 'tool_preparing'  // Early notification when tool call JSON is being streamed
  | 'on_tool_end'
  | 'on_chat_model_start'
  | 'on_chat_model_stream'
  | 'on_chat_model_end'
  | 'on_llm_stream'
  | 'token'
  | 'on_agent_action'
  | 'on_agent_finish'
  | 'on_llm_end'
  | 'checkpoint'
  | 'status'
  | 'node_status'
  | 'complete'
  | 'error'
  | 'warning'
  | 'ping'
  | 'hitl_approved'
  | 'hitl_rejected'
  | 'recursion_limit_hit'
  | 'node_completed'
  | 'subagent_start'
  | 'subagent_end'
  | 'subagent_error'
  | 'keepalive'
  // Tool progress events (for long-running tools)
  | 'tool_progress'
  // Agent context event (for debugging)
  | 'agent_context'
  // Debug mode events (detailed tracing)
  | 'debug_state_transition'
  | 'debug_checkpoint'
  | 'debug_graph_state';

export interface BaseEvent {
  event_id: number;
  sequence_number: number;
  idempotency_key: string;
  timestamp: string;
  channel: string;
  type: WorkflowEventType;
}

export interface ChatModelStreamEvent extends BaseEvent {
  type: 'on_chat_model_stream';
  data: {
    token: string;
    content: string;
    agent_label?: string;
    node_id?: string;
  };
}

export interface ToolStartEvent extends BaseEvent {
  type: 'on_tool_start';
  data: {
    tool_name: string;
    name?: string;
    input: string | Record<string, any>;
    input_preview?: string;
    agent_label?: string;
    node_id?: string;
    run_id?: string;
  };
}

export interface ToolEndEvent extends BaseEvent {
  type: 'on_tool_end';
  data: {
    tool_name: string;
    output: string | Record<string, any>;
    agent_label?: string;
    node_id?: string;
    run_id?: string;
    // Multimodal content from MCP tools
    content_blocks?: Array<{
      type: 'text' | 'image' | 'audio' | 'file' | 'resource';
      [key: string]: any;
    }>;
    artifacts?: Array<{
      type: 'text' | 'image' | 'audio' | 'file' | 'resource';
      [key: string]: any;
    }>;
    has_multimodal?: boolean;
  };
}

export interface ErrorEvent extends BaseEvent {
  type: 'error';
  data: {
    error: string;
    message?: string; // Some error events might use message instead of error
    details?: string;
    code?: string;
    severity?: 'info' | 'warning' | 'error' | 'fatal';
    recoverable?: boolean;
    suggestion?: string;
    tool_name?: string;
    agent_label?: string;
    node_id?: string;
  };
}

// Node completion event with token usage and tool metrics
export interface NodeCompletedEvent extends BaseEvent {
  type: 'node_completed';
  data: {
    node_id: string;
    agent_label: string;
    model?: string;
    timestamp?: string;
    tokenCost?: {
      promptTokens: number;
      completionTokens: number;
      totalTokens: number;
      costString?: string;
    };
    toolCalls?: Array<{ name: string; id: string }>;
    toolCallCount?: number;
    toolResultCount?: number;
  };
}
// Subagent start event for nested execution visualization
export interface SubagentStartEvent extends BaseEvent {
  type: 'subagent_start';
  data: {
    subagent_name: string;
    subagent_run_id: string;
    parent_agent_label?: string;
    parent_run_id?: string;
    input_preview?: string;
  };
}

// Subagent end event for nested execution visualization
export interface SubagentEndEvent extends BaseEvent {
  type: 'subagent_end';
  data: {
    subagent_name: string;
    subagent_run_id: string;
    parent_agent_label?: string;
    parent_run_id?: string;
    output_preview?: string;
    success: boolean;
  };
}

// Subagent error event for nested execution visualization
export interface SubagentErrorEvent extends BaseEvent {
  type: 'subagent_error';
  data: {
    subagent_name: string;
    subagent_run_id: string;
    parent_agent_label?: string;
    parent_run_id?: string;
    error_type: string;
    error: string;
    success: false;
  };
}

// Tool progress event for long-running operations
export interface ToolProgressEvent extends BaseEvent {
  type: 'tool_progress';
  data: {
    tool_name: string;
    message: string;
    progress_type: 'started' | 'update' | 'completed' | 'error';
    agent_label?: string;
    node_id?: string;
    percent_complete?: number;
    current_step?: number;
    total_steps?: number;
    task_id?: number;
    project_id?: number;
    metadata?: Record<string, any>;
  };
}

// Debug mode: state transition event
export interface DebugStateTransitionEvent extends BaseEvent {
  type: 'debug_state_transition';
  data: {
    event_kind: string;
    event_name: string;
    tags: string[];
    node_id?: string;
    agent_label?: string;
    run_id: string;
    parent_run_id?: string;
    state_keys: string[];
  };
}

// Debug mode: checkpoint event
export interface DebugCheckpointEvent extends BaseEvent {
  type: 'debug_checkpoint';
  data: {
    checkpoint_id: string;
    checkpoint_ns: string;
    state_keys: string[];
  };
}

// Debug mode: graph state event
export interface DebugGraphStateEvent extends BaseEvent {
  type: 'debug_graph_state';
  data: {
    node_name: string;
    state_update: Record<string, any>;
    state_keys_updated: string[];
  };
}

// Agent context event for debugging (shows what agent has access to)
export interface AgentContextEvent extends BaseEvent {
  type: 'agent_context';
  data: {
    agent_label: string;
    node_id: string;
    timestamp: string;
    system_prompt: {
      preview: string;
      length: number;
    };
    tools: string[];
    attachments: Array<{
      name: string;
      mimeType: string;
      hasData: boolean;
      dataSize?: number;
    }>;
    messages: Array<{
      type: string;
      content: any;
    }>;
    model_config: {
      model: string;
      temperature: number;
      max_tokens?: number;
      enable_memory?: boolean;
      enable_rag?: boolean;
    };
    metadata?: Record<string, any>;
    task_id?: number;
  };
}

// Generic event for other types
export interface GenericEvent extends BaseEvent {
  type: Exclude<WorkflowEventType,
    | 'on_chat_model_stream'
    | 'on_tool_start'
    | 'on_tool_end'
    | 'error'
    | 'node_completed'
    | 'subagent_start'
    | 'subagent_end'
    | 'subagent_error'
    | 'tool_progress'
    | 'agent_context'
    | 'debug_state_transition'
    | 'debug_checkpoint'
    | 'debug_graph_state'
  >;
  data: any;
}

export type WorkflowEvent =
  | ChatModelStreamEvent
  | ToolStartEvent
  | ToolEndEvent
  | ErrorEvent
  | NodeCompletedEvent
  | SubagentStartEvent
  | SubagentEndEvent
  | SubagentErrorEvent
  | ToolProgressEvent
  | DebugStateTransitionEvent
  | DebugCheckpointEvent
  | DebugGraphStateEvent
  | AgentContextEvent
  | GenericEvent;
