/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import axios, { AxiosInstance, AxiosError } from 'axios';
import type { ApiError, ConflictError, RateLimitError } from '@/types/api';

/**
 * Custom Error Classes
 */
export class ConflictErrorClass extends Error {
  constructor(
    message: string,
    public detail: ConflictError['detail']
  ) {
    super(message);
    this.name = 'ConflictError';
  }
}

export class RateLimitErrorClass extends Error {
  constructor(
    message: string,
    public detail: RateLimitError['detail']
  ) {
    super(message);
    this.name = 'RateLimitError';
  }
}

/**
 * API Client for LangConfig backend
 * Enhanced features:
 * - Optimistic locking (409 handling)
 * - Rate limiting (429 handling)
 * - Automatic toast notifications
 */
import { API_BASE_URL } from '../config/api';

/**
 * API Client for LangConfig backend
 * Enhanced features:
 * - Optimistic locking (409 handling)
 * - Rate limiting (429 handling)
 * - Automatic toast notifications
 */
class APIClient {
  private client: AxiosInstance;
  public baseURL: string = API_BASE_URL;

  constructor() {
    this.client = axios.create({
      baseURL: this.baseURL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Interceptor to remove Content-Type for FormData
    this.client.interceptors.request.use((config) => {
      if (config.data instanceof FormData) {
        delete config.headers['Content-Type'];
      }
      return config;
    });

    // Error handling interceptor
    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError<ApiError>) => {
        return this.handleError(error);
      }
    );
  }

  /**
   * Generic fetch wrapper for endpoints not yet typed in the client
   */
  async apiFetch(url: string, options?: any) {
    const response = await fetch(url, options);
    if (!response.ok) {
      throw new Error(`API request failed: ${response.statusText}`);
    }
    return response.json();
  }

  /**
   * Generic axios helpers for ad-hoc endpoints.
   * Prefer adding typed methods over time, but these unblock components safely.
   */
  get(url: string, config?: any) {
    return this.client.get(url, config);
  }

  post(url: string, data?: any, config?: any) {
    return this.client.post(url, data, config);
  }

  put(url: string, data?: any, config?: any) {
    return this.client.put(url, data, config);
  }

  patch(url: string, data?: any, config?: any) {
    return this.client.patch(url, data, config);
  }

  delete(url: string, config?: any) {
    return this.client.delete(url, config);
  }

  /**
   * Enhanced error handling
   */
  private handleError(error: AxiosError<ApiError>) {
    const status = error.response?.status;
    const errorData = error.response?.data;

    switch (status) {
      case 409: {
        // Conflict - Optimistic locking failure
        const message = errorData?.message || 'Resource was modified by another user';
        const detail = (errorData as ConflictError)?.detail;
        this.showToast(message, 'warning');
        throw new ConflictErrorClass(message, detail);
      }

      case 429: {
        // Rate limit exceeded
        const retryAfter = error.response?.headers['retry-after'] || '60';
        const message = errorData?.message || `Rate limit exceeded. Please wait ${retryAfter} seconds.`;
        const detail = (errorData as RateLimitError)?.detail || {
          limit: 60,
          window: '1 minute',
          retry_after: parseInt(retryAfter)
        };
        this.showToast(message, 'error');
        throw new RateLimitErrorClass(message, detail);
      }

      case 422: {
        // Validation error
        const message = errorData?.message || 'Validation failed';
        this.showToast(message, 'error');
        throw error;
      }

      case 404: {
        // Not found
        const message = errorData?.message || 'Resource not found';
        this.showToast(message, 'error');
        throw error;
      }

      case 403: {
        // Forbidden
        const message = errorData?.message || 'Access denied';
        this.showToast(message, 'error');
        throw error;
      }

      case 500:
      case 502:
      case 503: {
        // Server error
        const message = errorData?.message || 'Server error. Please try again later.';
        this.showToast(message, 'error');
        throw error;
      }

      default: {
        // Other errors
        if (error.response) {
          const message = errorData?.message || `Request failed with status ${status}`;
          this.showToast(message, 'error');
        } else if (error.request) {
          this.showToast('Network error. Please check your connection.', 'error');
        }
        throw error;
      }
    }
  }

