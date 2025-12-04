/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * API Configuration
 *
 * Centralized API configuration using environment variables.
 * Prevents hardcoded URLs and enables different environments (dev, staging, prod).
 */

// Get API base URL from environment variable, fallback to localhost for development
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8765';

/**
 * API Endpoints
 * All backend API endpoints organized by domain
 */
export const API_ENDPOINTS = {
  // Agent endpoints
  agents: {
    templates: `${API_BASE_URL}/api/agents/templates`,
    custom: `${API_BASE_URL}/api/deepagents`,
    create: `${API_BASE_URL}/api/deepagents`,
    update: (id: string) => `${API_BASE_URL}/api/deepagents/${id}`,
    delete: (id: string) => `${API_BASE_URL}/api/deepagents/${id}`,
  },

  // Workflow endpoints
  workflows: {
    list: `${API_BASE_URL}/api/workflows`,
    detail: (id: number) => `${API_BASE_URL}/api/workflows/${id}`,
    create: `${API_BASE_URL}/api/workflows`,
    update: (id: number) => `${API_BASE_URL}/api/workflows/${id}`,
    delete: (id: number) => `${API_BASE_URL}/api/workflows/${id}`,
    duplicate: (id: number) => `${API_BASE_URL}/api/workflows/${id}/duplicate`,
    rename: (id: number) => `${API_BASE_URL}/api/workflows/${id}/rename`,
    metrics: {
      cost: (id: number, days: number = 30) =>
        `${API_BASE_URL}/api/workflows/${id}/metrics/cost?days=${days}`,
      runs: (id: number) => `${API_BASE_URL}/api/workflows/${id}/metrics/runs`,
    },
  },

  // Project endpoints
  projects: {
    list: `${API_BASE_URL}/api/projects`,
    detail: (id: number) => `${API_BASE_URL}/api/projects/${id}`,
    create: `${API_BASE_URL}/api/projects`,
    update: (id: number) => `${API_BASE_URL}/api/projects/${id}`,
    delete: (id: number) => `${API_BASE_URL}/api/projects/${id}`,
  },

  // Custom tool endpoints
  tools: {
    list: `${API_BASE_URL}/api/custom-tools`,
    detail: (id: string) => `${API_BASE_URL}/api/custom-tools/${id}`,
    create: `${API_BASE_URL}/api/custom-tools`,
    update: (id: string) => `${API_BASE_URL}/api/custom-tools/${id}`,
    delete: (id: string) => `${API_BASE_URL}/api/custom-tools/${id}`,
    duplicate: (id: string, newId: string) =>
      `${API_BASE_URL}/api/custom-tools/${id}/duplicate?new_tool_id=${newId}`,
    test: (id: string) => `${API_BASE_URL}/api/custom-tools/${id}/test`,
  },
} as const;



/**
 * Check if API is available
 * Useful for health checks and error recovery
 */
export async function checkApiHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE_URL}/health`, {
      method: 'GET',
      signal: AbortSignal.timeout(5000), // 5 second timeout
    });
    return response.ok;
  } catch {
    return false;
  }
}
