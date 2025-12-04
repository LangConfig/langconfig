/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
}

export interface ChatSession {
  session_id: string;
  agent_id: number;
  agent_name: string;
  is_active: boolean;
  message_count: number;
  last_message_preview: string | null;
  created_at: string;
  updated_at: string;
}

export interface SessionMetrics {
  total_tokens: number;
  total_cost_usd?: number;
  rag_context_tokens?: number;
  context_tokens?: number;
  cost_per_token?: number;
  model_used?: string;
  tool_calls: number;
  subagent_spawns: number;
  context_operations: number;
}

export interface SessionDocument {
  id: number;
  session_id: string;
  filename: string;
  original_filename: string;
  file_size: number;
  mime_type: string | null;
  document_type: string;
  indexing_status: 'not_indexed' | 'indexing' | 'ready' | 'failed';
  uploaded_at: string;
  message_index: number | null;
  indexed_chunks_count: number | null;
}

export interface ToolCall {
  tool_name: string;
  arguments: Record<string, any>;
  result: string;
  timestamp: string;
}

export interface SubAgentActivity {
  subagent_name: string;
  action: string;
  timestamp: string;
}

export interface DeepAgent {
  id: number;
  name: string;
  description: string;
  category: string;
  config: any;
  is_public: boolean;
  created_at: string;
  updated_at: string;
}

export interface ChatStreamEvent {
  type: 'chunk' | 'complete' | 'error' | 'tool_start' | 'tool_end';
  content?: string;
  message?: string;
  tool_name?: string;
  data?: any;
}

export interface ChatContextState {
  isOpen: boolean;
  currentSessionId: string | null;
  sessions: ChatSession[];
  selectedAgentId: number | null;
  hitlEnabled: boolean;
}

export interface ChatContextValue extends ChatContextState {
  openChat: (agentId?: number) => void;
  closeChat: () => void;
  startSession: (agentId: number) => Promise<string>;
  switchSession: (sessionId: string) => void;
  endSession: (sessionId: string) => Promise<void>;
  setSelectedAgent: (agentId: number | null) => void;
  toggleHitl: () => void;
  refreshSessions: () => Promise<void>;
}