  /**
   * Show toast notification
   * Compatible with react-hot-toast
   */
  private showToast(message: string, type: 'success' | 'error' | 'warning' | 'info') {
    if (typeof window === 'undefined') return;

    // Try to use react-hot-toast if available
    if ('toast' in window && typeof (window as any).toast === 'object') {
      const toast = (window as any).toast;
      switch (type) {
        case 'success':
          toast.success(message);
          break;
        case 'error':
          toast.error(message);
          break;
        case 'warning':
          toast(message, { icon: '⚠️' });
          break;
        case 'info':
          toast(message);
          break;
      }
    } else {
      console[type === 'error' ? 'error' : 'log'](`[${type.toUpperCase()}]`, message);
    }
  }

  // Health Check
  async healthCheck() {
    return this.client.get('/health');
  }

  // Workflows
  async listWorkflows(config?: { project_id?: number; skip?: number; limit?: number; signal?: AbortSignal }) {
    const { signal, ...params } = config || {};
    return this.client.get('/api/workflows/', { params: Object.keys(params).length ? params : undefined, signal });
  }

  async getWorkflow(id: number) {
    return this.client.get(`/api/workflows/${id}`);
  }

  async createWorkflow(data: {
    name: string;
    project_id?: number;  // Optional - project association
    strategy_type?: string;  // Optional - only needed for predefined strategy workflows
    configuration: object;
    schema_output_config?: object;
    output_schema?: string;
    blueprint?: object;
  }) {
    return this.client.post('/api/workflows/', data);
  }

  async updateWorkflow(id: number, data: Partial<any>) {
    return this.client.patch(`/api/workflows/${id}`, data);
  }

  async deleteWorkflow(id: number) {
    return this.client.delete(`/api/workflows/${id}`);
  }

  async getWorkflowCode(id: number) {
    return this.client.get(`/api/workflows/${id}/code`, {
      responseType: 'text'
    });
  }

  async debugWorkflow(id: number) {
    return this.client.get(`/api/debug/workflow/${id}`);
  }

  async getWorkflowVersions(id: number) {
    return this.client.get(`/api/workflows/${id}/versions`);
  }

  async createWorkflowVersion(id: number, data: any) {
    return this.client.post(`/api/workflows/${id}/versions`, data);
  }

  async getWorkflowVersion(id: number, versionId: number) {
    return this.client.get(`/api/workflows/${id}/versions/${versionId}`);
  }

  async compareWorkflowVersions(id: number, v1: number, v2: number) {
    return this.client.get(`/api/workflows/${id}/versions/${v1}/compare/${v2}`);
  }

  async continueWorkflow(id: number, data: any) {
    return this.client.post(`/api/workflows/${id}/continue`, data);
  }

  async exportWorkflowExecutionDocx(executionId: number) {
    return this.client.get(`/api/workflows/executions/${executionId}/export/docx`, {
      responseType: 'blob'
    });
  }

  async getWorkflowCostMetrics(id: number, days: number = 30) {
    return this.client.get(`/api/workflows/${id}/metrics/cost`, {
      params: { days }
    });
  }


  // Workflow Memory
  async getWorkflowMemory(workflowId: number) {
    return this.client.get(`/api/workflows/${workflowId}/memory`);
  }

  async addWorkflowMemoryItem(workflowId: number, data: {
    namespace: string[];
    key: string;
    value: any;
  }) {
    return this.client.post(`/api/workflows/${workflowId}/memory`, data);
  }

  async deleteWorkflowMemoryItem(workflowId: number, key: string) {
    return this.client.delete(`/api/workflows/${workflowId}/memory/${key}`);
  }

  async clearWorkflowMemory(workflowId: number) {
    return this.client.delete(`/api/workflows/${workflowId}/memory`);
  }

  async batchUpdateWorkflowMemory(workflowId: number, items: any[]) {
    return this.client.post(`/api/workflows/${workflowId}/memory/batch`, { items });
  }

