/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useEffect } from 'react';
import { X, Settings, Plus, Trash2, ChevronDown, ChevronRight, Workflow, MessageSquare } from 'lucide-react';
import CustomToolBuilder from '@/features/tools/ui/CustomToolBuilder';
import { ModelSelectorInline } from '@/components/common/ModelSelector';
import apiClient from '@/lib/api-client';
import ContextPreviewModal from '@/components/workflows/ContextPreviewModal';

interface NodeConfig {
  id: string;
  name?: string;  // Display name for the agent node
  agentType: string;
  model: string;
  system_prompt: string;
  temperature: number;
  max_tokens?: number;  // Maximum tokens for agent output
  max_retries?: number;  // Maximum retries for failed tool calls
  recursion_limit?: number;  // Maximum recursion depth for agent execution
  tools: string[];  // Built-in tools
  native_tools: string[];  // Native Python tools
  custom_tools?: string[];  // User-created custom tools
  middleware?: any[];  // Middleware configuration
  subagents?: any[];  // Subagent configurations (Advanced: DeepAgents)
  use_deepagents?: boolean;  // Flag to enable DeepAgent mode
  condition?: string;  // For CONDITIONAL_NODE
  max_iterations?: number;  // For LOOP_NODE
  exit_condition?: string;  // For LOOP_NODE
  tool_type?: string;  // For TOOL_NODE - type of tool (custom, mcp, cli)
  tool_id?: string;  // For TOOL_NODE - specific tool identifier
  tool_params?: Record<string, any>;  // For TOOL_NODE - tool input parameters
  interrupt_before?: boolean; // HITL: Interrupt before execution
  interrupt_after?: boolean; // HITL: Interrupt after execution
  enable_structured_output?: boolean; // Structured Output
  output_schema_name?: string; // Structured Output Schema
  output_format?: 'json' | 'pydantic' | 'json_schema'; // Structured Output Format
  strict_mode?: boolean; // Structured Output Strict Mode
  debug?: boolean; // Advanced: Debug Mode
  cache?: boolean; // Advanced: Enable Cache
}

interface NodeConfigPanelProps {
  selectedNode: NodeConfig | null;
  onClose: () => void;
  onSave: (nodeId: string, config: any) => void;
  onDelete?: (nodeId: string) => void;
  availableModels?: string[];
  availableTools?: string[];
  tokenCostInfo?: {
    totalTokens: number;
    promptTokens: number;
    completionTokens: number;
    costString: string;
  };
}

// Available middleware types (LangChain 1.1) - matches backend middleware/core.py
const MIDDLEWARE_TYPES = [
  // Context Enhancement
  { id: 'timestamp', name: 'Timestamp Injection', description: 'Inject current time into agent context', category: 'Context' },
  { id: 'project_context', name: 'Project Context', description: 'Add project-specific context', category: 'Context' },

  // Monitoring & Debugging
  { id: 'logging', name: 'Request Logging', description: 'Log inputs and outputs for debugging', category: 'Monitoring' },
  { id: 'cost_tracking', name: 'Cost Tracking', description: 'Track token usage and API costs', category: 'Monitoring' },

  // Reliability (LangChain 1.1)
  { id: 'model_retry', name: 'Model Retry', description: 'Retry failed model calls with exponential backoff', category: 'Reliability' },
  { id: 'model_fallback', name: 'Model Fallback', description: 'Fall back to cheaper models on failure', category: 'Reliability' },
  { id: 'tool_retry', name: 'Tool Retry Logic', description: 'Automatically retry failed tool calls', category: 'Reliability' },

  // Security
  { id: 'validation', name: 'Input Validation', description: 'Validate inputs and outputs', category: 'Security' },
  { id: 'pii', name: 'PII Detection', description: 'Redact sensitive information from logs', category: 'Security' },
  { id: 'content_moderation', name: 'Content Moderation', description: 'OpenAI moderation for unsafe content', category: 'Security' },

  // Control
  { id: 'hitl', name: 'Human-in-Loop', description: 'Require human approval for actions', category: 'Control' },

  // Optimization (LangChain 1.1)
  { id: 'context_summarization', name: 'Dynamic Summarization', description: 'Auto-summarize at 80% context window', category: 'Optimization' },
  { id: 'summarization', name: 'Response Summarization', description: 'Summarize long conversations', category: 'Optimization' },
];

// Native Python Tools (local-first, no Node.js required)
// These map to backend/tools/native_tools.py with DeepAgents standard naming
// See: https://docs.langchain.com/oss/python/deepagents/harness
// Note: Memory tools (enable_memory, memory_store, memory_recall, enable_rag) moved to unified Context & Memory section
const AVAILABLE_TOOLS = [
  { id: 'web_search', name: 'Web Search', description: 'Search the web (DuckDuckGo)', category: 'web' },
  { id: 'web_fetch', name: 'Web Fetch', description: 'Fetch webpage content', category: 'web' },
  { id: 'browser', name: 'Browser Automation', description: 'Advanced web interaction (Playwright)', category: 'web' },
  // DeepAgents standard filesystem tools
  { id: 'read_file', name: 'Read File', description: 'Read file contents with line numbers', category: 'files' },
  { id: 'write_file', name: 'Write File', description: 'Create new files', category: 'files' },
  { id: 'ls', name: 'List Directory', description: 'List directory contents with metadata', category: 'files' },
  { id: 'edit_file', name: 'Edit File', description: 'Exact string replacements in files', category: 'files' },
  { id: 'glob', name: 'Glob', description: 'Find files matching patterns', category: 'files' },
  { id: 'grep', name: 'Grep', description: 'Search file contents with regex', category: 'files' },
  { id: 'reasoning_chain', name: 'Reasoning Chain', description: 'Multi-step reasoning', category: 'reasoning' },
];

// Legacy: Map old MCP tool names to new native tool names for backward compatibility
const LEGACY_TOOL_MAP: Record<string, string> = {
  'web': 'web_search',
  'fetch': 'web_fetch',
  'memory': 'memory_store',
  'sequential_thinking': 'reasoning_chain',
  'filesystem': 'read_file',  // Will show all file tools
  // Legacy filesystem tool aliases
  'file_read': 'read_file',
  'file_write': 'write_file',
  'file_list': 'ls',
};

