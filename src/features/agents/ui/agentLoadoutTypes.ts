/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * Shared types for the Agent Loadouts surface (agents, custom tools, skills).
 */

export interface CustomTool {
  id?: number;
  tool_id: string;
  name: string;
  description: string;
  tool_type: string;
  category?: string;
  tags: string[];
  is_template_based?: boolean;
  usage_count: number;
  error_count: number;
  last_used_at?: string;
  input_schema?: any;
  implementation_config?: any;
  output_format?: string;
  validation_rules?: any;
  is_advanced_mode?: boolean;
  template_type?: string;
}

export interface Skill {
  skill_id: string;
  name: string;
  description: string;
  version: string;
  source_type: 'builtin' | 'personal' | 'project';
  tags: string[];
  triggers: string[];
  allowed_tools: string[] | null;
  usage_count: number;
  last_used_at: string | null;
  avg_success_rate: number;
  // Extended detail fields (optional, populated when fetching detail)
  instructions?: string;
  examples?: string | null;
  source_path?: string;
  author?: string | null;
  required_context?: string[];
}

/**
 * Generic over the agent shape since the `Agent` interface lives inline in
 * AgentLoadouts.tsx (it is specific to that view's API payload).
 */
export type SelectedItem<TAgent = unknown> =
  | { type: 'agent'; data: TAgent }
  | { type: 'tool'; data: CustomTool }
  | { type: 'skill'; data: Skill }
  | { type: 'template'; category: 'agent' | 'tool' }
  | null;