  // Orchestration
  async executeWorkflow(data: {
    workflow_id: number;
    project_id: number;
    input_data: object;
    context_documents?: number[];
    attachments?: Array<{
      type: string;
      name: string;
      mime_type: string;
      data?: string;
      size?: number;
    }>;
  }) {
    return this.client.post('/api/orchestration/execute', data);
  }

  async getTaskStatus(taskId: number) {
    return this.client.get(`/api/orchestration/tasks/${taskId}`);
  }

  async cancelTask(taskId: number) {
    return this.client.post(`/api/orchestration/tasks/${taskId}/cancel`);
  }

  async listTaskFiles(taskId: number) {
    return this.client.get(`/api/orchestration/tasks/${taskId}/files`);
  }

  async downloadTaskFile(taskId: number, filename: string) {
    return this.client.get(`/api/orchestration/tasks/${taskId}/files/${filename}`, {
      responseType: 'blob', // Important for file downloads
    });
  }

  // Projects
  async listProjects(config?: { skip?: number; limit?: number; status?: string; signal?: AbortSignal }) {
    const { signal, ...params } = config || {};
    return this.client.get('/api/projects/', { params: Object.keys(params).length ? params : undefined, signal });
  }

  async getProject(id: number) {
    return this.client.get(`/api/projects/${id}`);
  }

  async createProject(data: {
    name: string;
    description?: string;
    configuration?: object;
  }) {
    return this.client.post('/api/projects/', data);
  }

  async updateProject(id: number, data: Partial<any>) {
    return this.client.patch(`/api/projects/${id}`, data);
  }

  async deleteProject(id: number) {
    return this.client.delete(`/api/projects/${id}`);
  }

  async indexProject(id: number) {
    return this.client.post(`/api/projects/${id}/index`);
  }

  // Tasks
  async listTasks(params?: {
    skip?: number;
    limit?: number;
    project_id?: number;
    status?: string;
  }) {
    return this.client.get('/api/tasks/', { params });
  }

  async getTask(id: number) {
    return this.client.get(`/api/tasks/${id}`);
  }

  async getRecentProjectTasks(projectId: number, limit: number = 10) {
    return this.client.get(`/api/tasks/project/${projectId}/recent`, {
      params: { limit },
    });
  }

  async getTaskStats(projectId?: number) {
    return this.client.get('/api/tasks/stats/summary', {
      params: { project_id: projectId },
    });
  }

  async deleteTask(id: number) {
    return this.client.delete(`/api/tasks/${id}`);
  }

  // RAG / Documents
  async uploadDocument(projectId: number, file: File, metadata?: { description?: string; tags?: string[] }) {
    const formData = new FormData();
    formData.append('file', file);
    if (metadata) {
      formData.append('metadata', JSON.stringify(metadata));
    }

    return this.client.post('/api/rag/upload', formData, {
      params: { project_id: projectId },
    });
  }

  async uploadDocumentsBulk(
    projectId: number,
    files: File[],
    extractArchives: boolean = true,
    metadata?: { description?: string; tags?: string[]; name?: string }
  ) {
    const formData = new FormData();

    // Append all files
    files.forEach((file) => {
      formData.append('files', file);
    });

    // Add form fields (not query params)
    formData.append('project_id', projectId.toString());
    formData.append('extract_archives', extractArchives.toString());

    // Add metadata if provided
    if (metadata) {
      formData.append('metadata', JSON.stringify(metadata));
    }

    return this.client.post('/api/rag/upload-bulk', formData);
  }

  async listDocuments(config: {
    project_id: number;
    skip?: number;
    limit?: number;
    status?: string;
    signal?: AbortSignal;
  }) {
    const { signal, ...params } = config;
    return this.client.get('/api/rag/documents', { params, signal });
  }

  async getDocument(id: number) {
    return this.client.get(`/api/rag/documents/${id}`);
  }

  async deleteDocument(id: number) {
    return this.client.delete(`/api/rag/documents/${id}`);
  }

