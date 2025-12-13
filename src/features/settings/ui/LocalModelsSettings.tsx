/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useEffect } from 'react';
import { apiClient } from '@/lib/api-client';
import type { LocalModel, LocalModelCreate, LocalModelUpdate, ValidationResult } from '@/types/api';
import SettingsSection, { SettingsInput, SettingsSelect } from './SettingsSection';

const providerPresets = {
  ollama: {
    name: 'Ollama',
    baseUrl: 'http://localhost:11434/v1',
    defaultModel: 'llama3.2:latest',
    requiresApiKey: false,
    port: 11434
  },
  lmstudio: {
    name: 'LM Studio',
    baseUrl: 'http://localhost:1234/v1',
    defaultModel: 'local-model',
    requiresApiKey: false,
    port: 1234
  },
  vllm: {
    name: 'vLLM',
    baseUrl: 'http://localhost:8000/v1',
    defaultModel: 'facebook/opt-125m',
    requiresApiKey: false,
    port: 8000
  },
  litellm: {
    name: 'LiteLLM Proxy',
    baseUrl: 'http://localhost:4000/v1',
    defaultModel: 'gpt-3.5-turbo',
    requiresApiKey: false,
    port: 4000
  },
  custom: {
    name: 'Custom OpenAI-Compatible',
    baseUrl: '',
    defaultModel: '',
    requiresApiKey: true,
    port: null
  }
};

interface LocalModelsSettingsProps {
  // No props needed - component manages its own state
}

