/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * Skill type definitions for the Skills System
 */

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
}

export interface SkillDetail extends Skill {
  instructions: string;
  examples: string | null;
  source_path: string;
  author: string | null;
  required_context: string[];
  created_at: string;
  updated_at: string;
}

export interface SkillMatch {
  skill: Skill;
  score: number;
  match_reason: string;
}

export interface SkillMatchRequest {
  query: string;
  file_path?: string;
  project_type?: string;
  tags?: string[];
  max_results?: number;
}

export interface SkillStats {
  skill_id: string;
  usage_count: number;
  last_used_at: string | null;
  avg_success_rate: number;
  recent_executions: SkillExecution[];
}

export interface SkillExecution {
  id: number;
  invocation_type: 'automatic' | 'explicit';
  status: string;
  execution_time_ms: number | null;
  created_at: string | null;
}

export interface SkillsSummary {
  total_skills: number;
  by_source: Record<string, number>;
  top_tags: Record<string, number>;
}

export type SkillSourceFilter = 'all' | 'builtin' | 'personal' | 'project';