  async searchDocuments(data: {
    query: string;
    project_id: number;
    top_k?: number;
    use_hyde?: boolean;
  }) {
    return this.client.post('/api/rag/search', data);
  }

  async indexDocument(id: number) {
    return this.client.post(`/api/rag/index/${id}`);
  }

  async getSearchHistory(params: {
    project_id: number;
    limit?: number;
    skip?: number;
  }) {
    return this.client.get('/api/rag/search-history', { params });
  }

  async getProjectStorageStats(projectId: number) {
    return this.client.get(`/api/rag/projects/${projectId}/storage-stats`);
  }

  // Settings
  async getSettings() {
    return this.client.get('/api/settings/');
  }

  async updateSettings(data: {
    default_model?: string;
    default_temperature?: number;
    max_tokens?: number;
    embedding_model?: string;
    chunk_size?: number;
    chunk_overlap?: number;
  }) {
    return this.client.patch('/api/settings/', data);
  }

  async resetSettings() {
    return this.client.post('/api/settings/reset');
  }

  async setApiKeys(data: {
    openai_api_key?: string;
    anthropic_api_key?: string;
    google_api_key?: string;
    cohere_api_key?: string;
    replicate_api_key?: string;
  }) {
    return this.client.post('/api/settings/api-keys', data);
  }

  async getApiKeys() {
    return this.client.get('/api/settings/api-keys');
  }

  async deleteApiKey(provider: string) {
    return this.client.delete(`/api/settings/api-keys/${provider}`);
  }

  async listAvailableModels() {
    return this.client.get('/api/settings/models');
  }

  // Local Models
  async listLocalModels(params?: { only_validated?: boolean; only_active?: boolean }) {
    return this.client.get('/api/local-models/', { params });
  }

  async getLocalModel(id: number) {
    return this.client.get(`/api/local-models/${id}`);
  }

  async createLocalModel(data: {
    name: string;
    display_name: string;
    description?: string;
    provider: string;
    base_url: string;
    model_name: string;
    api_key?: string;
    tags?: string[];
  }) {
    return this.client.post('/api/local-models/', data);
  }

  async updateLocalModel(id: number, data: Partial<any>) {
    return this.client.patch(`/api/local-models/${id}`, data);
  }

  async deleteLocalModel(id: number, hard_delete: boolean = false) {
    return this.client.delete(`/api/local-models/${id}`, {
      params: { hard_delete }
    });
  }

  async validateLocalModel(id: number) {
    return this.client.post(`/api/local-models/${id}/validate`);
  }

  async validateLocalModelConfig(base_url: string, api_key?: string) {
    return this.client.post('/api/local-models/validate-config', null, {
      params: { base_url, api_key }
    });
  }

  // New Settings Endpoints
  async getGeneralSettings() {
    return this.client.get('/api/settings/general');
  }

  async updateGeneralSettings(data: {
    app_name?: string;
    auto_save?: boolean;
    auto_save_interval?: number;
    confirm_before_delete?: boolean;
    show_notifications?: boolean;
    check_updates?: boolean;
    telemetry?: boolean;
    log_level?: string;
  }) {
    return this.client.post('/api/settings/general', data);
  }

  async getLocalModelsSettings() {
    return this.client.get('/api/settings/local-models');
  }

  async updateLocalModelsSettings(data: {
    provider?: string;
    base_url?: string;
    model_name?: string;
    api_key?: string | null;
  }) {
    return this.client.post('/api/settings/local-models', data);
  }

  async getWorkspaceSettings() {
    return this.client.get('/api/settings/workspace');
  }

  async updateWorkspaceSettings(data: {
    workspace_path?: string;
    allow_read?: boolean;
    allow_write?: boolean;
    require_approval?: boolean;
    auto_detect_git?: boolean;
    backup_before_edit?: boolean;
  }) {
    return this.client.post('/api/settings/workspace', data);
  }

  async getModelDefaults() {
    return this.client.get('/api/settings/model-defaults');
  }

