/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useEffect, useCallback } from 'react';
import { apiClient } from '@/lib/api-client';
import { getModelDisplayName, getModelProvider } from '@/lib/modelDisplayNames';
import type { LocalModel } from '@/types/api';

/**
 * Hook for fetching available models (cloud + local)
 *
 * This hook combines cloud models from the settings API with validated local models
 * from the local-models API, providing a unified list for model selection dropdowns.
 *
 * Usage:
 * ```typescript
 * const { models, isLoading, error, refetch } = useAvailableModels({
 *   includeLocal: true,
 *   onlyValidated: true,
 *   refreshInterval: 30000 // Auto-refresh every 30s
 * });
 * ```
 */

export interface ModelOption {
  id: string;                    // Model identifier (e.g., "gpt-4", "local-ollama-llama3")
  name: string;                  // Display name (e.g., "GPT-4", "Llama 3.2 (Ollama - Local)")
  provider: string;              // Provider name (e.g., "openai", "anthropic", "ollama")
  type: 'cloud' | 'local';       // Model type
  is_validated?: boolean;        // Only for local models
  capabilities?: {
    streaming?: boolean;
    tools?: boolean;
    max_context?: number;
    [key: string]: any;
  };
}

export interface UseAvailableModelsOptions {
  includeLocal?: boolean;         // Whether to include local models (default: true)
  onlyValidated?: boolean;        // Only include validated local models (default: true)
  refreshInterval?: number;       // Auto-refresh interval in ms (default: disabled)
}

export interface UseAvailableModelsResult {
  models: ModelOption[];          // Combined list of cloud + local models
  cloudModels: ModelOption[];     // Cloud models only
  localModels: ModelOption[];     // Local models only
  isLoading: boolean;
  error: string | null;
  refetch: () => Promise<void>;   // Manual refresh function
}

export function useAvailableModels(
  options: UseAvailableModelsOptions = {}
): UseAvailableModelsResult {
  const {
    includeLocal = true,
    onlyValidated = true,
    refreshInterval
  } = options;

  const [models, setModels] = useState<ModelOption[]>([]);
  const [cloudModels, setCloudModels] = useState<ModelOption[]>([]);
  const [localModels, setLocalModels] = useState<ModelOption[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchModels = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      // Fetch cloud models from settings endpoint
      const settingsResponse = await apiClient.listAvailableModels();
      const availableModels = settingsResponse.data.models || [];
      const localModelsList = settingsResponse.data.local_models || [];

      // Convert cloud models to ModelOption format using the shared
      // display-name module (single source of truth for model labels)
      const cloudModelOptions: ModelOption[] = availableModels
        .filter((modelId: string) => !modelId.startsWith('local-'))
        .map((modelId: string) => ({
          id: modelId,
          name: getModelDisplayName(modelId) || modelId,
          provider: getModelProvider(modelId),
          type: 'cloud' as const
        }));

      setCloudModels(cloudModelOptions);

      // Fetch local models if enabled
      let localModelOptions: ModelOption[] = [];
      if (includeLocal) {
        // Use local models already included in settings response
        localModelOptions = localModelsList
          .filter((model: any) => !onlyValidated || model.is_validated)
          .map((model: any) => ({
            id: model.name,  // Already has "local-" prefix from backend
            name: `${model.display_name} (${model.provider.charAt(0).toUpperCase() + model.provider.slice(1)} - Local)`,
            provider: model.provider,
            type: 'local' as const,
            is_validated: model.is_validated,
            capabilities: model.capabilities
          }));
      }

      setLocalModels(localModelOptions);

      // Combine cloud and local models
      const allModels = [...cloudModelOptions, ...localModelOptions];
      setModels(allModels);

      setIsLoading(false);
    } catch (err) {
      console.error('Failed to fetch available models:', err);
      const errorMsg = err instanceof Error ? err.message : 'Failed to fetch models';
      setError(errorMsg);
      setIsLoading(false);
    }
  }, [includeLocal, onlyValidated]);

  // Initial fetch and auto-refresh
  useEffect(() => {
    fetchModels();

    // Set up auto-refresh if interval provided
    if (refreshInterval && refreshInterval > 0) {
      const intervalId = setInterval(() => {
        fetchModels();
      }, refreshInterval);

      return () => clearInterval(intervalId);
    }
  }, [fetchModels, refreshInterval]);

  return {
    models,
    cloudModels,
    localModels,
    isLoading,
    error,
    refetch: fetchModels
  };
}
