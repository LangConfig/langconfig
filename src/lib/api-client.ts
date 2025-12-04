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
  async listWorkflows(params?: { project_id?: number; skip?: number; limit?: number }) {
    return this.client.get('/api/workflows/', { params });
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
  async listProjects(params?: { skip?: number; limit?: number; status?: string }) {
    return this.client.get('/api/projects/', { params });
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

  async listDocuments(params: {
    project_id: number;
    skip?: number;
    limit?: number;
    status?: string;
  }) {
    return this.client.get('/api/rag/documents', { params });
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

  async listDeepAgents(params?: { category?: string; public_only?: boolean }) {
    return this.client.get('/api/deepagents/', { params });
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
  async listCustomTools(params?: { project_id?: number; template_type?: string; tool_type?: string }) {
    return this.client.get('/api/custom-tools', { params });
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
}

// Export singleton instance
export const apiClient = new APIClient();
export default new APIClient();