  async updateModelDefaults(data: {
    primary_model?: string;
    fallback_model?: string;
    embedding_model?: string;
    routing_strategy?: string;
    daily_token_limit?: number;
    monthly_token_limit?: number;
    alert_threshold?: number;
  }) {
    return this.client.post('/api/settings/model-defaults', data);
  }

  async getModelDefaultsSettings() {
    return this.client.get('/api/settings/model-defaults');
  }

  async updateModelDefaultsSettings(data: {
    primary_model?: string;
    fallback_models?: string[];
    temperature?: number;
    max_tokens?: number;
    top_p?: number;
    routing_strategy?: string;
    daily_token_limit?: number;
    monthly_token_limit?: number;
    alert_threshold?: number;
  }) {
    return this.client.post('/api/settings/model-defaults', data);
  }

  // Workflow History
  async getWorkflowHistory(workflowId: number, limit: number = 50, offset: number = 0) {
    return this.client.get(`/api/orchestration/workflows/${workflowId}/history`, {
      params: { limit, offset }
    });
  }

  // DeepAgents
  async createDeepAgent(data: {
    name: string;
    description?: string;
    category: string;
    config: any;
    base_template_id?: string;
  }) {
    return this.client.post('/api/deepagents/', data);
  }

  async listDeepAgents(config?: { category?: string; public_only?: boolean; signal?: AbortSignal }) {
    const { signal, ...params } = config || {};
    return this.client.get('/api/deepagents/', { params: Object.keys(params).length ? params : undefined, signal });
  }

  async getDeepAgent(id: number) {
    return this.client.get(`/api/deepagents/${id}`);
  }

  async updateDeepAgent(id: number, data: Partial<any>) {
    return this.client.put(`/api/deepagents/${id}`, data);
  }

  async deleteDeepAgent(id: number) {
    return this.client.delete(`/api/deepagents/${id}`);
  }

  // Generation
  async generateAgentConfig(data: {
    name: string;
    description: string;
    agent_type: string;
    category: string;
  }) {
    return this.client.post('/api/generation/generate', data);
  }

  async exportDeepAgent(id: number, data: {
    export_type: string;
    include_chat_ui: boolean;
    include_docker: boolean;
  }) {
    return this.client.post(`/api/deepagents/${id}/export`, data);
  }

  // Custom Tools
  async listCustomTools(config?: { project_id?: number; template_type?: string; tool_type?: string; signal?: AbortSignal }) {
    const { signal, ...params } = config || {};
    return this.client.get('/api/custom-tools', { params: Object.keys(params).length ? params : undefined, signal });
  }

  async getCustomTool(toolId: string, config?: { signal?: AbortSignal }) {
    return this.client.get(`/api/custom-tools/${toolId}`, config);
  }

  async createCustomTool(data: any) {
    return this.client.post('/api/custom-tools', data);
  }

  async updateCustomTool(toolId: string, data: any) {
    return this.client.put(`/api/custom-tools/${toolId}`, data);
  }

  async deleteCustomTool(toolId: string) {
    return this.client.delete(`/api/custom-tools/${toolId}`);
  }

  async testCustomTool(toolId: string, testInput: any) {
    return this.client.post(`/api/custom-tools/${toolId}/test`, { test_input: testInput });
  }

  async duplicateCustomTool(toolId: string, newToolId: string) {
    return this.client.post(`/api/custom-tools/${toolId}/duplicate`, { new_tool_id: newToolId });
  }

  async exportCustomTool(toolId: string) {
    return this.client.post(`/api/custom-tools/${toolId}/export`, {}, { responseType: 'blob' });
  }

  async importCustomTool(file: File) {
    const formData = new FormData();
    formData.append('file', file);
    return this.client.post('/api/custom-tools/import', formData);
  }

  async listToolTemplates() {
    return this.client.get('/api/custom-tools/templates/list');
  }

  async getToolTemplate(templateId: string) {
    return this.client.get(`/api/custom-tools/templates/${templateId}`);
  }

  // Background Tasks
  async getBackgroundTask(taskId: number) {
    return this.client.get(`/api/background-tasks/${taskId}`);
  }

