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
  | 'keepalive';

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

// Generic event for other types
export interface GenericEvent extends BaseEvent {
  type: Exclude<WorkflowEventType, 'on_chat_model_stream' | 'on_tool_start' | 'on_tool_end' | 'error' | 'node_completed' | 'subagent_start' | 'subagent_end' | 'subagent_error'>;
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
  | GenericEvent;
