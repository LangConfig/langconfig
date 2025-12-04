/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useEffect } from 'react';
import { useAvailableModels } from '@/hooks/useAvailableModels';

/**
 * ModelSelector Component
 *
 * A reusable dropdown component for selecting LLM models (cloud + local).
 * Automatically fetches and displays both cloud models and validated local models,
 * organized into optgroups for easy navigation.
 *
 * Usage:
 * ```tsx
 * <ModelSelector
 *   value={config.model}
 *   onChange={(modelId) => updateConfig('model', modelId)}
 *   label="Primary Model"
 *   description="The main model for this agent"
 *   includeLocal={true}
 *   required={true}
 * />
 * ```
 */

export interface ModelSelectorProps {
  value: string;
  onChange: (modelId: string) => void;
  label?: string;
  description?: string;
  placeholder?: string;
  includeLocal?: boolean;
  onlyValidated?: boolean;
  required?: boolean;
  disabled?: boolean;
  showProviderLabels?: boolean;
  autoRefresh?: boolean;  // Auto-refresh model list every 30s
  className?: string;
}

export default function ModelSelector({
  value,
  onChange,
  label = 'Model',
  description,
  placeholder = 'Select a model',
  includeLocal = true,
  onlyValidated = true,
  required = false,
  disabled = false,
  showProviderLabels = true,
  autoRefresh = false,
  className = ''
}: ModelSelectorProps) {
  const { models, cloudModels, localModels, isLoading, error } = useAvailableModels({
    includeLocal,
    onlyValidated,
    refreshInterval: autoRefresh ? 30000 : undefined
  });

  // Log error if models fail to load
  useEffect(() => {
    if (error) {
      console.error('ModelSelector: Failed to load models:', error);
    }
  }, [error]);

  return (
    <div className={`flex flex-col gap-2 ${className}`}>
      {/* Label */}
      {label && (
        <label className="text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>
          {label}
          {required && <span className="text-red-500 ml-1">*</span>}
        </label>
      )}

      {/* Select Dropdown */}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled || isLoading}
        onMouseDown={(e) => e.stopPropagation()}
        onWheel={(e) => e.stopPropagation()}
        className="px-3 py-2 border border-gray-300 dark:border-border-dark rounded-lg focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50 disabled:cursor-not-allowed"
        style={{
          backgroundColor: 'var(--color-input-background)',
          color: 'var(--color-text-primary)'
        }}
      >
        {/* Placeholder */}
        <option value="" disabled>
          {isLoading ? 'Loading models...' : placeholder}
        </option>

        {/* Cloud Models Group */}
        {cloudModels.length > 0 && (
          <optgroup label="Cloud Models">
            {cloudModels.map((model) => (
              <option key={model.id} value={model.id}>
                {showProviderLabels
                  ? `${model.name} (${model.provider.charAt(0).toUpperCase() + model.provider.slice(1)})`
                  : model.name}
              </option>
            ))}
          </optgroup>
        )}

        {/* Local Models Group */}
        {includeLocal && localModels.length > 0 && (
          <optgroup label="Local Models">
            {localModels.map((model) => (
              <option key={model.id} value={model.id}>
                {model.name}
                {model.is_validated === false && ' [Not Validated]'}
              </option>
            ))}
          </optgroup>
        )}

        {/* No models available */}
        {!isLoading && models.length === 0 && (
          <option value="" disabled>
            No models available
          </option>
        )}
      </select>

      {/* Description */}
      {description && (
        <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
          {description}
        </p>
      )}

      {/* Error message */}
      {error && (
        <p className="text-xs text-red-500">
          Failed to load models. Please check your connection.
        </p>
      )}

      {/* No local models hint */}
      {includeLocal && !isLoading && localModels.length === 0 && cloudModels.length > 0 && (
        <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
          No local models configured. Visit Settings → Local Models to add one.
        </p>
      )}
    </div>
  );
}

/**
 * Minimal ModelSelector variant for inline use
 * Just the dropdown without label/description
 */
export function ModelSelectorInline({
  value,
  onChange,
  includeLocal = true,
  onlyValidated = true,
  disabled = false,
  className = ''
}: Pick<ModelSelectorProps, 'value' | 'onChange' | 'includeLocal' | 'onlyValidated' | 'disabled' | 'className'>) {
  const { models, cloudModels, localModels, isLoading } = useAvailableModels({
    includeLocal,
    onlyValidated
  });

  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled || isLoading}
      onMouseDown={(e) => e.stopPropagation()}
      onWheel={(e) => e.stopPropagation()}
      className={`w-full px-3 py-2 border border-gray-300 dark:border-border-dark rounded-lg focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50 ${className}`}
      style={{
        backgroundColor: 'var(--color-input-background)',
        color: 'var(--color-text-primary)'
      }}
    >
      <option value="">{isLoading ? 'Loading...' : 'Select model'}</option>

      {cloudModels.length > 0 && (
        <optgroup label="Cloud Models">
          {cloudModels.map((model) => (
            <option key={model.id} value={model.id}>
              {model.name}
            </option>
          ))}
        </optgroup>
      )}

      {includeLocal && localModels.length > 0 && (
        <optgroup label="Local Models">
          {localModels.map((model) => (
            <option key={model.id} value={model.id}>
              {model.name}
            </option>
          ))}
        </optgroup>
      )}
    </select>
  );
}