  async listBackgroundTasks(params?: { status?: string; limit?: number; skip?: number }) {
    return this.client.get('/api/background-tasks', { params });
  }

  async retryBackgroundTask(taskId: number) {
    return this.client.post(`/api/background-tasks/${taskId}/retry`);
  }

  async cancelBackgroundTask(taskId: number) {
    return this.client.post(`/api/background-tasks/${taskId}/cancel`);
  }

  // Chat
  async startChatSession(agentId: number) {
    return this.client.post('/api/chat/start', { agent_id: agentId });
  }

  async endChatSession(sessionId: string) {
    return this.client.post(`/api/chat/${sessionId}/end`);
  }

  async getChatSessions() {
    return this.client.get('/api/chat/sessions');
  }

  async getChatHistory(sessionId: string) {
    return this.client.get(`/api/chat/${sessionId}/history`);
  }

  async getChatMetrics(sessionId: string) {
    return this.client.get(`/api/chat/${sessionId}/metrics`);
  }

  // Action Presets
  async listActionPresets(params?: {
    category?: string;
    action_type?: string;
    risk_level?: string;
    requires_runtime?: boolean;
  }) {
    return this.client.get('/api/action-presets/', { params });
  }

  async getActionPreset(presetId: string) {
    return this.client.get(`/api/action-presets/${presetId}`);
  }

  async listActionCategories() {
    return this.client.get('/api/action-presets/categories/list');
  }

  async getRecommendedActions(agentType: string) {
    return this.client.get(`/api/action-presets/recommended/${agentType}`);
  }

  // Directory Browser
  async browseDirectories(path?: string) {
    return this.client.get('/api/settings/browse-directories', {
      params: { path: path || '.' }
    });
  }

  // Workflow Output Path
  async validateOutputPath(workflowId: number, path: string) {
    return this.client.post(`/api/workflows/${workflowId}/validate-output-path`, { path });
  }

  // =============================================================================
  // File Viewer - Tree, Versions, and Diff APIs
  // =============================================================================

  /**
   * Get hierarchical file tree for folder navigation
   */
  async getFileTree(workflowId?: number) {
    const params = workflowId ? { workflow_id: workflowId } : undefined;
    return this.client.get('/api/workspace/files/tree', { params });
  }

  /**
   * Get files grouped by task for a workflow
   */
  async getWorkflowFilesGrouped(workflowId: number) {
    return this.client.get(`/api/workspace/workflows/${workflowId}/files/grouped`);
  }

  /**
   * Get version history for a file
   */
  async getFileVersions(fileId: number) {
    return this.client.get(`/api/workspace/files/${fileId}/versions`);
  }

  /**
   * Get diff between two file versions
   */
  async getFileDiff(fileId: number, v1: number, v2: number) {
    return this.client.get(`/api/workspace/files/${fileId}/diff`, {
      params: { v1, v2 }
    });
  }

  /**
   * Get content of a specific file version
   */
  async getFileVersionContent(fileId: number, versionNumber: number) {
    return this.client.get(`/api/workspace/files/${fileId}/version/${versionNumber}/content`);
  }

  /**
   * Get full file metadata including version count
   */
  async getFullFileMetadata(fileId: number) {
    return this.client.get(`/api/workspace/files/${fileId}/metadata/full`);
  }

  /**
   * Get file metadata by path
   */
  async getFileMetadataByPath(filePath: string) {
    return this.client.get('/api/workspace/files/by-path', {
      params: { file_path: filePath }
    });
  }

  /**
   * Update file metadata (tags, description, etc.)
   */
  async updateFileMetadata(fileId: number, data: {
    description?: string;
    content_type?: string;
    tags?: string[];
  }) {
    return this.client.patch(`/api/workspace/files/metadata/${fileId}`, data);
  }

  // =============================================================================
  // Workflow Schedules
  // =============================================================================

  /**
   * List schedules for a workflow
   */
  async listSchedules(workflowId: number) {
    return this.client.get(`/api/schedules/workflow/${workflowId}`);
  }