const NodeConfigPanel = ({
  selectedNode,
  onClose,
  onSave,
  onDelete,
  availableModels = [],  // No longer used - ModelSelector fetches models directly
  availableTools = [],  // Tools now managed internally
  tokenCostInfo
}: NodeConfigPanelProps) => {
  const [config, setConfig] = useState<NodeConfig | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  // LangGraph HITL (Human-in-the-Loop) parameters
  const [interruptBefore, setInterruptBefore] = useState(false);
  const [interruptAfter, setInterruptAfter] = useState(false);

  // Structured output configuration
  const [enableStructuredOutput, setEnableStructuredOutput] = useState(false);
  const [outputSchemaName, setOutputSchemaName] = useState('');
  const [outputFormat, setOutputFormat] = useState<'json' | 'pydantic' | 'json_schema'>('json');
  const [strictMode, setStrictMode] = useState(true);
  const [availableSchemas, setAvailableSchemas] = useState<string[]>([]);

  // Advanced configuration
  const [debugMode, setDebugMode] = useState(false);
  const [enableCache, setEnableCache] = useState(true);
  const [enableParallelTools, setEnableParallelTools] = useState(true);

  // Control node configuration
  const [conditionExpression, setConditionExpression] = useState('');
  const [maxLoopIterations, setMaxLoopIterations] = useState(10);
  const [loopExitCondition, setLoopExitCondition] = useState('');
  const [recursionLimit, setRecursionLimit] = useState(75);

  // Context Window Management (LangChain 1.1)
  const [contextStrategy, setContextStrategy] = useState<'smart' | 'recent' | 'summary' | 'quarantine' | 'full'>('smart');
  const [maxContextTokens, setMaxContextTokens] = useState<number | null>(null);  // null = auto-detect from model
  const [enableAutoSummarization, setEnableAutoSummarization] = useState(true);

  // Long-Term Memory (unified section)
  const [enableLongTermMemory, setEnableLongTermMemory] = useState(false);
  const [enableMemoryStore, setEnableMemoryStore] = useState(true);  // Tool: save to memory (requires enableLongTermMemory)
  const [enableMemoryRecall, setEnableMemoryRecall] = useState(true); // Tool: recall from memory (requires enableLongTermMemory)

  // RAG (unified section)
  const [enableRAG, setEnableRAG] = useState(false);

  // Middleware configuration
  const [enabledMiddleware, setEnabledMiddleware] = useState<string[]>([]);

  // Agent name editing
  const [agentName, setAgentName] = useState('');

  // Custom tools
  const [availableCustomTools, setAvailableCustomTools] = useState<Array<{
    id: number,
    tool_id: string,
    name: string,
    description: string,
    implementation_config?: any,
    template_type?: string,
    tool_type?: string
  }>>([]);
  const [selectedCustomTools, setSelectedCustomTools] = useState<string[]>([]);

  // Skills
  const [availableSkills, setAvailableSkills] = useState<Array<{
    skill_id: string,
    name: string,
    description: string,
    tags: string[]
  }>>([]);
  const [selectedSkills, setSelectedSkills] = useState<string[]>([]);

  // Section collapse state
  const [middlewareCollapsed, setMiddlewareCollapsed] = useState(true);
  const [skillsCollapsed, setSkillsCollapsed] = useState(true);

  // Subagents configuration (Advanced: DeepAgents)
  const [subagents, setSubagents] = useState<Array<any>>([]);
  const [expandedSubagents, setExpandedSubagents] = useState<Set<number>>(new Set());
  const [availableWorkflows, setAvailableWorkflows] = useState<Array<{ id: number, name: string, description?: string }>>([]);

  // Tool Node configuration
  const [toolNodeAvailableTools, setToolNodeAvailableTools] = useState<{
    custom: Array<any>,
    mcp: Array<any>,
    cli: Array<any>
  }>({ custom: [], mcp: [], cli: [] });
  const [selectedToolType, setSelectedToolType] = useState<string | null>(null);
  const [selectedToolId, setSelectedToolId] = useState<string | null>(null);
  const [toolInputSchema, setToolInputSchema] = useState<any>(null);
  const [showToolConfigModal, setShowToolConfigModal] = useState(false);

  // Save feedback
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved'>('idle');

  // Conversation context configuration
  const [enableConversationContext, setEnableConversationContext] = useState(false);
  const [selectedDeepAgentId, setSelectedDeepAgentId] = useState<number | null>(null);
  const [contextMode, setContextMode] = useState<'recent' | 'smart' | 'full' | 'summary' | 'quarantine'>('smart');
  const [contextWindowSize, setContextWindowSize] = useState(20);
  const [deepAgents, setDeepAgents] = useState<Array<{
    id: number,
    name: string,
    description: string,
    chat_sessions_count: number
  }>>([]);
  const [showContextPreview, setShowContextPreview] = useState(false);
  const [deepAgentsFetched, setDeepAgentsFetched] = useState(false);

  // Fetch deep agents only when conversation context is enabled
  useEffect(() => {
    if (enableConversationContext && !deepAgentsFetched) {
      const fetchDeepAgents = async () => {
        try {
          const response = await apiClient.apiFetch(`${apiClient.baseURL}/api/deepagents/`);
          setDeepAgents(response || []);
          setDeepAgentsFetched(true);
        } catch (error) {
          // Silently fail - conversation context is optional
          setDeepAgentsFetched(true);
        }
      };
      fetchDeepAgents();
    }
  }, [enableConversationContext, deepAgentsFetched]);

  // Load tool schema for Tool Node
  const loadToolSchema = async (toolType: string, toolId: string) => {
    if (toolType === 'custom') {
      // Fetch from available custom tools (not toolNodeAvailableTools)
      const tool = availableCustomTools.find(t => t.tool_id === toolId);
      if (tool && (tool as any).input_schema) {
        setToolInputSchema((tool as any).input_schema);
      } else {
        setToolInputSchema(null);
      }
    } else if (toolType === 'mcp') {
      // MCP tools have simple schemas
      // DeepAgents standard tool schemas
      const mcpSchemas: Record<string, any> = {
        web_search: {
          type: 'object',
          properties: {
            query: { type: 'string', description: 'Search query' }
          },
          required: ['query']
        },
        read_file: {
          type: 'object',
          properties: {
            file_path: { type: 'string', description: 'Path to file' },
            max_chars: { type: 'number', description: 'Maximum characters to read (default: 50000)' }
          },
          required: ['file_path']
        },
        write_file: {
          type: 'object',
          properties: {
            file_path: { type: 'string', description: 'Path to file' },
            content: { type: 'string', description: 'Content to write' }
          },
          required: ['file_path', 'content']
        },
        ls: {
          type: 'object',
          properties: {
            directory_path: { type: 'string', description: 'Directory path (default: current dir)' },
            pattern: { type: 'string', description: 'Glob pattern for filtering' }
          },
          required: []
        },
        edit_file: {
          type: 'object',
          properties: {
            file_path: { type: 'string', description: 'Path to file' },
            old_string: { type: 'string', description: 'Text to find and replace' },
            new_string: { type: 'string', description: 'Replacement text' }
          },
          required: ['file_path', 'old_string', 'new_string']
        },
        glob: {
          type: 'object',
          properties: {
            pattern: { type: 'string', description: 'Glob pattern (e.g., "**/*.py")' },
            path: { type: 'string', description: 'Base path to search from' }
          },
          required: ['pattern']
        },
        grep: {
          type: 'object',
          properties: {
            pattern: { type: 'string', description: 'Regex pattern to search for' },
            path: { type: 'string', description: 'Directory to search in' },
            file_pattern: { type: 'string', description: 'Glob pattern to filter files' }
          },
          required: ['pattern']
        }
      };
      setToolInputSchema(mcpSchemas[toolId] || null);
    }
  };

  // Fetch available custom tools
  const fetchCustomTools = async (signal?: AbortSignal) => {
    try {
      const response = await apiClient.listCustomTools();
      setAvailableCustomTools(response.data || []);
    } catch (error) {
      console.error('Failed to fetch custom tools:', error);
    }
  };

  // Fetch available skills
  const fetchSkills = async (signal?: AbortSignal) => {
    try {
      const response = await apiClient.get('/api/skills/');
      setAvailableSkills(response.data || []);
    } catch (error) {
      console.error('Failed to fetch skills:', error);
    }
  };

  // Fetch available workflows for CompiledSubAgent
  useEffect(() => {
    const abortController = new AbortController();

    const fetchWorkflows = async () => {
      try {
        const response = await apiClient.listWorkflows();
        setAvailableWorkflows(response.data || []);
      } catch (error) {
        console.error('Failed to fetch workflows:', error);
      }
    };
    // Fetch available schemas
    const fetchSchemas = async () => {
      try {
        const response = await apiClient.apiFetch(`${apiClient.baseURL}/schemas/`, { signal: abortController.signal });
        setAvailableSchemas(response.names || []);
      } catch (error) {
        console.error('Failed to fetch schemas:', error);
      }
    };

    fetchSchemas();
    fetchCustomTools(abortController.signal);
    fetchSkills(abortController.signal);
    fetchWorkflows();

    return () => {
      abortController.abort();
    };
  }, []);

  // Fetch available tools for Tool Node
  useEffect(() => {
    const abortController = new AbortController();

    const fetchToolNodeTools = async () => {
      try {
        // Fetch custom tools
        const customToolsRes = await apiClient.listCustomTools();
        const customTools = customToolsRes.data || [];

        // MCP tools - DeepAgents standard naming
        const mcpTools = [
          { tool_id: 'web_search', name: 'Web Search', description: 'Search the web' },
          { tool_id: 'read_file', name: 'Read File', description: 'Read file contents with line numbers' },
          { tool_id: 'write_file', name: 'Write File', description: 'Create new files' },
          { tool_id: 'ls', name: 'List Directory', description: 'List directory contents with metadata' },
          { tool_id: 'edit_file', name: 'Edit File', description: 'Exact string replacements in files' },
          { tool_id: 'glob', name: 'Glob', description: 'Find files matching patterns' },
          { tool_id: 'grep', name: 'Grep', description: 'Search file contents with regex' }
        ];

        setToolNodeAvailableTools({ custom: customTools, mcp: mcpTools, cli: [] });
      } catch (error) {
        // Ignore abort errors
        if (error instanceof Error && error.name === 'AbortError') {
          return;
        }
        console.error('Failed to fetch tools:', error);
      }
    };

    fetchToolNodeTools();

    return () => {
      abortController.abort();
    };
  }, []);

  useEffect(() => {
    if (selectedNode) {
      // Ensure arrays are initialized
      // CRITICAL FIX: Check both top-level and nested config for tools
      // WorkflowCanvas stores tools in node.data.config.native_tools
      // But NodeConfigPanel expects them at node.data.native_tools
      const nodeConfig = (selectedNode as any).config || {};
      let nativeToolsList =
        (selectedNode as any).native_tools ||
        (selectedNode as any).nativeTools ||
        nodeConfig.native_tools ||
        nodeConfig.nativeTools ||
        (selectedNode as any).mcp_tools ||
        (selectedNode as any).mcpTools ||
        nodeConfig.mcp_tools ||
        nodeConfig.mcpTools ||
        [];

      // Add enable_memory and enable_rag back to UI if they're enabled in config
      // (They get filtered out when saving to backend, but need to be in UI for checkboxes)
      const enableMemory = (selectedNode as any).enable_memory || nodeConfig.enable_memory;
      const enableRag = (selectedNode as any).enable_rag || nodeConfig.enable_rag;
      if (enableMemory && !nativeToolsList.includes('enable_memory')) {
        nativeToolsList = [...nativeToolsList, 'enable_memory'];
      }
      if (enableRag && !nativeToolsList.includes('enable_rag')) {
        nativeToolsList = [...nativeToolsList, 'enable_rag'];
      }

      const normalizedNode = {
        ...selectedNode,
        ...nodeConfig,  // Spread config values to top level for easier access
        tools: selectedNode.tools || nodeConfig.tools || [],
        native_tools: nativeToolsList
      };

      setConfig(normalizedNode);

      // Load advanced configuration (check both top-level and config)
      setConditionExpression(selectedNode.condition || nodeConfig.condition || '');
      setMaxLoopIterations(selectedNode.max_iterations || nodeConfig.max_iterations || 10);
      setLoopExitCondition(selectedNode.exit_condition || nodeConfig.exit_condition || '');
      setRecursionLimit(selectedNode.recursion_limit || nodeConfig.recursion_limit || 300);
      setEnableParallelTools((selectedNode as any).enable_parallel_tools ?? nodeConfig.enable_parallel_tools ?? true);

      // Context Window Management (LangChain 1.1)
      setContextStrategy((selectedNode as any).context_management_strategy || nodeConfig.context_management_strategy || 'smart');
      setMaxContextTokens((selectedNode as any).max_context_tokens || nodeConfig.max_context_tokens || null);
      setEnableAutoSummarization((selectedNode as any).enable_auto_summarization ?? nodeConfig.enable_auto_summarization ?? true);

      // Long-Term Memory & RAG (unified section)
      // Check if memory tools are in native_tools array - if so, enable the toggle
      const hasMemoryStoreInTools = nativeToolsList.includes('memory_store');
      const hasMemoryRecallInTools = nativeToolsList.includes('memory_recall');
      const hasAnyMemoryTools = hasMemoryStoreInTools || hasMemoryRecallInTools;

      // Enable long-term memory if explicitly set OR if memory tools are present
      setEnableLongTermMemory(
        (selectedNode as any).enable_long_term_memory ??
        nodeConfig.enable_long_term_memory ??
        hasAnyMemoryTools
      );
      // Set store/recall based on explicit flags OR presence in native_tools
      setEnableMemoryStore(
        (selectedNode as any).enable_memory_store ??
        nodeConfig.enable_memory_store ??
        hasMemoryStoreInTools
      );
      setEnableMemoryRecall(
        (selectedNode as any).enable_memory_recall ??
        nodeConfig.enable_memory_recall ??
        hasMemoryRecallInTools
      );
      setEnableRAG((selectedNode as any).enable_rag ?? nodeConfig.enable_rag ?? false);

      // LangGraph HITL parameters
      setInterruptBefore(selectedNode.interrupt_before || nodeConfig.interrupt_before || false);
      setInterruptAfter(selectedNode.interrupt_after || nodeConfig.interrupt_after || false);
      setEnableStructuredOutput(selectedNode.enable_structured_output || nodeConfig.enable_structured_output || false);
      setOutputSchemaName(selectedNode.output_schema_name || nodeConfig.output_schema_name || '');
      setOutputFormat(selectedNode.output_format || nodeConfig.output_format || 'json');
      setStrictMode(selectedNode.strict_mode !== undefined ? selectedNode.strict_mode : (nodeConfig.strict_mode !== undefined ? nodeConfig.strict_mode : true));
      setDebugMode(selectedNode.debug || nodeConfig.debug || false);
      setEnableCache(selectedNode.cache !== undefined ? selectedNode.cache : (nodeConfig.cache !== undefined ? nodeConfig.cache : true));

      // Load middleware configuration
      const middlewareList = selectedNode.middleware || nodeConfig.middleware || [];
      setEnabledMiddleware(middlewareList.filter((m: any) => m.enabled).map((m: any) => m.type) || []);

      // Load agent name
      setAgentName(selectedNode.name || nodeConfig.name || selectedNode.id);

      // Load custom tools (check both locations)
      setSelectedCustomTools(selectedNode.custom_tools || nodeConfig.custom_tools || []);

      // Load subagents configuration (Advanced: DeepAgents)
      setSubagents(selectedNode.subagents || nodeConfig.subagents || []);

      // Tool Node configuration (instance-specific to this node)
      if (selectedNode.agentType === 'TOOL_NODE') {
        setSelectedToolType(selectedNode.tool_type || null);
        setSelectedToolId(selectedNode.tool_id || null);

        // Also initialize config with tool_params if they exist
        if (selectedNode.tool_params) {
          setConfig(prev => ({
            ...prev!,
            tool_params: selectedNode.tool_params
          }));
        }
      }

      // Load conversation context configuration
      setEnableConversationContext((selectedNode as any).enable_conversation_context || false);
      setSelectedDeepAgentId((selectedNode as any).deep_agent_template_id || null);
      setContextMode((selectedNode as any).context_mode || 'smart');
      setContextWindowSize((selectedNode as any).context_window_size || 20);

      setShowDeleteConfirm(false);
    }
  }, [selectedNode?.id]);

  // Load tool schema when both selectedNode and availableCustomTools are ready
  useEffect(() => {
    if (selectedNode?.agentType === 'TOOL_NODE' &&
      selectedNode.tool_type &&
      selectedNode.tool_id &&
      availableCustomTools.length > 0) {
      loadToolSchema(selectedNode.tool_type, selectedNode.tool_id);
    }
  }, [selectedNode?.tool_id, availableCustomTools.length]);

  if (!selectedNode || !config) {
    return (
      <aside className="w-96 bg-white dark:bg-panel-dark border-l border-gray-200 dark:border-border-dark flex items-center justify-center">
        <div className="text-center px-6">
          <span className="material-symbols-outlined text-gray-300 dark:text-gray-600 text-5xl mb-3 block">
            radio_button_unchecked
          </span>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Select a node to configure
          </p>
        </div>
      </aside>
    );
  }

  const handleSave = () => {
    if (config) {
      // Get native tools from config and sync with memory tool checkboxes
      let nativeTools = [...((config as any).native_tools || [])];

      // Sync memory tools with the checkbox states
      if (enableLongTermMemory) {
        // Add memory tools if enabled and not already present
        if (enableMemoryStore && !nativeTools.includes('memory_store')) {
          nativeTools.push('memory_store');
        }
        if (enableMemoryRecall && !nativeTools.includes('memory_recall')) {
          nativeTools.push('memory_recall');
        }
        // Remove memory tools if unchecked
        if (!enableMemoryStore) {
          nativeTools = nativeTools.filter(t => t !== 'memory_store');
        }
        if (!enableMemoryRecall) {
          nativeTools = nativeTools.filter(t => t !== 'memory_recall');
        }
      } else {
        // Long-term memory disabled - remove all memory tools
        nativeTools = nativeTools.filter(t => t !== 'memory_store' && t !== 'memory_recall');
      }

      // Build complete config object matching LangGraph/backend structure
      // DEBUG: Log what we're about to save

      const fullConfig = {
        // Agent identification
        name: agentName,

        // Core LangGraph parameters
        model: config.model,
        temperature: config.temperature,
        max_tokens: config.max_tokens || selectedNode?.max_tokens || 4000,  // Preserve dropdown changes
        max_retries: config.max_retries || selectedNode?.max_retries || 3,  // Preserve dropdown changes
        system_prompt: config.system_prompt,

        // Tools - now unified (no more separate "built-in" vs "MCP")
        // Backend expects mcp_tools, tools is deprecated but kept for compatibility
        tools: [],  // Deprecated, kept empty for backward compatibility
        native_tools: nativeTools,  // Native Python tools (memory flags handled in unified section)
        mcp_tools: [], // Deprecated in favor of native_tools
        custom_tools: selectedCustomTools,  // User-defined custom tools

        // Agent capabilities now handled in unified Context & Memory section below

        // LangGraph HITL parameters
        interrupt_before: interruptBefore,
        interrupt_after: interruptAfter,

        // Structured output
        enable_structured_output: enableStructuredOutput,
        output_schema_name: outputSchemaName || null,
        output_format: outputFormat,
        strict_mode: strictMode,

        // Advanced
        debug: debugMode,
        cache: enableCache,

        // Middleware (LangChain v1.0)
        middleware: enabledMiddleware.map(type => ({ type, enabled: true, config: {} })),
        enable_default_middleware: enabledMiddleware.length > 0,

        // Control node configuration
        condition: conditionExpression,
        max_iterations: maxLoopIterations,
        exit_condition: loopExitCondition,

        // Recursion limit (applies to all agent nodes)
        recursion_limit: recursionLimit,

        // Context Window Management (LangChain 1.1)
        context_management_strategy: contextStrategy,
        max_context_tokens: maxContextTokens,
        enable_auto_summarization: enableAutoSummarization,

        // Long-Term Memory & RAG (unified section)
        enable_long_term_memory: enableLongTermMemory,
        enable_memory_store: enableMemoryStore,
        enable_memory_recall: enableMemoryRecall,
        enable_rag: enableRAG,

        // Advanced: Parallel Tool Calling
        enable_parallel_tools: enableParallelTools,

        // Subagents configuration (Advanced: DeepAgents)
        subagents: subagents,

        // Conversation context configuration
        enable_conversation_context: enableConversationContext,
        deep_agent_template_id: selectedDeepAgentId,
        context_mode: contextMode,
        context_window_size: contextWindowSize,
        banked_message_ids: [],  // Will be populated when user banks messages

        // Tool Node configuration (instance-specific to this node)
        ...(config.agentType === 'TOOL_NODE' ? {
          tool_type: selectedToolType,
          tool_id: selectedToolId,
          tool_params: config.tool_params || {}
        } : {})
      };

      // Include the name in the full config so it updates everywhere
      const fullConfigWithName = {
        ...fullConfig,
        label: config.agentType === 'TOOL_NODE' && selectedToolId
          ? selectedToolId  // For TOOL_NODE, use the tool ID as the label
          : agentName,  // For regular agents, use the agent name
        name: config.agentType === 'TOOL_NODE' && selectedToolId
          ? selectedToolId
          : agentName
      };


      onSave(config.id, fullConfigWithName);

      // Show save feedback
      setSaveStatus('saving');
      setTimeout(() => {
        setSaveStatus('saved');
        setTimeout(() => setSaveStatus('idle'), 2000);
      }, 500);
    }
  };


  const handleDelete = () => {
    if (config && onDelete) {
      onDelete(config.id);
      setShowDeleteConfirm(false);
      onClose();
    }
  };

  // Subagent management functions
  const addSubagent = () => {
    const newSubagent = {
      name: `subagent-${subagents.length + 1}`,
      description: '',
      type: 'dictionary',  // Default to dictionary-based
      system_prompt: '',
      tools: [],
      model: config?.model || 'claude-sonnet-4-5-20250929',
      middleware: [],
      workflow_id: null,
      workflow_config: null
    };
    const updated = [...subagents, newSubagent];
    setSubagents(updated);
    // Auto-expand new subagent
    setExpandedSubagents(new Set([...expandedSubagents, updated.length - 1]));

    // Auto-save: Update node config immediately
    if (config) {
      onSave(config.id, {
        ...config,
        subagents: updated
      });
    }
  };

  const updateSubagent = (index: number, field: string, value: any) => {
    const updated = [...subagents];
    updated[index] = { ...updated[index], [field]: value };

    // Validation: If changing to 'compiled' type, ensure workflow_id exists
    // If changing type to 'dictionary', clear workflow_id
    if (field === 'type') {
      if (value === 'compiled' && !updated[index].workflow_id) {
        // Don't auto-save yet - user needs to select a workflow
        // Just update local state
        setSubagents(updated);
        return; // Don't auto-save until workflow is selected
      }
      if (value === 'dictionary') {
        // Clear workflow fields when switching to dictionary
        updated[index].workflow_id = null;
        updated[index].workflow_config = null;
      }
    }

    // Validation: If setting workflow_id, ensure type is 'compiled'
    if (field === 'workflow_id' && value) {
      updated[index].type = 'compiled';
    }

    setSubagents(updated);

    // Auto-save: Update node config immediately
    if (config) {
      onSave(config.id, {
        ...config,
        subagents: updated
      });
    }
  };

  const deleteSubagent = (index: number) => {
    const updated = subagents.filter((_: any, i: number) => i !== index);
    setSubagents(updated);
    // Remove from expanded set
    const newExpanded = new Set(expandedSubagents);
    newExpanded.delete(index);
    setExpandedSubagents(newExpanded);

    // Auto-save: Update node config immediately
    if (config) {
      onSave(config.id, {
        ...config,
        subagents: updated
      });
    }
  };

  const toggleSubagentExpanded = (index: number) => {
    const newExpanded = new Set(expandedSubagents);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedSubagents(newExpanded);
  };

  const toggleTool = (tool: string) => {
    setConfig(prev => {
      if (!prev) return prev;
      const tools = prev.tools.includes(tool)
        ? prev.tools.filter(t => t !== tool)
        : [...prev.tools, tool];
      return { ...prev, tools };
    });
  };

  const toggleNativeTool = (tool: string) => {
    setConfig(prev => {
      if (!prev) return prev;
      const native_tools = ((prev as any).native_tools || []).includes(tool)
        ? ((prev as any).native_tools || []).filter((t: string) => t !== tool)
        : [...((prev as any).native_tools || []), tool];

      const newConfig = { ...prev, native_tools };

      // Auto-save: Update node config immediately
      onSave(prev.id, {
        ...newConfig,
        native_tools: native_tools  // Backend expects native_tools
      });

      return newConfig;
    });
  };

  // Check if FilesystemMiddleware is enabled - if so, file tools are already equipped
  const filesystemMiddlewareEnabled = enabledMiddleware.includes('filesystem') ||
    (config as any)?.middleware?.some((m: any) => m.type === 'filesystem' && m.enabled !== false);

  // Tools that are automatically provided by FilesystemMiddleware
  const FILESYSTEM_MIDDLEWARE_TOOLS = ['read_file', 'write_file', 'ls', 'edit_file', 'glob', 'grep'];

  // Check if a tool is already equipped via middleware
  const isToolEquippedViaMiddleware = (toolId: string): boolean => {
    if (filesystemMiddlewareEnabled && FILESYSTEM_MIDDLEWARE_TOOLS.includes(toolId)) {
      return true;
    }
    return false;
  };

  return (
    <>
      <aside className="w-96 bg-white dark:bg-panel-dark border-l border-gray-200 dark:border-border-dark flex flex-col overflow-visible relative" style={{ zIndex: 100000 }}>
        {/* Header with Editable Agent Name */}
        <div className="p-4 border-b border-gray-200 dark:border-border-dark">
          <div className="flex items-center gap-2 mb-2">
            <input
              type="text"
              value={agentName}
              onChange={(e) => {
                const newName = e.target.value;
                setAgentName(newName);

                // Auto-save: Update node config immediately
                if (config) {
                  onSave(config.id, {
                    ...config,
                    name: newName,
                    label: newName  // Update label too for display
                  });
                }
              }}
              className="flex-1 px-3 py-2 text-lg font-semibold bg-transparent border border-transparent hover:border-gray-300 dark:hover:border-gray-600 focus:border-primary focus:outline-none rounded transition-colors"
              style={{ color: 'var(--color-text-primary)' }}
              placeholder="Agent Name"
            />
            <button
              onClick={onClose}
              className="p-1 hover:bg-gray-100 dark:hover:bg-panel-dark rounded transition-colors flex-shrink-0"
            >
              <X className="w-5 h-5 text-gray-500 dark:text-gray-400" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-6">

          {/* Control Node Configuration - CONDITIONAL_NODE */}
          {config.agentType === 'CONDITIONAL_NODE' && (
            <div>
              <label className="block text-xs font-medium mb-2" style={{ color: 'var(--color-text-primary, #1a1a1a)' }}>
                Condition Expression
              </label>
              <input
                type="text"
                value={conditionExpression}
                onChange={(e) => {
                  const newCondition = e.target.value;
                  setConditionExpression(newCondition);

                  // Auto-save: Update node config immediately
                  if (config) {
                    onSave(config.id, {
                      ...config,
                      condition: newCondition
                    });
                  }
                }}
                placeholder="e.g., state.get('retry_count', 0) < 3"
                className="w-full px-3 py-2 border rounded-lg text-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent font-mono"
                style={{
                  backgroundColor: 'var(--color-input-background)',
                  borderColor: 'var(--color-border-dark)',
                  color: 'var(--color-text-primary)'
                }}
              />
              <div className="mt-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-3">
                <p className="text-xs font-medium text-blue-900 dark:text-blue-300 mb-2">How it works:</p>
                <ul className="text-xs text-blue-800 dark:text-blue-400 space-y-1 list-disc list-inside">
                  <li>Expression evaluates to true or false</li>
                  <li>Connect edges labeled "true" and "false" from this node</li>
                  <li>Use <code className="bg-blue-100 dark:bg-blue-900/30 px-1 rounded">state.get('key')</code> to access workflow state</li>
                </ul>
                <p className="text-xs text-blue-800 dark:text-blue-400 mt-2">
                  <strong>Examples:</strong> <code className="bg-blue-100 dark:bg-blue-900/30 px-1 rounded">state.get("validation_passed") == True</code> or <code className="bg-blue-100 dark:bg-blue-900/30 px-1 rounded">len(state.get("messages", [])) &gt; 0</code>
                </p>
              </div>
            </div>
          )}

          {/* Control Node Configuration - LOOP_NODE */}
          {config.agentType === 'LOOP_NODE' && (
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium mb-2" style={{ color: 'var(--color-text-primary, #1a1a1a)' }}>
                  Maximum Iterations
                </label>
                <input
                  type="number"
                  value={maxLoopIterations}
                  onChange={(e) => {
                    const newValue = parseInt(e.target.value) || 10;
                    setMaxLoopIterations(newValue);

                    // Auto-save: Update node config immediately
                    if (config) {
                      onSave(config.id, {
                        ...config,
                        max_iterations: newValue
                      });
                    }
                  }}
                  min="1"
                  max="100"
                  className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
                  style={{
                    backgroundColor: 'var(--color-input-background)',
                    borderColor: 'var(--color-border-dark)',
                    color: 'var(--color-text-primary)'
                  }}
                />
                <p className="mt-1 text-xs" style={{ color: 'var(--color-text-muted, #6b7280)' }}>
                  Loop will exit after this many iterations (default: 10)
                </p>
              </div>

              <div>
                <label className="block text-xs font-medium mb-2" style={{ color: 'var(--color-text-primary, #1a1a1a)' }}>
                  Exit Condition (Optional)
                </label>
                <input
                  type="text"
                  value={loopExitCondition}
                  onChange={(e) => {
                    const newCondition = e.target.value;
                    setLoopExitCondition(newCondition);

                    // Auto-save: Update node config immediately
                    if (config) {
                      onSave(config.id, {
                        ...config,
                        exit_condition: newCondition
                      });
                    }
                  }}
                  placeholder="e.g., state.get('task_complete') == True"
                  className="w-full px-3 py-2 border rounded-lg text-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent font-mono"
                  style={{
                    backgroundColor: 'var(--color-input-background)',
                    borderColor: 'var(--color-border-dark)',
                    color: 'var(--color-text-primary)'
                  }}
                />
                <p className="mt-1 text-xs" style={{ color: 'var(--color-text-muted, #6b7280)' }}>
                  Optional: Exit loop early when this expression evaluates to true
                </p>
              </div>

              <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-3">
                <p className="text-xs font-medium text-blue-900 dark:text-blue-300 mb-2">How it works:</p>
                <ul className="text-xs text-blue-800 dark:text-blue-400 space-y-1 list-disc list-inside">
                  <li>Connect edge labeled "continue" to loop back to target node</li>
                  <li>Connect edge labeled "exit" to continue after loop completes</li>
                  <li>Access current iteration with <code className="bg-blue-100 dark:bg-blue-900/30 px-1 rounded">iteration</code> in expressions</li>
                </ul>
              </div>
            </div>
          )}

          {/* Tool Node Configuration - Only for TOOL_NODE */}
          {config.agentType === 'TOOL_NODE' && (
            <div>
              <div className="px-3 py-2 rounded-lg mb-3" style={{
                backgroundColor: 'var(--color-primary)',
              }}>
                <h3 className="text-base font-semibold text-white">
                  Tool Configuration
                </h3>
              </div>

              <div className="space-y-4 p-3">
                {/* Advanced Configuration */}
                <div className="border-t border-gray-200 dark:border-border-dark pt-4">
                  <div className="px-3 py-2 rounded-lg mb-3" style={{
                    backgroundColor: 'var(--color-primary)',
                  }}>
                    <h3 className="text-base font-semibold" style={{ color: 'white' }}>
                      Advanced Configuration
                    </h3>
                  </div>

                  <div className="space-y-3">
                    <label className="flex items-center justify-between p-2 rounded border cursor-pointer hover:border-primary/50 transition-colors" style={{ borderColor: 'var(--color-border)' }}>
                      <div>
                        <span className="text-sm font-medium block" style={{ color: 'var(--color-text-primary)' }}>Debug Mode</span>
                        <span className="text-xs opacity-70 block">Enable verbose logging for this agent</span>
                      </div>
                      <div className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${debugMode ? 'bg-primary' : 'bg-gray-300'}`}>
                        <input
                          type="checkbox"
                          checked={debugMode}
                          onChange={(e) => setDebugMode(e.target.checked)}
                          className="sr-only"
                        />
                        <span className={`inline-block h-3 w-3 transform rounded-full bg-white transition-transform ${debugMode ? 'translate-x-5' : 'translate-x-1'}`} />
                      </div>
                    </label>

                    <label className="flex items-center justify-between p-2 rounded border cursor-pointer hover:border-primary/50 transition-colors" style={{ borderColor: 'var(--color-border)' }}>
                      <div>
                        <span className="text-sm font-medium block" style={{ color: 'var(--color-text-primary)' }}>Enable Cache</span>
                        <span className="text-xs opacity-70 block">Cache LLM responses to save costs</span>
                      </div>
                      <div className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${enableCache ? 'bg-primary' : 'bg-gray-300'}`}>
                        <input
                          type="checkbox"
                          checked={enableCache}
                          onChange={(e) => setEnableCache(e.target.checked)}
                          className="sr-only"
                        />
                        <span className={`inline-block h-3 w-3 transform rounded-full bg-white transition-transform ${enableCache ? 'translate-x-5' : 'translate-x-1'}`} />
                      </div>
                    </label>

                    <label className="flex items-center justify-between p-2 rounded border cursor-pointer hover:border-primary/50 transition-colors" style={{ borderColor: 'var(--color-border)' }}>
                      <div>
                        <span className="text-sm font-medium block" style={{ color: 'var(--color-text-primary)' }}>Parallel Tool Calls</span>
                        <span className="text-xs opacity-70 block">Allow LLM to call multiple tools at once</span>
                      </div>
                      <div className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${enableParallelTools ? 'bg-primary' : 'bg-gray-300'}`}>
                        <input
                          type="checkbox"
                          checked={enableParallelTools}
                          onChange={(e) => {
                            const newVal = e.target.checked;
                            setEnableParallelTools(newVal);

                            // Auto-save: Update node config immediately
                            if (config) {
                              onSave(config.id, {
                                ...config,
                                enable_parallel_tools: newVal
                              });
                            }
                          }}
                          className="sr-only"
                        />
                        <span className={`inline-block h-3 w-3 transform rounded-full bg-white transition-transform ${enableParallelTools ? 'translate-x-5' : 'translate-x-1'}`} />
                      </div>
                    </label>
                  </div>
                </div>

                {/* Custom Tools Section */}
                <div>
                  <label className="block text-sm font-medium mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    Select Custom Tool
                  </label>
                  <select
                    value={selectedToolId || ''}
                    onChange={(e) => {
                      const toolId = e.target.value;
                      setSelectedToolId(toolId);
                      setSelectedToolType('custom');

                      // Find the tool and load its schema
                      const tool = availableCustomTools.find(t => t.tool_id === toolId);
                      if (tool) {
                        loadToolSchema('custom', toolId);
                      }

                      setConfig({
                        ...config,
                        tool_type: 'custom',
                        tool_id: toolId,
                        tool_params: {}
                      });
                    }}
                    onMouseDown={(e) => e.stopPropagation()}
                    onWheel={(e) => e.stopPropagation()}
                    className="w-full px-3 py-2 border rounded-lg"
                    style={{
                      backgroundColor: 'var(--color-input-background)',
                      borderColor: 'var(--color-border-dark)',
                      color: 'var(--color-text-primary)'
                    }}
                  >
                    <option value="">Select a custom tool...</option>
                    {availableCustomTools.map((tool: any) => (
                      <option key={tool.tool_id} value={tool.tool_id}>
                        {tool.name}
                      </option>
                    ))}
                  </select>
                  {selectedToolId && (
                    <p className="text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
                      {availableCustomTools.find(t => t.tool_id === selectedToolId)?.description}
                    </p>
                  )}
                </div>

                {/* Open Tool Configuration Button */}
                {selectedToolId && (
                  <div>
                    <button
                      onClick={() => setShowToolConfigModal(true)}
                      className="w-full inline-flex items-center justify-center gap-2 px-4 py-3 rounded-lg font-medium transition-all duration-200 hover:opacity-90"
                      style={{
                        backgroundColor: 'var(--color-primary)',
                        color: 'white'
                      }}
                    >
                      <Settings className="w-4 h-4" />
                      Open Tool Configuration
                    </button>
                    <p className="text-xs mt-2" style={{ color: 'var(--color-text-muted)' }}>
                      Opens the full tool editor to view/edit all tool settings
                    </p>
                  </div>
                )}
              </div>

              {/* Save Button for Tool Node */}
              <button
                onClick={handleSave}
                disabled={saveStatus === 'saving'}
                className="w-full mt-4 px-4 py-3 rounded-lg font-medium transition-all duration-200 disabled:opacity-50"
                style={{
                  backgroundColor: saveStatus === 'saved' ? '#10b981' : 'var(--color-primary)',
                  color: 'white'
                }}
              >
                {saveStatus === 'saving' ? 'Saving...' : saveStatus === 'saved' ? 'Saved!' : 'Save Tool Configuration'}
              </button>
            </div>
          )}

          {/* System Prompt - Only for regular agent nodes */}
          {config.agentType !== 'CONDITIONAL_NODE' && config.agentType !== 'LOOP_NODE' && config.agentType !== 'TOOL_NODE' && (
            <div>
              <div className="px-3 py-2 rounded-lg mb-3" style={{
                backgroundColor: 'var(--color-primary)',
              }}>
                <h3 className="text-base font-semibold" style={{ color: 'white' }}>
                  System Prompt
                </h3>
              </div>
              <textarea
                value={config.system_prompt}
                onChange={(e) => {
                  const newPrompt = e.target.value;
                  setConfig({ ...config, system_prompt: newPrompt });

                  // Auto-save: Update node config immediately
                  onSave(config.id, {
                    ...config,
                    system_prompt: newPrompt
                  });
                }}
                rows={20}
                placeholder="Enter the system prompt for this agent..."
                className="w-full px-3 py-2 border rounded-lg text-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent resize-none font-mono"
                style={{
                  backgroundColor: 'var(--color-input-background)',
                  borderColor: 'var(--color-border-dark)',
                  color: 'var(--color-text-primary)'
                }}
              />
              <p className="mt-1 text-xs" style={{ color: 'var(--color-text-muted, #6b7280)' }}>
                {config.system_prompt.length} characters
              </p>

              {/* Recursion Limit Slider */}
              <div className="mt-4">
                <label className="block text-xs font-medium mb-2" style={{ color: 'var(--color-text-primary)' }}>
                  Recursion Limit
                  <span className="ml-2 font-normal" style={{ color: 'var(--color-text-muted)' }}>
                    ({recursionLimit} iterations)
                  </span>
                </label>
                <input
                  type="range"
                  min="10"
                  max="200"
                  step="5"
                  value={recursionLimit}
                  onChange={(e) => {
                    const newLimit = parseInt(e.target.value);
                    setRecursionLimit(newLimit);

                    // Auto-save: Update node config immediately
                    if (config) {
                      onSave(config.id, {
                        ...config,
                        recursion_limit: newLimit
                      });
                    }
                  }}
                  className="w-full"
                  style={{ accentColor: 'var(--color-primary)' }}
                />
                <div className="flex justify-between text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
                  <span>10</span>
                  <span>100</span>
                  <span>200</span>
                </div>
                <p className="mt-2 text-xs" style={{ color: 'var(--color-text-muted)' }}>
                  Maximum recursion depth for agent execution. Higher values allow more complex reasoning chains but may take longer.
                </p>
              </div>

              {/* ═══════════════════════════════════════════════════════════════════
                  📊 CONTEXT & MEMORY - Unified Section
                  All context and memory settings organized in one place
                  ═══════════════════════════════════════════════════════════════════ */}
              <div className="mt-4 p-3 rounded-lg border" style={{
                borderColor: 'var(--color-primary)',
                backgroundColor: 'var(--color-background-secondary, rgba(0,0,0,0.02))'
              }}>
                <div className="flex items-center gap-2 mb-3">
                  <svg className="w-5 h-5" style={{ color: 'var(--color-primary)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
                  </svg>
                  <span className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                    Context & Memory
                  </span>
                </div>

                {/* ─────────────────────────────────────────────────────────────────
                    SUB-GROUP 1: Runtime Context Management (Always Visible)
                    How the agent handles context during execution
                    ───────────────────────────────────────────────────────────────── */}
                <div className="mb-4">
                  <div className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: 'var(--color-text-muted)' }}>
                    Runtime Context
                  </div>

                  {/* Strategy */}
                  <div className="mb-2">
                    <label className="block text-xs font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                      Strategy
                    </label>
                    <select
                      value={contextStrategy}
                      onChange={(e) => {
                        const strategy = e.target.value as 'smart' | 'recent' | 'summary' | 'quarantine' | 'full';
                        setContextStrategy(strategy);
                        if (config) {
                          onSave(config.id, { ...config, context_management_strategy: strategy });
                        }
                      }}
                      className="w-full px-2 py-1.5 border rounded text-xs"
                      style={{
                        backgroundColor: 'var(--color-input-background)',
                        borderColor: 'var(--color-border-dark)',
                        color: 'var(--color-text-primary)'
                      }}
                    >
                      <option value="recent">Recent — keeps last N messages only (fast, predictable)</option>
                      <option value="smart">Smart — hybrid: trims old messages, keeps important ones</option>
                      <option value="summary">Summary — compresses older messages into AI summaries</option>
                      <option value="quarantine">Quarantine — isolates large tool outputs to reduce tokens</option>
                      <option value="full">Full — no trimming (may hit context limit errors)</option>
                    </select>
                    <p className="mt-1 text-xs" style={{ color: 'var(--color-text-muted)' }}>
                      {contextStrategy === 'recent' && '💡 Best for fresh runs. Only keeps the most recent messages — fast and token-efficient.'}
                      {contextStrategy === 'smart' && '💡 Balances recency with relevance. Trims oldest messages but keeps bookmarked/important ones.'}
                      {contextStrategy === 'summary' && '💡 Uses AI to compress older messages. Good for long conversations but adds latency.'}
                      {contextStrategy === 'quarantine' && '💡 Moves large tool outputs (code, files) to a separate cache. Useful for code-heavy workflows.'}
                      {contextStrategy === 'full' && '⚠️ No context management — risks context_length_exceeded errors with long conversations.'}
                    </p>
                  </div>

                  {/* Max Context Tokens + Auto-Summarize in row */}
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-xs font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                        Max Tokens
                      </label>
                      <input
                        type="number"
                        value={maxContextTokens ?? ''}
                        placeholder="Auto"
                        onChange={(e) => {
                          const value = e.target.value ? parseInt(e.target.value) : null;
                          setMaxContextTokens(value);
                          if (config) {
                            onSave(config.id, { ...config, max_context_tokens: value });
                          }
                        }}
                        min="1000" max="200000" step="1000"
                        className="w-full px-2 py-1.5 border rounded text-xs"
                        style={{
                          backgroundColor: 'var(--color-input-background)',
                          borderColor: 'var(--color-border-dark)',
                          color: 'var(--color-text-primary)'
                        }}
                      />
                    </div>
                    <label className="flex items-center gap-2 cursor-pointer pt-5">
                      <input
                        type="checkbox"
                        checked={enableAutoSummarization}
                        onChange={(e) => {
                          setEnableAutoSummarization(e.target.checked);
                          if (config) {
                            onSave(config.id, { ...config, enable_auto_summarization: e.target.checked });
                          }
                        }}
                        className="w-4 h-4 rounded"
                        style={{ accentColor: 'var(--color-primary)' }}
                      />
                      <span className="text-xs" style={{ color: 'var(--color-text-primary)' }}>Auto-summarize at 80%</span>
                    </label>
                  </div>
                </div>

                {/* Divider */}
                <div className="border-t my-3" style={{ borderColor: 'var(--color-border-dark)' }} />

                {/* ─────────────────────────────────────────────────────────────────
                    SUB-GROUP 2: Long-Term Memory (Toggle)
                    Persistent memory across executions
                    ───────────────────────────────────────────────────────────────── */}
                <div className="mb-3">
                  <label className="flex items-center justify-between cursor-pointer">
                    <div className="flex items-center gap-2">
                      <svg className="w-4 h-4" style={{ color: enableLongTermMemory ? 'var(--color-primary)' : 'var(--color-text-muted)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7v8a2 2 0 002 2h6M8 7V5a2 2 0 012-2h4.586a1 1 0 01.707.293l4.414 4.414a1 1 0 01.293.707V15a2 2 0 01-2 2h-2M8 7H6a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2v-2" />
                      </svg>
                      <span className="text-xs font-medium" style={{ color: 'var(--color-text-primary)' }}>Long-Term Memory</span>
                    </div>
                    <div className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${enableLongTermMemory ? 'bg-primary' : 'bg-gray-300'}`}>
                      <input
                        type="checkbox"
                        checked={enableLongTermMemory}
                        onChange={(e) => {
                          const enabled = e.target.checked;
                          setEnableLongTermMemory(enabled);
                          if (config) {
                            // Update native_tools based on toggle state
                            let updatedTools = [...((config as any).native_tools || [])];
                            if (enabled) {
                              // Add memory tools if enabling and sub-options are checked
                              if (enableMemoryStore && !updatedTools.includes('memory_store')) {
                                updatedTools.push('memory_store');
                              }
                              if (enableMemoryRecall && !updatedTools.includes('memory_recall')) {
                                updatedTools.push('memory_recall');
                              }
                            } else {
                              // Remove all memory tools when disabling
                              updatedTools = updatedTools.filter(t => t !== 'memory_store' && t !== 'memory_recall');
                            }
                            onSave(config.id, { ...config, enable_long_term_memory: enabled, native_tools: updatedTools });
                          }
                        }}
                        className="sr-only"
                      />
                      <span className={`inline-block h-3 w-3 transform rounded-full bg-white transition-transform ${enableLongTermMemory ? 'translate-x-5' : 'translate-x-1'}`} />
                    </div>
                  </label>

                  {/* Memory tools when enabled */}
                  {enableLongTermMemory && (
                    <div className="mt-2 pl-6 space-y-1 border-l-2" style={{ borderColor: 'var(--color-primary)' }}>
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={enableMemoryStore}
                          onChange={(e) => {
                            const checked = e.target.checked;
                            setEnableMemoryStore(checked);
                            if (config) {
                              // Update native_tools array
                              let updatedTools = [...((config as any).native_tools || [])];
                              if (checked && !updatedTools.includes('memory_store')) {
                                updatedTools.push('memory_store');
                              } else if (!checked) {
                                updatedTools = updatedTools.filter(t => t !== 'memory_store');
                              }
                              onSave(config.id, { ...config, enable_memory_store: checked, native_tools: updatedTools });
                            }
                          }}
                          className="w-3 h-3 rounded"
                          style={{ accentColor: 'var(--color-primary)' }}
                        />
                        <span className="text-xs" style={{ color: 'var(--color-text-primary)' }}>Store Memory (save to memory)</span>
                      </label>
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={enableMemoryRecall}
                          onChange={(e) => {
                            const checked = e.target.checked;
                            setEnableMemoryRecall(checked);
                            if (config) {
                              // Update native_tools array
                              let updatedTools = [...((config as any).native_tools || [])];
                              if (checked && !updatedTools.includes('memory_recall')) {
                                updatedTools.push('memory_recall');
                              } else if (!checked) {
                                updatedTools = updatedTools.filter(t => t !== 'memory_recall');
                              }
                              onSave(config.id, { ...config, enable_memory_recall: checked, native_tools: updatedTools });
                            }
                          }}
                          className="w-3 h-3 rounded"
                          style={{ accentColor: 'var(--color-primary)' }}
                        />
                        <span className="text-xs" style={{ color: 'var(--color-text-primary)' }}>Recall Memory (retrieve from memory)</span>
                      </label>
                    </div>
                  )}
                </div>

                {/* ─────────────────────────────────────────────────────────────────
                    SUB-GROUP 3: RAG (Toggle)
                    Retrieve from project vector store
                    ───────────────────────────────────────────────────────────────── */}
                <div className="mb-3">
                  <label className="flex items-center justify-between cursor-pointer">
                    <div className="flex items-center gap-2">
                      <svg className="w-4 h-4" style={{ color: enableRAG ? 'var(--color-primary)' : 'var(--color-text-muted)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                      </svg>
                      <div>
                        <span className="text-xs font-medium" style={{ color: 'var(--color-text-primary)' }}>Enable RAG</span>
                        <span className="text-xs ml-1" style={{ color: 'var(--color-text-muted)' }}>(project docs/KB)</span>
                      </div>
                    </div>
                    <div className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${enableRAG ? 'bg-primary' : 'bg-gray-300'}`}>
                      <input
                        type="checkbox"
                        checked={enableRAG}
                        onChange={(e) => {
                          setEnableRAG(e.target.checked);
                          if (config) {
                            onSave(config.id, { ...config, enable_rag: e.target.checked });
                          }
                        }}
                        className="sr-only"
                      />
                      <span className={`inline-block h-3 w-3 transform rounded-full bg-white transition-transform ${enableRAG ? 'translate-x-5' : 'translate-x-1'}`} />
                    </div>
                  </label>
                </div>

                {/* ─────────────────────────────────────────────────────────────────
                    SUB-GROUP 4: Conversation History (Toggle)
                    Load chat history from a DeepAgent
                    ───────────────────────────────────────────────────────────────── */}
                <div>
                  <label className="flex items-center justify-between cursor-pointer">
                    <div className="flex items-center gap-2">
                      <MessageSquare className="w-4 h-4" style={{ color: enableConversationContext ? 'var(--color-primary)' : 'var(--color-text-muted)' }} />
                      <div>
                        <span className="text-xs font-medium" style={{ color: 'var(--color-text-primary)' }}>Conversation History</span>
                        <span className="text-xs ml-1" style={{ color: 'var(--color-text-muted)' }}>(from DeepAgent)</span>
                      </div>
                    </div>
                    <div className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${enableConversationContext ? 'bg-primary' : 'bg-gray-300'}`}>
                      <input
                        type="checkbox"
                        checked={enableConversationContext}
                        onChange={(e) => {
                          const newValue = e.target.checked;
                          setEnableConversationContext(newValue);
                          if (newValue && !selectedDeepAgentId && deepAgents.length > 0) {
                            setSelectedDeepAgentId(deepAgents[0].id);
                          }
                          if (config) {
                            onSave(config.id, {
                              ...config,
                              enable_conversation_context: newValue,
                              deep_agent_template_id: newValue && !selectedDeepAgentId && deepAgents.length > 0 ? deepAgents[0].id : selectedDeepAgentId
                            });
                          }
                        }}
                        className="sr-only"
                      />
                      <span className={`inline-block h-3 w-3 transform rounded-full bg-white transition-transform ${enableConversationContext ? 'translate-x-5' : 'translate-x-1'}`} />
                    </div>
                  </label>

                  {/* Conversation settings when enabled */}
                  {enableConversationContext && (
                    <div className="mt-2 pl-6 space-y-2 border-l-2" style={{ borderColor: 'var(--color-primary)' }}>
                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <label className="block text-xs font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                            Deep Agent
                          </label>
                          <select
                            value={selectedDeepAgentId || ''}
                            onChange={(e) => {
                              const agentId = e.target.value ? Number(e.target.value) : null;
                              setSelectedDeepAgentId(agentId);
                              if (config) {
                                onSave(config.id, { ...config, deep_agent_template_id: agentId });
                              }
                            }}
                            className="w-full px-2 py-1 border rounded text-xs"
                            style={{
                              backgroundColor: 'var(--color-input-background)',
                              borderColor: 'var(--color-border-dark)',
                              color: 'var(--color-text-primary)'
                            }}
                          >
                            <option value="">Select...</option>
                            {deepAgents.map(agent => (
                              <option key={agent.id} value={agent.id}>
                                {agent.name} ({agent.chat_sessions_count || 0})
                              </option>
                            ))}
                          </select>
                        </div>
                        <div>
                          <label className="block text-xs font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                            Mode
                          </label>
                          <select
                            value={contextMode}
                            onChange={(e) => {
                              const mode = e.target.value as 'recent' | 'smart' | 'full' | 'summary' | 'quarantine';
                              setContextMode(mode);
                              if (config) {
                                onSave(config.id, { ...config, context_mode: mode });
                              }
                            }}
                            className="w-full px-2 py-1 border rounded text-xs"
                            style={{
                              backgroundColor: 'var(--color-input-background)',
                              borderColor: 'var(--color-border-dark)',
                              color: 'var(--color-text-primary)'
                            }}
                          >
                            <option value="recent">Recent</option>
                            <option value="smart">Smart</option>
                            <option value="summary">Summary</option>
                            <option value="quarantine">Quarantine</option>
                            <option value="full">Full</option>
                          </select>
                        </div>
                      </div>
                      {contextMode === 'recent' && (
                        <div>
                          <label className="block text-xs mb-1" style={{ color: 'var(--color-text-primary)' }}>
                            Last {contextWindowSize} messages
                          </label>
                          <input
                            type="range"
                            min="5" max="100" step="5"
                            value={contextWindowSize}
                            onChange={(e) => {
                              const size = parseInt(e.target.value);
                              setContextWindowSize(size);
                              if (config) {
                                onSave(config.id, { ...config, context_window_size: size });
                              }
                            }}
                            className="w-full h-1"
                            style={{ accentColor: 'var(--color-primary)' }}
                          />
                        </div>
                      )}
                      {selectedDeepAgentId && (
                        <button
                          onClick={() => setShowContextPreview(true)}
                          className="w-full px-2 py-1 rounded text-xs font-medium flex items-center justify-center gap-1"
                          style={{ backgroundColor: 'var(--color-primary)', color: 'white' }}
                        >
                          <MessageSquare className="w-3 h-3" /> Preview
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </div>

              {/* Save Button - Right after system prompt */}
              <button
                onClick={handleSave}
                disabled={saveStatus === 'saving'}
                className="w-full px-3 py-2 rounded-md text-sm font-medium transition-all hover:opacity-90 disabled:opacity-50 mt-3"
                style={{
                  backgroundColor: saveStatus === 'saved' ? '#10b981' : 'var(--color-primary)',
                  color: 'white'
                }}
              >
                {saveStatus === 'saving' ? 'Saving...' : saveStatus === 'saved' ? 'Saved' : 'Save Changes'}
              </button>
            </div>
          )}

          {/* Agent Tools - Only for regular agent nodes */}
          {config.agentType !== 'CONDITIONAL_NODE' && config.agentType !== 'LOOP_NODE' && config.agentType !== 'TOOL_NODE' && (
            <div>
              <div className="px-3 py-2 rounded-lg mb-3" style={{
                backgroundColor: 'var(--color-primary)',
              }}>
                <h3 className="text-base font-semibold" style={{ color: 'white' }}>
                  Agent Tools
                </h3>
              </div>

              {/* Tools organized by category in 2x2 grid */}
              <div className="space-y-4">
                {/* Web Tools */}
                <div>
                  <p className="text-xs font-semibold mb-1.5" style={{ color: 'var(--color-primary)' }}>Web & Search</p>
                  <div className="grid grid-cols-2 gap-2">
                    {AVAILABLE_TOOLS.filter(t => t.category === 'web').map(tool => (
                      <label
                        key={tool.id}
                        className="flex items-start gap-1.5 p-2 rounded cursor-pointer transition-colors group border hover:border-primary/50"
                        style={{
                          backgroundColor: 'var(--color-background-dark, #f9fafb)',
                          borderColor: 'var(--color-border-dark)'
                        }}
                        title={tool.description}
                      >
                        <input
                          type="checkbox"
                          checked={((config as any).native_tools || []).includes(tool.id) || ((config as any).native_tools || []).includes(LEGACY_TOOL_MAP[tool.id] || '')}
                          onChange={() => toggleNativeTool(tool.id)}
                          className="w-3.5 h-3.5 text-primary rounded focus:ring-2 focus:ring-primary cursor-pointer mt-0.5 flex-shrink-0"
                        />
                        <div className="flex-1 min-w-0">
                          <span className="text-xs font-medium block leading-tight" style={{ color: 'var(--color-text-primary, #1a1a1a)' }}>
                            {tool.name}
                          </span>
                        </div>
                      </label>
                    ))}
                  </div>
                </div>

                {/* File Tools */}
                <div>
                  <div className="flex items-center gap-2 mb-1.5">
                    <p className="text-xs font-semibold" style={{ color: 'var(--color-primary)' }}>File Operations</p>
                    {filesystemMiddlewareEnabled && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 font-medium">
                        via Middleware
                      </span>
                    )}
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    {AVAILABLE_TOOLS.filter(t => t.category === 'files').map(tool => {
                      const equippedViaMiddleware = isToolEquippedViaMiddleware(tool.id);
                      return (
                        <label
                          key={tool.id}
                          className={`flex items-start gap-1.5 p-2 rounded transition-colors group border ${equippedViaMiddleware ? 'cursor-default' : 'cursor-pointer hover:border-primary/50'}`}
                          style={{
                            backgroundColor: equippedViaMiddleware ? 'var(--color-success-subtle, #f0fdf4)' : 'var(--color-background-dark, #f9fafb)',
                            borderColor: equippedViaMiddleware ? 'var(--color-success, #22c55e)' : 'var(--color-border-dark)',
                            opacity: equippedViaMiddleware ? 0.85 : 1
                          }}
                          title={equippedViaMiddleware ? `${tool.description} (Equipped via FilesystemMiddleware)` : tool.description}
                        >
                          <input
                            type="checkbox"
                            checked={equippedViaMiddleware || ((config as any).native_tools || []).includes(tool.id)}
                            onChange={() => !equippedViaMiddleware && toggleNativeTool(tool.id)}
                            disabled={equippedViaMiddleware}
                            className="w-3.5 h-3.5 text-primary rounded focus:ring-2 focus:ring-primary cursor-pointer mt-0.5 flex-shrink-0 disabled:opacity-60"
                          />
                          <div className="flex-1 min-w-0">
                            <span className="text-xs font-medium block leading-tight" style={{ color: 'var(--color-text-primary, #1a1a1a)' }}>
                              {tool.name}
                            </span>
                            {equippedViaMiddleware && (
                              <span className="text-[9px] text-green-600 dark:text-green-400">
                                Equipped
                              </span>
                            )}
                          </div>
                        </label>
                      );
                    })}
                  </div>
                </div>

                {/* Reasoning Tools */}
                <div>
                  <p className="text-xs font-semibold mb-1.5" style={{ color: 'var(--color-primary)' }}>Advanced Reasoning</p>
                  <div className="grid grid-cols-2 gap-2">
                    {AVAILABLE_TOOLS.filter(t => t.category === 'reasoning').map(tool => (
                      <label
                        key={tool.id}
                        className="flex items-start gap-1.5 p-2 rounded cursor-pointer transition-colors group border hover:border-primary/50"
                        style={{
                          backgroundColor: 'var(--color-background-dark, #f9fafb)',
                          borderColor: 'var(--color-border-dark)'
                        }}
                        title={tool.description}
                      >
                        <input
                          type="checkbox"
                          checked={((config as any).native_tools || []).includes(tool.id) || ((config as any).native_tools || []).includes('sequential_thinking')}
                          onChange={() => toggleNativeTool(tool.id)}
                          className="w-3.5 h-3.5 text-primary rounded focus:ring-2 focus:ring-primary cursor-pointer mt-0.5 flex-shrink-0"
                        />
                        <div className="flex-1 min-w-0">
                          <span className="text-xs font-medium block leading-tight" style={{ color: 'var(--color-text-primary, #1a1a1a)' }}>
                            {tool.name}
                          </span>
                        </div>
                      </label>
                    ))}
                  </div>
                </div>

                {/* Custom Tools */}
                {availableCustomTools.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold mb-1.5" style={{ color: 'var(--color-primary)' }}>Custom Tools</p>
                    <div className="grid grid-cols-2 gap-2">
                      {availableCustomTools.map(tool => (
                        <label
                          key={tool.tool_id}
                          className="flex items-start gap-1.5 p-2 rounded cursor-pointer transition-colors group border hover:border-primary/50"
                          style={{
                            backgroundColor: 'var(--color-background-dark, #f9fafb)',
                            borderColor: 'var(--color-border-dark)'
                          }}
                          title={tool.description}
                        >
                          <input
                            type="checkbox"
                            checked={selectedCustomTools.includes(tool.tool_id)}
                            onChange={() => {
                              const newCustomTools = selectedCustomTools.includes(tool.tool_id)
                                ? selectedCustomTools.filter(id => id !== tool.tool_id)
                                : [...selectedCustomTools, tool.tool_id];

                              setSelectedCustomTools(newCustomTools);

                              // Auto-save: Update node config immediately
                              if (config) {
                                onSave(config.id, {
                                  ...config,
                                  custom_tools: newCustomTools
                                });
                              }
                            }}
                            className="w-3.5 h-3.5 text-primary rounded focus:ring-2 focus:ring-primary cursor-pointer mt-0.5 flex-shrink-0"
                          />
                          <div className="flex-1 min-w-0">
                            <span className="text-xs font-medium block leading-tight" style={{ color: 'var(--color-text-primary, #1a1a1a)' }}>
                              {tool.name}
                            </span>
                          </div>
                        </label>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Claude Skills - Collapsible, collapsed by default */}
          {config.agentType !== 'CONDITIONAL_NODE' && config.agentType !== 'LOOP_NODE' && config.agentType !== 'TOOL_NODE' && (
            <div className="border-t border-gray-200 dark:border-border-dark pt-4">
              <button
                onClick={() => setSkillsCollapsed(!skillsCollapsed)}
                className="w-full px-3 py-2 rounded-lg mb-3 flex items-center justify-between"
                style={{ backgroundColor: 'var(--color-primary)' }}
              >
                <h3 className="text-base font-semibold" style={{ color: 'white' }}>
                  Claude Skills
                </h3>
                <div className="flex items-center gap-2">
                  {selectedSkills.length > 0 && (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-white/20" style={{ color: 'white' }}>
                      {selectedSkills.length}
                    </span>
                  )}
                  {skillsCollapsed ? (
                    <ChevronRight size={16} style={{ color: 'white' }} />
                  ) : (
                    <ChevronDown size={16} style={{ color: 'white' }} />
                  )}
                </div>
              </button>
              {!skillsCollapsed && (
                <>
                  <p className="text-xs mb-3 px-1" style={{ color: 'var(--color-text-muted)' }}>
                    Skills provide specialized instructions and context for specific tasks. When enabled, the skill's instructions are injected into the agent's system prompt.
                  </p>
                  {availableSkills.length === 0 ? (
                    <div className="text-center py-4 px-4">
                      <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                        No skills available. Create skills in the Agents page.
                      </p>
                    </div>
                  ) : (
                    <div className="grid grid-cols-2 gap-2">
                      {availableSkills.map(skill => (
                        <label
                          key={skill.skill_id}
                          className="flex items-start gap-1.5 p-2 rounded cursor-pointer transition-colors group border hover:border-primary/50"
                          style={{
                            backgroundColor: 'var(--color-background-dark, #f9fafb)',
                            borderColor: 'var(--color-border-dark)'
                          }}
                          title={skill.description}
                        >
                          <input
                            type="checkbox"
                            checked={selectedSkills.includes(skill.skill_id)}
                            onChange={() => {
                              const newSkills = selectedSkills.includes(skill.skill_id)
                                ? selectedSkills.filter(id => id !== skill.skill_id)
                                : [...selectedSkills, skill.skill_id];

                              setSelectedSkills(newSkills);

                              // Auto-save: Update node config immediately
                              if (config) {
                                onSave(config.id, {
                                  ...config,
                                  skills: newSkills
                                });
                              }
                            }}
                            className="w-3.5 h-3.5 text-primary rounded focus:ring-2 focus:ring-primary cursor-pointer mt-0.5 flex-shrink-0"
                          />
                          <div className="flex-1 min-w-0">
                            <span className="text-xs font-medium block leading-tight" style={{ color: 'var(--color-text-primary, #1a1a1a)' }}>
                              {skill.name}
                            </span>
                            <span className="text-[10px] block leading-tight mt-0.5" style={{ color: 'var(--color-text-muted, #6b7280)' }}>
                              {skill.description?.substring(0, 50)}{skill.description?.length > 50 ? '...' : ''}
                            </span>
                          </div>
                        </label>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          )}

          {/* Middleware Configuration - Collapsible, collapsed by default */}
          {config.agentType !== 'CONDITIONAL_NODE' && config.agentType !== 'LOOP_NODE' && config.agentType !== 'TOOL_NODE' && (
            <div className="border-t border-gray-200 dark:border-border-dark pt-4">
              <button
                onClick={() => setMiddlewareCollapsed(!middlewareCollapsed)}
                className="w-full px-3 py-2 rounded-lg mb-3 flex items-center justify-between"
                style={{ backgroundColor: 'var(--color-primary)' }}
              >
                <h3 className="text-base font-semibold" style={{ color: 'white' }}>
                  Middleware
                </h3>
                <div className="flex items-center gap-2">
                  {enabledMiddleware.length > 0 && (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-white/20" style={{ color: 'white' }}>
                      {enabledMiddleware.length}
                    </span>
                  )}
                  {middlewareCollapsed ? (
                    <ChevronRight size={16} style={{ color: 'white' }} />
                  ) : (
                    <ChevronDown size={16} style={{ color: 'white' }} />
                  )}
                </div>
              </button>
              {!middlewareCollapsed && (
                <div className="grid grid-cols-2 gap-2">
                  {MIDDLEWARE_TYPES.map((middleware) => (
                    <label
                      key={middleware.id}
                      className="flex items-start gap-1.5 p-2 rounded cursor-pointer transition-colors group border hover:border-primary/50"
                      style={{
                        backgroundColor: 'var(--color-background-dark, #f9fafb)',
                        borderColor: 'var(--color-border-dark)'
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={enabledMiddleware.includes(middleware.id)}
                        onChange={() => {
                          const newMiddleware = enabledMiddleware.includes(middleware.id)
                            ? enabledMiddleware.filter(m => m !== middleware.id)
                            : [...enabledMiddleware, middleware.id];

                          setEnabledMiddleware(newMiddleware);

                          // Auto-save: Update node config immediately
                          if (config) {
                            onSave(config.id, {
                              ...config,
                              middleware: newMiddleware.map(type => ({ type, enabled: true, config: {} })),
                              enable_default_middleware: newMiddleware.length > 0
                            });
                          }
                        }}
                        className="w-3.5 h-3.5 text-primary rounded focus:ring-2 focus:ring-primary cursor-pointer mt-0.5 flex-shrink-0"
                      />
                      <div className="flex-1 min-w-0">
                        <span className="text-xs font-medium block leading-tight" style={{ color: 'var(--color-text-primary, #1a1a1a)' }}>
                          {middleware.name}
                        </span>
                        <span className="text-[10px] block leading-tight mt-0.5" style={{ color: 'var(--color-text-muted, #6b7280)' }}>
                          {middleware.description}
                        </span>
                      </div>
                    </label>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Subagents Configuration (Advanced: DeepAgents) - Only for regular agent nodes */}
          {config.agentType !== 'CONDITIONAL_NODE' && config.agentType !== 'LOOP_NODE' && config.agentType !== 'TOOL_NODE' && (
            <div className="border-t border-gray-200 dark:border-border-dark pt-4">
              <div className="px-3 py-2 rounded-lg mb-3 flex items-center justify-between" style={{
                backgroundColor: 'var(--color-primary)',
              }}>
                <div>
                  <h3 className="text-base font-semibold" style={{ color: 'white' }}>
                    Subagents
                  </h3>
                  <p className="text-[10px] mt-0.5" style={{ color: 'rgba(255, 255, 255, 0.8)' }}>
                    Advanced: Delegate work to specialized agents or workflows
                  </p>
                </div>
                <button
                  onClick={addSubagent}
                  className="flex items-center gap-1 px-2 py-1 rounded text-xs font-medium hover:bg-white/20 transition-colors"
                  style={{ color: 'white' }}
                  title="Add new subagent"
                >
                  <Plus size={14} />
                  Add
                </button>
              </div>

              {subagents.length === 0 ? (
                <div className="text-center py-8 px-4">
                  <Workflow size={32} className="mx-auto mb-2 opacity-30" style={{ color: 'var(--color-text-muted)' }} />
                  <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                    No subagents configured. Click "Add" to create one.
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {subagents.map((subagent, index) => (
                    <div
                      key={subagent.name || `subagent-${index}`}
                      className="border rounded-lg overflow-hidden"
                      style={{ borderColor: 'var(--color-border-dark)' }}
                    >
                      {/* Subagent Header */}
                      <div
                        className="flex items-center justify-between p-3 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800/50"
                        onClick={() => toggleSubagentExpanded(index)}
                        style={{ backgroundColor: 'var(--color-background-dark)' }}
                      >
                        <div className="flex items-center gap-2 flex-1 min-w-0">
                          {expandedSubagents.has(index) ? (
                            <ChevronDown size={16} style={{ color: 'var(--color-text-muted)' }} />
                          ) : (
                            <ChevronRight size={16} style={{ color: 'var(--color-text-muted)' }} />
                          )}
                          <span className="text-sm font-medium truncate" style={{ color: 'var(--color-text-primary)' }}>
                            {subagent.name || `Subagent ${index + 1}`}
                          </span>
                          {subagent.type === 'compiled' && (
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-medium" style={{
                              backgroundColor: 'var(--color-primary)',
                              color: 'white'
                            }}>
                              Workflow
                            </span>
                          )}
                        </div>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            deleteSubagent(index);
                          }}
                          className="p-1 rounded hover:bg-red-100 dark:hover:bg-red-900/30 text-red-600 dark:text-red-400"
                          title="Delete subagent"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>

                      {/* Subagent Config (Expanded) */}
                      {expandedSubagents.has(index) && (
                        <div className="p-3 space-y-3 border-t" style={{ borderColor: 'var(--color-border-dark)' }}>


                          {/* Description */}
                          <div>
                            <label className="block text-xs font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                              Description
                            </label>
                            <input
                              type="text"
                              value={subagent.description}
                              onChange={(e) => updateSubagent(index, 'description', e.target.value)}
                              placeholder="What this subagent does (helps main agent decide when to delegate)"
                              className="w-full px-2 py-1 text-xs rounded border"
                              style={{
                                backgroundColor: 'var(--color-background)',
                                borderColor: 'var(--color-border-dark)',
                                color: 'var(--color-text-primary)'
                              }}
                            />
                          </div>

                          {/* Type Selector */}
                          <div>
                            <label className="block text-xs font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                              Type
                            </label>
                            <select
                              value={subagent.type}
                              onChange={(e) => updateSubagent(index, 'type', e.target.value)}
                              onMouseDown={(e) => e.stopPropagation()}
                              onWheel={(e) => e.stopPropagation()}
                              className="w-full px-2 py-1 text-xs rounded border"
                              style={{
                                backgroundColor: 'var(--color-background)',
                                borderColor: 'var(--color-border-dark)',
                                color: 'var(--color-text-primary)'
                              }}
                            >
                              <option value="dictionary">Dictionary (Simple Agent)</option>
                              <option value="compiled">Compiled (Workflow-based)</option>
                            </select>
                            <p className="text-[10px] mt-1" style={{ color: 'var(--color-text-muted)' }}>
                              {subagent.type === 'dictionary'
                                ? 'Simple agent with tools and prompt'
                                : 'Use an existing workflow as a subagent'}
                            </p>
                          </div>

                          {/* Dictionary-specific fields */}
                          {subagent.type === 'dictionary' && (
                            <>
                              <div>
                                <label className="block text-xs font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                                  System Prompt
                                </label>
                                <textarea
                                  value={subagent.system_prompt || ''}
                                  onChange={(e) => updateSubagent(index, 'system_prompt', e.target.value)}
                                  placeholder="Instructions for this subagent..."
                                  rows={3}
                                  className="w-full px-2 py-1 text-xs rounded border resize-none"
                                  style={{
                                    backgroundColor: 'var(--color-background)',
                                    borderColor: 'var(--color-border-dark)',
                                    color: 'var(--color-text-primary)'
                                  }}
                                />
                              </div>

                              <div>
                                <label className="block text-xs font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                                  Model (Optional)
                                </label>
                                <ModelSelectorInline
                                  value={subagent.model || ''}
                                  onChange={(modelId: string) => updateSubagent(index, 'model', modelId)}
                                  includeLocal={true}
                                  onlyValidated={true}
                                  className="text-xs"
                                />
                                <p className="text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
                                  Inherits from main agent if empty
                                </p>
                              </div>
                            </>
                          )}

                          {/* Compiled-specific fields */}
                          {subagent.type === 'compiled' && (
                            <div>
                              <label className="block text-xs font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                                Workflow <span className="text-red-500">*</span>
                              </label>
                              <select
                                value={subagent.workflow_id || ''}
                                onChange={(e) => updateSubagent(index, 'workflow_id', e.target.value ? parseInt(e.target.value) : null)}
                                onMouseDown={(e) => e.stopPropagation()}
                                onWheel={(e) => e.stopPropagation()}
                                className={`w-full px-2 py-1 text-xs rounded border ${!subagent.workflow_id ? 'border-red-500' : ''}`}
                                style={{
                                  backgroundColor: 'var(--color-background)',
                                  borderColor: !subagent.workflow_id ? '#ef4444' : 'var(--color-border-dark)',
                                  color: 'var(--color-text-primary)'
                                }}
                              >
                                <option value="">Select a workflow...</option>
                                {availableWorkflows.map(workflow => (
                                  <option key={workflow.id} value={workflow.id}>
                                    {workflow.name} {workflow.description ? `- ${workflow.description}` : ''}
                                  </option>
                                ))}
                              </select>
                              {!subagent.workflow_id && (
                                <p className="text-[10px] mt-1 text-red-500">
                                  ⚠️ Required: Select a workflow or change type to "Dictionary"
                                </p>
                              )}
                              <p className="text-[10px] mt-1" style={{ color: 'var(--color-text-muted)' }}>
                                The selected workflow will be compiled and used as a subagent
                              </p>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

        </div>
      </aside>

      {/* Custom Tool Builder Modal for Tool Node */}
      {showToolConfigModal && selectedToolId && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50"
          onClick={() => setShowToolConfigModal(false)}
        >
          <div
            className="bg-white dark:bg-panel-dark border border-gray-200 dark:border-border-dark rounded-xl w-full max-w-full md:max-w-6xl h-full md:h-[90vh] flex flex-col shadow-2xl overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <CustomToolBuilder
              existingToolId={selectedToolId}
              skipTemplateStep={false}
              onClose={() => {
                setShowToolConfigModal(false);
                // Optionally refresh the tool data here
              }}
            />
          </div>
        </div>
      )}

      {/* Context Preview Modal */}
      {showContextPreview && selectedDeepAgentId && (
        <ContextPreviewModal
          agentTemplateId={selectedDeepAgentId}
          query=""
          contextMode={contextMode}
          windowSize={contextWindowSize}
          onClose={() => setShowContextPreview(false)}
        />
      )}
    </>
  );
};

export default NodeConfigPanel;
