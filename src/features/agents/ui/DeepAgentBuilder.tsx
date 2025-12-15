/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Save,
  Play,
  Download,
  Plus,
  Trash2,
  ChevronDown,
  ChevronRight,
  Settings,
  Zap,
  Brain,
  Database,
  Shield,
  Sparkles,
  ArrowLeft,
  AlertTriangle,
  X,
  Wrench,
  Info
} from 'lucide-react';
import { useNotification } from '../../../hooks/useNotification';
import { ModelSelectorInline } from '../../../components/common/ModelSelector';

import apiClient from '../../../lib/api-client';

// Type definitions

// Regular Agent Config (LangChain AgentExecutor)
export interface RegularAgentConfig {
  name?: string;
  description?: string;
  category?: string;
  model: string;
  temperature: number;
  max_tokens?: number;
  system_prompt: string;
  tools: string[];
  native_tools: string[];
  cli_tools: string[];
  custom_tools?: string[];  // User-created custom tools
  // AgentExecutor-specific parameters
  max_iterations?: number;  // Maximum steps before stopping (default: 15)
  early_stopping_method?: 'force' | 'generate';  // How to handle non-completion
  handle_parsing_errors?: boolean;  // Auto-retry on malformed output
  verbose?: boolean;  // Enable detailed logging
  return_intermediate_steps?: boolean;  // Return tool calls and results for debugging
  // Simple memory
  enable_memory?: boolean;
  memory_type?: 'buffer' | 'summary' | 'buffer_window';
  // Middleware (LangGraph v1.0)
  middleware?: MiddlewareConfig[];
}

interface MiddlewareConfig {
  type: string;
  enabled: boolean;
  config: Record<string, any>;
}

interface SubAgentConfig {
  name: string;
  description: string;
  template_id?: string;
  model?: string;
  system_prompt?: string;
  tools: string[];
  middleware: string[];
  interrupt_on: Record<string, any>;
}

interface BackendConfig {
  type: string;
  config: Record<string, any>;
  mappings?: Record<string, Record<string, any>>;
}

interface GuardrailsConfig {
  interrupts: Record<string, Record<string, any>>;
  token_limits: {
    max_total_tokens: number;
    eviction_threshold: number;
    summarization_threshold: number;
  };
  enable_auto_eviction: boolean;
  enable_summarization: boolean;
  // LangGraph context compaction strategies
  compaction_strategy: 'none' | 'trim_messages' | 'summarization' | 'filter_custom';
  preserve_recent_messages: number;
  long_term_memory: boolean;
  // Context window modes for different use cases
  context_window_mode: 'rapid' | 'balanced' | 'long-term';
  // Trim strategy when using trim_messages
  trim_strategy: 'first' | 'last' | 'oldest';
}

interface DeepAgentConfig {
  name?: string;
  description?: string;
  category?: string;
  model: string;
  temperature: number;
  max_tokens?: number;
  system_prompt: string;
  tools: string[];
  native_tools: string[];
  cli_tools: string[];
  custom_tools?: string[];  // User-created custom tools
  use_deepagents: boolean;
  middleware: MiddlewareConfig[];
  subagents: SubAgentConfig[];
  backend: BackendConfig;
  guardrails: GuardrailsConfig;
  export_format: string;
  include_chat_ui: boolean;
  include_docker: boolean;
  enforce_tool_constraints?: boolean;  // Enable/disable action preset enforcement
}

// Unified AgentConfig that supports both Regular and Deep agent fields
// This allows type-safe access without `as any` casts
interface AgentConfig extends DeepAgentConfig {
  // Regular Agent specific fields (AgentExecutor parameters)
  max_iterations?: number;
  early_stopping_method?: 'force' | 'generate';
  handle_parsing_errors?: boolean;
  verbose?: boolean;
  return_intermediate_steps?: boolean;
  enable_memory?: boolean;
  memory_type?: 'buffer' | 'summary' | 'buffer_window';
}

interface DeepAgentBuilderProps {
  initialConfig?: Partial<DeepAgentConfig>;
  agentType?: 'regular' | 'deep';
  onSave?: (config: DeepAgentConfig) => void;
  onTest?: (config: DeepAgentConfig) => void;
  onExport?: (config: DeepAgentConfig) => void;
  onClose: () => void;
  onBack?: () => void;
}

// Default config for Regular Agents (will be merged with shared defaults)
const REGULAR_AGENT_DEFAULTS = {
  max_iterations: 15,
  early_stopping_method: 'force' as const,
  handle_parsing_errors: true,
  verbose: false,
  return_intermediate_steps: false,
  enable_memory: false,
  memory_type: 'buffer' as const,
  middleware: [],
  use_deepagents: false,  // Regular agents don't use deepagents features
  subagents: [],  // Regular agents don't have subagents
  enforce_tool_constraints: false  // Disabled by default - users can enable for production safety
};

// DeepAgents standard filesystem tools
// See: https://docs.langchain.com/oss/python/deepagents/harness
const FILESYSTEM_TOOLS = ['ls', 'read_file', 'write_file', 'edit_file', 'glob', 'grep'];
// Default tools for new agents: filesystem + web_search for research capabilities
const DEFAULT_AGENT_TOOLS = [...FILESYSTEM_TOOLS, 'web_search'];

const DEFAULT_CONFIG: DeepAgentConfig = {
  model: 'claude-sonnet-4-5-20250929',
  temperature: 0.7,
  system_prompt: 'You are a helpful AI assistant with planning and research capabilities.',
  tools: [],
  native_tools: DEFAULT_AGENT_TOOLS,  // Filesystem + web_search for research
  cli_tools: [],
  use_deepagents: true,
  middleware: [
    {
      type: 'todo_list',
      enabled: true,
      config: { auto_track: true }
    },
    {
      type: 'filesystem',
      enabled: true,
      config: { auto_eviction: true, eviction_threshold_bytes: 1000000 }
    },
    {
      type: 'subagent',
      enabled: true,
      config: { max_depth: 3, max_concurrent: 5 }
    }
  ],
  subagents: [],
  backend: {
    type: 'state',
    config: {}
  },
  guardrails: {
    interrupts: {},
    token_limits: {
      max_total_tokens: 100000,
      eviction_threshold: 80000,
      summarization_threshold: 60000
    },
    enable_auto_eviction: true,
    enable_summarization: true,
    compaction_strategy: 'trim_messages',
    preserve_recent_messages: 10,
    long_term_memory: false,
    context_window_mode: 'balanced',
    trim_strategy: 'oldest'
  },
  export_format: 'standalone',
  include_chat_ui: true,
  include_docker: false,
  enforce_tool_constraints: false  // Disabled by default - users can enable for production safety
};

// Native tools registry with DeepAgents standard naming
// See: https://docs.langchain.com/oss/python/deepagents/harness
const NATIVE_TOOLS = [
  // Filesystem tools (DeepAgents standard)
  { id: 'ls', name: 'List Directory', description: 'List directory contents with metadata (file sizes, types). Shows files and subdirectories.' },
  { id: 'read_file', name: 'Read File', description: 'Read file contents with line numbers. Supports offset and limit for large files.' },
  { id: 'write_file', name: 'Write File', description: 'Create new files with content. Workspace-aware for organized file storage.' },
  { id: 'edit_file', name: 'Edit File', description: 'Perform exact string replacements in files. The search string must be unique.' },
  { id: 'glob', name: 'Find Files', description: 'Find files matching a glob pattern (e.g., **/*.py, src/*.ts).' },
  { id: 'grep', name: 'Search Contents', description: 'Search file contents for a regex pattern. Returns matching lines with file paths and line numbers.' },
  // Web tools
  { id: 'web_search', name: 'Web Search', description: 'Search the web using DuckDuckGo (FREE, no API key required). Perfect for finding current information, news, and general knowledge.' },
  { id: 'web_fetch', name: 'Web Fetch', description: 'Fetch and extract text content from webpages using HTTP requests. Useful for reading articles, documentation, and web pages.' },
  { id: 'browser', name: 'Browser Automation', description: 'Advanced web interaction using Playwright. Navigate, click, extract text, take screenshots, and interact with JavaScript-rendered content.' },
  // Memory tools
  { id: 'memory_store', name: 'Store Memory', description: 'Save information to agent memory for later recall. Uses PostgreSQL for persistence across sessions. Supports key-value storage with context categories.' },
  { id: 'memory_recall', name: 'Recall Memory', description: 'Retrieve previously stored information from memory by key. Access saved data across different conversation sessions.' },
  // Reasoning tools
  { id: 'reasoning_chain', name: 'Reasoning Chain', description: 'Break down complex tasks into logical reasoning steps. Provides structured framework for multi-step problem solving and analysis.' },
];

const BACKEND_TYPES = [
  { id: 'state', name: 'State (Ephemeral)', description: 'Session-only memory - fast, temporary' },
  { id: 'store', name: 'Store (Persistent)', description: 'Cross-session storage - survives restarts' },
  { id: 'filesystem', name: 'Filesystem', description: 'Local file storage - for large data' },
  { id: 'vectordb', name: 'Vector Database', description: 'Semantic search - for embeddings' },
  { id: 'composite', name: 'Composite', description: 'Multiple backends (auto-configured)' },
];

// Backend toggle helper functions
const getSelectedBackends = (backend: BackendConfig): string[] => {
  if (backend.type === 'composite' && backend.mappings) {
    return Object.values(backend.mappings).map((m: Record<string, any>) => m.type);
  }
  return backend.type === 'state' ? [] : [backend.type];
};

const createBackendConfig = (selectedBackends: string[]): BackendConfig => {
  if (selectedBackends.length === 0) {
    return { type: 'state', config: {} };
  }

  if (selectedBackends.length === 1) {
    return { type: selectedBackends[0], config: {} };
  }

  // Multiple backends - create composite with path mappings
  const mappings: Record<string, Record<string, any>> = {};
  const pathMap: Record<string, string> = {
    state: '/memory/',
    store: '/store/',
    filesystem: '/files/',
    vectordb: '/embeddings/'
  };

  selectedBackends.forEach(type => {
    const path = pathMap[type] || `/${type}/`;
    mappings[path] = { type, config: {} };
  });

  return { type: 'composite', config: {}, mappings };
};