export default function LocalModelsSettings(props: LocalModelsSettingsProps) {
  const [models, setModels] = useState<LocalModel[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingModel, setEditingModel] = useState<LocalModel | null>(null);
  const [validatingModelId, setValidatingModelId] = useState<number | null>(null);

  // Fetch local models on mount
  useEffect(() => {
    fetchModels();
  }, []);

  const fetchModels = async () => {
    try {
      setIsLoading(true);
      const response = await apiClient.listLocalModels({ only_active: true });
      setModels(response.data || []);
    } catch (error) {
      console.error('Failed to fetch local models:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleAddModel = () => {
    setEditingModel(null);
    setIsModalOpen(true);
  };

  const handleEditModel = (model: LocalModel) => {
    setEditingModel(model);
    setIsModalOpen(true);
  };

  const handleDeleteModel = async (model: LocalModel) => {
    if (!confirm(`Are you sure you want to delete "${model.display_name}"?`)) {
      return;
    }

    try {
      await apiClient.deleteLocalModel(model.id, false);
      await fetchModels();
    } catch (error) {
      console.error('Failed to delete model:', error);
      alert('Failed to delete model. Please try again.');
    }
  };

  const handleValidateModel = async (model: LocalModel) => {
    setValidatingModelId(model.id);
    try {
      const response = await apiClient.validateLocalModel(model.id);
      const result: ValidationResult = response.data;

      if (result.success) {
        alert(`✓ ${result.message}`);
      } else {
        alert(`✗ ${result.message}`);
      }

      // Refresh to get updated validation status
      await fetchModels();
    } catch (error: any) {
      console.error('Validation failed:', error);
      alert(`Failed to validate: ${error.message || 'Unknown error'}`);
    } finally {
      setValidatingModelId(null);
    }
  };

  const getStatusBadge = (model: LocalModel) => {
    if (model.is_validated) {
      const lastValidated = model.last_validated_at
        ? new Date(model.last_validated_at)
        : null;

      const timeAgo = lastValidated
        ? getTimeAgo(lastValidated)
        : '';

      return (
        <span className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded-full bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300">
          <span className="w-2 h-2 rounded-full bg-green-500"></span>
          Connected {timeAgo && `(${timeAgo})`}
        </span>
      );
    } else {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded-full bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300">
          <span className="w-2 h-2 rounded-full bg-red-500"></span>
          Not Validated
        </span>
      );
    }
  };

  const getTimeAgo = (date: Date): string => {
    const now = new Date();
    const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);

    if (seconds < 60) return 'just now';
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
  };

  return (
    <div>
      <SettingsSection
        title="Local Models"
        description="Connect to local LLM providers like Ollama, LM Studio, or vLLM. Configure multiple models and use them in your workflows."
        icon="computer"
      >
        {/* Add New Model Button */}
        <div className="mb-4">
          <button
            onClick={handleAddModel}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:opacity-90 transition-opacity"
          >
            <span className="material-symbols-outlined text-base">add</span>
            Add Local Model
          </button>
        </div>

        {/* Models List */}
        {isLoading ? (
          <div className="text-center py-8" style={{ color: 'var(--color-text-muted)' }}>
            Loading models...
          </div>
        ) : models.length === 0 ? (
          <div className="text-center py-8 space-y-2">
            <p style={{ color: 'var(--color-text-muted)' }}>
              No local models configured yet.
            </p>
            <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
              Click "Add Local Model" above to get started.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {models.map((model) => (
              <div
                key={model.id}
                className="border border-gray-200 dark:border-border-dark rounded-lg p-4 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
              >
                {/* Header Row */}
                <div className="flex items-start justify-between mb-2">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="text-base font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                        {model.display_name}
                      </h3>
                      <span className="text-xs px-2 py-0.5 rounded bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300">
                        {model.provider.charAt(0).toUpperCase() + model.provider.slice(1)}
                      </span>
                    </div>
                    <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
                      {model.model_name} • {model.base_url.replace('/v1', '')}
                    </p>
                  </div>

                  {/* Status Badge */}
                  <div>
                    {getStatusBadge(model)}
                  </div>
                </div>

                {/* Description */}
                {model.description && (
                  <p className="text-sm mb-3" style={{ color: 'var(--color-text-muted)' }}>
                    {model.description}
                  </p>
                )}

                {/* Validation Error */}
                {!model.is_validated && model.validation_error && (
                  <p className="text-xs text-red-600 dark:text-red-400 mb-3">
                    Error: {model.validation_error}
                  </p>
                )}

                {/* Tags */}
                {model.tags && model.tags.length > 0 && (
                  <div className="flex flex-wrap gap-1 mb-3">
                    {model.tags.map((tag, idx) => (
                      <span
                        key={idx}
                        className="text-xs px-2 py-0.5 rounded bg-gray-200 dark:bg-gray-700"
                        style={{ color: 'var(--color-text-muted)' }}
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                )}

                {/* Action Buttons */}
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleValidateModel(model)}
                    disabled={validatingModelId === model.id}
                    className="inline-flex items-center gap-1 px-3 py-1.5 text-sm font-medium text-primary border border-primary rounded-lg hover:bg-primary hover:text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    <span className="material-symbols-outlined text-base">
                      {validatingModelId === model.id ? 'refresh' : 'link'}
                    </span>
                    {validatingModelId === model.id ? 'Testing...' : 'Test Connection'}
                  </button>

                  <button
                    onClick={() => handleEditModel(model)}
                    className="inline-flex items-center gap-1 px-3 py-1.5 text-sm font-medium border border-gray-300 dark:border-border-dark rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                    style={{ color: 'var(--color-text-primary)' }}
                  >
                    <span className="material-symbols-outlined text-base">edit</span>
                    Edit
                  </button>

                  <button
                    onClick={() => handleDeleteModel(model)}
                    className="inline-flex items-center gap-1 px-3 py-1.5 text-sm font-medium text-red-600 dark:text-red-400 border border-red-300 dark:border-red-700 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                  >
                    <span className="material-symbols-outlined text-base">delete</span>
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </SettingsSection>

      {/* Setup Instructions */}
      <SettingsSection
        title="Setup Instructions"
        icon="help"
      >
        <div className="space-y-4 text-sm" style={{ color: 'var(--color-text-muted)' }}>
          <div>
            <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
              Ollama Setup:
            </h4>
            <ol className="list-decimal list-inside space-y-1 ml-2">
              <li>Install Ollama from <a href="https://ollama.ai" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">ollama.ai</a></li>
              <li>Run: <code className="px-2 py-1 bg-gray-100 dark:bg-background-dark rounded">ollama pull llama3.2</code></li>
              <li>Ollama will start automatically on <code className="px-2 py-1 bg-gray-100 dark:bg-background-dark rounded">http://localhost:11434</code></li>
              <li>Use model format: <code className="px-2 py-1 bg-gray-100 dark:bg-background-dark rounded">llama3.2:latest</code></li>
            </ol>
          </div>

          <div>
            <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
              LM Studio Setup:
            </h4>
            <ol className="list-decimal list-inside space-y-1 ml-2">
              <li>Install LM Studio from <a href="https://lmstudio.ai" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">lmstudio.ai</a></li>
              <li>Download a model from the catalog</li>
              <li>Click "Start Server" in the Local Server tab</li>
              <li>Server runs on <code className="px-2 py-1 bg-gray-100 dark:bg-background-dark rounded">http://localhost:1234</code></li>
            </ol>
          </div>

          <div>
            <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
              Important Notes:
            </h4>
            <ul className="list-disc list-inside space-y-1 ml-2">
              <li>Local models run on your hardware - GPU recommended for good performance</li>
              <li>No API keys needed - everything runs locally</li>
              <li>Your data never leaves your machine</li>
              <li>Models must be validated before they appear in agent dropdowns</li>
              <li>Some features like function calling may not be supported by all models</li>
            </ul>
          </div>
        </div>
      </SettingsSection>

      {/* Add/Edit Modal */}
      {isModalOpen && (
        <LocalModelModal
          model={editingModel}
          onClose={() => setIsModalOpen(false)}
          onSave={async () => {
            await fetchModels();
            setIsModalOpen(false);
          }}
        />
      )}
    </div>
  );
}

// Modal Component for Add/Edit
interface LocalModelModalProps {
  model: LocalModel | null;
  onClose: () => void;
  onSave: () => void;
}

function LocalModelModal({ model, onClose, onSave }: LocalModelModalProps) {
  const isEditing = !!model;

  const [formData, setFormData] = useState({
    name: model?.name || '',
    display_name: model?.display_name || '',
    description: model?.description || '',
    provider: model?.provider || 'ollama',
    base_url: model?.base_url || 'http://localhost:11434/v1',
    model_name: model?.model_name || 'llama3.2:latest',
    api_key: '',  // Never pre-fill API keys
    tags: model?.tags?.join(', ') || ''
  });

  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleProviderChange = (provider: string) => {
    const preset = providerPresets[provider as keyof typeof providerPresets];
    setFormData({
      ...formData,
      provider,
      base_url: preset.baseUrl,
      model_name: preset.defaultModel
    });
  };

  const handleSave = async () => {
    // Validation
    if (!formData.display_name.trim()) {
      setError('Display name is required');
      return;
    }
    if (!isEditing && !formData.name.trim()) {
      setError('Name is required');
      return;
    }
    if (!formData.base_url.trim() || !formData.base_url.endsWith('/v1')) {
      setError('Base URL must end with /v1');
      return;
    }
    if (!formData.model_name.trim()) {
      setError('Model name is required');
      return;
    }

    setIsSaving(true);
    setError(null);

    try {
      if (isEditing && model) {
        // Update existing model
        const updateData: LocalModelUpdate = {
          display_name: formData.display_name,
          description: formData.description || undefined,
          base_url: formData.base_url,
          model_name: formData.model_name,
          tags: formData.tags.split(',').map(t => t.trim()).filter(Boolean)
        };

        if (formData.api_key) {
          updateData.api_key = formData.api_key;
        }

        await apiClient.updateLocalModel(model.id, updateData);
      } else {
        // Create new model
        const createData: LocalModelCreate = {
          name: formData.name,
          display_name: formData.display_name,
          description: formData.description || undefined,
          provider: formData.provider,
          base_url: formData.base_url,
          model_name: formData.model_name,
          api_key: formData.api_key || undefined,
          tags: formData.tags.split(',').map(t => t.trim()).filter(Boolean)
        };

        await apiClient.createLocalModel(createData);
      }

      onSave();
    } catch (error: any) {
      console.error('Failed to save model:', error);
      setError(error.response?.data?.detail || error.message || 'Failed to save model');
    } finally {
      setIsSaving(false);
    }
  };

  const selectedPreset = providerPresets[formData.provider as keyof typeof providerPresets];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="bg-white rounded-lg shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header with Primary Color */}
        <div
          className="px-6 py-4 flex items-center justify-between"
          style={{ backgroundColor: 'var(--color-primary)' }}
        >
          <h2 className="text-xl font-semibold text-white">
            {isEditing ? 'Edit Local Model' : 'Add Local Model'}
          </h2>
          <button
            onClick={onClose}
            className="text-white/90 hover:text-white transition-colors"
          >
            <span className="material-symbols-outlined">close</span>
          </button>
        </div>

        {/* Content Area - White Background with Scroll */}
        <div className="flex-1 overflow-y-auto px-6 py-6 bg-white">
          <div className="space-y-4">
            {/* Name (only for new models) */}
            {!isEditing && (
              <SettingsInput
                label="Name (Identifier)"
                value={formData.name}
                onChange={(value) => setFormData({ ...formData, name: value.toLowerCase().replace(/[^a-z0-9-_]/g, '-') })}
                placeholder="ollama-llama3"
                description="Unique identifier for this model (lowercase, hyphens allowed)"
                required
              />
            )}

            {/* Display Name */}
            <SettingsInput
              label="Display Name"
              value={formData.display_name}
              onChange={(value) => setFormData({ ...formData, display_name: value })}
              placeholder="My Llama 3.2"
              description="Human-readable name shown in dropdowns"
              required
            />

            {/* Description */}
            <SettingsInput
              label="Description (Optional)"
              value={formData.description}
              onChange={(value) => setFormData({ ...formData, description: value })}
              placeholder="My local Llama model for testing"
            />

            {/* Provider */}
            <SettingsSelect
              label="Provider"
              value={formData.provider}
              onChange={handleProviderChange}
              options={Object.entries(providerPresets).map(([key, preset]) => ({
                value: key,
                label: preset.name
              }))}
              description="Select your local model provider"
              disabled={isEditing}  // Can't change provider on edit
            />

            {/* Base URL */}
            <SettingsInput
              label="Base URL"
              type="url"
              value={formData.base_url}
              onChange={(value) => setFormData({ ...formData, base_url: value })}
              placeholder="http://localhost:11434/v1"
              description="Must end with /v1 for OpenAI compatibility"
              required
            />

            {/* Model Name */}
            <SettingsInput
              label="Model Name"
              value={formData.model_name}
              onChange={(value) => setFormData({ ...formData, model_name: value })}
              placeholder="llama3.2:latest"
              description="Provider's model identifier"
              required
            />

            {/* API Key */}
            {selectedPreset?.requiresApiKey !== false && (
              <SettingsInput
                label="API Key (Optional)"
                type="password"
                value={formData.api_key}
                onChange={(value) => setFormData({ ...formData, api_key: value })}
                placeholder={isEditing ? "Leave blank to keep existing" : ""}
                description={isEditing ? "Leave blank to keep existing API key" : "Optional API key if your server requires authentication"}
              />
            )}

            {/* Tags */}
            <SettingsInput
              label="Tags (Optional)"
              value={formData.tags}
              onChange={(value) => setFormData({ ...formData, tags: value })}
              placeholder="development, testing, fast"
              description="Comma-separated tags for organization"
            />

            {/* Error Message */}
            {error && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
                <p className="text-sm text-red-600">{error}</p>
              </div>
            )}
          </div>
        </div>

        {/* Footer with Action Buttons - White Background */}
        <div className="px-6 py-4 bg-white border-t border-gray-200 flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <button
              onClick={handleSave}
              disabled={isSaving}
              className="flex-1 px-4 py-2.5 text-sm font-medium text-white rounded-lg hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-opacity"
              style={{ backgroundColor: 'var(--color-primary)' }}
            >
              {isSaving ? 'Saving...' : isEditing ? 'Update Model' : 'Create Model'}
            </button>
            <button
              onClick={onClose}
              disabled={isSaving}
              className="px-4 py-2.5 text-sm font-medium border border-gray-300 rounded-lg hover:bg-gray-100 transition-colors"
              style={{ color: 'var(--color-text-primary)' }}
            >
              Cancel
            </button>
          </div>

          {/* Hint */}
          <p className="text-xs text-center" style={{ color: 'var(--color-text-muted)' }}>
            After saving, click "Test Connection" to validate the model before using it in workflows.
          </p>
        </div>
      </div>
    </div>
  );
}
