/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * API Type Definitions
 *
 * TypeScript types for backend API responses
 * 
 */

// ============================================================================
// Optimistic Locking Types
// ============================================================================

export interface WorkflowProfile {
  id: number;
  name: string;
  description?: string;
  project_id?: number;
  strategy_type?: string;
  configuration: any;
  schema_output_config?: any;
  output_schema?: string;
  blueprint?: any;
  lock_version: number;  // Optimistic locking
  created_at: string;
  updated_at: string;
  usage_count: number;
  last_used_at?: string;
}

export interface WorkflowProfileUpdate {
  name?: string;
  description?: string;
  project_id?: number;
  strategy_type?: string;
  configuration?: any;
  schema_output_config?: any;
  output_schema?: string;
  blueprint?: any;
  lock_version: number;  // Required for updates
}

export interface DeepAgent {
  id: number;
  name: string;
  description?: string;
  category: string;
  config: any;
  middleware_config: any[];
  subagents_config: any[];
  backend_config: any;
  guardrails_config: any;
  usage_count: number;
  version: string;  // Semantic version (e.g., "1.0.0")
  lock_version: number;  // Optimistic lock version
  is_public: boolean;
  created_at: string;
  updated_at: string;
}

export interface DeepAgentUpdate {
  name?: string;
  description?: string;
  config?: any;
  lock_version: number;  // Required for updates
}

// ============================================================================
// Error Types
// ============================================================================

export interface ConflictError {
  error: "ConflictError" | "OptimisticLockError";
  message: string;
  status_code: 409;
  detail: {
    resource_type?: string;
    resource_id?: number;
    client_lock_version: number;
    database_lock_version: number;
  };
}

export interface ValidationError {
  error: "ValidationError";
  message: string;
  status_code: 422;
  detail: {
    errors: Array<{
      field: string;
      message: string;
      type: string;
    }>;
  };
}

export interface RateLimitError {
  error: "TooManyRequestsError";
  message: string;
  status_code: 429;
  detail: {
    limit: number;
    window: string;
    retry_after: number;
  };
}

export type ApiError = ConflictError | ValidationError | RateLimitError | {
  error: string;
  message: string;
  status_code: number;
  detail?: any;
};

// ============================================================================
// Background Task Types
// ============================================================================

export type TaskStatus = "PENDING" | "RUNNING" | "COMPLETED" | "FAILED";

export interface BackgroundTask {
  id: number;
  task_type: string;
  payload: any;
  priority: number;
  status: TaskStatus;
  result?: any;
  error?: string;
  retry_count: number;
  max_retries: number;
  created_at: string;
  started_at?: string;
  completed_at?: string;
}

export interface ExportResponse {
  export_id: number;
  export_type: string;
  file_path?: string;
  download_url?: string;
  created_at: string;
  task_id?: number;  // Background task ID
  status?: string;   // "pending" | "in_progress" | "completed" | "failed"
}

// ============================================================================
// Health Check Types
// ============================================================================

export interface HealthStatus {
  status: "healthy" | "degraded" | "unhealthy";
  message: string;
  timestamp: number;
}

export interface DetailedHealthStatus extends HealthStatus {
  components: {
    [key: string]: {
      status: string;
      message?: string;
      [key: string]: any;
    };
  };
  system: {
    cpu_percent: number;
    memory_percent: number;
    disk_percent: number;
    python_version: string;
    process_uptime_seconds: number;
  };
}

export interface PerformanceMetrics {
  total_requests: number;
  avg_duration_ms: number;
  slow_requests: number;
  errors: number;
  error_rate: number;
  by_endpoint: {
    [endpoint: string]: {
      count: number;
      avg_duration_ms: number;
      errors: number;
      error_rate: number;
    };
  };
  by_status_code: {
    [code: string]: number;
  };
}

// ============================================================================
// Local Model Types
// ============================================================================

export interface LocalModel {
  id: number;
  name: string;
  display_name: string;
  description?: string;
  provider: string;
  base_url: string;
  model_name: string;
  is_validated: boolean;
  last_validated_at?: string;
  validation_error?: string;
  capabilities: {
    streaming?: boolean;
    tools?: boolean;
    max_context?: number;
    [key: string]: any;
  };
  usage_count: number;
  last_used_at?: string;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export interface LocalModelCreate {
  name: string;
  display_name: string;
  description?: string;
  provider: string;
  base_url: string;
  model_name: string;
  api_key?: string;
  tags?: string[];
}

export interface LocalModelUpdate {
  display_name?: string;
  description?: string;
  base_url?: string;
  model_name?: string;
  api_key?: string;
  tags?: string[];
}

export interface ValidationResult {
  success: boolean;
  message: string;
  model_count?: number;
  capabilities?: {
    streaming?: boolean;
    tools?: boolean;
    max_context?: number;
    [key: string]: any;
  };
  error_details?: string;
}

// ============================================================================
// Helper Types
// ============================================================================

export interface ApiResponse<T> {
  data?: T;
  error?: ApiError;
  status: number;
}
