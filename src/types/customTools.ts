/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

// TypeScript interfaces for Custom Tools feature

export type ToolType = 'api' | 'notification' | 'image_video' | 'database' | 'data_transform';

export type ToolTemplateType =
  | 'slack_notification'
  | 'discord_notification'
  | 'email_notification'
  | 'dalle3_image'
  | 'video_generator'
  | 'sql_query'
  | 'rest_api'
  | 'json_transformer'
  | 'csv_parser';

export interface CustomTool {
  id: number;
  tool_id: string;
  name: string;
  description: string;
  tool_type: ToolType;
  template_type?: ToolTemplateType;
  implementation_config: Record<string, any>;
  input_schema: Record<string, any>;
  output_format: string;
  is_template_based: boolean;
  is_advanced_mode: boolean;
  category?: string;
  tags: string[];
  usage_count: number;
  error_count: number;
  last_used_at?: string;
  created_at: string;
  updated_at: string;
  version: string;
  project_id?: number;
}

export interface CustomToolCreate {
  tool_id: string;
  name: string;
  description: string;
  tool_type: ToolType;
  template_type?: ToolTemplateType;
  implementation_config: Record<string, any>;
  input_schema: Record<string, any>;
  output_format?: string;
  is_template_based?: boolean;
  is_advanced_mode?: boolean;
  category?: string;
  tags?: string[];
  project_id?: number;
}

export interface CustomToolUpdate {
  name?: string;
  description?: string;
  implementation_config?: Record<string, any>;
  input_schema?: Record<string, any>;
  output_format?: string;
  category?: string;
  tags?: string[];
}

export interface ToolTemplate {
  template_id: string;
  name: string;
  description: string;
  category: string;
  tool_type: ToolType;
  icon: string;
  priority: number;
  is_featured: boolean;
  required_user_fields: string[];
  config_template: Record<string, any>;
  input_schema_template: Record<string, any>;
  example_use_cases: string[];
  tags: string[];
}

export interface ToolTestRequest {
  test_input: Record<string, any>;
}

export interface ToolTestResult {
  success: boolean;
  result?: any;
  error?: string;
  execution_time_ms?: number;
}

export interface ToolExportResponse {
  tool_data: CustomTool;
  export_format: string;
  exported_at: string;
}

export interface ToolImportRequest {
  file: File;
}