  /**
   * Get a specific schedule
   */
  async getSchedule(scheduleId: number) {
    return this.client.get(`/api/schedules/${scheduleId}`);
  }

  /**
   * Create a new schedule
   */
  async createSchedule(data: {
    workflow_id: number;
    name?: string;
    cron_expression: string;
    timezone?: string;
    enabled?: boolean;
    default_input_data?: Record<string, unknown>;
    max_concurrent_runs?: number;
    timeout_minutes?: number;
    idempotency_key_template?: string;
  }) {
    return this.client.post('/api/schedules/', data);
  }

  /**
   * Update an existing schedule
   */
  async updateSchedule(scheduleId: number, data: {
    name?: string;
    cron_expression?: string;
    timezone?: string;
    enabled?: boolean;
    default_input_data?: Record<string, unknown>;
    max_concurrent_runs?: number;
    timeout_minutes?: number;
    idempotency_key_template?: string;
  }) {
    return this.client.patch(`/api/schedules/${scheduleId}`, data);
  }

  /**
   * Delete a schedule
   */
  async deleteSchedule(scheduleId: number) {
    return this.client.delete(`/api/schedules/${scheduleId}`);
  }

  /**
   * Manually trigger a schedule
   */
  async triggerScheduleNow(scheduleId: number) {
    return this.client.post(`/api/schedules/${scheduleId}/trigger`);
  }

  /**
   * Get execution history for a schedule
   */
  async getScheduleHistory(scheduleId: number, params?: { limit?: number; skip?: number }) {
    return this.client.get(`/api/schedules/${scheduleId}/history`, { params });
  }

  /**
   * Validate a cron expression
   */
  async validateCronExpression(cronExpression: string, timezone?: string) {
    return this.client.post('/api/schedules/validate-cron', {
      cron_expression: cronExpression,
      timezone: timezone || 'UTC'
    });
  }

  // =============================================================================
  // Workflow Triggers (Webhooks, File Watch)
  // =============================================================================

  /**
   * List triggers for a workflow
   */
  async listTriggers(workflowId: number) {
    return this.client.get(`/api/triggers/workflow/${workflowId}`);
  }

  /**
   * Get a specific trigger
   */
  async getTrigger(triggerId: number) {
    return this.client.get(`/api/triggers/${triggerId}`);
  }

  /**
   * Create a new trigger
   */
  async createTrigger(data: {
    workflow_id: number;
    trigger_type: 'webhook' | 'file_watch';
    name?: string;
    enabled?: boolean;
    config: Record<string, unknown>;
  }) {
    return this.client.post('/api/triggers/', data);
  }

  /**
   * Update an existing trigger
   */
  async updateTrigger(triggerId: number, data: {
    name?: string;
    enabled?: boolean;
    config?: Record<string, unknown>;
  }) {
    return this.client.patch(`/api/triggers/${triggerId}`, data);
  }

  /**
   * Delete a trigger
   */
  async deleteTrigger(triggerId: number) {
    return this.client.delete(`/api/triggers/${triggerId}`);
  }

  /**
   * Test-fire a trigger
   */
  async testTrigger(triggerId: number, testPayload?: Record<string, unknown>) {
    return this.client.post(`/api/triggers/${triggerId}/test`, {
      test_payload: testPayload || {}
    });
  }

  /**
   * Regenerate webhook secret
   */
  async regenerateWebhookSecret(triggerId: number) {
    return this.client.post(`/api/triggers/${triggerId}/regenerate-secret`);
  }

  /**
   * Get trigger execution history
   */
  async getTriggerHistory(triggerId: number, params?: { limit?: number; skip?: number }) {
    return this.client.get(`/api/triggers/${triggerId}/history`, { params });
  }

  /**
   * Validate a file watch path
   */
  async validateWatchPath(path: string) {
    return this.client.post('/api/triggers/validate-path', null, {
      params: { path }
    });
  }
}

// Export singleton instance
export const apiClient = new APIClient();
export default apiClient;