// Memoized ToolCheckbox component for performance
interface ToolCheckboxProps {
  tool: { id: string; name: string; description: string };
  checked: boolean;
  onChange: () => void;
}

const ToolCheckbox = React.memo(({ tool, checked, onChange }: ToolCheckboxProps) => (
  <label className="flex items-start gap-3 p-3 bg-gray-50 dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg cursor-pointer hover:bg-gray-100 dark:hover:bg-white/5 transition-colors">
    <input
      type="checkbox"
      checked={checked}
      onChange={onChange}
      className="mt-0.5"
    />
    <div className="flex-1">
      <div className="text-sm font-medium text-gray-900 dark:text-white">{tool.name}</div>
      <div className="text-xs text-gray-600 dark:text-gray-400">{tool.description}</div>
    </div>
  </label>
), (prev, next) => prev.checked === next.checked && prev.tool.id === next.tool.id);

ToolCheckbox.displayName = 'ToolCheckbox';

export default function DeepAgentBuilder({
  initialConfig,
  agentType = 'deep',
  onSave,
  onTest,
  onExport,
  onClose,
  onBack
}: DeepAgentBuilderProps) {
  const { showSuccess, logError, showWarning, NotificationModal } = useNotification();
  const [config, setConfig] = useState<AgentConfig>(() => {
    const baseConfig: AgentConfig = {
      ...DEFAULT_CONFIG,
      ...initialConfig
    };

    // Add Regular Agent defaults if this is a regular agent
    if (agentType === 'regular') {
      return {
        ...baseConfig,
        ...REGULAR_AGENT_DEFAULTS,
        ...initialConfig // Re-apply initialConfig to override defaults if provided
      };
    }

    return baseConfig;
  });

  const [expandedSections, setExpandedSections] = useState({
    basic: true,       // Always expanded - most important settings
    prompt: true,      // Always expanded - core configuration
    tools: true,       // Always expanded - essential capabilities
    execution: false,  // Collapsed - advanced Regular Agent controls
    memory: false,     // Collapsed - advanced Regular Agent memory
    middleware: false, // Collapsed - middleware configuration (both agent types)
    backend: false,    // Collapsed - advanced Deep Agent features
    guardrails: false  // Collapsed - advanced Deep Agent features
  });

  // AI Generation state
  const [aiLoading, setAiLoading] = useState(false);

  // Custom tools state
  const [availableCustomTools, setAvailableCustomTools] = useState<Array<{ id: number, tool_id: string, name: string, description: string }>>([]);
  const [selectedCustomTools, setSelectedCustomTools] = useState<string[]>(initialConfig?.custom_tools || []);

  // Unsaved changes tracking
  const [showDiscardDialog, setShowDiscardDialog] = useState(false);
  const [pendingCloseAction, setPendingCloseAction] = useState<'close' | 'back' | null>(null);

  // Store initial state for comparison (serialized for deep comparison)
  const initialConfigRef = useMemo(() => JSON.stringify({
    config: {
      ...DEFAULT_CONFIG,
      ...initialConfig,
      ...(agentType === 'regular' ? REGULAR_AGENT_DEFAULTS : {})
    },
    customTools: initialConfig?.custom_tools || []
  }), []);

  // Check if there are unsaved changes
  const hasUnsavedChanges = useMemo(() => {
    const currentState = JSON.stringify({
      config,
      customTools: selectedCustomTools
    });
    return currentState !== initialConfigRef;
  }, [config, selectedCustomTools, initialConfigRef]);

  // Warning: System prompt mentions file operations but filesystem tools are disabled
  const fileToolWarning = useMemo(() => {
    if (agentType !== 'deep') return null;

    const prompt = config.system_prompt?.toLowerCase() || '';
    const fileKeywords = ['write file', 'create file', 'save file', 'output file', 'read file', 'edit file'];
    const mentionsFiles = fileKeywords.some(keyword => prompt.includes(keyword));

    if (!mentionsFiles) return null;

    const fsMiddlewareEnabled = config.middleware?.some(m => m.type === 'filesystem' && m.enabled);
    const hasFileTools = config.native_tools?.some(t =>
      ['write_file', 'read_file', 'edit_file', 'ls', 'glob', 'grep'].includes(t)
    );

    if (fsMiddlewareEnabled || hasFileTools) return null;

    return 'System prompt mentions file operations, but FilesystemMiddleware is disabled. Enable it in the Middleware section or the agent will not have access to file tools.';
  }, [config.system_prompt, config.middleware, config.native_tools, agentType]);

  // Fetch custom tools on mount with cleanup for race condition
  useEffect(() => {
    let isMounted = true;

    const fetchCustomTools = async () => {
      try {
        const response = await apiClient.listCustomTools();
        if (isMounted) {
          setAvailableCustomTools(response.data);
        }
      } catch (error) {
        if (isMounted) {
          console.error('Failed to fetch custom tools:', error);
        }
      }
    };

    fetchCustomTools();

    return () => { isMounted = false; };
  }, []);

  const toggleSection = (section: keyof typeof expandedSections) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }));
  };

  const updateConfig = <K extends keyof AgentConfig>(
    key: K,
    value: AgentConfig[K]
  ) => {
    setConfig(prev => ({ ...prev, [key]: value }));
  };

  const toggleMiddleware = (index: number) => {
    const newMiddleware = [...config.middleware];
    newMiddleware[index].enabled = !newMiddleware[index].enabled;
    setConfig(prev => ({ ...prev, middleware: newMiddleware }));
  };

  const addRegularAgentMiddleware = (type: string, defaultConfig: Record<string, any> = {}) => {
    const middleware = config.middleware || [];

    // Check if middleware already exists
    if (middleware.some((mw: MiddlewareConfig) => mw.type === type)) {
      return; // Already added
    }

    const newMiddleware: MiddlewareConfig = {
      type,
      enabled: true,
      config: defaultConfig
    };

    setConfig(prev => ({
      ...prev,
      middleware: [...middleware, newMiddleware]
    }));
  };

  const removeRegularAgentMiddleware = (index: number) => {
    const middleware = config.middleware || [];
    setConfig(prev => ({
      ...prev,
      middleware: middleware.filter((_, i) => i !== index)
    }));
  };

  const toggleRegularMiddleware = (index: number) => {
    const middleware = config.middleware || [];
    const newMiddleware = [...middleware];
    newMiddleware[index].enabled = !newMiddleware[index].enabled;
    setConfig(prev => ({ ...prev, middleware: newMiddleware }));
  };

  const toggleNativeTool = useCallback((toolId: string) => {
    setConfig(prev => ({
      ...prev,
      native_tools: prev.native_tools.includes(toolId)
        ? prev.native_tools.filter(t => t !== toolId)
        : [...prev.native_tools, toolId]
    }));
  }, []);

  const toggleCustomTool = useCallback((toolId: string) => {
    setSelectedCustomTools(prev =>
      prev.includes(toolId)
        ? prev.filter(t => t !== toolId)
        : [...prev, toolId]
    );
  }, []);

  const toggleBackend = useCallback((backendId: string) => {
    setConfig(prev => {
      // Get currently selected backends using helper
      let selectedBackends = getSelectedBackends(prev.backend);

      // Toggle the backend
      if (selectedBackends.includes(backendId)) {
        selectedBackends = selectedBackends.filter(b => b !== backendId);
      } else {
        selectedBackends = [...selectedBackends, backendId];
      }

      // Create new backend config using helper
      return {
        ...prev,
        backend: createBackendConfig(selectedBackends)
      };
    });
  }, []);

  // Config validation function
  const validateConfig = (cfg: AgentConfig): string[] => {
    const errors: string[] = [];

    if (!cfg.name?.trim()) errors.push("Agent name is required");
    if (!cfg.description?.trim()) errors.push("Agent description is required");
    if (!cfg.category) errors.push("Agent category is required");
    if (!cfg.system_prompt?.trim()) errors.push("System prompt is required");
    if (cfg.temperature < 0 || cfg.temperature > 2) {
      errors.push("Temperature must be between 0 and 2");
    }

    // Token limits validation for Deep agents
    if (agentType === 'deep') {
      const tl = cfg.guardrails?.token_limits;
      if (tl && !(tl.summarization_threshold < tl.eviction_threshold &&
        tl.eviction_threshold < tl.max_total_tokens)) {
        errors.push("Token limits: summarization < eviction < max_total");
      }
    }

    return errors;
  };

  const handleSave = () => {
    const errors = validateConfig(config);
    if (errors.length > 0) {
      logError("Validation failed", errors.join("\n"));
      return;
    }

    if (onSave) {
      // Include custom tools in config
      const configWithCustomTools = {
        ...config,
        custom_tools: selectedCustomTools,
        // CRITICAL: Force use_deepagents based on agentType prop
        // This ensures the flag is always correct regardless of initialConfig
        use_deepagents: agentType === 'deep'
      };
      onSave(configWithCustomTools);
    }
  };

  const handleTest = () => {
    const errors = validateConfig(config);
    if (errors.length > 0) {
      logError("Validation failed", errors.join("\n"));
      return;
    }

    if (onTest) {
      const configWithCustomTools = {
        ...config,
        custom_tools: selectedCustomTools
      };
      onTest(configWithCustomTools);
    }
  };

  const handleExport = () => {
    const errors = validateConfig(config);
    if (errors.length > 0) {
      logError("Validation failed", errors.join("\n"));
      return;
    }

    if (onExport) {
      const configWithCustomTools = {
        ...config,
        custom_tools: selectedCustomTools
      };
      onExport(configWithCustomTools);
    }
  };

  // Handle close with unsaved changes check
  const handleCloseAttempt = useCallback((action: 'close' | 'back') => {
    if (hasUnsavedChanges) {
      setPendingCloseAction(action);
      setShowDiscardDialog(true);
    } else {
      if (action === 'back' && onBack) {
        onBack();
      } else {
        onClose();
      }
    }
  }, [hasUnsavedChanges, onBack, onClose]);

  const handleConfirmDiscard = useCallback(() => {
    setShowDiscardDialog(false);
    if (pendingCloseAction === 'back' && onBack) {
      onBack();
    } else {
      onClose();
    }
  }, [pendingCloseAction, onBack, onClose]);

  const handleCancelDiscard = useCallback(() => {
    setShowDiscardDialog(false);
    setPendingCloseAction(null);
  }, []);

  const handleAIGenerate = async () => {
    // Validate that user has filled out basic settings first
    if (!config.name?.trim() || !config.description?.trim() || !config.category?.trim()) {
      showWarning('Please fill out Agent Name, Description, and Category in Basic Settings first');
      return;
    }

    setAiLoading(true);
    try {
      const response = await apiClient.generateAgentConfig({
        name: config.name,
        description: config.description,
        agent_type: agentType,
        category: config.category
      });

      const result = response.data;

      if (!result.config) {
        throw new Error('Invalid response format: missing config');
      }

      // Fill the form with AI-generated config (keeping user's name and description)
      setConfig(prev => ({
        ...prev,
        model: result.config.model,
        temperature: result.config.temperature,
        system_prompt: result.config.system_prompt,
        native_tools: result.config.native_tools || result.config.mcp_tools || []
      }));

      // Show success with reasoning
      showSuccess('Configuration generated!', result.config.reasoning || 'AI configured your agent');
    } catch (error: any) {
      logError('Generation failed', error.message || 'An unexpected error occurred');
    } finally {
      setAiLoading(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-gray-50 dark:bg-background-dark">
      {/* Fixed Header - Primary Color with White Text */}
      <div className="border-b p-6" style={{
        backgroundColor: 'var(--color-primary)',
        borderBottomColor: 'var(--color-border-dark)'
      }}>
        <div className="max-w-5xl mx-auto">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-3 flex-1">
              <button
                onClick={() => handleCloseAttempt(onBack ? 'back' : 'close')}
                className="p-2 transition-all text-white/90 hover:text-white hover:bg-white/15 rounded-lg"
                style={{ textShadow: '0 1px 2px rgba(0, 0, 0, 0.15)' }}
                title="Back"
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
              <div className="flex-1">
                <h2 className="text-2xl font-semibold text-white" style={{ textShadow: '0 1px 2px rgba(0, 0, 0, 0.25)' }}>
                  {agentType === 'regular' ? 'Regular Agent Builder' : 'Deep Agent Builder'}
                </h2>
                <p className="text-sm mt-1 text-white/90" style={{ textShadow: '0 1px 2px rgba(0, 0, 0, 0.15)' }}>
                  {agentType === 'regular'
                    ? 'Configure a standard LangChain agent node with model, tools, and system prompt'
                    : 'Configure an advanced agent with planning, subagents, and advanced capabilities'
                  }
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleAIGenerate}
                disabled={aiLoading}
                className="flex items-center gap-2 px-4 py-2 rounded-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                style={{
                  backgroundColor: 'rgba(255, 255, 255, 0.2)',
                  color: 'white',
                  backdropFilter: 'blur(8px)',
                  border: '1px solid rgba(255, 255, 255, 0.3)',
                  textShadow: '0 1px 2px rgba(0, 0, 0, 0.15)'
                }}
                onMouseEnter={(e) => {
                  if (!aiLoading) {
                    e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.3)';
                  }
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.2)';
                }}
              >
                {aiLoading ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    Generating...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4" />
                    AI Generate
                  </>
                )}
              </button>
              <button
                onClick={() => handleCloseAttempt('close')}
                className="p-2 transition-all text-white/90 hover:text-white hover:bg-white/15 rounded-lg"
                style={{ textShadow: '0 1px 2px rgba(0, 0, 0, 0.15)' }}
                title="Close"
              >
                <X className="w-6 h-6" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Scrollable Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-5xl mx-auto space-y-4">

          {/* Basic Settings */}
          <ConfigSection
            title="Basic Settings"
            icon={<Settings className="w-5 h-5" />}
            expanded={expandedSections.basic}
            onToggle={() => toggleSection('basic')}
          >
            <div>
              <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-2 uppercase">
                Agent Name <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={config.name || ''}
                onChange={(e) => updateConfig('name', e.target.value)}
                placeholder="e.g., Code Researcher, Bug Hunter"
                className="w-full px-3 py-2 bg-white dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg text-sm text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-2 uppercase">
                Description <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={config.description || ''}
                onChange={(e) => updateConfig('description', e.target.value)}
                placeholder="Brief description of what this agent does"
                className="w-full px-3 py-2 bg-white dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg text-sm text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
              />
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                💡 Fill out Name & Description, then click "AI Generate" to auto-fill the rest
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-2 uppercase">
                  Category <span className="text-red-500">*</span>
                </label>
                <select
                  value={config.category || 'Custom'}
                  onChange={(e) => updateConfig('category', e.target.value)}
                  className="w-full px-3 py-2 bg-white dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg text-sm text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
                >
                  <option value="Code Generation">Code Generation</option>
                  <option value="Research">Research</option>
                  <option value="Testing">Testing</option>
                  <option value="Documentation">Documentation</option>
                  <option value="Custom">Custom</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-2 uppercase">
                  Model
                </label>
                <ModelSelectorInline
                  value={config.model}
                  onChange={(modelId) => updateConfig('model', modelId)}
                  includeLocal={true}
                  onlyValidated={true}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-2 uppercase">
                  Temperature ({config.temperature})
                </label>
                <input
                  type="range"
                  min="0"
                  max="2"
                  step="0.1"
                  value={config.temperature}
                  onChange={(e) => updateConfig('temperature', parseFloat(e.target.value))}
                  className="w-full"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-2 uppercase">
                  Max Tokens (Optional)
                </label>
                <input
                  type="number"
                  value={config.max_tokens || ''}
                  onChange={(e) => updateConfig('max_tokens', e.target.value ? parseInt(e.target.value) : undefined)}
                  placeholder="Leave empty for default"
                  className="w-full px-3 py-2 bg-white dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg text-sm text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
                />
              </div>
            </div>
          </ConfigSection>

          {/* System Prompt */}
          <ConfigSection
            title="System Prompt"
            icon={<Brain className="w-5 h-5" />}
            expanded={expandedSections.prompt}
            onToggle={() => toggleSection('prompt')}
          >
            <div>
              <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-2 uppercase">
                Instructions for the agent <span className="text-red-500">*</span>
              </label>
              <textarea
                value={config.system_prompt}
                onChange={(e) => updateConfig('system_prompt', e.target.value)}
                rows={6}
                placeholder="Enter the system prompt that defines the agent's behavior and capabilities... (or use AI Generate to auto-fill)"
                className="w-full px-3 py-2 bg-white dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg text-sm text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent resize-none"
              />

              {/* Warning badge for missing file tools */}
              {fileToolWarning && (
                <div className="mt-3 flex items-start gap-2 p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg">
                  <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400 mt-0.5 flex-shrink-0" />
                  <p className="text-xs text-amber-700 dark:text-amber-300">
                    {fileToolWarning}
                  </p>
                </div>
              )}
            </div>
          </ConfigSection>

          {/* Tools */}
          <ConfigSection
            title="Tools & Capabilities"
            icon={<Zap className="w-5 h-5" />}
            expanded={expandedSections.tools}
            onToggle={() => toggleSection('tools')}
          >
            <div>
              <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 uppercase mb-3">
                MCP Tools (Native)
              </label>
              <div className="grid grid-cols-2 gap-3">
                {NATIVE_TOOLS.map(tool => (
                  <ToolCheckbox
                    key={tool.id}
                    tool={tool}
                    checked={config.native_tools.includes(tool.id)}
                    onChange={() => toggleNativeTool(tool.id)}
                  />
                ))}
              </div>

              {/* Action Presets Toggle - Prominent Feature Highlight */}
              <div
                className={`mt-4 p-4 rounded-lg border transition-all ${config.enforce_tool_constraints ? 'bg-primary/10' : 'bg-white dark:bg-panel-dark'}`}
                style={{
                  borderColor: config.enforce_tool_constraints
                    ? 'var(--color-primary)'
                    : 'var(--color-border-dark)'
                }}
              >
                <div className="flex items-start gap-3">
                  <Shield
                    className={`w-5 h-5 flex-shrink-0 ${config.enforce_tool_constraints ? 'mt-0' : 'mt-0.5'}`}
                    style={{
                      color: config.enforce_tool_constraints
                        ? 'var(--color-primary)'
                        : 'var(--color-text-muted)'
                    }}
                  />
                  <div className="flex-1">
                    <label className="flex items-start gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={config.enforce_tool_constraints ?? false}
                        onChange={(e) => updateConfig('enforce_tool_constraints', e.target.checked)}
                        className="mt-1"
                        style={{ accentColor: 'var(--color-primary)' }}
                      />
                      <div className="flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span
                            className="text-sm font-semibold"
                            style={{ color: 'var(--color-text-primary)' }}
                          >
                            Action Preset Safety Controls
                          </span>
                          {!config.enforce_tool_constraints && (
                            <span
                              className="px-2 py-0.5 text-[10px] font-bold rounded"
                              style={{
                                backgroundColor: 'rgba(234, 179, 8, 0.15)',
                                color: '#eab308',
                                border: '1px solid rgba(234, 179, 8, 0.3)'
                              }}
                            >
                              OPTIONAL FEATURE
                            </span>
                          )}
                          {config.enforce_tool_constraints && (
                            <span
                              className="px-2 py-0.5 text-[10px] font-bold rounded"
                              style={{
                                backgroundColor: 'rgba(34, 197, 94, 0.15)',
                                color: '#22c55e',
                                border: '1px solid rgba(34, 197, 94, 0.3)'
                              }}
                            >
                              ✓ ENABLED
                            </span>
                          )}
                        </div>
                        <p
                          className="text-xs mt-1.5 leading-relaxed"
                          style={{ color: 'var(--color-text-muted)' }}
                        >
                          {config.enforce_tool_constraints ? (
                            <>
                              <strong>Enabled:</strong> Tools are automatically wrapped with safety constraints including timeouts (60s for terminal), retry limits, and human-in-the-loop (HITL) approval for high-risk operations.
                            </>
                          ) : (
                            <>
                              <strong>Disabled:</strong> Tools run without safety constraints. Enable this to add automatic timeouts, retry logic, and HITL approval gates for high-risk tools like terminal access.
                            </>
                          )}
                        </p>
                        {!config.enforce_tool_constraints && (
                          <div
                            className="mt-2 p-2 rounded text-xs"
                            style={{
                              backgroundColor: 'rgba(59, 130, 246, 0.1)',
                              borderLeft: '3px solid var(--color-primary)'
                            }}
                          >
                            <p style={{ color: 'var(--color-text-primary)' }}>
                              <strong>💡 New Feature:</strong> Action Presets provide production-ready safety controls. Learn more in <strong>Library → Learn LangChain → Section 9</strong>.
                            </p>
                          </div>
                        )}
                      </div>
                    </label>
                  </div>
                </div>
              </div>
            </div>

            {/* Custom Tools Section */}
            {availableCustomTools.length > 0 && (
              <div className="mt-6">
                <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-3 uppercase">
                  Custom Tools
                </label>
                <div className="grid grid-cols-2 gap-3">
                  {availableCustomTools.map(tool => (
                    <ToolCheckbox
                      key={tool.tool_id}
                      tool={{ id: tool.tool_id, name: tool.name, description: tool.description }}
                      checked={selectedCustomTools.includes(tool.tool_id)}
                      onChange={() => toggleCustomTool(tool.tool_id)}
                    />
                  ))}
                </div>
              </div>
            )}
          </ConfigSection>

          {/* Execution Control - Regular Agent Only */}
          {agentType === 'regular' && (
            <ConfigSection
              title="Execution Control"
              icon={<Settings className="w-5 h-5" />}
              expanded={expandedSections.execution}
              onToggle={() => toggleSection('execution')}
            >
              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-2 uppercase">
                    Max Iterations
                  </label>
                  <input
                    type="number"
                    value={config.max_iterations || 15}
                    onChange={(e) => updateConfig('max_iterations', parseInt(e.target.value))}
                    min="1"
                    max="100"
                    className="w-full px-3 py-2 bg-white dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg text-sm text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
                  />
                  <div className="mt-2 p-3 rounded-lg bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800">
                    <p className="text-xs text-gray-700 dark:text-gray-300 font-medium mb-2">
                      💡 Each tool call = 1 iteration. Default: 15 (good for most tasks)
                    </p>
                    <div className="space-y-1 text-xs text-gray-600 dark:text-gray-400">
                      <p>• <strong>10-15:</strong> Simple tasks (2-3 tool calls)</p>
                      <p>• <strong>20-30:</strong> Multi-step workflows</p>
                      <p>• <strong>40+:</strong> Complex research tasks</p>
                    </div>
                    <p className="text-xs text-orange-600 dark:text-orange-400 mt-2">
                      ⚠️ Hitting limit repeatedly? Add stopping criteria to your system prompt instead:
                    </p>
                    <div className="mt-1 p-2 bg-gray-100 dark:bg-gray-800 rounded text-xs font-mono text-gray-700 dark:text-gray-300">
                      "After finding 2-3 relevant sources, provide your answer and STOP."
                    </div>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-2 uppercase">
                    Early Stopping Method
                  </label>
                  <select
                    value={config.early_stopping_method || 'force'}
                    onChange={(e) => updateConfig('early_stopping_method', e.target.value as 'force' | 'generate')}
                    className="w-full px-3 py-2 bg-white dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg text-sm text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
                  >
                    <option value="force">Force - Return incomplete answer</option>
                    <option value="generate">Generate - Continue to generate answer</option>
                  </select>
                  <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">
                    How to handle when max iterations reached without final answer
                  </p>
                </div>

                <div>
                  <label className="flex items-center gap-2 text-sm font-medium text-gray-900 dark:text-white">
                    <input
                      type="checkbox"
                      checked={config.handle_parsing_errors ?? true}
                      onChange={(e) => updateConfig('handle_parsing_errors', e.target.checked)}
                    />
                    Handle Parsing Errors
                  </label>
                  <p className="text-xs text-gray-600 dark:text-gray-400 mt-1 ml-6">
                    Automatically retry when agent output is malformed
                  </p>
                </div>

                <div>
                  <label className="flex items-center gap-2 text-sm font-medium text-gray-900 dark:text-white">
                    <input
                      type="checkbox"
                      checked={config.verbose ?? false}
                      onChange={(e) => updateConfig('verbose', e.target.checked)}
                    />
                    Verbose Logging
                  </label>
                  <p className="text-xs text-gray-600 dark:text-gray-400 mt-1 ml-6">
                    Enable detailed logging for debugging
                  </p>
                </div>

                <div>
                  <label className="flex items-center gap-2 text-sm font-medium text-gray-900 dark:text-white">
                    <input
                      type="checkbox"
                      checked={config.return_intermediate_steps ?? false}
                      onChange={(e) => updateConfig('return_intermediate_steps', e.target.checked)}
                    />
                    Return Intermediate Steps
                  </label>
                  <p className="text-xs text-gray-600 dark:text-gray-400 mt-1 ml-6">
                    Include tool calls and results in response (useful for debugging)
                  </p>
                </div>
              </div>
            </ConfigSection>
          )}

          {/* Memory - Regular Agent Only */}
          {agentType === 'regular' && (
            <ConfigSection
              title="Memory"
              icon={<Brain className="w-5 h-5" />}
              expanded={expandedSections.memory}
              onToggle={() => toggleSection('memory')}
            >
              <div className="space-y-4">
                <div>
                  <label className="flex items-center gap-2 text-sm font-medium text-gray-900 dark:text-white">
                    <input
                      type="checkbox"
                      checked={config.enable_memory ?? false}
                      onChange={(e) => updateConfig('enable_memory', e.target.checked)}
                    />
                    Enable Conversation Memory
                  </label>
                  <p className="text-xs text-gray-600 dark:text-gray-400 mt-1 ml-6">
                    Remember previous messages in the conversation
                  </p>
                </div>

                {config.enable_memory && (
                  <div className="pl-4 border-l-2 border-primary">
                    <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-2 uppercase">
                      Memory Type
                    </label>
                    <select
                      value={config.memory_type || 'buffer'}
                      onChange={(e) => updateConfig('memory_type', e.target.value as 'buffer' | 'summary' | 'buffer_window')}
                      className="w-full px-3 py-2 bg-white dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg text-sm text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
                    >
                      <option value="buffer">Buffer - Keep all messages in memory</option>
                      <option value="buffer_window">Buffer Window - Keep last N messages</option>
                      <option value="summary">Summary - Summarize old messages</option>
                    </select>
                    <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">
                      {config.memory_type === 'buffer' && 'Stores all conversation history (can grow large)'}
                      {config.memory_type === 'buffer_window' && 'Keeps only recent messages to manage memory size'}
                      {config.memory_type === 'summary' && 'Summarizes older messages to save tokens'}
                    </p>
                  </div>
                )}
              </div>
            </ConfigSection>
          )}

          {/* Middleware - Regular Agent Only */}
          {agentType === 'regular' && (
            <ConfigSection
              title="Middleware (Advanced)"
              icon={<Zap className="w-5 h-5" />}
              expanded={expandedSections.middleware}
              onToggle={() => toggleSection('middleware')}
            >
              <div className="space-y-4">
                <p className="text-xs text-gray-600 dark:text-gray-400">
                  Add middleware to enhance agent capabilities with logging, cost tracking, validation, and more.
                </p>

                {/* Available Middleware to Add */}
                <div>
                  <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-2 uppercase">
                    Add Middleware
                  </label>
                  <div className="grid grid-cols-1 gap-2">
                    <button
                      onClick={() => addRegularAgentMiddleware('logging', { log_inputs: true, log_outputs: true, max_log_length: 500 })}
                      className="flex items-start gap-3 p-3 text-left bg-gray-50 dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg hover:bg-gray-100 dark:hover:bg-white/5 transition-colors"
                    >
                      <Plus className="w-4 h-4 mt-0.5 flex-shrink-0 text-gray-500" />
                      <div className="flex-1">
                        <div className="text-sm font-medium text-gray-900 dark:text-white">Logging</div>
                        <div className="text-xs text-gray-600 dark:text-gray-400 mt-0.5">Record agent inputs and outputs for debugging and monitoring. Configurable log length limits.</div>
                      </div>
                    </button>
                    <button
                      onClick={() => addRegularAgentMiddleware('cost_tracking', {})}
                      className="flex items-start gap-3 p-3 text-left bg-gray-50 dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg hover:bg-gray-100 dark:hover:bg-white/5 transition-colors"
                    >
                      <Plus className="w-4 h-4 mt-0.5 flex-shrink-0 text-gray-500" />
                      <div className="flex-1">
                        <div className="text-sm font-medium text-gray-900 dark:text-white">Cost Tracking</div>
                        <div className="text-xs text-gray-600 dark:text-gray-400 mt-0.5">Track token usage and API costs per agent execution. Provides detailed cost breakdowns by model and operation.</div>
                      </div>
                    </button>
                    <button
                      onClick={() => addRegularAgentMiddleware('validation', { min_length: null, max_length: null })}
                      className="flex items-start gap-3 p-3 text-left bg-gray-50 dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg hover:bg-gray-100 dark:hover:bg-white/5 transition-colors"
                    >
                      <Plus className="w-4 h-4 mt-0.5 flex-shrink-0 text-gray-500" />
                      <div className="flex-1">
                        <div className="text-sm font-medium text-gray-900 dark:text-white">Validation</div>
                        <div className="text-xs text-gray-600 dark:text-gray-400 mt-0.5">Validate agent outputs against custom rules (length, format, content patterns). Automatically retry on validation failures.</div>
                      </div>
                    </button>
                    <button
                      onClick={() => addRegularAgentMiddleware('summarization', { model: 'gpt-4o-mini', max_tokens_before_summary: 1000, keep_last_n_messages: 5 })}
                      className="flex items-start gap-3 p-3 text-left bg-gray-50 dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg hover:bg-gray-100 dark:hover:bg-white/5 transition-colors"
                    >
                      <Plus className="w-4 h-4 mt-0.5 flex-shrink-0 text-gray-500" />
                      <div className="flex-1">
                        <div className="text-sm font-medium text-gray-900 dark:text-white">Summarization</div>
                        <div className="text-xs text-gray-600 dark:text-gray-400 mt-0.5">Automatically summarize long conversation histories to stay within context limits. Uses a smaller model for cost efficiency.</div>
                      </div>
                    </button>
                    <button
                      onClick={() => addRegularAgentMiddleware('hitl', { interrupt_on: {}, description: 'Human approval required' })}
                      className="flex items-start gap-3 p-3 text-left bg-gray-50 dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg hover:bg-gray-100 dark:hover:bg-white/5 transition-colors"
                    >
                      <Plus className="w-4 h-4 mt-0.5 flex-shrink-0 text-gray-500" />
                      <div className="flex-1">
                        <div className="text-sm font-medium text-gray-900 dark:text-white">Human-in-the-Loop</div>
                        <div className="text-xs text-gray-600 dark:text-gray-400 mt-0.5">Pause execution for human review and approval before critical actions. Configure which operations require approval.</div>
                      </div>
                    </button>
                    <button
                      onClick={() => addRegularAgentMiddleware('tool_retry', { max_retries: 3, backoff_factor: 2.0 })}
                      className="flex items-start gap-3 p-3 text-left bg-gray-50 dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg hover:bg-gray-100 dark:hover:bg-white/5 transition-colors"
                    >
                      <Plus className="w-4 h-4 mt-0.5 flex-shrink-0 text-gray-500" />
                      <div className="flex-1">
                        <div className="text-sm font-medium text-gray-900 dark:text-white">Tool Retry</div>
                        <div className="text-xs text-gray-600 dark:text-gray-400 mt-0.5">Automatically retry failed tool calls with exponential backoff. Handles transient errors and rate limits gracefully.</div>
                      </div>
                    </button>
                    <button
                      onClick={() => addRegularAgentMiddleware('pii', { patterns: null, replacement: '[REDACTED]', store_mappings: false })}
                      className="flex items-start gap-3 p-3 text-left bg-gray-50 dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg hover:bg-gray-100 dark:hover:bg-white/5 transition-colors"
                    >
                      <Plus className="w-4 h-4 mt-0.5 flex-shrink-0 text-gray-500" />
                      <div className="flex-1">
                        <div className="text-sm font-medium text-gray-900 dark:text-white">PII Redaction</div>
                        <div className="text-xs text-gray-600 dark:text-gray-400 mt-0.5">Automatically detect and redact personally identifiable information (emails, phone numbers, SSNs) from agent inputs and outputs.</div>
                      </div>
                    </button>
                    <button
                      onClick={() => addRegularAgentMiddleware('timestamp', { timezone: 'UTC', format: '%Y-%m-%d %H:%M:%S' })}
                      className="flex items-start gap-3 p-3 text-left bg-gray-50 dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg hover:bg-gray-100 dark:hover:bg-white/5 transition-colors"
                    >
                      <Plus className="w-4 h-4 mt-0.5 flex-shrink-0 text-gray-500" />
                      <div className="flex-1">
                        <div className="text-sm font-medium text-gray-900 dark:text-white">Timestamp Injection</div>
                        <div className="text-xs text-gray-600 dark:text-gray-400 mt-0.5">Inject current timestamp into agent context. Helps agents understand temporal context for time-sensitive tasks.</div>
                      </div>
                    </button>
                    <button
                      onClick={() => addRegularAgentMiddleware('project_context', {})}
                      className="flex items-start gap-3 p-3 text-left bg-gray-50 dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg hover:bg-gray-100 dark:hover:bg-white/5 transition-colors"
                    >
                      <Plus className="w-4 h-4 mt-0.5 flex-shrink-0 text-gray-500" />
                      <div className="flex-1">
                        <div className="text-sm font-medium text-gray-900 dark:text-white">Project Context</div>
                        <div className="text-xs text-gray-600 dark:text-gray-400 mt-0.5">Inject project-specific context (workspace path, project name, active files) into agent prompts for better awareness.</div>
                      </div>
                    </button>
                  </div>
                </div>

                {/* Active Middleware List */}
                {(config.middleware || []).length > 0 && (
                  <div className="space-y-3">
                    <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 uppercase">
                      Active Middleware ({(config.middleware || []).length})
                    </label>
                    {(config.middleware || []).map((mw: MiddlewareConfig, index: number) => (
                      <div
                        key={index}
                        className="border border-gray-200 dark:border-border-dark rounded-lg overflow-hidden"
                      >
                        {/* Header */}
                        <div className="flex items-center justify-between p-3 bg-gray-50 dark:bg-background-dark">
                          <div className="flex items-center gap-3">
                            <input
                              type="checkbox"
                              checked={mw.enabled}
                              onChange={() => toggleRegularMiddleware(index)}
                            />
                            <div>
                              <div className="text-sm font-medium text-gray-900 dark:text-white capitalize">
                                {mw.type.replace('_', ' ')}
                              </div>
                            </div>
                          </div>
                          <button
                            onClick={() => removeRegularAgentMiddleware(index)}
                            className="p-1 text-red-500 hover:text-red-700 transition-colors"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>

                        {/* Config panel */}
                        {mw.enabled && (
                          <div className="p-4 border-t border-gray-200 dark:border-border-dark bg-white dark:bg-panel-dark space-y-3">
                            {/* Logging Config */}
                            {mw.type === 'logging' && (
                              <>
                                <div>
                                  <label className="flex items-center gap-2 text-sm font-medium text-gray-900 dark:text-white">
                                    <input
                                      type="checkbox"
                                      checked={mw.config.log_inputs ?? true}
                                      onChange={(e) => {
                                        const middleware = [...config.middleware];
                                        middleware[index].config.log_inputs = e.target.checked;
                                        setConfig(prev => ({ ...prev, middleware }));
                                      }}
                                    />
                                    Log Inputs
                                  </label>
                                </div>
                                <div>
                                  <label className="flex items-center gap-2 text-sm font-medium text-gray-900 dark:text-white">
                                    <input
                                      type="checkbox"
                                      checked={mw.config.log_outputs ?? true}
                                      onChange={(e) => {
                                        const middleware = [...config.middleware];
                                        middleware[index].config.log_outputs = e.target.checked;
                                        setConfig(prev => ({ ...prev, middleware }));
                                      }}
                                    />
                                    Log Outputs
                                  </label>
                                </div>
                                <div>
                                  <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-2 uppercase">
                                    Max Log Length
                                  </label>
                                  <input
                                    type="number"
                                    value={mw.config.max_log_length ?? 500}
                                    onChange={(e) => {
                                      const middleware = [...config.middleware];
                                      middleware[index].config.max_log_length = parseInt(e.target.value);
                                      setConfig(prev => ({ ...prev, middleware }));
                                    }}
                                    className="w-full px-3 py-2 bg-white dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg text-sm"
                                  />
                                </div>
                              </>
                            )}

                            {/* Cost Tracking has no config */}
                            {mw.type === 'cost_tracking' && (
                              <p className="text-xs text-gray-600 dark:text-gray-400">
                                Tracks estimated costs for model usage. No configuration needed.
                              </p>
                            )}

                            {/* Validation Config */}
                            {mw.type === 'validation' && (
                              <>
                                <div>
                                  <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-2 uppercase">
                                    Min Length (optional)
                                  </label>
                                  <input
                                    type="number"
                                    value={mw.config.min_length ?? ''}
                                    onChange={(e) => {
                                      const middleware = [...config.middleware];
                                      middleware[index].config.min_length = e.target.value ? parseInt(e.target.value) : null;
                                      setConfig(prev => ({ ...prev, middleware }));
                                    }}
                                    placeholder="Leave empty for no minimum"
                                    className="w-full px-3 py-2 bg-white dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg text-sm"
                                  />
                                </div>
                                <div>
                                  <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-2 uppercase">
                                    Max Length (optional)
                                  </label>
                                  <input
                                    type="number"
                                    value={mw.config.max_length ?? ''}
                                    onChange={(e) => {
                                      const middleware = [...config.middleware];
                                      middleware[index].config.max_length = e.target.value ? parseInt(e.target.value) : null;
                                      setConfig(prev => ({ ...prev, middleware }));
                                    }}
                                    placeholder="Leave empty for no maximum"
                                    className="w-full px-3 py-2 bg-white dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg text-sm"
                                  />
                                </div>
                              </>
                            )}

                            {/* Summarization Config */}
                            {mw.type === 'summarization' && (
                              <>
                                <div>
                                  <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-2 uppercase">
                                    Summary Model
                                  </label>
                                  <input
                                    type="text"
                                    value={mw.config.model ?? 'gpt-4o-mini'}
                                    onChange={(e) => {
                                      const middleware = [...config.middleware];
                                      middleware[index].config.model = e.target.value;
                                      setConfig(prev => ({ ...prev, middleware }));
                                    }}
                                    className="w-full px-3 py-2 bg-white dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg text-sm"
                                  />
                                </div>
                                <div>
                                  <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-2 uppercase">
                                    Max Tokens Before Summary
                                  </label>
                                  <input
                                    type="number"
                                    value={mw.config.max_tokens_before_summary ?? 1000}
                                    onChange={(e) => {
                                      const middleware = [...config.middleware];
                                      middleware[index].config.max_tokens_before_summary = parseInt(e.target.value);
                                      setConfig(prev => ({ ...prev, middleware }));
                                    }}
                                    className="w-full px-3 py-2 bg-white dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg text-sm"
                                  />
                                </div>
                                <div>
                                  <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-2 uppercase">
                                    Keep Last N Messages
                                  </label>
                                  <input
                                    type="number"
                                    value={mw.config.keep_last_n_messages ?? 5}
                                    onChange={(e) => {
                                      const middleware = [...config.middleware];
                                      middleware[index].config.keep_last_n_messages = parseInt(e.target.value);
                                      setConfig(prev => ({ ...prev, middleware }));
                                    }}
                                    className="w-full px-3 py-2 bg-white dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg text-sm"
                                  />
                                </div>
                              </>
                            )}

                            {/* HITL Config */}
                            {mw.type === 'hitl' && (
                              <>
                                <div>
                                  <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-2 uppercase">
                                    Description
                                  </label>
                                  <input
                                    type="text"
                                    value={mw.config.description ?? 'Human approval required'}
                                    onChange={(e) => {
                                      const middleware = [...config.middleware];
                                      middleware[index].config.description = e.target.value;
                                      setConfig(prev => ({ ...prev, middleware }));
                                    }}
                                    className="w-full px-3 py-2 bg-white dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg text-sm"
                                  />
                                </div>
                                <p className="text-xs text-gray-600 dark:text-gray-400">
                                  Configure tool-specific interrupts in the interrupt_on field (requires manual JSON editing)
                                </p>
                              </>
                            )}

                            {/* Tool Retry Config */}
                            {mw.type === 'tool_retry' && (
                              <>
                                <div>
                                  <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-2 uppercase">
                                    Max Retries
                                  </label>
                                  <input
                                    type="number"
                                    value={mw.config.max_retries ?? 3}
                                    onChange={(e) => {
                                      const middleware = [...config.middleware];
                                      middleware[index].config.max_retries = parseInt(e.target.value);
                                      setConfig(prev => ({ ...prev, middleware }));
                                    }}
                                    min="1"
                                    max="10"
                                    className="w-full px-3 py-2 bg-white dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg text-sm"
                                  />
                                </div>
                                <div>
                                  <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-2 uppercase">
                                    Backoff Factor
                                  </label>
                                  <input
                                    type="number"
                                    value={mw.config.backoff_factor ?? 2.0}
                                    onChange={(e) => {
                                      const middleware = [...config.middleware];
                                      middleware[index].config.backoff_factor = parseFloat(e.target.value);
                                      setConfig(prev => ({ ...prev, middleware }));
                                    }}
                                    step="0.1"
                                    min="1"
                                    max="5"
                                    className="w-full px-3 py-2 bg-white dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg text-sm"
                                  />
                                </div>
                              </>
                            )}

                            {/* PII Config */}
                            {mw.type === 'pii' && (
                              <>
                                <div>
                                  <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-2 uppercase">
                                    Replacement Text
                                  </label>
                                  <input
                                    type="text"
                                    value={mw.config.replacement ?? '[REDACTED]'}
                                    onChange={(e) => {
                                      const middleware = [...config.middleware];
                                      middleware[index].config.replacement = e.target.value;
                                      setConfig(prev => ({ ...prev, middleware }));
                                    }}
                                    className="w-full px-3 py-2 bg-white dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg text-sm"
                                  />
                                </div>
                                <div>
                                  <label className="flex items-center gap-2 text-sm font-medium text-gray-900 dark:text-white">
                                    <input
                                      type="checkbox"
                                      checked={mw.config.store_mappings ?? false}
                                      onChange={(e) => {
                                        const middleware = [...config.middleware];
                                        middleware[index].config.store_mappings = e.target.checked;
                                        setConfig(prev => ({ ...prev, middleware }));
                                      }}
                                    />
                                    Store Redaction Mappings
                                  </label>
                                  <p className="text-xs text-gray-600 dark:text-gray-400 mt-1 ml-6">
                                    Store original values for potential restoration
                                  </p>
                                </div>
                                <p className="text-xs text-gray-600 dark:text-gray-400">
                                  Patterns: email, phone, ssn, credit_card, api_key, ip_address, password
                                </p>
                              </>
                            )}

                            {/* Timestamp Config */}
                            {mw.type === 'timestamp' && (
                              <>
                                <div>
                                  <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-2 uppercase">
                                    Timezone
                                  </label>
                                  <input
                                    type="text"
                                    value={mw.config.timezone ?? 'UTC'}
                                    onChange={(e) => {
                                      const middleware = [...config.middleware];
                                      middleware[index].config.timezone = e.target.value;
                                      setConfig(prev => ({ ...prev, middleware }));
                                    }}
                                    className="w-full px-3 py-2 bg-white dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg text-sm"
                                  />
                                </div>
                                <div>
                                  <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-2 uppercase">
                                    Format
                                  </label>
                                  <input
                                    type="text"
                                    value={mw.config.format ?? '%Y-%m-%d %H:%M:%S'}
                                    onChange={(e) => {
                                      const middleware = [...config.middleware];
                                      middleware[index].config.format = e.target.value;
                                      setConfig(prev => ({ ...prev, middleware }));
                                    }}
                                    className="w-full px-3 py-2 bg-white dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg text-sm"
                                  />
                                  <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">
                                    Python strftime format
                                  </p>
                                </div>
                              </>
                            )}

                            {/* Project Context has no config */}
                            {mw.type === 'project_context' && (
                              <p className="text-xs text-gray-600 dark:text-gray-400">
                                Injects project and task metadata into model context. No configuration needed.
                              </p>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </ConfigSection>
          )}

          {/* Middleware - Deep Agent Only */}
          {agentType === 'deep' && (
            <ConfigSection
              title="Middleware"
              icon={<Zap className="w-5 h-5" />}
              expanded={expandedSections.middleware}
              onToggle={() => toggleSection('middleware')}
            >
              <div className="space-y-3">
                {config.middleware.map((mw, index) => (
                  <div
                    key={index}
                    className="border border-gray-200 dark:border-border-dark rounded-lg overflow-hidden"
                  >
                    {/* Header with toggle */}
                    <div className="flex items-center justify-between p-3 bg-gray-50 dark:bg-background-dark">
                      <div className="flex items-center gap-3">
                        <input
                          type="checkbox"
                          checked={mw.enabled}
                          onChange={() => toggleMiddleware(index)}
                        />
                        <div>
                          <div className="text-sm font-medium text-gray-900 dark:text-white capitalize">
                            {mw.type.replace('_', ' ')}
                          </div>
                          <div className="text-xs text-gray-600 dark:text-gray-400">
                            {mw.type === 'todo_list' && 'Automatically create and track tasks as the agent works. Provides structured task management with status tracking (pending, in_progress, completed).'}
                            {mw.type === 'filesystem' && (
                              <span>
                                Enables filesystem tools: <code className="text-xs bg-gray-100 dark:bg-gray-700 px-1 rounded">ls</code>, <code className="text-xs bg-gray-100 dark:bg-gray-700 px-1 rounded">read_file</code>, <code className="text-xs bg-gray-100 dark:bg-gray-700 px-1 rounded">write_file</code>, <code className="text-xs bg-gray-100 dark:bg-gray-700 px-1 rounded">edit_file</code>, <code className="text-xs bg-gray-100 dark:bg-gray-700 px-1 rounded">glob</code>, <code className="text-xs bg-gray-100 dark:bg-gray-700 px-1 rounded">grep</code>. Also auto-evicts large outputs to disk.
                              </span>
                            )}
                            {mw.type === 'subagent' && 'Dynamically spawn specialized sub-agents for complex tasks. Enables hierarchical agent architectures with task delegation and result aggregation.'}
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Configuration panel (shown when enabled) */}
                    {mw.enabled && (
                      <div className="p-4 border-t border-gray-200 dark:border-border-dark bg-white dark:bg-panel-dark space-y-3">
                        {/* TodoList Config */}
                        {mw.type === 'todo_list' && (
                          <div>
                            <label className="flex items-center gap-2 text-sm font-medium text-gray-900 dark:text-white">
                              <input
                                type="checkbox"
                                checked={mw.config.auto_track ?? true}
                                onChange={(e) => {
                                  const newMiddleware = [...config.middleware];
                                  newMiddleware[index].config.auto_track = e.target.checked;
                                  setConfig(prev => ({ ...prev, middleware: newMiddleware }));
                                }}
                              />
                              Auto-track Tasks
                            </label>
                            <p className="text-xs text-gray-600 dark:text-gray-400 mt-1 ml-6">
                              Automatically track tasks as the agent works
                            </p>
                          </div>
                        )}

                        {/* Filesystem Config */}
                        {mw.type === 'filesystem' && (
                          <>
                            <div>
                              <label className="flex items-center gap-2 text-sm font-medium text-gray-900 dark:text-white">
                                <input
                                  type="checkbox"
                                  checked={mw.config.auto_eviction ?? true}
                                  onChange={(e) => {
                                    const newMiddleware = [...config.middleware];
                                    newMiddleware[index].config.auto_eviction = e.target.checked;
                                    setConfig(prev => ({ ...prev, middleware: newMiddleware }));
                                  }}
                                />
                                Auto-eviction to Filesystem
                              </label>
                              <p className="text-xs text-gray-600 dark:text-gray-400 mt-1 ml-6">
                                Automatically save large tool outputs/results to disk when they exceed the size threshold
                              </p>
                            </div>
                            <div>
                              <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-2 uppercase">
                                File Size Threshold (bytes)
                              </label>
                              <input
                                type="number"
                                value={mw.config.eviction_threshold_bytes ?? 1000000}
                                onChange={(e) => {
                                  const newMiddleware = [...config.middleware];
                                  newMiddleware[index].config.eviction_threshold_bytes = parseInt(e.target.value);
                                  setConfig(prev => ({ ...prev, middleware: newMiddleware }));
                                }}
                                min="0"
                                step="100000"
                                className="w-full px-3 py-2 bg-white dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg text-sm text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
                              />
                              <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">
                                Tool outputs larger than this will be saved to disk (Default: 1MB)
                              </p>
                            </div>
                          </>
                        )}

                        {/* SubAgent Config */}
                        {mw.type === 'subagent' && (
                          <>
                            <div>
                              <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-2 uppercase">
                                Max Depth
                              </label>
                              <input
                                type="number"
                                value={mw.config.max_depth ?? 3}
                                onChange={(e) => {
                                  const newMiddleware = [...config.middleware];
                                  newMiddleware[index].config.max_depth = parseInt(e.target.value);
                                  setConfig(prev => ({ ...prev, middleware: newMiddleware }));
                                }}
                                min="1"
                                max="10"
                                className="w-full px-3 py-2 bg-white dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg text-sm text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
                              />
                              <div className="mt-2 p-2 rounded bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700">
                                <p className="text-xs text-gray-600 dark:text-gray-400">
                                  <strong>Subagent nesting:</strong> Agent → SubAgent → Sub-SubAgent
                                </p>
                                <p className="text-xs text-gray-500 dark:text-gray-500 mt-1">
                                  Depth 3 (default) = Agent can spawn subagents 3 levels deep. Prevents infinite delegation loops.
                                </p>
                              </div>
                            </div>
                            <div>
                              <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-2 uppercase">
                                Max Concurrent Subagents
                              </label>
                              <input
                                type="number"
                                value={mw.config.max_concurrent ?? 5}
                                onChange={(e) => {
                                  const newMiddleware = [...config.middleware];
                                  newMiddleware[index].config.max_concurrent = parseInt(e.target.value);
                                  setConfig(prev => ({ ...prev, middleware: newMiddleware }));
                                }}
                                min="1"
                                max="20"
                                className="w-full px-3 py-2 bg-white dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg text-sm text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
                              />
                              <div className="mt-2 p-2 rounded bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700">
                                <p className="text-xs text-gray-600 dark:text-gray-400">
                                  <strong>Concurrent = running at the same time.</strong> Default: 5
                                </p>
                                <p className="text-xs text-gray-500 dark:text-gray-500 mt-1">
                                  Higher = faster parallel work, but uses more tokens/memory. Lower if hitting recursion limits.
                                </p>
                              </div>
                            </div>
                          </>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </ConfigSection>
          )}

          {/* Available Tools Reference - Deep Agent Only */}
          {agentType === 'deep' && (
            <ConfigSection
              title="Available Tools Reference"
              icon={<Wrench className="w-5 h-5" />}
              expanded={expandedSections.tools || false}
              onToggle={() => toggleSection('tools')}
            >
              <div className="space-y-4">
                <div className="flex items-start gap-2 p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
                  <Info className="w-4 h-4 text-blue-600 dark:text-blue-400 mt-0.5 flex-shrink-0" />
                  <p className="text-xs text-blue-700 dark:text-blue-300">
                    DeepAgents have access to the tools below based on enabled middleware. If your agent tries to call a tool that isn't available, enable the corresponding middleware.
                  </p>
                </div>

                {/* Filesystem Tools */}
                <div>
                  <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-2 flex items-center gap-2">
                    Filesystem Tools
                    <span className="text-xs px-2 py-0.5 bg-gray-100 dark:bg-gray-700 rounded">
                      {config.middleware?.find(m => m.type === 'filesystem')?.enabled ? 'Enabled' : 'Disabled'}
                    </span>
                  </h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    {[
                      { name: 'ls', desc: 'List directory contents with metadata' },
                      { name: 'read_file', desc: 'Read file contents with line numbers' },
                      { name: 'write_file', desc: 'Create new files with content' },
                      { name: 'edit_file', desc: 'Exact string replacement in files' },
                      { name: 'glob', desc: 'Find files matching patterns' },
                      { name: 'grep', desc: 'Search file contents with regex' },
                    ].map(tool => (
                      <div key={tool.name} className="flex items-start gap-2 p-2 bg-gray-50 dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700">
                        <code className="text-xs font-mono bg-gray-200 dark:bg-gray-700 px-1.5 py-0.5 rounded text-gray-800 dark:text-gray-200">
                          {tool.name}
                        </code>
                        <span className="text-xs text-gray-600 dark:text-gray-400">{tool.desc}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Task Management Tools */}
                <div>
                  <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-2 flex items-center gap-2">
                    Task Management
                    <span className="text-xs px-2 py-0.5 bg-gray-100 dark:bg-gray-700 rounded">
                      {config.middleware?.find(m => m.type === 'todo_list')?.enabled ? 'Enabled' : 'Disabled'}
                    </span>
                  </h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    <div className="flex items-start gap-2 p-2 bg-gray-50 dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700">
                      <code className="text-xs font-mono bg-gray-200 dark:bg-gray-700 px-1.5 py-0.5 rounded text-gray-800 dark:text-gray-200">
                        write_todos
                      </code>
                      <span className="text-xs text-gray-600 dark:text-gray-400">Create and update task lists</span>
                    </div>
                  </div>
                </div>

                {/* Web Tools */}
                <div>
                  <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-2 flex items-center gap-2">
                    Web Tools
                    <span className="text-xs px-2 py-0.5 bg-gray-100 dark:bg-gray-700 rounded">
                      {config.native_tools?.some(t => ['web_search', 'web_fetch'].includes(t)) ? 'Configured' : 'Not configured'}
                    </span>
                  </h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    {[
                      { name: 'web_search', desc: 'Search the web (DuckDuckGo)' },
                      { name: 'web_fetch', desc: 'Fetch webpage content' },
                    ].map(tool => (
                      <div key={tool.name} className="flex items-start gap-2 p-2 bg-gray-50 dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700">
                        <code className="text-xs font-mono bg-gray-200 dark:bg-gray-700 px-1.5 py-0.5 rounded text-gray-800 dark:text-gray-200">
                          {tool.name}
                        </code>
                        <span className="text-xs text-gray-600 dark:text-gray-400">{tool.desc}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <p className="text-xs text-gray-500 dark:text-gray-500 mt-2">
                  See <a href="https://docs.langchain.com/oss/python/deepagents/harness" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">DeepAgents Harness docs</a> for full tool documentation.
                </p>
              </div>
            </ConfigSection>
          )}

          {/* Memory & Storage - Deep Agent Only */}
          {agentType === 'deep' && (
            <ConfigSection
              title="Memory & Storage"
              icon={<Database className="w-5 h-5" />}
              expanded={expandedSections.backend}
              onToggle={() => toggleSection('backend')}
            >
              <div>
                <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-2 uppercase">
                  Select Storage Backends
                </label>
                <p className="text-xs text-gray-600 dark:text-gray-400 mb-3">
                  Choose one or more backends. Multiple selections will automatically create a Composite backend with path-based routing.
                </p>
                <div className="space-y-2">
                  {BACKEND_TYPES.filter(b => b.id !== 'composite').map(backend => {
                    const isSelected = (() => {
                      if (config.backend.type === backend.id) return true;
                      if (config.backend.type === 'composite' && config.backend.mappings) {
                        return Object.values(config.backend.mappings).some(
                          (m: any) => m.type === backend.id
                        );
                      }
                      return false;
                    })();

                    return (
                      <label
                        key={backend.id}
                        className={`flex items-start gap-3 p-3 border rounded-lg cursor-pointer transition-colors ${isSelected
                          ? 'bg-primary/10 border-primary dark:border-primary'
                          : 'bg-gray-50 dark:bg-background-dark border-gray-200 dark:border-border-dark hover:bg-gray-100 dark:hover:bg-white/5'
                          }`}
                      >
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleBackend(backend.id)}
                          className="mt-0.5"
                        />
                        <div className="flex-1">
                          <div className="text-sm font-medium text-gray-900 dark:text-white">{backend.name}</div>
                          <div className="text-xs text-gray-600 dark:text-gray-400">{backend.description}</div>
                        </div>
                      </label>
                    );
                  })}
                </div>

                {/* Show composite info if multiple selected */}
                {config.backend.type === 'composite' && config.backend.mappings && (
                  <div className="mt-4 p-3 bg-blue-50 dark:bg-blue-500/10 border border-blue-200 dark:border-blue-500/30 rounded-lg">
                    <div className="flex items-start gap-2 mb-2">
                      <Database className="w-4 h-4 text-blue-600 dark:text-blue-400 mt-0.5" />
                      <div className="flex-1">
                        <div className="text-sm font-medium text-blue-900 dark:text-blue-300">
                          Composite Backend Active
                        </div>
                        <div className="text-xs text-blue-700 dark:text-blue-400 mt-1">
                          Using {Object.keys(config.backend.mappings).length} backend(s) with automatic path routing:
                        </div>
                      </div>
                    </div>
                    <div className="ml-6 space-y-1">
                      {Object.entries(config.backend.mappings).map(([path, backendConfig]: [string, any]) => (
                        <div key={path} className="text-xs text-blue-700 dark:text-blue-400 font-mono">
                          <span className="font-semibold">{path}</span> → {backendConfig.type}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Long-term Memory */}
                <div className="mt-4">
                  <label className="flex items-center gap-2 text-sm font-medium text-gray-900 dark:text-white">
                    <input
                      type="checkbox"
                      checked={config.guardrails.long_term_memory}
                      onChange={(e) => updateConfig('guardrails', {
                        ...config.guardrails,
                        long_term_memory: e.target.checked
                      })}
                    />
                    Long-term Memory (Workflow-Scoped)
                  </label>
                  <p className="text-xs text-gray-600 dark:text-gray-400 mt-1 ml-6">
                    Enable persistent memory across sessions using LangGraph Store. The agent can remember context from previous workflow executions. Memory is isolated per workflow.
                  </p>
                </div>
              </div>
            </ConfigSection>
          )}

          {/* Guardrails & Safety - Deep Agent Only */}
          {agentType === 'deep' && (
            <ConfigSection
              title="Guardrails & Safety"
              icon={<Shield className="w-5 h-5" />}
              expanded={expandedSections.guardrails}
              onToggle={() => toggleSection('guardrails')}
            >
              <div className="space-y-4">
                <div>
                  <label className="flex items-center gap-2 text-sm font-medium text-gray-900 dark:text-white">
                    <input
                      type="checkbox"
                      checked={config.guardrails.enable_auto_eviction}
                      onChange={(e) => updateConfig('guardrails', {
                        ...config.guardrails,
                        enable_auto_eviction: e.target.checked
                      })}
                    />
                    Auto-eviction of Context (Token Management)
                  </label>
                  <p className="text-xs text-gray-600 dark:text-gray-400 mt-1 ml-6">
                    Automatically remove old conversation messages/context from memory when token limits are reached
                  </p>
                </div>

                <div>
                  <label className="flex items-center gap-2 text-sm font-medium text-gray-900 dark:text-white">
                    <input
                      type="checkbox"
                      checked={config.guardrails.enable_summarization}
                      onChange={(e) => updateConfig('guardrails', {
                        ...config.guardrails,
                        enable_summarization: e.target.checked
                      })}
                    />
                    Auto-summarization
                  </label>
                  <p className="text-xs text-gray-600 dark:text-gray-400 mt-1 ml-6">
                    Summarize long context to preserve token budget
                  </p>
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-2 uppercase">
                    Max Total Tokens
                  </label>
                  <input
                    type="number"
                    value={config.guardrails.token_limits.max_total_tokens}
                    onChange={(e) => updateConfig('guardrails', {
                      ...config.guardrails,
                      token_limits: {
                        ...config.guardrails.token_limits,
                        max_total_tokens: parseInt(e.target.value)
                      }
                    })}
                    className="w-full px-3 py-2 bg-white dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg text-sm text-gray-900 dark:text-white"
                  />
                </div>

                {/* Context Window Mode Presets */}
                <div className="border-t border-gray-200 dark:border-border-dark pt-4">
                  <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-2 uppercase">
                    Context Window Mode
                  </label>
                  <select
                    value={config.guardrails.context_window_mode}
                    onChange={(e) => {
                      const mode = e.target.value as 'rapid' | 'balanced' | 'long-term';
                      // Auto-adjust settings based on mode
                      const presets = {
                        rapid: { max_total_tokens: 50000, preserve_recent_messages: 5 },
                        balanced: { max_total_tokens: 100000, preserve_recent_messages: 10 },
                        'long-term': { max_total_tokens: 200000, preserve_recent_messages: 20 }
                      };
                      updateConfig('guardrails', {
                        ...config.guardrails,
                        context_window_mode: mode,
                        token_limits: {
                          ...config.guardrails.token_limits,
                          max_total_tokens: presets[mode].max_total_tokens
                        },
                        preserve_recent_messages: presets[mode].preserve_recent_messages
                      });
                    }}
                    className="w-full px-3 py-2 bg-white dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg text-sm text-gray-900 dark:text-white"
                  >
                    <option value="rapid">Rapid Prototyping (50K tokens, faster)</option>
                    <option value="balanced">Balanced Testing (100K tokens, moderate)</option>
                    <option value="long-term">Long-term Testing (200K tokens, preserves more history)</option>
                  </select>
                  <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">
                    Choose preset based on your testing needs. Auto-adjusts token limits and preservation settings.
                  </p>
                </div>

                {/* Compaction Strategy - LangGraph methods */}
                <div>
                  <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-2 uppercase">
                    Context Compaction Strategy
                  </label>
                  <select
                    value={config.guardrails.compaction_strategy}
                    onChange={(e) => updateConfig('guardrails', {
                      ...config.guardrails,
                      compaction_strategy: e.target.value as 'none' | 'trim_messages' | 'summarization' | 'filter_custom'
                    })}
                    className="w-full px-3 py-2 bg-white dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg text-sm text-gray-900 dark:text-white"
                  >
                    <option value="none">None - Keep all messages</option>
                    <option value="trim_messages">Trim Messages - Remove old messages (LangGraph trim_messages)</option>
                    <option value="summarization">Summarization - Summarize earlier messages (LangGraph SummarizationNode)</option>
                    <option value="filter_custom">Filter Custom - Custom message filtering</option>
                  </select>
                  <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">
                    LangGraph compaction method for managing long conversations
                  </p>
                </div>

                {/* Trim Strategy (when using trim_messages) */}
                {config.guardrails.compaction_strategy === 'trim_messages' && (
                  <div className="pl-4 border-l-2 border-blue-500 dark:border-blue-400">
                    <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-2 uppercase">
                      Trim Strategy
                    </label>
                    <select
                      value={config.guardrails.trim_strategy}
                      onChange={(e) => updateConfig('guardrails', {
                        ...config.guardrails,
                        trim_strategy: e.target.value as 'first' | 'last' | 'oldest'
                      })}
                      className="w-full px-3 py-2 bg-white dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg text-sm text-gray-900 dark:text-white"
                    >
                      <option value="oldest">Remove Oldest - FIFO (first in, first out)</option>
                      <option value="first">Remove First - Keep most recent only</option>
                      <option value="last">Remove Last - Keep earliest context</option>
                    </select>
                  </div>
                )}

                {/* Preserve Recent Messages */}
                <div>
                  <label className="flex items-center justify-between text-xs font-medium text-gray-700 dark:text-gray-300 mb-2 uppercase">
                    <span>Preserve Recent Messages</span>
                    <span className="text-primary font-bold">{config.guardrails.preserve_recent_messages}</span>
                  </label>
                  <input
                    type="range"
                    min="0"
                    max="50"
                    step="5"
                    value={config.guardrails.preserve_recent_messages}
                    onChange={(e) => updateConfig('guardrails', {
                      ...config.guardrails,
                      preserve_recent_messages: parseInt(e.target.value)
                    })}
                    className="w-full"
                  />
                  <div className="flex justify-between text-xs text-gray-500 dark:text-gray-400 mt-1">
                    <span>None</span>
                    <span>Preserve most recent {config.guardrails.preserve_recent_messages} messages from compaction</span>
                    <span>50</span>
                  </div>
                </div>
              </div>
            </ConfigSection>
          )}

          {/* Action Buttons */}
          <div className="flex items-center justify-end gap-3 p-6 bg-white dark:bg-panel-dark border border-gray-200 dark:border-border-dark rounded-lg">
            {onTest && (
              <button
                onClick={handleTest}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 dark:bg-blue-500 text-white rounded-lg hover:bg-blue-700 dark:hover:bg-blue-600 transition-colors"
              >
                <Play className="w-4 h-4" />
                Test Chat
              </button>
            )}

            {onExport && (
              <button
                onClick={handleExport}
                className="flex items-center gap-2 px-4 py-2 bg-green-600 dark:bg-green-500 text-white rounded-lg hover:bg-green-700 dark:hover:bg-green-600 transition-colors"
              >
                <Download className="w-4 h-4" />
                Export
              </button>
            )}

            {onSave && (
              <button
                onClick={handleSave}
                className="flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-lg hover:opacity-90 transition-opacity"
              >
                <Save className="w-4 h-4" />
                Save Agent
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Unsaved Changes Indicator */}
      {hasUnsavedChanges && (
        <div className="fixed bottom-4 left-4 flex items-center gap-2 px-3 py-2 bg-yellow-100 dark:bg-yellow-900/30 border border-yellow-300 dark:border-yellow-700 rounded-lg shadow-lg z-50">
          <AlertTriangle className="w-4 h-4 text-yellow-600 dark:text-yellow-500" />
          <span className="text-sm font-medium text-yellow-700 dark:text-yellow-400">
            Unsaved changes
          </span>
        </div>
      )}

      {/* Discard Changes Confirmation Dialog */}
      {showDiscardDialog && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[100]">
          <div className="bg-white dark:bg-panel-dark rounded-xl shadow-2xl max-w-md w-full mx-4 overflow-hidden">
            <div className="p-6">
              <div className="flex items-center gap-3 mb-4">
                <div className="p-2 bg-yellow-100 dark:bg-yellow-900/30 rounded-full">
                  <AlertTriangle className="w-6 h-6 text-yellow-600 dark:text-yellow-500" />
                </div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                  Unsaved Changes
                </h3>
              </div>
              <p className="text-gray-600 dark:text-gray-400 mb-6">
                You have unsaved changes to this agent configuration. Are you sure you want to leave? Your changes will be lost.
              </p>
              <div className="flex justify-end gap-3">
                <button
                  onClick={handleCancelDiscard}
                  className="px-4 py-2 text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg transition-colors"
                >
                  Keep Editing
                </button>
                <button
                  onClick={handleConfirmDiscard}
                  className="px-4 py-2 text-white bg-red-600 hover:bg-red-700 rounded-lg transition-colors"
                >
                  Discard Changes
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Notification Modal */}
      <NotificationModal />
    </div>
  );
}

// ConfigSection Component
interface ConfigSectionProps {
  title: string;
  icon: React.ReactNode;
  expanded: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}

function ConfigSection({ title, icon, expanded, onToggle, children }: ConfigSectionProps) {
  return (
    <div className="border border-gray-200 dark:border-border-dark rounded-lg overflow-hidden bg-white dark:bg-panel-dark">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="text-primary">{icon}</div>
          <h3 className="font-semibold text-gray-900 dark:text-white">{title}</h3>
        </div>
        {expanded ? (
          <ChevronDown className="w-5 h-5 text-gray-600 dark:text-gray-400" />
        ) : (
          <ChevronRight className="w-5 h-5 text-gray-600 dark:text-gray-400" />
        )}
      </button>

      {expanded && (
        <div className="p-4 border-t border-gray-200 dark:border-border-dark space-y-4">
          {children}
        </div>
      )}
    </div>
  );
}
