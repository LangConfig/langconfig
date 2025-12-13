/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState } from 'react';
import SettingsSection, { SettingsInput, SettingsSelect } from './SettingsSection';
import { useAvailableModels } from '@/hooks/useAvailableModels';

interface ModelDefaultsSettingsProps {
  settings: {
    primaryModel: string;
    fallbackModels: string[];
    temperature: number;
    maxTokens: number;
    topP: number;
    routingStrategy: string;
    dailyTokenLimit: number;
    monthlyTokenLimit: number;
    alertThreshold: number;
  };
  onSettingsChange: (settings: any) => void;
}

export default function ModelDefaultsSettings({
  settings,
  onSettingsChange
}: ModelDefaultsSettingsProps) {
  // Fetch available models (cloud + local)
  const { models, isLoading } = useAvailableModels({
    includeLocal: true,
    onlyValidated: true
  });

  // Convert to options format for select dropdown
  const availableModels = models.map(model => ({
    value: model.id,
    label: model.name
  }));
  const handleFallbackModelChange = (index: number, value: string) => {
    const newFallbackModels = [...settings.fallbackModels];
    newFallbackModels[index] = value;
    onSettingsChange({ ...settings, fallbackModels: newFallbackModels });
  };

  const addFallbackModel = () => {
    onSettingsChange({
      ...settings,
      fallbackModels: [...settings.fallbackModels, '']
    });
  };

  const removeFallbackModel = (index: number) => {
    const newFallbackModels = settings.fallbackModels.filter((_, i) => i !== index);
    onSettingsChange({ ...settings, fallbackModels: newFallbackModels });
  };

  return (
    <div>
      <SettingsSection
        title="Model Defaults"
        description="Configure default model selection and parameters. These settings apply to all agents unless overridden in individual agent configurations."
        icon="psychology"
      >
        {/* Primary Model */}
        <SettingsSelect
          label="Primary Model"
          value={settings.primaryModel}
          onChange={(value) => onSettingsChange({ ...settings, primaryModel: value })}
          options={availableModels}
          description="The default model used for all workflows and agents"
          required
        />

        {/* Fallback Models */}
        <div>
          <label className="text-sm font-medium mb-2 block" style={{ color: 'var(--color-text-primary)' }}>
            Fallback Models
          </label>
          <p className="text-xs mb-3" style={{ color: 'var(--color-text-muted)' }}>
            If the primary model fails or is unavailable, these models will be tried in order
          </p>

          <div className="space-y-2">
            {settings.fallbackModels.map((model, index) => (
              <div key={index} className="flex gap-2">
                <div className="flex-1">
                  <select
                    value={model}
                    onChange={(e) => handleFallbackModelChange(index, e.target.value)}
                    className="w-full px-3 py-2 bg-white dark:bg-background-dark border border-gray-300 dark:border-border-dark rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                    style={{ color: 'var(--color-text-primary)' }}
                  >
                    <option value="">Select fallback model {index + 1}</option>
                    {availableModels.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>
                <button
                  onClick={() => removeFallbackModel(index)}
                  className="px-3 py-2 text-red-600 dark:text-red-400 bg-white dark:bg-background-dark border border-gray-300 dark:border-border-dark rounded-lg hover:bg-red-50 dark:hover:bg-red-500/10 transition-colors"
                  title="Remove fallback model"
                >
                  <span className="material-symbols-outlined text-base">delete</span>
                </button>
              </div>
            ))}

            {settings.fallbackModels.length < 3 && (
              <button
                onClick={addFallbackModel}
                className="inline-flex items-center gap-2 px-3 py-2 text-sm font-medium bg-white dark:bg-background-dark border border-gray-300 dark:border-border-dark rounded-lg hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
                style={{ color: 'var(--color-text-primary)' }}
              >
                <span className="material-symbols-outlined text-base">add</span>
                Add Fallback Model
              </button>
            )}
          </div>
        </div>
      </SettingsSection>

      {/* Model Parameters */}
      <SettingsSection
        title="Default Parameters"
        description="Default generation parameters for all models. These can be overridden per agent."
        icon="tune"
      >
        {/* Temperature */}
        <div>
          <label className="text-sm font-medium mb-2 flex items-center justify-between" style={{ color: 'var(--color-text-primary)' }}>
            <span>Temperature</span>
            <span className="text-xs font-normal" style={{ color: 'var(--color-text-muted)' }}>
              {settings.temperature.toFixed(2)}
            </span>
          </label>
          <input
            type="range"
            min="0"
            max="2"
            step="0.1"
            value={settings.temperature}
            onChange={(e) => onSettingsChange({ ...settings, temperature: parseFloat(e.target.value) })}
            className="w-full h-2 bg-gray-200 dark:bg-border-dark rounded-lg appearance-none cursor-pointer"
          />
          <p className="text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
            Controls randomness. Lower = more focused, higher = more creative. Range: 0.0-2.0
          </p>
        </div>

        {/* Max Tokens */}
        <SettingsInput
          label="Max Tokens"
          type="number"
          value={settings.maxTokens.toString()}
          onChange={(value) => onSettingsChange({ ...settings, maxTokens: parseInt(value) || 4096 })}
          description="Maximum number of tokens to generate in responses. Common values: 1024, 2048, 4096, 8192"
        />

        {/* Top P */}
        <div>
          <label className="text-sm font-medium mb-2 flex items-center justify-between" style={{ color: 'var(--color-text-primary)' }}>
            <span>Top P (Nucleus Sampling)</span>
            <span className="text-xs font-normal" style={{ color: 'var(--color-text-muted)' }}>
              {settings.topP.toFixed(2)}
            </span>
          </label>
          <input
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={settings.topP}
            onChange={(e) => onSettingsChange({ ...settings, topP: parseFloat(e.target.value) })}
            className="w-full h-2 bg-gray-200 dark:bg-border-dark rounded-lg appearance-none cursor-pointer"
          />
          <p className="text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
            Alternative to temperature. Consider only tokens with top_p probability mass. Range: 0.0-1.0
          </p>
        </div>
      </SettingsSection>

      {/* Model Routing */}
      <SettingsSection
        title="Model Routing"
        description="Configure intelligent model selection based on cost, speed, or quality preferences."
        icon="alt_route"
      >
        <SettingsSelect
          label="Routing Strategy"
          value={settings.routingStrategy}
          onChange={(value) => onSettingsChange({ ...settings, routingStrategy: value })}
          options={[
            { value: 'balanced', label: 'Balanced (Cost, Speed, Quality)' },
            { value: 'cost', label: 'Cost Optimized (Cheapest models first)' },
            { value: 'speed', label: 'Speed Optimized (Fastest models first)' },
            { value: 'quality', label: 'Quality Optimized (Best models first)' },
            { value: 'none', label: 'No Routing (Use primary model only)' }
          ]}
          description="Determines how fallback models are selected when the primary model is unavailable"
        />
      </SettingsSection>

      {/* Token Budget */}
      <SettingsSection
        title="Token Budget & Limits"
        description="Set usage limits to control costs. Leave at 0 to disable limits."
        icon="account_balance_wallet"
      >
        <div className="grid grid-cols-2 gap-4">
          <SettingsInput
            label="Daily Token Limit"
            type="number"
            value={settings.dailyTokenLimit.toString()}
            onChange={(value) => onSettingsChange({ ...settings, dailyTokenLimit: parseInt(value) || 0 })}
            placeholder="100000"
            description="Maximum tokens per day (0 = unlimited)"
          />

          <SettingsInput
            label="Monthly Token Limit"
            type="number"
            value={settings.monthlyTokenLimit.toString()}
            onChange={(value) => onSettingsChange({ ...settings, monthlyTokenLimit: parseInt(value) || 0 })}
            placeholder="3000000"
            description="Maximum tokens per month (0 = unlimited)"
          />
        </div>

        <SettingsInput
          label="Alert Threshold (%)"
          type="number"
          value={settings.alertThreshold.toString()}
          onChange={(value) => onSettingsChange({ ...settings, alertThreshold: parseInt(value) || 80 })}
          placeholder="80"
          description="Show warning when you've used this percentage of your limit"
        />
      </SettingsSection>
    </div>
  );
}
