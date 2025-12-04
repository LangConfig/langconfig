/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import apiClient from '../lib/api-client';
import { themes, applyTheme, loadTheme, type ThemeName } from '../lib/themes';
import SettingsLayout, { SettingsCategory } from "../features/settings/components/SettingsLayout";
import LocalModelsSettings from "../features/settings/components/LocalModelsSettings";
import LocalWorkspaceSettings from "../features/settings/components/LocalWorkspaceSettings";
import ModelDefaultsSettings from '../features/settings/components/ModelDefaultsSettings';
import SettingsSection, { SettingsInput } from '../features/settings/components/SettingsSection';

export default function SettingsView() {
  const [currentCategory, setCurrentCategory] = useState<SettingsCategory>('general');
  const [isLoading, setIsLoading] = useState(true);
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // API Keys state
  const [apiKeys, setApiKeys] = useState({
    anthropic: '',
    openai: '',
    google: '',
  });

  // Theme state
  const [currentTheme, setCurrentTheme] = useState<ThemeName>('dark');

  // Type definitions for settings
  interface LocalModelsSettings {
    provider: string;
    baseUrl: string;
    modelName: string;
    apiKey: string;
  }

  interface WorkspaceSettings {
    workspacePath: string;
    allowRead: boolean;
    allowWrite: boolean;
    requireApproval: boolean;
    autoDetectGit: boolean;
    backupBeforeEdit: boolean;
  }

  interface ModelDefaultsSettings {
    primaryModel: string;
    fallbackModels: string[];
    temperature: number;
    maxTokens: number;
    topP: number;
    routingStrategy: string;
    dailyTokenLimit: number;
    monthlyTokenLimit: number;
    alertThreshold: number;
  }

  interface GeneralSettings {
    appName: string;
    storagePath: string;
    autoSave: boolean;
    autoSaveInterval: number;
    confirmBeforeDelete: boolean;
    showNotifications: boolean;
    checkUpdates: boolean;
    telemetry: boolean;
    logLevel: string;
  }

  interface RagSettings {
    embeddingModel: string;
    chunkSize: number;
    chunkOverlap: number;
  }

  // Local Models state - start with null, load from backend
  const [localModelsSettings, setLocalModelsSettings] = useState<LocalModelsSettings | null>(null);

  // Local Workspace state - start with null, load from backend
  const [workspaceSettings, setWorkspaceSettings] = useState<WorkspaceSettings | null>(null);

  // Model Defaults state - start with null, load from backend
  const [modelDefaultsSettings, setModelDefaultsSettings] = useState<ModelDefaultsSettings | null>(null);

  // General settings state - start with null, load from backend
  const [generalSettings, setGeneralSettings] = useState<GeneralSettings>({
    appName: 'LangConfig',
    autoSave: true,
    autoSaveInterval: 300,
    confirmBeforeDelete: true,
    showNotifications: true,
    checkUpdates: true,
    telemetry: false,
    logLevel: 'info',
    storagePath: ''
  });

  // RAG settings state - start with null, load from backend
  const [ragSettings, setRagSettings] = useState<RagSettings | null>(null);

  useEffect(() => {
    const abortController = new AbortController();

    loadSettings();
    const theme = loadTheme();
    setCurrentTheme(theme.name);

    return () => {
      abortController.abort();
    };
  }, []);

  const loadSettings = async () => {
    try {
      // Load API keys
      const keysResponse = await apiClient.getApiKeys();
      const keys = keysResponse.data || {};
      setApiKeys({
        anthropic: keys.find((k: any) => k.provider === 'anthropic')?.masked_key || '',
        openai: keys.find((k: any) => k.provider === 'openai')?.masked_key || '',
        google: keys.find((k: any) => k.provider === 'google')?.masked_key || '',
      });

      // Load general settings
      try {
        const generalResponse = await apiClient.getGeneralSettings();
        const generalData = generalResponse.data;
        setGeneralSettings({
          appName: generalData.app_name || 'LangConfig',
          autoSave: generalData.auto_save ?? true,
          autoSaveInterval: generalData.auto_save_interval || 300,
          confirmBeforeDelete: generalData.confirm_before_delete ?? true,
          showNotifications: generalData.show_notifications ?? true,
          checkUpdates: generalData.check_updates ?? true,
          telemetry: generalData.telemetry ?? false,
          logLevel: generalData.log_level || 'info',
          storagePath: generalData.storage_path || ''
        });
      } catch (error) {
      }

      // Load local models settings
      try {
        const localModelsResponse = await apiClient.getLocalModelsSettings();
        const localModelsData = localModelsResponse.data;
        setLocalModelsSettings({
          provider: localModelsData.provider || 'ollama',
          baseUrl: localModelsData.base_url || 'http://localhost:11434/v1',
          modelName: localModelsData.model_name || 'llama3.2:latest',
          apiKey: localModelsData.api_key || ''
        });
      } catch (error) {
      }

      // Load workspace settings
      try {
        const workspaceResponse = await apiClient.getWorkspaceSettings();
        const workspaceData = workspaceResponse.data;
        setWorkspaceSettings({
          workspacePath: workspaceData.workspace_path || '',
          allowRead: workspaceData.allow_read ?? true,
          allowWrite: workspaceData.allow_write ?? true,
          requireApproval: workspaceData.require_approval ?? true,
          autoDetectGit: workspaceData.auto_detect_git ?? true,
          backupBeforeEdit: workspaceData.backup_before_edit ?? true
        });
      } catch (error) {
      }

      // Load model defaults settings
      try {
        const modelDefaultsResponse = await apiClient.getModelDefaults();
        const modelDefaultsData = modelDefaultsResponse.data;
        setModelDefaultsSettings({
          primaryModel: modelDefaultsData.primary_model || 'gpt-4o',
          fallbackModels: modelDefaultsData.fallback_models || ['claude-sonnet-4-5'],
          temperature: modelDefaultsData.temperature ?? 0.7,
          maxTokens: modelDefaultsData.max_tokens || 4096,
          topP: modelDefaultsData.top_p ?? 1.0,
          routingStrategy: modelDefaultsData.routing_strategy || 'balanced',
          dailyTokenLimit: modelDefaultsData.daily_token_limit || 0,
          monthlyTokenLimit: modelDefaultsData.monthly_token_limit || 0,
          alertThreshold: modelDefaultsData.alert_threshold || 80
        });
      } catch (error) {
      }

      // Load RAG settings from main settings endpoint
      try {
        const settingsResponse = await apiClient.getSettings();
        const settingsData = settingsResponse.data;
        setRagSettings({
          embeddingModel: settingsData.embedding_model || 'text-embedding-3-small',
          chunkSize: settingsData.chunk_size || 1000,
          chunkOverlap: settingsData.chunk_overlap || 200
        });
      } catch (error) {
        console.error('Failed to load RAG settings:', error);
      }

    } catch (error) {
      // Ignore abort errors
      if (error instanceof Error && error.name === 'AbortError') {
        return;
      }
      console.error('Failed to load settings:', error);
    } finally {
      setIsLoading(false);
    }
  };

  // Debounced autosave function
  const autoSave = useCallback((category: SettingsCategory) => {
    // Clear existing timeout
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }

    // Set new timeout to save after 1 second of no changes
    saveTimeoutRef.current = setTimeout(async () => {
      try {
        switch (category) {
          case 'api-keys':
            await apiClient.setApiKeys({
              anthropic_api_key: apiKeys.anthropic || undefined,
              openai_api_key: apiKeys.openai || undefined,
              google_api_key: apiKeys.google || undefined,
            });
            break;

          case 'general':
            if (!generalSettings) return;
            await apiClient.updateGeneralSettings({
              app_name: generalSettings.appName,
              auto_save: generalSettings.autoSave,
              auto_save_interval: generalSettings.autoSaveInterval,
              confirm_before_delete: generalSettings.confirmBeforeDelete,
              show_notifications: generalSettings.showNotifications,
              check_updates: generalSettings.checkUpdates,
              telemetry: generalSettings.telemetry,
              log_level: generalSettings.logLevel
            });
            // Also save RAG settings to main settings endpoint
            if (ragSettings) {
              await apiClient.updateSettings({
                embedding_model: ragSettings.embeddingModel,
                chunk_size: ragSettings.chunkSize,
                chunk_overlap: ragSettings.chunkOverlap
              });
            }
            break;

          case 'local-models':
            if (!localModelsSettings) return;
            await apiClient.updateLocalModelsSettings({
              provider: localModelsSettings.provider,
              base_url: localModelsSettings.baseUrl,
              model_name: localModelsSettings.modelName,
              api_key: localModelsSettings.apiKey || null
            });
            break;

          case 'local-workspace':
            if (!workspaceSettings) return;
            await apiClient.updateWorkspaceSettings({
              workspace_path: workspaceSettings.workspacePath,
              allow_read: workspaceSettings.allowRead,
              allow_write: workspaceSettings.allowWrite,
              require_approval: workspaceSettings.requireApproval,
              auto_detect_git: workspaceSettings.autoDetectGit,
              backup_before_edit: workspaceSettings.backupBeforeEdit
            });
            break;

          case 'model-defaults':
            if (!modelDefaultsSettings) return;
            await apiClient.updateModelDefaultsSettings({
              primary_model: modelDefaultsSettings.primaryModel,
              fallback_models: modelDefaultsSettings.fallbackModels,
              temperature: modelDefaultsSettings.temperature,
              max_tokens: modelDefaultsSettings.maxTokens,
              top_p: modelDefaultsSettings.topP,
              routing_strategy: modelDefaultsSettings.routingStrategy,
              daily_token_limit: modelDefaultsSettings.dailyTokenLimit,
              monthly_token_limit: modelDefaultsSettings.monthlyTokenLimit,
              alert_threshold: modelDefaultsSettings.alertThreshold
            });
            break;
        }
      } catch (error) {
        console.error('Failed to autosave settings:', error);
      }
    }, 1000); // 1 second debounce
  }, [apiKeys, generalSettings, ragSettings, localModelsSettings, workspaceSettings, modelDefaultsSettings]);

  const handleThemeChange = (themeName: ThemeName) => {
    const theme = themes[themeName];
    applyTheme(theme);
    setCurrentTheme(themeName);
  };

  const renderCategoryContent = () => {
    switch (currentCategory) {
      case 'general':
        return (
          <div>
            <SettingsSection
              title="Application Settings"
              description="General application preferences and behavior"
              icon="tune"
            >
              <div className="space-y-4">
                <div className="border-t border-gray-200 dark:border-border-dark pt-3 mt-3">
                  <h4 className="text-sm font-medium mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    Auto-Save
                  </h4>
                  <div className="space-y-2.5">
                    <label className="flex items-center gap-3 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={generalSettings.autoSave}
                        onChange={(e) => {
                          setGeneralSettings({ ...generalSettings, autoSave: e.target.checked });
                          autoSave('general');
                        }}
                        className="w-4 h-4 text-primary bg-white dark:bg-background-dark border-gray-300 dark:border-border-dark rounded focus:ring-2 focus:ring-primary"
                      />
                      <div className="flex-1">
                        <span className="text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>
                          Enable auto-save
                        </span>
                        <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                          Automatically save workflows at regular intervals
                        </p>
                      </div>
                    </label>

                    {generalSettings.autoSave && (
                      <SettingsInput
                        label="Auto-save interval (seconds)"
                        type="number"
                        value={generalSettings.autoSaveInterval.toString()}
                        onChange={(value) => {
                          setGeneralSettings({ ...generalSettings, autoSaveInterval: parseInt(value) || 60 });
                          autoSave('general');
                        }}
                        description="How often to automatically save (minimum 30 seconds)"
                      />
                    )}
                  </div>
                </div>

                <div className="border-t border-gray-200 dark:border-border-dark pt-3 mt-3">
                  <h4 className="text-sm font-medium mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    Notifications & Confirmations
                  </h4>
                  <div className="space-y-2.5">
                    <label className="flex items-center gap-3 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={generalSettings.confirmBeforeDelete}
                        onChange={(e) => {
                          setGeneralSettings({ ...generalSettings, confirmBeforeDelete: e.target.checked });
                          autoSave('general');
                        }}
                        className="w-4 h-4 text-primary bg-white dark:bg-background-dark border-gray-300 dark:border-border-dark rounded focus:ring-2 focus:ring-primary"
                      />
                      <div className="flex-1">
                        <span className="text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>
                          Confirm before deleting
                        </span>
                        <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                          Show confirmation dialog before deleting workflows or agents
                        </p>
                      </div>
                    </label>

                    <label className="flex items-center gap-3 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={generalSettings.showNotifications}
                        onChange={(e) => {
                          setGeneralSettings({ ...generalSettings, showNotifications: e.target.checked });
                          autoSave('general');
                        }}
                        className="w-4 h-4 text-primary bg-white dark:bg-background-dark border-gray-300 dark:border-border-dark rounded focus:ring-2 focus:ring-primary"
                      />
                      <div className="flex-1">
                        <span className="text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>
                          Show notifications
                        </span>
                        <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                          Display system notifications for workflow completion and errors
                        </p>
                      </div>
                    </label>
                  </div>
                </div>

                <div className="border-t border-gray-200 dark:border-border-dark pt-3 mt-3">
                  <h4 className="text-sm font-medium mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    RAG Document Storage
                  </h4>
                  <div>
                    <label className="text-sm font-medium mb-1.5 block" style={{ color: 'var(--color-text-primary)' }}>
                      Storage Path for Vector Database Documents
                    </label>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={generalSettings.storagePath}
                        onChange={(e) => {
                          setGeneralSettings({ ...generalSettings, storagePath: e.target.value });
                          autoSave('general');
                        }}
                        placeholder="C:\Users\YourName\Documents\LangConfig or ./data/documents"
                        className="flex-1 px-3 py-1.5 text-sm border border-gray-300 dark:border-border-dark rounded-lg focus:outline-none focus:ring-2 focus:ring-primary font-mono"
                        style={{
                          backgroundColor: 'var(--color-input-background)',
                          color: 'var(--color-text-primary)'
                        }}
                      />
                      <button
                        onClick={async () => {
                          try {
                            const windowWithTauri = window as typeof window & { __TAURI__?: unknown };
                            if (windowWithTauri.__TAURI__) {
                              const { open } = await import('@tauri-apps/plugin-dialog');
                              const selected = await open({
                                directory: true,
                                multiple: false,
                                defaultPath: generalSettings.storagePath || undefined
                              });
                              if (selected && typeof selected === 'string') {
                                setGeneralSettings({ ...generalSettings, storagePath: selected });
                                autoSave('general');
                              }
                            }
                          } catch (error) {
                            console.error('Error selecting folder:', error);
                          }
                        }}
                        title={(window as typeof window & { __TAURI__?: unknown }).__TAURI__ ? 'Browse for folder' : 'Browse button only available in desktop app - enter path manually'}
                        className="px-3 py-1.5 text-sm font-medium bg-white dark:bg-background-dark border border-gray-300 dark:border-border-dark rounded-lg hover:bg-gray-50 dark:hover:bg-white/5 transition-colors whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed"
                        style={{ color: 'var(--color-text-primary)' }}
                      >
                        Browse
                      </button>
                    </div>
                    <p className="text-xs mt-1 leading-relaxed" style={{ color: 'var(--color-text-muted)' }}>
                      Enter full path (e.g., <code className="px-1 py-0.5 bg-gray-100 dark:bg-white/10 rounded text-xs">C:\Documents\LangConfig</code> or <code className="px-1 py-0.5 bg-gray-100 dark:bg-white/10 rounded text-xs">./data/documents</code>). Documents are stored here before indexing into embedded pgvector database. Change requires restart.
                    </p>
                  </div>
                </div>

                <div className="border-t border-gray-200 dark:border-border-dark pt-3 mt-3">
                  <h4 className="text-sm font-medium mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    RAG Configuration
                  </h4>
                  <div className="space-y-3">
                    <div>
                      <label className="text-sm font-medium mb-1.5 block" style={{ color: 'var(--color-text-primary)' }}>
                        Embedding Model
                      </label>
                      <select
                        value={ragSettings?.embeddingModel || 'text-embedding-3-small'}
                        onChange={(e) => {
                          if (ragSettings) {
                            setRagSettings({ ...ragSettings, embeddingModel: e.target.value });
                            autoSave('general');
                          }
                        }}
                        className="w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-border-dark rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                        style={{
                          backgroundColor: 'var(--color-input-background)',
                          color: 'var(--color-text-primary)'
                        }}
                      >
                        <option value="text-embedding-3-small">text-embedding-3-small (OpenAI)</option>
                        <option value="text-embedding-3-large">text-embedding-3-large (OpenAI)</option>
                        <option value="text-embedding-ada-002">text-embedding-ada-002 (OpenAI Legacy)</option>
                      </select>
                      <p className="text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
                        Model used for generating embeddings for document chunking
                      </p>
                    </div>

                    <div>
                      <label className="text-sm font-medium mb-1.5 block" style={{ color: 'var(--color-text-primary)' }}>
                        Chunk Size
                      </label>
                      <input
                        type="number"
                        min="100"
                        max="4000"
                        step="100"
                        value={ragSettings?.chunkSize || 1000}
                        onChange={(e) => {
                          if (ragSettings) {
                            setRagSettings({ ...ragSettings, chunkSize: parseInt(e.target.value) || 1000 });
                            autoSave('general');
                          }
                        }}
                        className="w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-border-dark rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                        style={{
                          backgroundColor: 'var(--color-input-background)',
                          color: 'var(--color-text-primary)'
                        }}
                      />
                      <p className="text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
                        Maximum characters per document chunk (100-4000)
                      </p>
                    </div>

                    <div>
                      <label className="text-sm font-medium mb-1.5 block" style={{ color: 'var(--color-text-primary)' }}>
                        Chunk Overlap
                      </label>
                      <input
                        type="number"
                        min="0"
                        max="1000"
                        step="50"
                        value={ragSettings?.chunkOverlap || 200}
                        onChange={(e) => {
                          if (ragSettings) {
                            setRagSettings({ ...ragSettings, chunkOverlap: parseInt(e.target.value) || 200 });
                            autoSave('general');
                          }
                        }}
                        className="w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-border-dark rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                        style={{
                          backgroundColor: 'var(--color-input-background)',
                          color: 'var(--color-text-primary)'
                        }}
                      />
                      <p className="text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
                        Characters of overlap between consecutive chunks (0-1000)
                      </p>
                    </div>
                  </div>
                </div>

                <div className="border-t border-gray-200 dark:border-border-dark pt-3 mt-3">
                  <h4 className="text-sm font-medium mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    Updates & Telemetry
                  </h4>
                  <div className="space-y-2.5">
                    <label className="flex items-center gap-3 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={generalSettings.checkUpdates}
                        onChange={(e) => {
                          setGeneralSettings({ ...generalSettings, checkUpdates: e.target.checked });
                          autoSave('general');
                        }}
                        className="w-4 h-4 text-primary bg-white dark:bg-background-dark border-gray-300 dark:border-border-dark rounded focus:ring-2 focus:ring-primary"
                      />
                      <div className="flex-1">
                        <span className="text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>
                          Check for updates
                        </span>
                        <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                          Automatically check for new versions on startup
                        </p>
                      </div>
                    </label>

                    <label className="flex items-center gap-3 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={generalSettings.telemetry}
                        onChange={(e) => {
                          setGeneralSettings({ ...generalSettings, telemetry: e.target.checked });
                          autoSave('general');
                        }}
                        className="w-4 h-4 text-primary bg-white dark:bg-background-dark border-gray-300 dark:border-border-dark rounded focus:ring-2 focus:ring-primary"
                      />
                      <div className="flex-1">
                        <span className="text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>
                          Anonymous usage statistics
                        </span>
                        <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                          Help improve LangConfig by sharing anonymous usage data
                        </p>
                      </div>
                    </label>
                  </div>
                </div>
              </div>
            </SettingsSection>
          </div>
        );

      case 'api-keys':
        return (
          <div>
            <SettingsSection
              title="API Keys & Providers"
              description="Configure your AI provider API keys. These are required for agent execution. Keys are stored in PostgreSQL database and persist across restarts."
              icon="key"
            >
              <div className="space-y-4">
                <SettingsInput
                  label="Anthropic API Key"
                  type="password"
                  value={apiKeys.anthropic}
                  onChange={(value) => {
                    setApiKeys({ ...apiKeys, anthropic: value });
                    autoSave('api-keys');
                  }}
                  placeholder="sk-ant-..."
                  description="Required for Claude models (claude-sonnet-4-5, claude-haiku-4-5, etc.)"
                />

                <SettingsInput
                  label="OpenAI API Key"
                  type="password"
                  value={apiKeys.openai}
                  onChange={(value) => {
                    setApiKeys({ ...apiKeys, openai: value });
                    autoSave('api-keys');
                  }}
                  placeholder="sk-..."
                  description="Required for GPT models (gpt-4o, gpt-4o-mini, gpt-4-turbo, etc.)"
                />

                <SettingsInput
                  label="Google API Key"
                  type="password"
                  value={apiKeys.google}
                  onChange={(value) => {
                    setApiKeys({ ...apiKeys, google: value });
                    autoSave('api-keys');
                  }}
                  placeholder="AIza..."
                  description="Required for Gemini models (gemini-2.5-pro, gemini-2.5-flash, etc.)"
                />
              </div>
            </SettingsSection>

            <SettingsSection
              title="Security Notice"
              icon="warning"
            >
              <div className="flex gap-3 p-4 bg-yellow-50 dark:bg-yellow-500/10 border border-yellow-200 dark:border-yellow-500/30 rounded-lg">
                <span className="material-symbols-outlined text-yellow-600 dark:text-yellow-400 text-xl">
                  lock
                </span>
                <div>
                  <h5 className="text-sm font-semibold text-yellow-800 dark:text-yellow-400 mb-1">
                    Database Storage
                  </h5>
                  <p className="text-xs text-yellow-700 dark:text-yellow-400/80 mb-2">
                    API keys are stored in PostgreSQL database (<code className="px-1 py-0.5 bg-yellow-100 dark:bg-yellow-900/30 rounded">settings</code> table) and persist across backend restarts.
                  </p>
                  <p className="text-xs text-yellow-700 dark:text-yellow-400/80">
                    <strong>Note:</strong> Keys are currently stored unencrypted. Future versions will add encryption and migrate to OS keychain (macOS Keychain, Windows Credential Manager, Linux Secret Service) via Tauri for enhanced security.
                  </p>
                </div>
              </div>
            </SettingsSection>
          </div>
        );

      case 'local-models':
        return <LocalModelsSettings />;

      case 'local-workspace':
        if (!workspaceSettings) return null;
        return (
          <LocalWorkspaceSettings
            settings={workspaceSettings}
            onSettingsChange={(newSettings: WorkspaceSettings) => {
              setWorkspaceSettings(newSettings);
              autoSave('local-workspace');
            }}
          />
        );

      case 'model-defaults':
        if (!modelDefaultsSettings) return null;
        return (
          <div>
            <ModelDefaultsSettings
              settings={modelDefaultsSettings}
              onSettingsChange={(newSettings: ModelDefaultsSettings) => {
                setModelDefaultsSettings(newSettings);
                autoSave('model-defaults');
              }}
            />
            <SettingsSection
              title="Override Behavior"
              icon="info"
            >
              <div className="flex gap-3 p-4 bg-blue-50 dark:bg-blue-500/10 border border-blue-200 dark:border-blue-500/30 rounded-lg">
                <span className="material-symbols-outlined text-blue-600 dark:text-blue-400 text-xl">
                  info
                </span>
                <div>
                  <h5 className="text-sm font-semibold text-blue-800 dark:text-blue-400 mb-1">
                    Settings Hierarchy
                  </h5>
                  <p className="text-xs text-blue-700 dark:text-blue-400/80">
                    These are <strong>default settings</strong> used when creating new agents or workflows.
                    Each agent node can override these settings individually. Agent-specific configurations always take precedence over these defaults.
                  </p>
                </div>
              </div>
            </SettingsSection>
          </div>
        );

      case 'appearance':
        return (
          <SettingsSection
            title="Appearance & Theme"
            description="Customize the look and feel of LangConfig"
            icon="palette"
          >
            <div>
              <label className="text-sm font-medium mb-3 block" style={{ color: 'var(--color-text-primary)' }}>
                Color Theme
              </label>
              <div className="grid grid-cols-2 gap-3">
                {Object.values(themes).map((theme) => (
                  <button
                    key={theme.name}
                    onClick={() => handleThemeChange(theme.name)}
                    className="p-4 rounded-lg border-2 transition-all text-left hover:border-primary/50"
                    style={{
                      borderColor: currentTheme === theme.name
                        ? 'var(--color-primary)'
                        : 'var(--color-border-dark)',
                      backgroundColor: currentTheme === theme.name
                        ? 'var(--color-primary)' + '10'
                        : 'transparent'
                    }}
                  >
                    <div className="flex items-center gap-3">
                      <div className="flex gap-1">
                        <div
                          className="w-4 h-4 rounded-full"
                          style={{ backgroundColor: theme.colors.primary }}
                        />
                        <div
                          className="w-4 h-4 rounded-full"
                          style={{ backgroundColor: theme.colors.backgroundDark }}
                        />
                        <div
                          className="w-4 h-4 rounded-full"
                          style={{ backgroundColor: theme.colors.panelDark }}
                        />
                      </div>
                      <span className="font-medium text-sm" style={{ color: 'var(--color-text-primary)' }}>
                        {theme.displayName}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </SettingsSection>
        );

      case 'about':
        return (
          <div>
            <SettingsSection
              title="About LangConfig"
              icon="info"
            >
              <div className="space-y-4">
                {/* App Header */}
                <div className="flex items-center gap-4 p-4 bg-white dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg">
                  <div className="w-16 h-16 bg-primary/10 rounded-lg flex items-center justify-center">
                    <span className="material-symbols-outlined text-3xl text-primary">account_tree</span>
                  </div>
                  <div className="flex-1">
                    <h3 className="text-lg font-bold" style={{ color: 'var(--color-text-primary)' }}>
                      LangConfig
                    </h3>
                    <p className="text-sm font-medium" style={{ color: 'var(--color-primary)' }}>
                      Powered by LangChain & LangGraph
                    </p>
                    <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
                      Version 0.1.0 (Alpha)
                    </p>
                  </div>
                </div>

                {/* Built With */}
                <div className="p-4 bg-white dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg">
                  <h4 className="text-sm font-semibold mb-3" style={{ color: 'var(--color-text-primary)' }}>
                    Built with LangChain & LangGraph
                  </h4>
                  <p className="text-sm mb-3" style={{ color: 'var(--color-text-muted)' }}>
                    LangConfig is a visual interface for LangGraph. Every workflow you build is a real LangGraph state graph under the hood. We use these frameworks because they're excellent for building production AI applications.
                  </p>
                  <div className="flex gap-2">
                    <a
                      href="https://www.langchain.com"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-2 px-3 py-1.5 text-xs font-medium bg-white dark:bg-panel-dark border border-gray-300 dark:border-border-dark rounded-lg hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
                      style={{ color: 'var(--color-text-primary)' }}
                    >
                      <span className="material-symbols-outlined text-sm">open_in_new</span>
                      LangChain
                    </a>
                    <a
                      href="https://langchain-ai.github.io/langgraph/"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-2 px-3 py-1.5 text-xs font-medium bg-white dark:bg-panel-dark border border-gray-300 dark:border-border-dark rounded-lg hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
                      style={{ color: 'var(--color-text-primary)' }}
                    >
                      <span className="material-symbols-outlined text-sm">open_in_new</span>
                      LangGraph
                    </a>
                  </div>
                </div>

                {/* What You're Building With */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="p-3 bg-white dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="material-symbols-outlined text-lg text-primary">settings_suggest</span>
                      <h5 className="text-xs font-bold" style={{ color: 'var(--color-text-primary)' }}>LangGraph Workflows</h5>
                    </div>
                    <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                      State graphs with checkpointing
                    </p>
                  </div>

                  <div className="p-3 bg-white dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="material-symbols-outlined text-lg text-primary">smart_toy</span>
                      <h5 className="text-xs font-bold" style={{ color: 'var(--color-text-primary)' }}>LangChain Agents</h5>
                    </div>
                    <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                      Tools, memory, and chains
                    </p>
                  </div>

                  <div className="p-3 bg-white dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="material-symbols-outlined text-lg text-primary">description</span>
                      <h5 className="text-xs font-bold" style={{ color: 'var(--color-text-primary)' }}>LangChain RAG</h5>
                    </div>
                    <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                      Vector stores and retrievers
                    </p>
                  </div>

                  <div className="p-3 bg-white dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="material-symbols-outlined text-lg text-primary">code</span>
                      <h5 className="text-xs font-bold" style={{ color: 'var(--color-text-primary)' }}>Export to Code</h5>
                    </div>
                    <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                      Production LangGraph Python
                    </p>
                  </div>
                </div>

                {/* Mission */}
                <div>
                  <h4 className="text-sm font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    Our Mission
                  </h4>
                  <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
                    Making LangChain and LangGraph accessible to everyone through visual, no-code workflows. We believe these frameworks are the future of AI development, and everyone should be able to learn and use them - whether you're a developer, product manager, researcher, or just curious about AI agents.
                  </p>
                </div>
              </div>
            </SettingsSection>

            {/* Tech Stack - Compact */}
            <SettingsSection
              title="Built With"
              icon="layers"
            >
              <div className="text-sm space-y-2" style={{ color: 'var(--color-text-muted)' }}>
                <p><strong style={{ color: 'var(--color-text-primary)' }}>Frontend:</strong> React 19, TypeScript, Tailwind CSS, ReactFlow, Tauri 2</p>
                <p><strong style={{ color: 'var(--color-text-primary)' }}>Backend:</strong> Python 3.11, FastAPI, LangChain v1.0, LangGraph, DeepAgents</p>
                <p><strong style={{ color: 'var(--color-text-primary)' }}>Database:</strong> PostgreSQL 16 with pgvector for LangChain vector stores</p>
                <p><strong style={{ color: 'var(--color-text-primary)' }}>AI:</strong> OpenAI, Anthropic, Google models via LangChain integrations</p>
              </div>
            </SettingsSection>

            {/* Links and License */}
            <SettingsSection
              title="Resources"
              icon="link"
            >
              <div className="space-y-4">
                <div className="flex gap-2 flex-wrap">
                  <button className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium bg-white dark:bg-background-dark border border-gray-300 dark:border-border-dark rounded-lg hover:bg-gray-50 dark:hover:bg-white/5 transition-colors" style={{ color: 'var(--color-text-primary)' }}>
                    <span className="material-symbols-outlined text-base">code</span>
                    GitHub
                  </button>
                </div>

                <hr className="border-gray-200 dark:border-border-dark" />

                <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                  <p className="font-semibold mb-1" style={{ color: 'var(--color-text-primary)' }}>License</p>
                  <p>MIT License © 2025</p>
                  <p className="mt-2">Making agentic AI accessible to everyone.</p>
                </div>
              </div>
            </SettingsSection>
          </div>
        );

      default:
        return (
          <SettingsSection
            title="Coming Soon"
            icon="construction"
          >
            <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
              This settings category is under development and will be available soon.
            </p>
          </SettingsSection>
        );
    }
  };

  // Show loading state while fetching settings from backend
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary mb-4"></div>
          <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>Loading settings...</p>
        </div>
      </div>
    );
  }

  // Don't render if settings haven't loaded yet
  if (!generalSettings || !localModelsSettings || !workspaceSettings || !modelDefaultsSettings || !ragSettings) {
    return null;
  }

  return (
    <SettingsLayout
      currentCategory={currentCategory}
      onCategoryChange={setCurrentCategory}
    >
      {renderCategoryContent()}
    </SettingsLayout>
  );
}
