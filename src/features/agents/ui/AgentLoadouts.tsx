/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Search, Plus, Trash2, Edit, Download, Copy, Upload, Sparkles, Code, Database, Terminal, X, Save, BookOpen, Tag, Clock, TrendingUp } from 'lucide-react';
import DeepAgentBuilder from './DeepAgentBuilder';
import SkillBuilderModal from './SkillBuilderModal';
import CustomToolBuilder from '../../tools/ui/CustomToolBuilder';
import apiClient, { ConflictErrorClass } from '../../../lib/api-client';
import ConflictDialog from '../../workflows/ui/ConflictDialog';
import { useNotification } from '../../../hooks/useNotification';

interface Agent {
  id: number;
  name: string;
  description: string;
  category: string;
  config: any;
  usage_count: number;
  version: string;
  lock_version: number;  // Optimistic locking
  is_public: boolean;
  created_at: string;
  updated_at: string;
}

interface CustomTool {
  id?: number;
  tool_id: string;
  name: string;
  description: string;
  tool_type: string;
  category?: string;
  tags: string[];
  is_template_based?: boolean;
  usage_count: number;
  error_count: number;
  last_used_at?: string;
  input_schema?: any;
  implementation_config?: any;
  output_format?: string;
  validation_rules?: any;
  is_advanced_mode?: boolean;
  template_type?: string;
}

interface Skill {
  skill_id: string;
  name: string;
  description: string;
  version: string;
  source_type: 'builtin' | 'personal' | 'project';
  tags: string[];
  triggers: string[];
  allowed_tools: string[] | null;
  usage_count: number;
  last_used_at: string | null;
  avg_success_rate: number;
  // Extended detail fields (optional, populated when fetching detail)
  instructions?: string;
  examples?: string | null;
  source_path?: string;
  author?: string | null;
  required_context?: string[];
}

type SelectedItem =
  | { type: 'agent'; data: Agent }
  | { type: 'tool'; data: CustomTool }
  | { type: 'skill'; data: Skill }
  | { type: 'template'; category: 'agent' | 'tool' }
  | null;

// Agent Configuration View Component
interface AgentConfigViewProps {
  agent: Agent;
  onSave: (config: any) => Promise<void>;
  onDelete: () => void;
  onClose: () => void;
}

const AgentConfigView = ({ agent, onSave, onDelete, onClose }: AgentConfigViewProps) => {
  const [config, setConfig] = useState(agent.config || {});
  const [agentName, setAgentName] = useState(agent.name);
  const [agentDescription, setAgentDescription] = useState(agent.description);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved'>('idle');
  const [availableCustomTools, setAvailableCustomTools] = useState<Array<{
    id: number;
    tool_id: string;
    name: string;
    description: string;
    tool_type: string;
    category?: string;
    tags: string[];
    implementation_config?: any;
    template_type?: string;
  }>>([]);
  const [expandedTools, setExpandedTools] = useState<Set<string>>(new Set());
  const [showCodeModal, setShowCodeModal] = useState(false);
  const [generatedCode, setGeneratedCode] = useState('');
  const [subagents, setSubagents] = useState(agent.config?.subagents || []);
  const [expandedSubagents, setExpandedSubagents] = useState<Set<number>>(new Set());
  const [availableWorkflows, setAvailableWorkflows] = useState<Array<{ id: number, name: string, description?: string }>>([]);

  // Update config when agent changes
  useEffect(() => {
    setConfig(agent.config || {});
    setAgentName(agent.name);
    setAgentDescription(agent.description);
  }, [agent]);

  // Fetch custom tools
  useEffect(() => {
    const abortController = new AbortController();

    const fetchCustomTools = async () => {
      try {
        const response = await apiClient.listCustomTools({ signal: abortController.signal } as any);
        setAvailableCustomTools(response.data || []);
      } catch (error) {
        // Ignore abort errors
        if (error instanceof Error && error.name === 'AbortError') {
          return;
        }
        console.error('Failed to fetch custom tools:', error);
      }
    };
    fetchCustomTools();

    return () => {
      abortController.abort();
    };
  }, []);

  // Fetch available workflows for CompiledSubAgent
  useEffect(() => {
    const abortController = new AbortController();

    const fetchWorkflows = async () => {
      try {
        const response = await apiClient.listWorkflows();
        setAvailableWorkflows(response.data || []);
      } catch (error) {
        // Ignore abort errors
        if (error instanceof Error && error.name === 'AbortError') {
          return;
        }
        console.error('Failed to fetch workflows:', error);
      }
    };
    fetchWorkflows();

    return () => {
      abortController.abort();
    };
  }, []);

  // Complete tool list from backend/tools/native_tools.py with DeepAgents standard naming
  // See: https://docs.langchain.com/oss/python/deepagents/harness
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
    { id: 'enable_memory', name: 'Enable Memory', description: 'Capability flag: enables long‑term memory for this agent (persisted via project/workflow store). Not a tool by itself; pair with Store/Recall Memory.', category: 'memory' },
    { id: 'memory_store', name: 'Store Memory', description: 'Save information to the agent\'s long‑term memory store', category: 'memory' },
    { id: 'memory_recall', name: 'Recall Memory', description: 'Retrieve previously stored information from memory', category: 'memory' },
    { id: 'enable_rag', name: 'Enable RAG', description: 'Capability flag: enables retrieval from the project\'s vector store (documents/KB). Not a tool by itself.', category: 'memory' },
    { id: 'reasoning_chain', name: 'Reasoning Chain', description: 'Multi-step reasoning', category: 'reasoning' },
  ];

  // Complete middleware list from backend/orchestration/middleware_presets.py
  const MIDDLEWARE_OPTIONS = [
    { id: 'timestamp', name: 'Timestamp Injection', description: 'Inject current time into agent context', category: 'Context' },
    { id: 'project_context', name: 'Project Context', description: 'Add project-specific context', category: 'Context' },
    { id: 'logging', name: 'Request Logging', description: 'Log inputs and outputs for debugging', category: 'Monitoring' },
    { id: 'validation', name: 'Input Validation', description: 'Validate inputs and outputs', category: 'Security' },
    { id: 'cost_tracking', name: 'Cost Tracking', description: 'Track token usage and API costs', category: 'Monitoring' },
    { id: 'tool_retry', name: 'Tool Retry Logic', description: 'Automatically retry failed tool calls', category: 'Reliability' },
    { id: 'pii', name: 'PII Detection', description: 'Redact sensitive information from logs', category: 'Security' },
    { id: 'hitl', name: 'Human-in-Loop', description: 'Require human approval for actions', category: 'Control' },
    { id: 'summarization', name: 'Response Summarization', description: 'Summarize long conversations', category: 'Optimization' },
  ];

  const toggleTool = (toolId: string) => {
    const nativeTools = config.native_tools || [];
    const updated = nativeTools.includes(toolId)
      ? nativeTools.filter((t: string) => t !== toolId)
      : [...nativeTools, toolId];
    setConfig({ ...config, native_tools: updated });
  };

  const toggleCustomTool = (toolId: string) => {
    const customTools = config.custom_tools || [];
    const updated = customTools.includes(toolId)
      ? customTools.filter((t: string) => t !== toolId)
      : [...customTools, toolId];
    setConfig({ ...config, custom_tools: updated });
  };

  const toggleMiddleware = (middlewareId: string) => {
    const middleware = config.middleware || [];
    const exists = middleware.find((m: any) => m.type === middlewareId);
    const updated = exists
      ? middleware.filter((m: any) => m.type !== middlewareId)
      : [...middleware, { type: middlewareId, enabled: true, config: {} }];
    setConfig({ ...config, middleware: updated });
  };

  // Subagent management functions
  const addSubagent = () => {
    const newSubagent = {
      name: '',
      description: '',
      type: 'dictionary',  // Default to dictionary-based
      system_prompt: '',
      tools: [],
      model: config.model || 'claude-sonnet-4-5-20250929',
      middleware: [],
      workflow_id: null,
      workflow_config: null
    };
    const updated = [...subagents, newSubagent];
    setSubagents(updated);
    setConfig({ ...config, subagents: updated });
    // Auto-expand new subagent
    setExpandedSubagents(new Set([...expandedSubagents, updated.length - 1]));
  };

  const updateSubagent = (index: number, field: string, value: any) => {
    const updated = [...subagents];
    updated[index] = { ...updated[index], [field]: value };
    setSubagents(updated);
    setConfig({ ...config, subagents: updated });
  };

  const deleteSubagent = (index: number) => {
    const updated = subagents.filter((_: any, i: number) => i !== index);
    setSubagents(updated);
    setConfig({ ...config, subagents: updated });
    // Remove from expanded set
    const newExpanded = new Set(expandedSubagents);
    newExpanded.delete(index);
    setExpandedSubagents(newExpanded);
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

  const toggleSubagentTool = (subagentIndex: number, toolId: string, checked: boolean) => {
    const updated = [...subagents];
    const tools = updated[subagentIndex].tools || [];
    updated[subagentIndex].tools = checked
      ? [...tools, toolId]
      : tools.filter((t: string) => t !== toolId);
    setSubagents(updated);
    setConfig({ ...config, subagents: updated });
  };

  const handleSave = async () => {
    setSaveStatus('saving');
    try {
      await onSave({
        ...config,
        name: agentName,
        description: agentDescription,
      });
      setSaveStatus('saved');
      setTimeout(() => setSaveStatus('idle'), 2000);
    } catch (error) {
      console.error('Failed to save agent:', error);
      setSaveStatus('idle');
    }
  };

  const generateLangChainCode = () => {
    const tools = config.native_tools || [];
    const customTools = config.custom_tools || [];
    const middleware = config.middleware || [];

    let code = `"""
LangChain Agent Configuration
Agent: ${agentName}
Generated from LangConfig
"""

from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import SystemMessage
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.prebuilt import create_react_agent

# Initialize LLM
llm = ChatOpenAI(
    model="${config.model || 'gpt-4o'}",
    temperature=${config.temperature ?? 0.7},
    max_tokens=${config.max_tokens || 4000}
)

# System Prompt
system_prompt = """${config.system_prompt || 'You are a helpful AI assistant.'}"""

# Load Tools
tools = []
`;

    if (tools.length > 0) {
      code += `\n# Native Tools\n`;
      code += `from tools.native_tools import load_native_tools\n`;
      code += `tools.extend(load_native_tools([\n`;
      tools.forEach((tool: string) => {
        code += `    "${tool}",\n`;
      });
      code += `]))\n`;
    }

    if (customTools.length > 0) {
      code += `\n# Custom Tools\n`;
      code += `from orchestration.tool_factory import ToolFactory\n`;
      code += `tool_factory = ToolFactory()\n`;
      customTools.forEach((toolId: string) => {
        code += `tools.append(tool_factory.load_custom_tool("${toolId}"))\n`;
      });
    }

    if (middleware.length > 0) {
      code += `\n# Middleware Configuration\n`;
      code += `middleware_config = [\n`;
      middleware.forEach((m: any) => {
        code += `    {"type": "${m.type}", "enabled": True, "config": {}},\n`;
      });
      code += `]\n`;
    }

    code += `
# Create Agent
agent = create_react_agent(
    llm,
    tools,
    state_modifier=system_prompt
)

# PostgreSQL Checkpointer for memory
checkpointer = PostgresSaver.from_conn_string(
    "postgresql://user:pass@localhost/langconfig"
)

# Create Agent Executor with checkpointing
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    checkpointer=checkpointer,
    verbose=True
)

# Run the agent
result = agent_executor.invoke(
    {"messages": [("user", "Your input here")]},
    config={"configurable": {"thread_id": "unique-thread-id"}}
)

print(result)
`;

    return code;
  };

  const handleViewCode = () => {
    const code = generateLangChainCode();
    setGeneratedCode(code);
    setShowCodeModal(true);
  };

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="p-6">
        <div className="max-w-6xl mx-auto">
          {/* Compact Header with All Basic Info */}
          <div className="mb-4 pb-4 border-b" style={{ borderBottomColor: 'var(--color-border-dark)' }}>
            <div className="flex items-start gap-4">
              <div
                className="w-16 h-16 rounded-xl flex items-center justify-center flex-shrink-0 shadow-sm"
                style={{ backgroundColor: 'var(--color-background-light)' }}
              >
                <span className="material-symbols-outlined text-3xl" style={{ color: 'var(--color-primary)' }}>
                  psychology
                </span>
              </div>
              <div className="flex-1 min-w-0 flex flex-col">
                {/* Name */}
                <input
                  type="text"
                  value={agentName}
                  onChange={(e) => setAgentName(e.target.value)}
                  className="text-xl font-bold w-full px-3 py-2 border border-gray-200 dark:border-border-dark bg-white dark:bg-panel-dark rounded-lg focus:outline-none focus:ring-2 focus:ring-primary mb-3"
                  style={{
                    color: 'var(--color-text-primary)'
                  }}
                />
                {/* Description */}
                <textarea
                  value={agentDescription}
                  onChange={(e) => setAgentDescription(e.target.value)}
                  className="text-sm w-full px-3 py-2 border border-gray-200 dark:border-border-dark bg-white dark:bg-panel-dark rounded-lg focus:outline-none focus:ring-2 focus:ring-primary resize-none flex-1"
                  rows={4}
                  placeholder="Description..."
                  style={{
                    color: 'var(--color-text-primary)',
                    minHeight: '100px'
                  }}
                />

                {/* Agent Type Toggle - PROMINENT */}
                <div className="mt-4 p-4 rounded-lg border-2" style={{
                  borderColor: config.use_deepagents ? 'var(--color-primary)' : 'var(--color-border-dark)',
                  backgroundColor: config.use_deepagents ? 'rgba(var(--color-primary-rgb), 0.05)' : 'var(--color-background-light)'
                }}>
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                      Agent Framework
                    </label>
                    <select
                      value={config.use_deepagents ? 'deep' : 'regular'}
                      onChange={(e) => {
                        const isDeep = e.target.value === 'deep';
                        setConfig({
                          ...config,
                          use_deepagents: isDeep,
                          subagents: isDeep ? (config.subagents || []) : [],
                          middleware: isDeep ? (config.middleware || []) : []
                        });
                      }}
                      className="px-4 py-2 rounded-lg text-sm font-semibold border-2 min-w-[180px]"
                      style={{
                        backgroundColor: 'var(--color-background)',
                        borderColor: config.use_deepagents ? 'var(--color-primary)' : 'var(--color-border-dark)',
                        color: config.use_deepagents ? 'var(--color-primary)' : 'var(--color-text-primary)'
                      }}
                    >
                      <option value="regular">Regular Agent</option>
                      <option value="deep">Deep Agent</option>
                    </select>
                  </div>
                  <p className="text-xs leading-relaxed" style={{ color: 'var(--color-text-muted)' }}>
                    {config.use_deepagents
                      ? 'Deep Agents support subagents (workflow reuse), middleware, and advanced context management'
                      : 'Regular Agents are standard LangChain agents with tool calling'}
                  </p>
                  {!config.use_deepagents && (
                    <div className="mt-2 p-2 rounded" style={{ backgroundColor: 'rgba(59, 130, 246, 0.1)', borderLeft: '3px solid #3b82f6' }}>
                      <p className="text-xs font-medium" style={{ color: '#3b82f6' }}>
                        Switch to Deep Agent to enable Subagents and Compiled Workflows
                      </p>
                    </div>
                  )}
                </div>

                {/* Tags Row - Simplified */}
                <div className="flex flex-wrap items-center gap-2 mt-3">
                  <span className="text-xs px-2.5 py-1 rounded-md font-medium" style={{
                    backgroundColor: 'var(--color-primary)',
                    color: 'white'
                  }}>
                    {agent.category}
                  </span>
                  <span className="text-xs px-2.5 py-1 rounded-md" style={{
                    backgroundColor: 'var(--color-background-light)',
                    color: 'var(--color-text-muted)'
                  }}>
                    v{agent.version}
                  </span>
                  <span className="text-xs px-2.5 py-1 rounded-md" style={{
                    backgroundColor: 'var(--color-background-light)',
                    color: 'var(--color-text-muted)'
                  }}>
                    {agent.usage_count} uses
                  </span>
                </div>
              </div>

              {/* Right Side - Stacked Vertically */}
              <div className="flex flex-col gap-3 justify-between">
                {/* Action Buttons Row */}
                <div className="flex items-center gap-2">
                  <button
                    onClick={handleViewCode}
                    className="px-4 py-2 rounded-lg text-sm font-medium border border-gray-200 dark:border-border-dark bg-white dark:bg-panel-dark text-gray-700 dark:text-gray-200 flex items-center gap-2 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
                  >
                    <Code size={16} />
                    View Code
                  </button>
                  <button
                    onClick={handleSave}
                    disabled={saveStatus === 'saving'}
                    className="px-4 py-2 rounded-lg text-sm font-medium text-white hover:opacity-90 transition-opacity"
                    style={{
                      backgroundColor: saveStatus === 'saved' ? '#10b981' : 'var(--color-primary)',
                      opacity: saveStatus === 'saving' ? 0.5 : 1
                    }}
                  >
                    {saveStatus === 'saving' ? 'Saving...' : saveStatus === 'saved' ? '✓ Saved' : 'Save'}
                  </button>
                  <button
                    onClick={onDelete}
                    className="px-3 py-2 rounded-lg text-sm font-medium border hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                    style={{
                      backgroundColor: 'rgba(239, 68, 68, 0.1)',
                      borderColor: 'rgba(239, 68, 68, 0.3)',
                      color: '#ef4444'
                    }}
                  >
                    <Trash2 size={16} />
                  </button>
                </div>

                {/* Model Configuration - With Labels */}
                <div className="flex items-center gap-3">
                  <div className="flex flex-col gap-1">
                    <label className="text-xs font-medium" style={{ color: 'var(--color-text-muted)' }}>
                      Model
                    </label>
                    <select
                      value={config.model || 'gpt-4o'}
                      onChange={(e) => setConfig({ ...config, model: e.target.value })}
                      className="px-3 py-2 border border-gray-200 dark:border-border-dark bg-white dark:bg-panel-dark rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                      style={{
                        color: 'var(--color-text-primary)',
                        minWidth: '160px'
                      }}
                    >
                      <option value="gpt-5.2">GPT-5.2</option>
                      <option value="gpt-5.1">GPT-5.1</option>
                      <option value="gpt-4o">GPT-4o</option>
                      <option value="gpt-4o-mini">GPT-4o Mini</option>
                      <option value="claude-sonnet-4-5">Claude Sonnet 4.5</option>
                      <option value="claude-haiku-4-5">Claude Haiku 4.5</option>
                    </select>
                  </div>

                  <div className="flex flex-col gap-1">
                    <label className="text-xs font-medium" style={{ color: 'var(--color-text-muted)' }}>
                      Temperature
                    </label>
                    <input
                      type="number"
                      min="0"
                      max="2"
                      step="0.1"
                      value={config.temperature ?? 0.7}
                      onChange={(e) => setConfig({ ...config, temperature: parseFloat(e.target.value) })}
                      className="w-24 px-3 py-2 border border-gray-200 dark:border-border-dark bg-white dark:bg-panel-dark rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                      style={{
                        color: 'var(--color-text-primary)'
                      }}
                    />
                  </div>

                  <div className="flex flex-col gap-1">
                    <label className="text-xs font-medium" style={{ color: 'var(--color-text-muted)' }}>
                      Max Tokens
                    </label>
                    <input
                      type="number"
                      min="100"
                      max="16000"
                      step="100"
                      value={config.max_tokens || 4000}
                      onChange={(e) => setConfig({ ...config, max_tokens: parseInt(e.target.value) })}
                      className="w-28 px-3 py-2 border border-gray-200 dark:border-border-dark bg-white dark:bg-panel-dark rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                      style={{
                        color: 'var(--color-text-primary)'
                      }}
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Top Row: Two Column Layout */}
          <div className="grid grid-cols-2 gap-6 mb-4">
            {/* Left Column - Agent Tools */}
            <div>
              <div className="px-3 py-1.5 rounded-lg mb-2" style={{ backgroundColor: 'var(--color-primary)' }}>
                <h3 className="text-sm font-semibold" style={{ color: 'white' }}>
                  Agent Tools
                </h3>
              </div>
              <div className="grid grid-cols-2 gap-3">
                {/* All Tools in 2 Column Grid */}
                {AVAILABLE_TOOLS.map(tool => (
                  <label
                    key={tool.id}
                    className="group relative flex items-start gap-2 px-3 py-2.5 rounded-xl cursor-pointer transition-all duration-200 border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 hover:border-primary/50 hover:shadow-md"
                    title={tool.id === 'enable_memory' || tool.id === 'enable_rag' ? undefined : tool.description}
                  >
                    <input
                      type="checkbox"
                      checked={(config.native_tools || []).includes(tool.id)}
                      onChange={() => toggleTool(tool.id)}
                      className="w-3.5 h-3.5 text-primary rounded focus:ring-1 focus:ring-primary cursor-pointer flex-shrink-0 mt-0.5"
                    />
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-semibold mb-0.5" style={{ color: 'var(--color-text-primary, #1a1a1a)' }}>
                        {tool.name}
                      </div>
                      <div className="text-xs leading-snug" style={{ color: 'var(--color-text-secondary, #6b7280)' }}>
                        {tool.description}
                      </div>
                    </div>

                    {(tool.id === 'enable_memory' || tool.id === 'enable_rag') && (
                      <div
                        className="pointer-events-none absolute -top-2 right-full mr-2 w-64 px-3 py-2 rounded border shadow-lg opacity-0 group-hover:opacity-100 transition-opacity"
                        style={{ backgroundColor: 'var(--color-panel-dark)', borderColor: 'var(--color-border-dark)', color: 'var(--color-text-primary)', zIndex: 100001 }}
                        role="tooltip"
                      >
                        {tool.id === 'enable_memory' ? (
                          <>
                            <div className="text-xs font-semibold mb-1">Enable Memory</div>
                            <div className="text-[11px] leading-snug">
                              Turns on long‑term memory for this agent (project/workflow store). Use <strong>Store Memory</strong> and <strong>Recall Memory</strong> to write/read entries.
                            </div>
                          </>
                        ) : (
                          <>
                            <div className="text-xs font-semibold mb-1">Enable RAG</div>
                            <div className="text-[11px] leading-snug">
                              Allows retrieval from your project’s vector store (documents/KB). This is a capability flag, not a tool.
                            </div>
                          </>
                        )}
                      </div>
                    )}
                  </label>
                ))}

                {/* Custom Tools */}
                {availableCustomTools.length > 0 && (
                  <>
                    <div className="px-3 py-1.5 rounded-lg mb-2 mt-4" style={{ backgroundColor: 'var(--color-primary)' }}>
                      <h3 className="text-sm font-semibold" style={{ color: 'white' }}>
                        Custom Tools
                      </h3>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      {availableCustomTools.map(tool => {
                        const isExpanded = expandedTools.has(tool.tool_id);
                        return (
                          <div key={tool.tool_id} className="flex flex-col">
                            <label
                              className="group relative flex items-start gap-2 px-3 py-2.5 rounded-xl cursor-pointer transition-all duration-200 border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 hover:border-primary/50 hover:shadow-md"
                            >
                              <input
                                type="checkbox"
                                checked={(config.custom_tools || []).includes(tool.tool_id)}
                                onChange={() => toggleCustomTool(tool.tool_id)}
                                className="w-3.5 h-3.5 text-primary rounded focus:ring-1 focus:ring-primary cursor-pointer flex-shrink-0 mt-0.5"
                              />
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center justify-between gap-2 mb-1">
                                  <div className="text-xs font-semibold truncate flex-1" style={{ color: 'var(--color-text-primary, #1a1a1a)' }}>
                                    {tool.name || tool.tool_id}
                                  </div>
                                  <button
                                    onClick={(e) => {
                                      e.preventDefault();
                                      setExpandedTools(prev => {
                                        const next = new Set(prev);
                                        if (next.has(tool.tool_id)) {
                                          next.delete(tool.tool_id);
                                        } else {
                                          next.add(tool.tool_id);
                                        }
                                        return next;
                                      });
                                    }}
                                    className="text-xs px-2 py-0.5 rounded hover:bg-primary/10 flex-shrink-0"
                                    style={{ color: 'var(--color-primary)' }}
                                  >
                                    {isExpanded ? 'Hide' : 'Details'}
                                  </button>
                                </div>
                                {tool.category && (
                                  <div className="text-xs mb-1 truncate" style={{ color: 'var(--color-text-secondary, #6b7280)' }}>
                                    {tool.category}
                                  </div>
                                )}
                                <div className="text-xs leading-snug line-clamp-2" style={{ color: 'var(--color-text-secondary, #6b7280)' }}>
                                  {tool.description || 'No description available'}
                                </div>
                              </div>
                            </label>

                            {isExpanded && tool.implementation_config && (
                              <div className="mt-1 px-3 py-2.5 border border-gray-200 dark:border-gray-800 rounded-xl bg-gray-50/50 dark:bg-gray-800/50">
                                <div className="text-xs space-y-1">
                                  <div className="font-semibold mb-1.5" style={{ color: 'var(--color-text-primary)' }}>Configuration:</div>
                                  {tool.implementation_config.provider && (
                                    <div><strong>Provider:</strong> {tool.implementation_config.provider}</div>
                                  )}
                                  {tool.implementation_config.model && (
                                    <div><strong>Model:</strong> {tool.implementation_config.model}</div>
                                  )}
                                  {tool.implementation_config.url && (
                                    <div><strong>URL:</strong> {tool.implementation_config.url}</div>
                                  )}
                                  {tool.implementation_config.webhook_url && (
                                    <div><strong>Webhook:</strong> {tool.implementation_config.webhook_url}</div>
                                  )}
                                  {tool.template_type && (
                                    <div><strong>Template:</strong> {tool.template_type}</div>
                                  )}
                                  <div className="mt-1.5 pt-1.5 border-t border-gray-200 dark:border-gray-700" style={{ color: 'var(--color-text-muted)' }}>
                                    <strong>Tool ID:</strong> {tool.tool_id}
                                  </div>
                                </div>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </>
                )}

              </div>
            </div>

            {/* Right Column - System Prompt */}
            <div>
              {/* System Prompt */}
              <div>
                <div className="px-3 py-1.5 rounded-lg mb-2" style={{ backgroundColor: 'var(--color-primary)' }}>
                  <h3 className="text-sm font-semibold" style={{ color: 'white' }}>
                    System Prompt
                  </h3>
                </div>
                <textarea
                  value={config.system_prompt || ''}
                  onChange={(e) => setConfig({ ...config, system_prompt: e.target.value })}
                  rows={30}
                  className="w-full px-2 py-1.5 border border-gray-200 dark:border-border-dark bg-white dark:bg-panel-dark rounded-lg text-xs font-mono focus:outline-none focus:ring-1 focus:ring-primary resize-none"
                  placeholder="Enter system prompt..."
                  style={{
                    color: 'var(--color-text-primary)'
                  }}
                />
                <p className="text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
                  {(config.system_prompt || '').length} characters
                </p>
              </div>
            </div>
          </div>

          {/* Bottom Row: Middleware (Full Width) */}
          <div>
            <div className="px-3 py-1.5 rounded-lg mb-2" style={{ backgroundColor: 'var(--color-primary)' }}>
              <h3 className="text-sm font-semibold" style={{ color: 'white' }}>
                Middleware
              </h3>
            </div>
            <div className="grid grid-cols-4 gap-3">
              {MIDDLEWARE_OPTIONS.map(middleware => (
                <label
                  key={middleware.id}
                  className="flex items-start gap-2 px-3 py-2.5 rounded cursor-pointer transition-colors border border-gray-200 dark:border-border-dark bg-white dark:bg-panel-dark hover:border-primary/50"
                >
                  <input
                    type="checkbox"
                    checked={(config.middleware || []).some((m: any) => m.type === middleware.id)}
                    onChange={() => toggleMiddleware(middleware.id)}
                    className="w-3.5 h-3.5 text-primary rounded focus:ring-1 focus:ring-primary cursor-pointer flex-shrink-0 mt-0.5"
                  />
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-semibold mb-0.5" style={{ color: 'var(--color-text-primary, #1a1a1a)' }}>
                      {middleware.name}
                    </div>
                    <div className="text-xs leading-snug" style={{ color: 'var(--color-text-secondary, #6b7280)' }}>
                      {middleware.description}
                    </div>
                  </div>
                </label>
              ))}
            </div>
          </div>

          {/* Subagents Section - Only for Deep Agents */}
          {config.use_deepagents && (
            <div className="mt-6">
              <div className="px-3 py-1.5 rounded-lg mb-2 flex items-center justify-between" style={{ backgroundColor: 'var(--color-primary)' }}>
                <h3 className="text-sm font-semibold" style={{ color: 'white' }}>
                  Subagents
                </h3>
                <button
                  onClick={addSubagent}
                  className="px-3 py-1 rounded text-xs font-medium bg-white text-primary hover:bg-opacity-90 transition-opacity flex items-center gap-1"
                >
                  <Plus size={14} />
                  Add Subagent
                </button>
              </div>

              {subagents.length === 0 ? (
                <div className="text-center py-8 border rounded-lg" style={{
                  borderColor: 'var(--color-border-dark)',
                  backgroundColor: 'var(--color-background-light)'
                }}>
                  <p className="text-sm mb-2" style={{ color: 'var(--color-text-muted)' }}>
                    No subagents configured
                  </p>
                  <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                    Subagents help isolate context and delegate specialized tasks
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {subagents.map((subagent: any, index: number) => {
                    const isExpanded = expandedSubagents.has(index);
                    const hasErrors = !subagent.name || !subagent.description || !subagent.system_prompt;

                    return (
                      <div
                        key={index}
                        className="border rounded-lg"
                        style={{
                          borderColor: hasErrors ? '#ef4444' : 'var(--color-border-dark)',
                          backgroundColor: 'var(--color-background-light)'
                        }}
                      >
                        {/* Subagent Header */}
                        <div
                          className="px-4 py-3 flex items-center justify-between cursor-pointer"
                          onClick={() => toggleSubagentExpanded(index)}
                        >
                          <div className="flex items-center gap-3 flex-1">
                            <button
                              className="text-gray-500 hover:text-gray-700 transition-colors"
                              onClick={(e) => {
                                e.stopPropagation();
                                toggleSubagentExpanded(index);
                              }}
                            >
                              {isExpanded ? '▼' : '▶'}
                            </button>
                            <div className="flex-1">
                              <div className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                                {subagent.name || <span style={{ color: 'var(--color-text-muted)' }}>Unnamed Subagent</span>}
                              </div>
                              {subagent.description && (
                                <div className="text-xs mt-0.5" style={{ color: 'var(--color-text-muted)' }}>
                                  {subagent.description.substring(0, 60)}{subagent.description.length > 60 ? '...' : ''}
                                </div>
                              )}
                            </div>
                          </div>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              if (confirm('Delete this subagent?')) {
                                deleteSubagent(index);
                              }
                            }}
                            className="px-3 py-1.5 rounded text-xs font-medium text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                          >
                            Delete
                          </button>
                        </div>

                        {/* Subagent Configuration - Expanded */}
                        {isExpanded && (
                          <div className="px-4 pb-4 space-y-4 border-t" style={{ borderTopColor: 'var(--color-border-dark)' }}>
                            {/* Name - Required */}
                            <div>
                              <label className="block text-xs font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                                Name <span className="text-red-500">*</span>
                              </label>
                              <input
                                type="text"
                                value={subagent.name}
                                onChange={(e) => updateSubagent(index, 'name', e.target.value)}
                                placeholder="e.g., research-agent"
                                className="w-full px-3 py-2 border rounded-lg text-sm"
                                style={{
                                  backgroundColor: 'var(--color-background-light)',
                                  borderColor: !subagent.name ? '#ef4444' : 'var(--color-border-dark)',
                                  color: 'var(--color-text-primary)'
                                }}
                              />
                              <p className="text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
                                Unique identifier used when delegating tasks
                              </p>
                            </div>

                            {/* Description - Required */}
                            <div>
                              <label className="block text-xs font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                                Description <span className="text-red-500">*</span>
                              </label>
                              <textarea
                                value={subagent.description}
                                onChange={(e) => updateSubagent(index, 'description', e.target.value)}
                                placeholder="What this subagent does (be specific and action-oriented)"
                                rows={2}
                                className="w-full px-3 py-2 border rounded-lg text-sm resize-none"
                                style={{
                                  backgroundColor: 'var(--color-background-light)',
                                  borderColor: !subagent.description ? '#ef4444' : 'var(--color-border-dark)',
                                  color: 'var(--color-text-primary)'
                                }}
                              />
                              <p className="text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
                                The main agent uses this to decide when to delegate
                              </p>
                            </div>

                            {/* Type Selector */}
                            <div>
                              <label className="block text-xs font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                                Subagent Type <span className="text-red-500">*</span>
                              </label>
                              <select
                                value={subagent.type || 'dictionary'}
                                onChange={(e) => updateSubagent(index, 'type', e.target.value)}
                                className="w-full px-3 py-2 border rounded-lg text-sm"
                                style={{
                                  backgroundColor: 'var(--color-background-light)',
                                  borderColor: 'var(--color-border-dark)',
                                  color: 'var(--color-text-primary)'
                                }}
                              >
                                <option value="dictionary">Dictionary (Simple Agent)</option>
                                <option value="compiled">Compiled (Workflow-based)</option>
                              </select>
                              <p className="text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
                                {subagent.type === 'compiled'
                                  ? 'Use an existing workflow as a subagent - great for reusing complex multi-agent workflows'
                                  : 'Simple agent with tools and prompt - ideal for focused, single-purpose tasks'}
                              </p>
                            </div>

                            {/* Dictionary-specific fields */}
                            {(!subagent.type || subagent.type === 'dictionary') && (
                              <>
                                {/* System Prompt - Required */}
                                <div>
                                  <label className="block text-xs font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                                    System Prompt <span className="text-red-500">*</span>
                                  </label>
                                  <textarea
                                    value={subagent.system_prompt}
                                    onChange={(e) => updateSubagent(index, 'system_prompt', e.target.value)}
                                    placeholder="Instructions for the subagent (include tool usage guidance and output format)"
                                    rows={6}
                                    className="w-full px-3 py-2 border rounded-lg text-sm font-mono resize-none"
                                    style={{
                                      backgroundColor: 'var(--color-background-light)',
                                      borderColor: !subagent.system_prompt ? '#ef4444' : 'var(--color-border-dark)',
                                      color: 'var(--color-text-primary)'
                                    }}
                                  />
                                </div>

                                {/* Tools */}
                                <div>
                                  <label className="block text-xs font-medium mb-2" style={{ color: 'var(--color-text-primary)' }}>
                                    Tools
                                  </label>
                                  <div className="grid grid-cols-2 gap-2 max-h-48 overflow-y-auto">
                                    {AVAILABLE_TOOLS.map(tool => (
                                      <label
                                        key={tool.id}
                                        className="flex items-start gap-2 px-2 py-1.5 rounded cursor-pointer transition-colors border hover:border-primary/50"
                                        style={{
                                          backgroundColor: 'var(--color-background-dark)',
                                          borderColor: 'var(--color-border-dark)'
                                        }}
                                      >
                                        <input
                                          type="checkbox"
                                          checked={(subagent.tools || []).includes(tool.id)}
                                          onChange={(e) => toggleSubagentTool(index, tool.id, e.target.checked)}
                                          className="w-3 h-3 text-primary rounded cursor-pointer flex-shrink-0 mt-0.5"
                                        />
                                        <div className="flex-1 min-w-0">
                                          <div className="text-xs font-medium" style={{ color: 'var(--color-text-primary)' }}>
                                            {tool.name}
                                          </div>
                                        </div>
                                      </label>
                                    ))}
                                    {availableCustomTools.map(tool => (
                                      <label
                                        key={tool.tool_id}
                                        className="flex items-start gap-2 px-2 py-1.5 rounded cursor-pointer transition-colors border hover:border-primary/50"
                                        style={{
                                          backgroundColor: 'var(--color-background-dark)',
                                          borderColor: 'var(--color-border-dark)'
                                        }}
                                      >
                                        <input
                                          type="checkbox"
                                          checked={(subagent.tools || []).includes(tool.tool_id)}
                                          onChange={(e) => toggleSubagentTool(index, tool.tool_id, e.target.checked)}
                                          className="w-3 h-3 text-primary rounded cursor-pointer flex-shrink-0 mt-0.5"
                                        />
                                        <div className="flex-1 min-w-0">
                                          <div className="text-xs font-medium" style={{ color: 'var(--color-text-primary)' }}>
                                            {tool.name || tool.tool_id}
                                          </div>
                                        </div>
                                      </label>
                                    ))}
                                  </div>
                                  <p className="text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
                                    Only include tools needed for this subagent's specific task
                                  </p>
                                </div>

                                {/* Model Override */}
                                <div>
                                  <label className="block text-xs font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                                    Model Override <span className="text-xs font-normal" style={{ color: 'var(--color-text-muted)' }}>(optional)</span>
                                  </label>
                                  <select
                                    value={subagent.model || ''}
                                    onChange={(e) => updateSubagent(index, 'model', e.target.value)}
                                    className="w-full px-3 py-2 border rounded-lg text-sm"
                                    style={{
                                      backgroundColor: 'var(--color-background-light)',
                                      borderColor: 'var(--color-border-dark)',
                                      color: 'var(--color-text-primary)'
                                    }}
                                  >
                                    <option value="">Use parent agent model</option>
                                    <option value="openai:gpt-5.2">GPT-5.2</option>
                                    <option value="openai:gpt-4o">GPT-4o</option>
                                    <option value="openai:gpt-4o-mini">GPT-4o Mini</option>
                                    <option value="claude-sonnet-4-5-20250929">Claude Sonnet 4.5</option>
                                    <option value="claude-3-5-sonnet-20241022">Claude 3.5 Sonnet</option>
                                    <option value="anthropic:claude-opus-4-20250514">Claude Opus 4</option>
                                  </select>
                                  <p className="text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
                                    Different models excel at different tasks (e.g., use GPT-4o for numerical analysis)
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
                                  onChange={(e) => updateSubagent(index, 'workflow_id', parseInt(e.target.value))}
                                  className="w-full px-3 py-2 border rounded-lg text-sm"
                                  style={{
                                    backgroundColor: 'var(--color-background-light)',
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
                                <p className="text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
                                  The selected workflow will be compiled and executed as a subagent. Perfect for reusing complex multi-agent workflows.
                                </p>
                                <div className="mt-2 p-2 rounded" style={{ backgroundColor: 'var(--color-background)', borderLeft: '3px solid var(--color-primary)' }}>
                                  <p className="text-xs font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                                    💡 Context Quarantine
                                  </p>
                                  <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                                    The main agent receives only the final result from this workflow, keeping its context clean and focused.
                                  </p>
                                </div>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Code Modal */}
      {showCodeModal && (
        <div
          className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4"
          onClick={() => setShowCodeModal(false)}
        >
          <div
            className="bg-white dark:bg-panel-dark rounded-xl w-full max-w-4xl max-h-[90vh] flex flex-col shadow-2xl"
            onClick={(e) => e.stopPropagation()}
            style={{ borderColor: 'var(--color-border-dark)' }}
          >
            {/* Modal Header */}
            <div className="flex items-center justify-between p-6 border-b" style={{
              backgroundColor: 'var(--color-primary)',
              borderBottomColor: 'var(--color-border-dark)'
            }}>
              <div className="flex items-center gap-2">
                <Code size={20} className="text-white" />
                <h3 className="text-lg font-semibold text-white" style={{ textShadow: '0 1px 2px rgba(0, 0, 0, 0.25)' }}>
                  LangChain Agent Code
                </h3>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(generatedCode);
                  }}
                  className="px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-all"
                  style={{
                    backgroundColor: 'rgba(255, 255, 255, 0.2)',
                    border: '1px solid rgba(255, 255, 255, 0.3)',
                    color: 'white',
                    textShadow: '0 1px 2px rgba(0, 0, 0, 0.15)'
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.3)'}
                  onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.2)'}
                >
                  <Copy size={14} />
                  Copy
                </button>
                <button
                  onClick={() => setShowCodeModal(false)}
                  className="p-2 transition-all text-white/90 hover:text-white hover:bg-white/15 rounded-lg"
                  style={{ textShadow: '0 1px 2px rgba(0, 0, 0, 0.15)' }}
                  title="Close"
                >
                  <X size={20} className="text-white" />
                </button>
              </div>
            </div>

            {/* Modal Content */}
            <div className="flex-1 overflow-y-auto p-4">
              <pre className="text-xs font-mono whitespace-pre-wrap" style={{
                backgroundColor: 'var(--color-background-dark)',
                color: 'var(--color-text-primary)',
                padding: '16px',
                borderRadius: '8px',
                border: '1px solid var(--color-border-dark)'
              }}>
                {generatedCode}
              </pre>
            </div>

            {/* Modal Footer */}
            <div className="p-4 border-t" style={{ borderTopColor: 'var(--color-border-dark)' }}>
              <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                This code represents the LangChain/LangGraph configuration for this agent. Copy and use it in your Python projects.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// Tool Configuration View Component
interface ToolConfigViewProps {
  tool: CustomTool;
  onSave: (toolData: any) => Promise<void>;
  onDelete: () => void;
  onClose: () => void;
}

const ToolConfigView = ({ tool, onSave, onDelete, onClose }: ToolConfigViewProps) => {
  const [toolName, setToolName] = useState(tool.name);
  const [description, setDescription] = useState(tool.description);
  const [category, setCategory] = useState(tool.category || '');
  const [tags, setTags] = useState<string[]>(tool.tags || []);
  const [implementationConfig, setImplementationConfig] = useState<any>(tool.implementation_config || {});
  const [inputSchema, setInputSchema] = useState<any>(tool.input_schema || { type: 'object', properties: {}, required: [] });
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved'>('idle');

  // Update state when tool changes
  useEffect(() => {
    setToolName(tool.name);
    setDescription(tool.description);
    setCategory(tool.category || '');
    setTags(tool.tags || []);
    setImplementationConfig(tool.implementation_config || {});
    setInputSchema(tool.input_schema || { type: 'object', properties: {}, required: [] });
  }, [tool]);

  const handleSave = async () => {
    setSaveStatus('saving');
    try {
      const toolData = {
        tool_id: tool.tool_id,
        name: toolName,
        description,
        tool_type: tool.tool_type,
        template_type: tool.template_type || null,
        implementation_config: implementationConfig,
        input_schema: inputSchema,
        output_format: tool.output_format || 'string',
        is_template_based: tool.is_template_based || false,
        is_advanced_mode: tool.is_advanced_mode || false,
        category,
        tags
      };

      await onSave(toolData);
      setSaveStatus('saved');
      setTimeout(() => setSaveStatus('idle'), 2000);
    } catch (error) {
      console.error('Failed to save tool:', error);
      setSaveStatus('idle');
    }
  };

  const properties = inputSchema.properties || {};
  const required = inputSchema.required || [];

  const addProperty = () => {
    const newProp = `param_${Object.keys(properties).length + 1}`;
    setInputSchema({
      ...inputSchema,
      properties: {
        ...properties,
        [newProp]: {
          type: 'string',
          description: ''
        }
      }
    });
  };

  const removeProperty = (propName: string) => {
    const newProps = { ...properties };
    delete newProps[propName];
    setInputSchema({
      ...inputSchema,
      properties: newProps,
      required: required.filter((r: string) => r !== propName)
    });
  };

  const updateProperty = (oldName: string, newName: string, updates: any) => {
    if (oldName !== newName && properties[newName]) {
      alert('Property name already exists');
      return;
    }

    const newProps = { ...properties };
    if (oldName !== newName) {
      delete newProps[oldName];
    }
    newProps[newName] = { ...properties[oldName], ...updates };

    setInputSchema({
      ...inputSchema,
      properties: newProps,
      required: required.map((r: string) => r === oldName ? newName : r)
    });
  };

  const toggleRequired = (propName: string) => {
    const newRequired = required.includes(propName)
      ? required.filter((r: string) => r !== propName)
      : [...required, propName];

    setInputSchema({ ...inputSchema, required: newRequired });
  };

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="p-8">
        <div className="max-w-6xl mx-auto">
          {/* Header */}
          <div className="mb-6 pb-6 border-b" style={{ borderBottomColor: 'var(--color-border-dark)' }}>
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-start gap-4">
                <div
                  className="w-16 h-16 rounded-xl flex items-center justify-center flex-shrink-0 shadow-sm"
                  style={{ backgroundColor: 'var(--color-background-light)' }}
                >
                  <span className="material-symbols-outlined text-3xl" style={{ color: 'var(--color-primary)' }}>
                    build
                  </span>
                </div>
                <div className="flex-1">
                  <input
                    type="text"
                    value={toolName}
                    onChange={(e) => setToolName(e.target.value)}
                    className="text-2xl font-bold mb-2 w-full bg-transparent border-b-2 border-transparent focus:border-primary outline-none transition-colors"
                    style={{ color: 'var(--color-text-primary)' }}
                  />
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs px-2 py-1 rounded" style={{
                      backgroundColor: 'var(--color-background-light)',
                      color: 'var(--color-primary)'
                    }}>
                      {tool.tool_type}
                    </span>
                    {tool.is_template_based && (
                      <span className="px-2 py-1 bg-purple-500/20 text-purple-500 text-xs rounded font-medium">
                        Template
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-2">
                <button
                  onClick={handleSave}
                  disabled={saveStatus === 'saving'}
                  className="px-4 py-2 rounded-lg text-sm font-medium text-white flex items-center gap-2"
                  style={{ backgroundColor: 'var(--color-primary)' }}
                  onMouseEnter={(e) => e.currentTarget.style.opacity = '0.9'}
                  onMouseLeave={(e) => e.currentTarget.style.opacity = '1'}
                >
                  <Save size={16} />
                  {saveStatus === 'saving' ? 'Saving...' : saveStatus === 'saved' ? 'Saved!' : 'Save'}
                </button>
                <button
                  onClick={onDelete}
                  className="px-4 py-2 rounded-lg text-sm font-medium border flex items-center gap-2"
                  style={{
                    backgroundColor: 'rgba(239, 68, 68, 0.1)',
                    borderColor: 'rgba(239, 68, 68, 0.3)',
                    color: '#ef4444'
                  }}
                >
                  <Trash2 size={16} />
                  Delete
                </button>
              </div>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-3 gap-4">
              <div className="p-4 rounded-lg border" style={{
                backgroundColor: 'var(--color-background-light)',
                borderColor: 'var(--color-border-dark)'
              }}>
                <div className="text-xs mb-1" style={{ color: 'var(--color-text-muted)' }}>Usage Count</div>
                <div className="text-2xl font-bold" style={{ color: 'var(--color-text-primary)' }}>
                  {tool.usage_count}
                </div>
              </div>
              <div className="p-4 rounded-lg border" style={{
                backgroundColor: 'var(--color-background-light)',
                borderColor: 'var(--color-border-dark)'
              }}>
                <div className="text-xs mb-1" style={{ color: 'var(--color-text-muted)' }}>Errors</div>
                <div className="text-2xl font-bold" style={{ color: tool.error_count > 0 ? '#ef4444' : 'var(--color-text-primary)' }}>
                  {tool.error_count}
                </div>
              </div>
              <div className="p-4 rounded-lg border" style={{
                backgroundColor: 'var(--color-background-light)',
                borderColor: 'var(--color-border-dark)'
              }}>
                <div className="text-xs mb-1" style={{ color: 'var(--color-text-muted)' }}>Success Rate</div>
                <div className="text-2xl font-bold" style={{ color: 'var(--color-text-primary)' }}>
                  {tool.usage_count > 0
                    ? Math.round(((tool.usage_count - tool.error_count) / tool.usage_count) * 100)
                    : 0}%
                </div>
              </div>
            </div>
          </div>

          {/* Main Configuration Grid */}
          <div className="grid grid-cols-2 gap-6">
            {/* Left Column - Basic Info & Implementation Config */}
            <div className="space-y-6">
              {/* Basic Information */}
              <div className="p-6 rounded-lg border" style={{
                backgroundColor: 'var(--color-background-light)',
                borderColor: 'var(--color-border-dark)'
              }}>
                <h3 className="text-base font-semibold mb-4 px-4 py-2 -mx-6 -mt-6 rounded-t-lg" style={{
                  backgroundColor: 'var(--color-primary)',
                  color: 'white'
                }}>
                  Basic Information
                </h3>

                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                      Tool ID
                    </label>
                    <input
                      type="text"
                      value={tool.tool_id}
                      disabled
                      className="w-full px-4 py-2 rounded-lg border text-sm font-mono"
                      style={{
                        backgroundColor: 'var(--color-background-dark)',
                        borderColor: 'var(--color-border-dark)',
                        color: 'var(--color-text-primary)',
                        opacity: 0.8
                      }}
                    />
                    <p className="text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
                      This is the unique identifier used by agents to call this tool
                    </p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                      Description <span className="text-red-500">*</span>
                    </label>
                    <textarea
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      placeholder="Describe what this tool does..."
                      rows={4}
                      className="w-full px-4 py-2 rounded-lg border text-sm transition-all"
                      style={{
                        backgroundColor: 'var(--color-input-background)',
                        borderColor: 'var(--color-border-dark)',
                        color: 'var(--color-text-primary)'
                      }}
                      onFocus={(e) => e.currentTarget.style.borderColor = 'var(--color-primary)'}
                      onBlur={(e) => e.currentTarget.style.borderColor = 'var(--color-border-dark)'}
                    />
                    <p className="text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
                      This description helps the LLM understand when to use the tool
                    </p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                      Category
                    </label>
                    <input
                      type="text"
                      value={category}
                      onChange={(e) => setCategory(e.target.value)}
                      placeholder="e.g., notifications, integrations"
                      className="w-full px-4 py-2 rounded-lg border text-sm transition-all"
                      style={{
                        backgroundColor: 'var(--color-input-background)',
                        borderColor: 'var(--color-border-dark)',
                        color: 'var(--color-text-primary)'
                      }}
                      onFocus={(e) => e.currentTarget.style.borderColor = 'var(--color-primary)'}
                      onBlur={(e) => e.currentTarget.style.borderColor = 'var(--color-border-dark)'}
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                      Tags
                    </label>
                    <input
                      type="text"
                      value={tags.join(', ')}
                      onChange={(e) => setTags(e.target.value.split(',').map(t => t.trim()).filter(Boolean))}
                      placeholder="slack, notification, alerts"
                      className="w-full px-4 py-2 rounded-lg border text-sm transition-all"
                      style={{
                        backgroundColor: 'var(--color-input-background)',
                        borderColor: 'var(--color-border-dark)',
                        color: 'var(--color-text-primary)'
                      }}
                      onFocus={(e) => e.currentTarget.style.borderColor = 'var(--color-primary)'}
                      onBlur={(e) => e.currentTarget.style.borderColor = 'var(--color-border-dark)'}
                    />
                  </div>
                </div>
              </div>

              {/* Implementation Configuration */}
              <div className="p-6 rounded-lg border" style={{
                backgroundColor: 'var(--color-background-light)',
                borderColor: 'var(--color-border-dark)'
              }}>
                <h3 className="text-base font-semibold mb-4 px-4 py-2 -mx-6 -mt-6 rounded-t-lg" style={{
                  backgroundColor: 'var(--color-primary)',
                  color: 'white'
                }}>
                  Tool Configuration
                </h3>

                <div className="space-y-4">
                  {/* Notification Tool Config */}
                  {tool.tool_type === 'notification' && (
                    <>
                      <div>
                        <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                          Provider
                        </label>
                        <select
                          value={implementationConfig.provider || 'discord'}
                          onChange={(e) => setImplementationConfig({ ...implementationConfig, provider: e.target.value })}
                          className="w-full px-4 py-2 rounded-lg border text-sm"
                          style={{
                            backgroundColor: 'var(--color-input-background)',
                            borderColor: 'var(--color-border-dark)',
                            color: 'var(--color-text-primary)'
                          }}
                        >
                          <option value="slack">Slack</option>
                          <option value="discord">Discord</option>
                        </select>
                      </div>

                      <div>
                        <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                          Webhook URL
                        </label>
                        <input
                          type="text"
                          value={implementationConfig.webhook_url || ''}
                          onChange={(e) => setImplementationConfig({ ...implementationConfig, webhook_url: e.target.value })}
                          placeholder="https://hooks.slack.com/services/..."
                          className="w-full px-4 py-2 rounded-lg border text-sm transition-all"
                          style={{
                            backgroundColor: 'var(--color-input-background)',
                            borderColor: 'var(--color-border-dark)',
                            color: 'var(--color-text-primary)'
                          }}
                          onFocus={(e) => e.currentTarget.style.borderColor = 'var(--color-primary)'}
                          onBlur={(e) => e.currentTarget.style.borderColor = 'var(--color-border-dark)'}
                        />
                      </div>

                      {implementationConfig.provider === 'slack' && (
                        <div>
                          <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                            Default Channel
                          </label>
                          <input
                            type="text"
                            value={implementationConfig.channel || '#general'}
                            onChange={(e) => setImplementationConfig({ ...implementationConfig, channel: e.target.value })}
                            placeholder="#general"
                            className="w-full px-4 py-2 rounded-lg border text-sm transition-all"
                            style={{
                              backgroundColor: 'var(--color-input-background)',
                              borderColor: 'var(--color-border-dark)',
                              color: 'var(--color-text-primary)'
                            }}
                            onFocus={(e) => e.currentTarget.style.borderColor = 'var(--color-primary)'}
                            onBlur={(e) => e.currentTarget.style.borderColor = 'var(--color-border-dark)'}
                          />
                        </div>
                      )}
                    </>
                  )}

                  {/* API Tool Config */}
                  {tool.tool_type === 'api' && (
                    <>
                      <div>
                        <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                          HTTP Method
                        </label>
                        <select
                          value={implementationConfig.method || 'GET'}
                          onChange={(e) => setImplementationConfig({ ...implementationConfig, method: e.target.value })}
                          className="w-full px-4 py-2 rounded-lg border text-sm"
                          style={{
                            backgroundColor: 'var(--color-input-background)',
                            borderColor: 'var(--color-border-dark)',
                            color: 'var(--color-text-primary)'
                          }}
                        >
                          <option value="GET">GET</option>
                          <option value="POST">POST</option>
                          <option value="PUT">PUT</option>
                          <option value="DELETE">DELETE</option>
                          <option value="PATCH">PATCH</option>
                        </select>
                      </div>

                      <div>
                        <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                          API URL
                        </label>
                        <input
                          type="text"
                          value={implementationConfig.url || ''}
                          onChange={(e) => setImplementationConfig({ ...implementationConfig, url: e.target.value })}
                          placeholder="https://api.example.com/{endpoint}"
                          className="w-full px-4 py-2 rounded-lg border text-sm transition-all"
                          style={{
                            backgroundColor: 'var(--color-input-background)',
                            borderColor: 'var(--color-border-dark)',
                            color: 'var(--color-text-primary)'
                          }}
                          onFocus={(e) => e.currentTarget.style.borderColor = 'var(--color-primary)'}
                          onBlur={(e) => e.currentTarget.style.borderColor = 'var(--color-border-dark)'}
                        />
                        <p className="text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
                          Use {'{variable}'} for dynamic parameters
                        </p>
                      </div>

                      <div>
                        <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                          Timeout (seconds)
                        </label>
                        <input
                          type="number"
                          value={implementationConfig.timeout || 30}
                          onChange={(e) => setImplementationConfig({ ...implementationConfig, timeout: parseInt(e.target.value) })}
                          className="w-full px-4 py-2 rounded-lg border text-sm transition-all"
                          style={{
                            backgroundColor: 'var(--color-input-background)',
                            borderColor: 'var(--color-border-dark)',
                            color: 'var(--color-text-primary)'
                          }}
                          onFocus={(e) => e.currentTarget.style.borderColor = 'var(--color-primary)'}
                          onBlur={(e) => e.currentTarget.style.borderColor = 'var(--color-border-dark)'}
                        />
                      </div>
                    </>
                  )}

                  {/* Image/Video Tool Config */}
                  {tool.tool_type === 'image_video' && (
                    <>
                      <div>
                        <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                          Provider
                        </label>
                        <select
                          value={implementationConfig.provider || 'google'}
                          onChange={(e) => {
                            const newProvider = e.target.value;
                            const defaultModel = newProvider === 'google' ? 'gemini-3-pro-image-preview' : 'dall-e-3';
                            setImplementationConfig({
                              ...implementationConfig,
                              provider: newProvider,
                              model: defaultModel
                            });
                          }}
                          className="w-full px-4 py-2 rounded-lg border text-sm"
                          style={{
                            backgroundColor: 'var(--color-input-background)',
                            borderColor: 'var(--color-border-dark)',
                            color: 'var(--color-text-primary)'
                          }}
                        >
                          <option value="google">Google (Nano Banana, Imagen 3, Veo 3)</option>
                          <option value="openai">OpenAI (GPT-Image-1.5, DALL-E 3, Sora)</option>
                        </select>
                      </div>

                      <div>
                        <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                          Model
                        </label>
                        <select
                          value={implementationConfig.model || (implementationConfig.provider === 'google' ? 'gemini-3-pro-image-preview' : 'dall-e-3')}
                          onChange={(e) => setImplementationConfig({ ...implementationConfig, model: e.target.value })}
                          className="w-full px-4 py-2 rounded-lg border text-sm"
                          style={{
                            backgroundColor: 'var(--color-input-background)',
                            borderColor: 'var(--color-border-dark)',
                            color: 'var(--color-text-primary)'
                          }}
                        >
                          {implementationConfig.provider === 'openai' ? (
                            <>
                              <option value="gpt-image-1.5">GPT-Image-1.5 (Image)</option>
                              <option value="dall-e-3">DALL-E 3 (Image)</option>
                              <option value="sora">Sora (Video)</option>
                            </>
                          ) : (
                            <>
                              <option value="gemini-3-pro-image-preview">🍌 Nano Banana Pro (Gemini 3 Pro) - RECOMMENDED</option>
                              <option value="gemini-2.5-flash-image">🍌 Nano Banana (Gemini 2.5 Flash)</option>
                              <option value="imagen-3">Imagen 3 (Image)</option>
                              <option value="veo-3">Veo 3 (Video)</option>
                              <option value="veo-3.1">Veo 3.1 (Video)</option>
                            </>
                          )}
                        </select>
                      </div>

                      <div>
                        <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                          API Key
                        </label>
                        <input
                          type="password"
                          value={implementationConfig.api_key || ''}
                          onChange={(e) => setImplementationConfig({ ...implementationConfig, api_key: e.target.value })}
                          placeholder="sk-..."
                          className="w-full px-4 py-2 rounded-lg border text-sm transition-all"
                          style={{
                            backgroundColor: 'var(--color-input-background)',
                            borderColor: 'var(--color-border-dark)',
                            color: 'var(--color-text-primary)'
                          }}
                          onFocus={(e) => e.currentTarget.style.borderColor = 'var(--color-primary)'}
                          onBlur={(e) => e.currentTarget.style.borderColor = 'var(--color-border-dark)'}
                        />
                      </div>
                    </>
                  )}

                  {/* Database Tool Config */}
                  {tool.tool_type === 'database' && (
                    <>
                      <div>
                        <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                          Database Type
                        </label>
                        <select
                          value={implementationConfig.db_type || 'postgresql'}
                          onChange={(e) => setImplementationConfig({ ...implementationConfig, db_type: e.target.value })}
                          className="w-full px-4 py-2 rounded-lg border text-sm"
                          style={{
                            backgroundColor: 'var(--color-input-background)',
                            borderColor: 'var(--color-border-dark)',
                            color: 'var(--color-text-primary)'
                          }}
                        >
                          <option value="postgresql">PostgreSQL</option>
                          <option value="mysql">MySQL</option>
                          <option value="mongodb">MongoDB</option>
                        </select>
                      </div>

                      <div>
                        <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                          Host
                        </label>
                        <input
                          type="text"
                          value={implementationConfig.host || 'localhost'}
                          onChange={(e) => setImplementationConfig({ ...implementationConfig, host: e.target.value })}
                          placeholder="localhost"
                          className="w-full px-4 py-2 rounded-lg border text-sm transition-all"
                          style={{
                            backgroundColor: 'var(--color-input-background)',
                            borderColor: 'var(--color-border-dark)',
                            color: 'var(--color-text-primary)'
                          }}
                          onFocus={(e) => e.currentTarget.style.borderColor = 'var(--color-primary)'}
                          onBlur={(e) => e.currentTarget.style.borderColor = 'var(--color-border-dark)'}
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                          Port
                        </label>
                        <input
                          type="number"
                          value={implementationConfig.port || 5432}
                          onChange={(e) => setImplementationConfig({ ...implementationConfig, port: parseInt(e.target.value) })}
                          className="w-full px-4 py-2 rounded-lg border text-sm transition-all"
                          style={{
                            backgroundColor: 'var(--color-input-background)',
                            borderColor: 'var(--color-border-dark)',
                            color: 'var(--color-text-primary)'
                          }}
                          onFocus={(e) => e.currentTarget.style.borderColor = 'var(--color-primary)'}
                          onBlur={(e) => e.currentTarget.style.borderColor = 'var(--color-border-dark)'}
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                          Database Name
                        </label>
                        <input
                          type="text"
                          value={implementationConfig.database || ''}
                          onChange={(e) => setImplementationConfig({ ...implementationConfig, database: e.target.value })}
                          placeholder="myapp_db"
                          className="w-full px-4 py-2 rounded-lg border text-sm transition-all"
                          style={{
                            backgroundColor: 'var(--color-input-background)',
                            borderColor: 'var(--color-border-dark)',
                            color: 'var(--color-text-primary)'
                          }}
                          onFocus={(e) => e.currentTarget.style.borderColor = 'var(--color-primary)'}
                          onBlur={(e) => e.currentTarget.style.borderColor = 'var(--color-border-dark)'}
                        />
                      </div>
                    </>
                  )}

                  {/* Data Transform Tool Config */}
                  {tool.tool_type === 'data_transform' && (
                    <>
                      <div>
                        <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                          Input Format
                        </label>
                        <select
                          value={implementationConfig.input_format || 'json'}
                          onChange={(e) => setImplementationConfig({ ...implementationConfig, input_format: e.target.value })}
                          className="w-full px-4 py-2 rounded-lg border text-sm"
                          style={{
                            backgroundColor: 'var(--color-input-background)',
                            borderColor: 'var(--color-border-dark)',
                            color: 'var(--color-text-primary)'
                          }}
                        >
                          <option value="json">JSON</option>
                          <option value="csv">CSV</option>
                          <option value="xml">XML</option>
                          <option value="yaml">YAML</option>
                        </select>
                      </div>

                      <div>
                        <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                          Output Format
                        </label>
                        <select
                          value={implementationConfig.output_format || 'json'}
                          onChange={(e) => setImplementationConfig({ ...implementationConfig, output_format: e.target.value })}
                          className="w-full px-4 py-2 rounded-lg border text-sm"
                          style={{
                            backgroundColor: 'var(--color-input-background)',
                            borderColor: 'var(--color-border-dark)',
                            color: 'var(--color-text-primary)'
                          }}
                        >
                          <option value="json">JSON</option>
                          <option value="csv">CSV</option>
                          <option value="xml">XML</option>
                          <option value="yaml">YAML</option>
                        </select>
                      </div>
                    </>
                  )}

                  {Object.keys(implementationConfig).length === 0 && (
                    <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
                      No specific configuration required for this tool type.
                    </p>
                  )}
                </div>
              </div>
            </div>

            {/* Right Column - Input Schema */}
            <div>
              <div className="p-6 rounded-lg border" style={{
                backgroundColor: 'var(--color-background-light)',
                borderColor: 'var(--color-border-dark)'
              }}>
                <div className="flex items-center justify-between mb-4 px-4 py-2 -mx-6 -mt-6 rounded-t-lg" style={{
                  backgroundColor: 'var(--color-primary)',
                  color: 'white'
                }}>
                  <h3 className="text-base font-semibold">
                    Input Parameters
                  </h3>
                  <button
                    onClick={addProperty}
                    className="px-3 py-1 rounded text-xs font-medium flex items-center gap-1 bg-white/20 hover:bg-white/30 transition-colors"
                  >
                    <Plus size={14} />
                    Add Parameter
                  </button>
                </div>

                <p className="text-sm mb-4" style={{ color: 'var(--color-text-muted)' }}>
                  Define what parameters your tool accepts from the LLM
                </p>

                <div className="space-y-4">
                  {Object.keys(properties).length === 0 ? (
                    <div className="text-center py-8">
                      <p className="text-sm mb-3" style={{ color: 'var(--color-text-muted)' }}>
                        No parameters defined yet
                      </p>
                      <button
                        onClick={addProperty}
                        className="text-xs px-3 py-1.5 rounded-lg"
                        style={{ color: 'var(--color-primary)', backgroundColor: 'var(--color-background-dark)' }}
                      >
                        Add First Parameter
                      </button>
                    </div>
                  ) : (
                    Object.entries(properties).map(([propName, prop]: [string, any]) => (
                      <div key={propName} className="p-4 rounded-lg border" style={{
                        borderColor: 'var(--color-border-dark)',
                        backgroundColor: 'var(--color-panel-dark)'
                      }}>
                        <div className="flex items-start justify-between mb-3">
                          <div className="flex-1">
                            <input
                              type="text"
                              value={propName}
                              onChange={(e) => updateProperty(propName, e.target.value, prop)}
                              className="font-medium text-sm mb-1 w-full bg-transparent border-b border-transparent focus:border-primary outline-none"
                              style={{ color: 'var(--color-text-primary)' }}
                            />
                          </div>
                          <button
                            onClick={() => removeProperty(propName)}
                            className="text-red-500 hover:text-red-600 ml-2"
                          >
                            <X size={16} />
                          </button>
                        </div>

                        <div className="space-y-3">
                          <div>
                            <label className="block text-xs font-medium mb-1" style={{ color: 'var(--color-text-muted)' }}>
                              Type
                            </label>
                            <select
                              value={prop.type || 'string'}
                              onChange={(e) => updateProperty(propName, propName, { ...prop, type: e.target.value })}
                              className="w-full px-3 py-1.5 rounded border text-xs"
                              style={{
                                backgroundColor: 'var(--color-input-background)',
                                borderColor: 'var(--color-border-dark)',
                                color: 'var(--color-text-primary)'
                              }}
                            >
                              <option value="string">String</option>
                              <option value="number">Number</option>
                              <option value="boolean">Boolean</option>
                              <option value="array">Array</option>
                              <option value="object">Object</option>
                            </select>
                          </div>

                          <div>
                            <label className="block text-xs font-medium mb-1" style={{ color: 'var(--color-text-muted)' }}>
                              Description
                            </label>
                            <textarea
                              value={prop.description || ''}
                              onChange={(e) => updateProperty(propName, propName, { ...prop, description: e.target.value })}
                              placeholder="Describe this parameter..."
                              rows={2}
                              className="w-full px-3 py-1.5 rounded border text-xs"
                              style={{
                                backgroundColor: 'var(--color-input-background)',
                                borderColor: 'var(--color-border-dark)',
                                color: 'var(--color-text-primary)'
                              }}
                            />
                          </div>

                          <label className="flex items-center gap-2 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={required.includes(propName)}
                              onChange={() => toggleRequired(propName)}
                              className="w-4 h-4 text-primary rounded focus:ring-1 focus:ring-primary"
                            />
                            <span className="text-xs" style={{ color: 'var(--color-text-primary)' }}>
                              Required parameter
                            </span>
                          </label>
                        </div>
                      </div>
                    ))
                  )}
                </div>

                {/* JSON Preview */}
                {Object.keys(properties).length > 0 && (
                  <div className="mt-6">
                    <h4 className="text-sm font-medium mb-2" style={{ color: 'var(--color-text-primary)' }}>
                      Schema Preview
                    </h4>
                    <div className="p-3 rounded-lg border font-mono text-xs whitespace-pre-wrap" style={{
                      backgroundColor: 'var(--color-background-dark)',
                      borderColor: 'var(--color-border-dark)',
                      color: 'var(--color-text-muted)'
                    }}>
                      {JSON.stringify(inputSchema, null, 2)}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// Skill Configuration View Component (Read-only)
interface SkillConfigViewProps {
  skill: Skill;
  onClose: () => void;
  onDelete?: (skillId: string) => void;
}

const SOURCE_STYLES: Record<string, { label: string; color: string }> = {
  builtin: { label: 'Built-in', color: 'var(--color-primary)' },
  personal: { label: 'Personal', color: '#10b981' },
  project: { label: 'Project', color: '#8b5cf6' },
};

const SkillConfigView = ({ skill, onClose, onDelete }: SkillConfigViewProps) => {
  const sourceStyle = SOURCE_STYLES[skill.source_type] || SOURCE_STYLES.builtin;
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  // Editable state
  const [name, setName] = useState(skill.name || '');
  const [triggers, setTriggers] = useState<string[]>(skill.triggers || []);
  const [instructions, setInstructions] = useState(skill.instructions || '');
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved'>('idle');
  const [newTrigger, setNewTrigger] = useState('');

  // Update state when skill changes
  useEffect(() => {
    setName(skill.name || '');
    setTriggers(skill.triggers || []);
    setInstructions(skill.instructions || '');
  }, [skill.skill_id]);

  const formatLastUsed = (dateStr: string | null) => {
    if (!dateStr) return 'Never';
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays} days ago`;
    return date.toLocaleDateString();
  };

  const handleSave = async () => {
    setSaveStatus('saving');
    try {
      await apiClient.put(`/api/skills/${skill.skill_id}`, {
        name,
        triggers,
        instructions
      });
      setSaveStatus('saved');
      setTimeout(() => setSaveStatus('idle'), 2000);
    } catch (e) {
      console.error('Failed to save skill:', e);
      setSaveStatus('idle');
    }
  };

  const addTrigger = () => {
    if (newTrigger.trim()) {
      setTriggers([...triggers, newTrigger.trim()]);
      setNewTrigger('');
    }
  };

  const removeTrigger = (index: number) => {
    setTriggers(triggers.filter((_, i) => i !== index));
  };

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="p-8">
        <div className="max-w-6xl mx-auto">
          {/* Header */}
          <div className="mb-6 pb-6 border-b" style={{ borderBottomColor: 'var(--color-border-dark)' }}>
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-start gap-4">
                <div
                  className="w-16 h-16 rounded-xl flex items-center justify-center flex-shrink-0 shadow-sm"
                  style={{ backgroundColor: 'var(--color-background-light)' }}
                >
                  <BookOpen className="w-8 h-8" style={{ color: 'var(--color-primary)' }} />
                </div>
                <div className="flex-1">
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="text-2xl font-bold mb-2 bg-transparent border-none outline-none w-full"
                    style={{ color: 'var(--color-text-primary)' }}
                    placeholder="Skill Name"
                  />
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs px-2 py-1 rounded" style={{
                      backgroundColor: `${sourceStyle.color}15`,
                      color: sourceStyle.color
                    }}>
                      {sourceStyle.label}
                    </span>
                    <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                      v{skill.version}
                    </span>
                    {skill.author && (
                      <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                        • by {skill.author}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-2">
                {onDelete && skill.source_type !== 'builtin' && (
                  <button
                    onClick={() => setShowDeleteConfirm(true)}
                    className="px-3 py-2 rounded-lg text-sm font-medium flex items-center gap-2 transition-colors"
                    style={{
                      backgroundColor: 'var(--color-background-light)',
                      color: '#ef4444',
                      border: '1px solid #ef4444'
                    }}
                    title="Delete Skill"
                  >
                    <Trash2 size={16} />
                    Delete
                  </button>
                )}
                <button
                  onClick={handleSave}
                  disabled={saveStatus === 'saving'}
                  className="px-4 py-2 rounded-lg text-sm font-medium text-white flex items-center gap-2"
                  style={{ backgroundColor: 'var(--color-primary)' }}
                  onMouseEnter={(e) => e.currentTarget.style.opacity = '0.9'}
                  onMouseLeave={(e) => e.currentTarget.style.opacity = '1'}
                >
                  <Save size={16} />
                  {saveStatus === 'saving' ? 'Saving...' : saveStatus === 'saved' ? 'Saved!' : 'Save'}
                </button>
                <button
                  onClick={onClose}
                  className="p-2 rounded-lg border transition-colors"
                  style={{
                    backgroundColor: 'var(--color-background-light)',
                    borderColor: 'var(--color-border-dark)',
                    color: 'var(--color-text-muted)'
                  }}
                >
                  <X size={20} />
                </button>
              </div>

              {/* Delete Confirmation Modal */}
              {showDeleteConfirm && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setShowDeleteConfirm(false)}>
                  <div className="bg-white dark:bg-panel-dark rounded-xl p-6 max-w-md shadow-xl" onClick={e => e.stopPropagation()}>
                    <h3 className="text-lg font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>Delete Skill?</h3>
                    <p className="text-sm mb-4" style={{ color: 'var(--color-text-muted)' }}>
                      Are you sure you want to delete "{skill.name}"? This action cannot be undone.
                    </p>
                    <div className="flex justify-end gap-2">
                      <button
                        onClick={() => setShowDeleteConfirm(false)}
                        className="px-4 py-2 rounded-lg text-sm font-medium bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={() => {
                          if (onDelete) onDelete(skill.skill_id);
                          setShowDeleteConfirm(false);
                        }}
                        className="px-4 py-2 rounded-lg text-sm font-medium text-white"
                        style={{ backgroundColor: '#ef4444' }}
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Stats */}
            <div className="grid grid-cols-3 gap-4">
              <div className="p-4 rounded-lg border" style={{
                backgroundColor: 'var(--color-background-light)',
                borderColor: 'var(--color-border-dark)'
              }}>
                <div className="text-xs mb-1" style={{ color: 'var(--color-text-muted)' }}>Usage Count</div>
                <div className="text-2xl font-bold" style={{ color: 'var(--color-text-primary)' }}>
                  {skill.usage_count}
                </div>
              </div>
              <div className="p-4 rounded-lg border" style={{
                backgroundColor: 'var(--color-background-light)',
                borderColor: 'var(--color-border-dark)'
              }}>
                <div className="text-xs mb-1" style={{ color: 'var(--color-text-muted)' }}>Success Rate</div>
                <div className="text-2xl font-bold" style={{ color: skill.avg_success_rate >= 0.8 ? '#10b981' : '#f59e0b' }}>
                  {Math.round(skill.avg_success_rate * 100)}%
                </div>
              </div>
              <div className="p-4 rounded-lg border" style={{
                backgroundColor: 'var(--color-background-light)',
                borderColor: 'var(--color-border-dark)'
              }}>
                <div className="text-xs mb-1" style={{ color: 'var(--color-text-muted)' }}>Last Used</div>
                <div className="text-2xl font-bold" style={{ color: 'var(--color-text-primary)' }}>
                  {formatLastUsed(skill.last_used_at)}
                </div>
              </div>
            </div>
          </div>

          {/* Description */}
          <div className="mb-6">
            <h3 className="text-sm font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
              Description
            </h3>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--color-text-muted)' }}>
              {skill.description}
            </p>
          </div>

          {/* Tags */}
          {skill.tags.length > 0 && (
            <div className="mb-6">
              <h3 className="text-sm font-semibold mb-2 flex items-center gap-2" style={{ color: 'var(--color-text-primary)' }}>
                <Tag size={14} />
                Tags
              </h3>
              <div className="flex items-center gap-2 flex-wrap">
                {skill.tags.map((tag) => (
                  <span
                    key={tag}
                    className="text-xs px-2.5 py-1 rounded-full"
                    style={{
                      backgroundColor: 'var(--color-background-dark)',
                      color: 'var(--color-text-muted)',
                    }}
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Triggers (Editable) */}
          <div className="mb-6">
            <h3 className="text-sm font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
              Auto-triggers
            </h3>
            <div className="p-4 rounded-lg" style={{ backgroundColor: 'var(--color-background-light)' }}>
              <ul className="space-y-2 mb-3">
                {triggers.map((trigger, i) => (
                  <li key={i} className="flex items-center gap-2 text-sm group" style={{ color: 'var(--color-text-primary)' }}>
                    <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ backgroundColor: 'var(--color-primary)' }} />
                    <span className="flex-1">{trigger}</span>
                    <button
                      onClick={() => removeTrigger(i)}
                      className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-500/10 text-red-500 transition-opacity"
                    >
                      <X size={14} />
                    </button>
                  </li>
                ))}
              </ul>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={newTrigger}
                  onChange={(e) => setNewTrigger(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && addTrigger()}
                  placeholder="Add a trigger..."
                  className="flex-1 px-3 py-2 rounded-lg text-sm border"
                  style={{
                    backgroundColor: 'var(--color-background-dark)',
                    borderColor: 'var(--color-border-dark)',
                    color: 'var(--color-text-primary)'
                  }}
                />
                <button
                  onClick={addTrigger}
                  className="px-3 py-2 rounded-lg text-sm font-medium"
                  style={{ backgroundColor: 'var(--color-primary)', color: 'white' }}
                >
                  <Plus size={16} />
                </button>
              </div>
            </div>
          </div>

          {/* Instructions (Editable) */}
          <div className="mb-6">
            <h3 className="text-sm font-semibold mb-2 flex items-center gap-2" style={{ color: 'var(--color-text-primary)' }}>
              <BookOpen size={14} />
              Instructions
            </h3>
            <textarea
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              rows={20}
              className="w-full p-4 rounded-lg font-mono text-xs border resize-y"
              style={{
                backgroundColor: 'white',
                borderColor: 'var(--color-border-dark)',
                color: 'var(--color-text-primary)',
                minHeight: '300px'
              }}
            />
          </div>

          {/* Allowed Tools */}
          {skill.allowed_tools && skill.allowed_tools.length > 0 && (
            <div className="mb-6">
              <h3 className="text-sm font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                Allowed Tools
              </h3>
              <div className="flex items-center gap-2 flex-wrap">
                {skill.allowed_tools.map((tool) => (
                  <span
                    key={tool}
                    className="text-xs px-2.5 py-1 rounded-lg font-mono"
                    style={{
                      backgroundColor: 'var(--color-primary)',
                      color: 'white',
                    }}
                  >
                    {tool}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

const AgentLoadouts = () => {

  const [searchParams, setSearchParams] = useSearchParams();
  const { showSuccess, logError, showWarning, NotificationModal } = useNotification();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [tools, setTools] = useState<CustomTool[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedItem, setSelectedItem] = useState<SelectedItem>(null);
  const [showAgentBuilder, setShowAgentBuilder] = useState(false);
  const [showTypeSelector, setShowTypeSelector] = useState(false);
  const [editingAgent, setEditingAgent] = useState<Agent | null>(null);
  const [agentType, setAgentType] = useState<'regular' | 'deep'>('deep');
  const [showToolBuilder, setShowToolBuilder] = useState(false);
  const [editingTool, setEditingTool] = useState<string | null>(null);
  const [cameFromTypeSelector, setCameFromTypeSelector] = useState(false);
  const [toolTemplate, setToolTemplate] = useState<any>(null);

  // Skills state
  const [skills, setSkills] = useState<Skill[]>([]);
  const [skillSearchQuery, setSkillSearchQuery] = useState('');
  const [rightPanelTab, setRightPanelTab] = useState<'tools' | 'skills'>('tools');
  const [showSkillBuilder, setShowSkillBuilder] = useState(false);

  // Optimistic Locking
  const [showConflictDialog, setShowConflictDialog] = useState(false);
  const [conflictData, setConflictData] = useState<{
    agent: Agent;
    localData: any;
    remoteData: any;
  } | null>(null);

  const selectedAgentId = searchParams.get('agent');
  const selectedAgent = agents.find(a => a.id.toString() === selectedAgentId) || null;

  useEffect(() => {
    const abortController = new AbortController();

    loadAgents(abortController.signal);
    loadTools(abortController.signal);
    loadSkills(abortController.signal);

    return () => {
      abortController.abort();
    };
  }, []);

  // Handle Escape key to close modals
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (showToolBuilder) {
          setSelectedItem({ type: 'template', category: 'tool' });
          setShowToolBuilder(false);
          setEditingTool(null);
          setToolTemplate(null);
        } else if (showAgentBuilder) {
          setShowAgentBuilder(false);
          setEditingAgent(null);
          setCameFromTypeSelector(false);
          setSelectedItem({ type: 'template', category: 'agent' });
        } else if (selectedAgent) {
          setSearchParams({});
        } else if (showTypeSelector) {
          setShowTypeSelector(false);
        }
      }
    };

    if (showToolBuilder || showAgentBuilder || selectedAgent || showTypeSelector) {
      window.addEventListener('keydown', handleEscape);
      return () => window.removeEventListener('keydown', handleEscape);
    }
  }, [showToolBuilder, showAgentBuilder, selectedAgent, showTypeSelector]);

  const loadAgents = async (signal?: AbortSignal) => {
    try {
      const res = await apiClient.listDeepAgents({ signal } as any);
      setAgents(res.data || []);
    } catch (e) {
      // Ignore abort errors
      if (e instanceof Error && e.name === 'AbortError') {
        return;
      }
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const loadTools = async (signal?: AbortSignal) => {
    try {
      const res = await apiClient.listCustomTools({ signal } as any);
      setTools(res.data || []);
    } catch (e) {
      // Ignore abort errors
      if (e instanceof Error && e.name === 'AbortError') {
        return;
      }
      console.error('[AgentLoadouts] Failed to load tools:', e);
    }
  };

  const loadSkills = async (signal?: AbortSignal) => {
    try {
      const res = await apiClient.get('/api/skills', { signal });
      setSkills(res.data || []);
    } catch (e) {
      // Ignore abort errors
      if (e instanceof Error && e.name === 'AbortError') {
        return;
      }
      console.error('[AgentLoadouts] Failed to load skills:', e);
    }
  };

  const fetchSkillDetail = async (skillId: string) => {
    try {
      const res = await apiClient.get(`/api/skills/${skillId}`);
      // Update selectedItem with full skill details
      setSelectedItem({ type: 'skill', data: res.data });
    } catch (e) {
      console.error('[AgentLoadouts] Failed to fetch skill details:', e);
    }
  };

  const handleSave = async (config: any) => {
    try {
      const requestData = {
        name: config.name || 'Untitled Agent',
        description: config.description || '',
        category: config.category || 'Custom',
        config
      };

      if (editingAgent) {
        await apiClient.updateDeepAgent(editingAgent.id, { config });
        showSuccess('Agent updated successfully!');
      } else {
        await apiClient.createDeepAgent(requestData);
        showSuccess('Agent created successfully!');
      }

      await loadAgents();
      setShowAgentBuilder(false);
      setEditingAgent(null);

    } catch (error: any) {
      console.error('Failed to save agent:', error);
      logError('Failed to save agent', error.message || 'An unexpected error occurred');
    }
  };

  const handleSaveAgentFromConfigView = async (agentId: number, config: any) => {
    try {
      // Find the agent to get its current lock_version
      const agent = agents.find(a => a.id === agentId);
      if (!agent) {
        throw new Error('Agent not found');
      }

      // Extract name and description from config (they're added by AgentConfigView.handleSave)
      const { name, description, ...restConfig } = config;

      // UPDATE with lock_version for optimistic locking
      // Include name and description at top level for API
      const response = await apiClient.updateDeepAgent(agentId, {
        name: name || agent.name,
        description: description !== undefined ? description : agent.description,
        config: restConfig,
        lock_version: agent.lock_version
      });

      // Update local agent list with new lock_version
      const updatedAgent = response.data;
      setAgents(prev => prev.map(a =>
        a.id === agentId
          ? { ...a, name: updatedAgent.name, description: updatedAgent.description, config: updatedAgent.config, lock_version: updatedAgent.lock_version }
          : a
      ));

      // Update selectedItem if it's the current agent
      if (selectedItem?.type === 'agent' && selectedItem.data.id === agentId) {
        setSelectedItem({
          ...selectedItem,
          data: { ...selectedItem.data, name: updatedAgent.name, description: updatedAgent.description, config: updatedAgent.config, lock_version: updatedAgent.lock_version }
        });
      }

      // Show success notification
      showSuccess('Agent configuration saved successfully!');

    } catch (error: any) {
      console.error('Failed to save agent:', error);

      // Handle optimistic lock conflicts
      if (error instanceof ConflictErrorClass) {
        const agent = agents.find(a => a.id === agentId);
        if (agent) {
          try {
            // Fetch latest version from server
            const latestResponse = await apiClient.getDeepAgent(agentId);
            const remoteAgent = latestResponse.data;

            // Show conflict dialog
            setConflictData({
              agent,
              localData: { config, lock_version: agent.lock_version },
              remoteData: remoteAgent
            });
            setShowConflictDialog(true);
          } catch (fetchError) {
            console.error('Failed to fetch latest agent version:', fetchError);
            logError('Conflict detected', 'Unable to fetch latest agent version');
          }
        }
        return;
      }

      logError('Failed to save agent', error.message || 'An unexpected error occurred');
      throw error;
    }
  };

  // Handle conflict resolution
  const handleConflictResolve = async (resolution: 'reload' | 'force' | 'cancel') => {
    if (!conflictData) return;

    if (resolution === 'reload') {
      // Reload latest version from server
      try {
        const latestResponse = await apiClient.getDeepAgent(conflictData.agent.id);
        const latestAgent = latestResponse.data;

        // Update local agents list
        setAgents(prev => prev.map(a =>
          a.id === conflictData.agent.id ? latestAgent : a
        ));

        // Update selectedItem if it's the current agent
        if (selectedItem?.type === 'agent' && selectedItem.data.id === conflictData.agent.id) {
          setSelectedItem({
            ...selectedItem,
            data: latestAgent
          });
        }

        alert('Agent reloaded with latest changes');
      } catch (error) {
        console.error('Failed to reload agent:', error);
        alert('Failed to reload agent');
      }
    } else if (resolution === 'force') {
      // Force save with latest lock_version
      try {
        const latestResponse = await apiClient.getDeepAgent(conflictData.agent.id);
        const latestAgent = latestResponse.data;

        // Retry save with new lock_version
        const response = await apiClient.updateDeepAgent(conflictData.agent.id, {
          config: conflictData.localData.config,
          lock_version: latestAgent.lock_version
        });

        // Update local state
        const updatedAgent = response.data;
        setAgents(prev => prev.map(a =>
          a.id === conflictData.agent.id ? updatedAgent : a
        ));

        if (selectedItem?.type === 'agent' && selectedItem.data.id === conflictData.agent.id) {
          setSelectedItem({
            ...selectedItem,
            data: updatedAgent
          });
        }

        alert('Agent force-saved successfully');
      } catch (error) {
        console.error('Failed to force save agent:', error);
        alert('Force save failed');
      }
    }
    // 'cancel' - just close dialog

    setShowConflictDialog(false);
    setConflictData(null);
  };

  const handleDeleteAgent = async (id: number) => {
    if (!confirm('Are you sure you want to delete this agent?')) return;

    try {
      await apiClient.deleteDeepAgent(id);
      await loadAgents();
      if (selectedItem?.type === 'agent' && selectedItem.data.id === id) {
        setSelectedItem(null);
      }
    } catch (error) {
      console.error('Failed to delete agent:', error);
    }
  };

  const handleDeleteTool = async (toolId: string) => {
    if (!confirm('Are you sure you want to delete this tool?')) return;

    try {
      await apiClient.deleteCustomTool(toolId);
      await loadTools();
      if (selectedItem?.type === 'tool' && selectedItem.data.tool_id === toolId) {
        setSelectedItem(null);
      }
    } catch (error) {
      console.error('Failed to delete tool:', error);
    }
  };

  const handleSaveTool = async (toolData: any) => {
    try {
      await apiClient.updateCustomTool(toolData.tool_id, toolData);
      await loadTools();
    } catch (error) {
      console.error('Failed to save tool:', error);
      throw error;
    }
  };

  const handleDuplicateTool = async (toolId: string) => {
    const newToolId = `${toolId}_copy_${Date.now()}`;
    try {
      await apiClient.duplicateCustomTool(toolId, newToolId);
      await loadTools();
    } catch (error) {
      console.error('Failed to duplicate tool:', error);
    }
  };

  const handleExportTool = async (toolId: string, toolName: string) => {
    try {
      const response = await apiClient.exportCustomTool(toolId);
      const blob = new Blob([response.data], { type: 'application/json' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${toolName}_export.json`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Failed to export tool:', error);
    }
  };

  const handleImportTool = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      await apiClient.importCustomTool(file);
      await loadTools();
    } catch (error) {
      console.error('Failed to import tool:', error);
    }
  };

  const [toolSearchQuery, setToolSearchQuery] = useState('');
  const [expandedSections, setExpandedSections] = useState<Set<string>>(
    new Set(['regular', 'deep'])
  );

  const toggleSection = (section: string) => {
    const newExpanded = new Set(expandedSections);
    if (newExpanded.has(section)) {
      newExpanded.delete(section);
    } else {
      newExpanded.add(section);
    }
    setExpandedSections(newExpanded);
  };

  const filteredAgents = agents.filter(a =>
    a.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    a.description?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Group agents by type
  const regularAgents = filteredAgents.filter(a => !a.config?.use_deepagents);
  const deepAgents = filteredAgents.filter(a => a.config?.use_deepagents);

  const filteredTools = tools.filter(t =>
    t.name.toLowerCase().includes(toolSearchQuery.toLowerCase()) ||
    t.description?.toLowerCase().includes(toolSearchQuery.toLowerCase())
  );

  const filteredSkills = skills.filter(s =>
    s.name.toLowerCase().includes(skillSearchQuery.toLowerCase()) ||
    s.description?.toLowerCase().includes(skillSearchQuery.toLowerCase())
  );

  // Map tags to 4 main categories
  const getSkillCategory = (skill: Skill): string => {
    const tags = skill.tags.map(t => t.toLowerCase());
    if (tags.some(t => ['code-review', 'refactoring', 'debugging', 'performance', 'security'].includes(t))) {
      return 'Development';
    }
    if (tags.some(t => ['documentation', 'api-docs', 'readme', 'comments'].includes(t))) {
      return 'Documentation';
    }
    if (tags.some(t => ['testing', 'unit-test', 'integration', 'qa', 'quality'].includes(t))) {
      return 'Testing';
    }
    return 'General';
  };

  // Group skills by category
  const skillsByCategory = filteredSkills.reduce((acc, skill) => {
    const category = getSkillCategory(skill);
    if (!acc[category]) {
      acc[category] = [];
    }
    acc[category].push(skill);
    return acc;
  }, {} as Record<string, Skill[]>);

  const getToolIcon = (toolType: string) => {
    const icons: Record<string, string> = {
      notification: 'notifications',
      api: 'api',
      image_video: 'image',
      database: 'storage',
      data_transform: 'transform',
      web_search: 'search',
      rag: 'database',
      custom: 'extension',
      middleware: 'settings_ethernet',
    };
    return icons[toolType] || 'build';
  };


  return (
    <div className="h-full flex flex-col bg-gray-50 dark:bg-background-dark">
      {/* Header */}


      {/* Three Column Layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Sidebar - Agent/Tool List (25%) */}
        <div className="w-[25%] flex flex-col border-r border-gray-200 dark:border-border-dark bg-white dark:bg-panel-dark">
          {/* Sidebar Header */}
          <div className="p-4 border-b border-gray-200 dark:border-border-dark bg-white/50 dark:bg-panel-dark/50 backdrop-blur-sm sticky top-0 z-10">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold text-gray-900 dark:text-white font-display">
                Agent Loadouts
              </h2>
            </div>

            {/* Search Bar */}
            <div className="relative group">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 group-focus-within:text-primary transition-colors" size={16} />
              <input
                type="text"
                placeholder="Search agents..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all shadow-sm"
              />
            </div>
          </div>

          {/* Agents List */}
          <div className="flex-1 overflow-y-auto">
            <div className="px-4 py-3">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                    Agents
                  </h3>
                  <span className="text-xs px-2 py-0.5 rounded-full" style={{
                    backgroundColor: 'var(--color-background-dark)',
                    color: 'var(--color-text-muted)'
                  }}>
                    {filteredAgents.length}
                  </span>
                </div>
                <button
                  onClick={() => {
                    setEditingAgent(null);
                    setShowTypeSelector(true);
                  }}
                  className="px-3 py-1.5 rounded-lg text-xs font-medium text-white flex items-center gap-1.5"
                  style={{ backgroundColor: 'var(--color-primary)' }}
                  onMouseEnter={(e) => e.currentTarget.style.opacity = '0.9'}
                  onMouseLeave={(e) => e.currentTarget.style.opacity = '1'}
                >
                  <Plus size={14} />
                  New Agent
                </button>
              </div>

              {loading ? (
                <div className="text-center py-8 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                  Loading...
                </div>
              ) : filteredAgents.length === 0 ? (
                <div className="text-center py-8 px-4">
                  <span className="material-symbols-outlined text-3xl mb-2 block" style={{ color: 'var(--color-text-muted)' }}>
                    smart_toy
                  </span>
                  <p className="text-sm mb-3" style={{ color: 'var(--color-text-muted)' }}>
                    No agents yet
                  </p>
                  <button
                    onClick={() => setSelectedItem({ type: 'template', category: 'agent' })}
                    className="text-xs px-3 py-1.5 rounded-lg"
                    style={{ color: 'var(--color-primary)', backgroundColor: 'var(--color-background-dark)' }}
                  >
                    View Templates
                  </button>
                </div>
              ) : (
                <div className="space-y-3">
                  {/* Agents Section */}
                  {regularAgents.length > 0 && (
                    <div>
                      <button
                        onClick={() => toggleSection('regular')}
                        className="w-full flex items-center justify-between px-2 py-1.5 rounded hover:bg-opacity-80 transition-colors"
                        style={{ backgroundColor: 'var(--color-background-dark)' }}
                      >
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                            Agents
                          </span>
                          <span className="text-xs px-1.5 py-0.5 rounded" style={{
                            backgroundColor: 'var(--color-background-light)',
                            color: 'var(--color-text-muted)'
                          }}>
                            {regularAgents.length}
                          </span>
                        </div>
                        <span style={{ color: 'var(--color-text-muted)' }}>
                          {expandedSections.has('regular') ? '▼' : '▶'}
                        </span>
                      </button>
                      {expandedSections.has('regular') && (
                        <div className="mt-1.5 space-y-1.5">
                          {regularAgents.map(agent => (
                            <div
                              key={agent.id}
                              onClick={() => setSelectedItem({ type: 'agent', data: agent })}
                              className={`group p-3 rounded-xl border cursor-pointer transition-all duration-200 hover:shadow-md ${selectedItem?.type === 'agent' && selectedItem.data.id === agent.id
                                ? 'bg-white dark:bg-gray-800 border-primary shadow-sm ring-1 ring-primary/20'
                                : 'bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800 hover:border-primary/50'
                                }`}
                            >
                              <div className="flex items-start gap-3">
                                <div
                                  className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 transition-colors ${selectedItem?.type === 'agent' && selectedItem.data.id === agent.id
                                    ? 'bg-primary/10 text-primary'
                                    : 'bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400 group-hover:text-primary group-hover:bg-primary/5'
                                    }`}
                                >
                                  <span className="material-symbols-outlined text-xl">
                                    psychology
                                  </span>
                                </div>
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center justify-between mb-0.5">
                                    <h4 className="font-semibold text-sm truncate text-gray-900 dark:text-gray-100">
                                      {agent.name}
                                    </h4>
                                  </div>
                                  <p className="text-xs text-gray-500 dark:text-gray-400 line-clamp-2 leading-relaxed">
                                    {agent.description}
                                  </p>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Deep Agents Section */}
                  {deepAgents.length > 0 && (
                    <div>
                      <button
                        onClick={() => toggleSection('deep')}
                        className="w-full flex items-center justify-between px-2 py-1.5 rounded hover:bg-opacity-80 transition-colors"
                        style={{ backgroundColor: 'var(--color-background-dark)' }}
                      >
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                            Deep Agents
                          </span>
                          <span className="text-xs px-1.5 py-0.5 rounded" style={{
                            backgroundColor: 'var(--color-background-light)',
                            color: 'var(--color-text-muted)'
                          }}>
                            {deepAgents.length}
                          </span>
                        </div>
                        <span style={{ color: 'var(--color-text-muted)' }}>
                          {expandedSections.has('deep') ? '▼' : '▶'}
                        </span>
                      </button>
                      {expandedSections.has('deep') && (
                        <div className="mt-1.5 space-y-1.5">
                          {deepAgents.map(agent => (
                            <div
                              key={agent.id}
                              onClick={() => setSelectedItem({ type: 'agent', data: agent })}
                              className={`group p-3 rounded-xl border cursor-pointer transition-all duration-200 hover:shadow-md ${selectedItem?.type === 'agent' && selectedItem.data.id === agent.id
                                ? 'bg-white dark:bg-gray-800 border-primary shadow-sm ring-1 ring-primary/20'
                                : 'bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800 hover:border-primary/50'
                                }`}
                            >
                              <div className="flex items-start gap-3">
                                <div
                                  className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 transition-colors ${selectedItem?.type === 'agent' && selectedItem.data.id === agent.id
                                    ? 'bg-primary/10 text-primary'
                                    : 'bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400 group-hover:text-primary group-hover:bg-primary/5'
                                    }`}
                                >
                                  <span className="material-symbols-outlined text-xl">
                                    psychology
                                  </span>
                                </div>
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center justify-between mb-0.5">
                                    <h4 className="font-semibold text-sm truncate text-gray-900 dark:text-gray-100">
                                      {agent.name}
                                    </h4>
                                  </div>
                                  <p className="text-xs text-gray-500 dark:text-gray-400 line-clamp-2 leading-relaxed">
                                    {agent.description}
                                  </p>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Center Panel - Preview (60%) */}
        {/* Center Panel - Preview (75%) */}
        <div className="w-[75%] flex flex-col overflow-hidden bg-white dark:bg-panel-dark">
          {selectedItem === null || selectedItem.type === 'template' ? (
            /* Template Gallery */
            <div className="flex-1 overflow-y-auto flex items-center justify-center p-12">
              <div className="max-w-6xl w-full">
                <div className="mb-12 text-center">
                  <h2 className="text-3xl font-bold mb-3" style={{ color: 'var(--color-text-primary)' }}>
                    Get Started
                  </h2>
                  <p className="text-base" style={{ color: 'var(--color-text-muted)' }}>
                    Choose a template to quickly create agents and tools
                  </p>
                </div>

                {/* Side by Side Layout */}
                <div className="grid grid-cols-2 gap-12">
                  {/* Agent Templates - Left Side */}
                  <div className="flex flex-col">
                    <h3 className="text-xl font-semibold mb-6 flex items-center justify-center gap-2" style={{ color: 'var(--color-text-primary)' }}>
                      <Sparkles size={20} style={{ color: 'var(--color-primary)' }} />
                      Agent Templates
                    </h3>
                    <div className="space-y-4 flex-1">
                      <button
                        onClick={() => {
                          setEditingAgent({
                            id: 0,
                            name: 'Code Generator',
                            description: 'Generate, refactor, and document code',
                            category: 'Development',
                            config: {
                              name: 'Code Generator',
                              description: 'Generate, refactor, and document code with filesystem tools and GitHub integration',
                              model: 'claude-3-5-sonnet-20241022',
                              temperature: 0.3,
                              system_prompt: `You are an expert software engineer and code generator. Your role is to:

1. Generate clean, well-structured, and documented code
2. Follow best practices and design patterns for the target language
3. Write comprehensive documentation and comments
4. Refactor existing code to improve quality and maintainability
5. Use filesystem tools to read, write, and modify files
6. Integrate with GitHub for version control operations

Always explain your code changes and provide context for your decisions.`,
                              mcp_tools: ['read_file', 'write_file', 'ls', 'edit_file', 'glob', 'grep'],
                              enable_memory: true,
                              enable_rag: false,
                              enable_model_routing: false,
                              enable_parallel_tools: true,
                              timeout_seconds: 300,
                              max_retries: 3
                            },
                            usage_count: 0,
                            version: '1.0.0',
                            is_public: false,
                            created_at: new Date().toISOString(),
                            updated_at: new Date().toISOString()
                          } as Agent);
                          setAgentType('deep');
                          setCameFromTypeSelector(false);
                          setShowAgentBuilder(true);
                        }}
                        className="w-full p-5 rounded-xl border-2 border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 text-left transition-all duration-200 shadow-sm hover:border-primary hover:-translate-y-0.5 hover:shadow-lg"
                      >
                        <div className="flex items-center gap-4">
                          <span className="material-symbols-outlined text-4xl" style={{ color: 'var(--color-primary)' }}>
                            code
                          </span>
                          <div>
                            <h4 className="font-semibold text-base mb-1" style={{ color: 'var(--color-text-primary)' }}>
                              Code Generator
                            </h4>
                            <p className="text-xs" style={{ color: 'var(--color-text-muted)', lineHeight: '1.3' }}>
                              Generate, refactor, and document code with filesystem tools and GitHub integration
                            </p>
                          </div>
                        </div>
                      </button>

                      <button
                        onClick={() => {
                          setEditingAgent({
                            id: 0,
                            name: 'Research Assistant',
                            description: 'Gather information and generate reports',
                            category: 'Research',
                            config: {
                              name: 'Research Assistant',
                              description: 'Gather information from the web, synthesize findings, and generate comprehensive reports',
                              model: 'claude-3-5-sonnet-20241022',
                              temperature: 0.7,
                              system_prompt: `You are an expert research assistant specializing in information gathering and synthesis. Your role is to:

1. Search the web for relevant and credible information
2. Analyze and synthesize findings from multiple sources
3. Identify key trends, patterns, and insights
4. Generate well-structured, comprehensive reports
5. Cite sources and provide references
6. Verify information accuracy and credibility

Always provide balanced perspectives and acknowledge uncertainties when appropriate.`,
                              mcp_tools: ['web_search', 'web_fetch'],
                              enable_memory: true,
                              enable_rag: true,
                              enable_model_routing: false,
                              enable_parallel_tools: true,
                              timeout_seconds: 300,
                              max_retries: 3
                            },
                            usage_count: 0,
                            version: '1.0.0',
                            is_public: false,
                            created_at: new Date().toISOString(),
                            updated_at: new Date().toISOString()
                          } as Agent);
                          setAgentType('deep');
                          setCameFromTypeSelector(false);
                          setShowAgentBuilder(true);
                        }}
                        className="w-full p-5 rounded-xl border-2 border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 text-left transition-all duration-200 shadow-sm hover:border-primary hover:-translate-y-0.5 hover:shadow-lg"
                      >
                        <div className="flex items-center gap-4">
                          <span className="material-symbols-outlined text-4xl" style={{ color: 'var(--color-primary)' }}>
                            search
                          </span>
                          <div>
                            <h4 className="font-semibold text-base mb-1" style={{ color: 'var(--color-text-primary)' }}>
                              Research Assistant
                            </h4>
                            <p className="text-xs" style={{ color: 'var(--color-text-muted)', lineHeight: '1.3' }}>
                              Gather information from the web, synthesize findings, and generate reports
                            </p>
                          </div>
                        </div>
                      </button>

                      <button
                        onClick={() => {
                          setEditingAgent({
                            id: 0,
                            name: 'Testing Agent',
                            description: 'Write and execute comprehensive tests',
                            category: 'Testing',
                            config: {
                              name: 'Testing Agent',
                              description: 'Write and execute tests, analyze coverage, and identify edge cases',
                              model: 'claude-3-5-sonnet-20241022',
                              temperature: 0.4,
                              system_prompt: `You are an expert QA engineer and testing specialist. Your role is to:

1. Write comprehensive unit, integration, and end-to-end tests
2. Identify edge cases and potential failure scenarios
3. Analyze test coverage and suggest improvements
4. Execute tests and interpret results
5. Use testing frameworks and tools appropriate for the language
6. Provide clear test documentation and assertions

Focus on writing maintainable, reliable tests that catch real issues.`,
                              mcp_tools: ['read_file', 'write_file', 'ls', 'edit_file', 'glob', 'grep'],
                              enable_memory: true,
                              enable_rag: false,
                              enable_model_routing: false,
                              enable_parallel_tools: true,
                              timeout_seconds: 300,
                              max_retries: 3
                            },
                            usage_count: 0,
                            version: '1.0.0',
                            is_public: false,
                            created_at: new Date().toISOString(),
                            updated_at: new Date().toISOString()
                          } as Agent);
                          setAgentType('deep');
                          setCameFromTypeSelector(false);
                          setShowAgentBuilder(true);
                        }}
                        className="w-full p-5 rounded-xl border-2 border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 text-left transition-all duration-200 shadow-sm hover:border-primary hover:-translate-y-0.5 hover:shadow-lg"
                      >
                        <div className="flex items-center gap-4">
                          <span className="material-symbols-outlined text-4xl" style={{ color: 'var(--color-primary)' }}>
                            terminal
                          </span>
                          <div>
                            <h4 className="font-semibold text-base mb-1" style={{ color: 'var(--color-text-primary)' }}>
                              Testing Agent
                            </h4>
                            <p className="text-xs" style={{ color: 'var(--color-text-muted)', lineHeight: '1.3' }}>
                              Write and execute tests, analyze coverage, and identify edge cases
                            </p>
                          </div>
                        </div>
                      </button>
                    </div>

                    {/* Create Custom Agent Button */}
                    <div className="mt-6">
                      <button
                        onClick={() => {
                          setEditingAgent(null);
                          setShowTypeSelector(true);
                        }}
                        className="w-full py-3 rounded-xl text-sm font-semibold text-white flex items-center justify-center gap-2 transition-all shadow-lg"
                        style={{ backgroundColor: 'var(--color-primary)' }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.transform = 'translateY(-2px)';
                          e.currentTarget.style.boxShadow = '0 12px 24px rgba(0,0,0,0.15)';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.transform = 'translateY(0)';
                          e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)';
                        }}
                      >
                        <Plus size={20} />
                        Create Custom Agent
                      </button>
                    </div>
                  </div>

                  {/* Tool Templates - Right Side */}
                  <div className="flex flex-col">
                    <h3 className="text-xl font-semibold mb-6 flex items-center justify-center gap-2" style={{ color: 'var(--color-text-primary)' }}>
                      <Database size={20} style={{ color: 'var(--color-primary)' }} />
                      Tool Templates
                    </h3>
                    <div className="space-y-4 flex-1">
                      <button
                        onClick={() => {
                          setEditingTool(null);
                          setSelectedItem({ type: 'template', category: 'tool' });
                          setToolTemplate({
                            toolType: 'api',
                            name: 'Weather Forecast API',
                            description: 'Get weather forecast data from the National Weather Service',
                            category: 'API Integration',
                            tags: ['weather', 'api', 'government'],
                            implementationConfig: {
                              url: 'https://api.weather.gov/gridpoints/TOP/31,80/forecast',
                              method: 'GET',
                              headers: {
                                'User-Agent': '(YourApp, contact@example.com)',
                                'Accept': 'application/geo+json'
                              },
                              timeout: 30
                            },
                            inputSchema: {
                              type: 'object',
                              properties: {
                                office: {
                                  type: 'string',
                                  description: 'NWS office code (e.g., TOP for Topeka)',
                                  default: 'TOP'
                                },
                                gridX: {
                                  type: 'number',
                                  description: 'Grid X coordinate',
                                  default: 31
                                },
                                gridY: {
                                  type: 'number',
                                  description: 'Grid Y coordinate',
                                  default: 80
                                }
                              },
                              required: ['office', 'gridX', 'gridY']
                            }
                          });
                          setShowToolBuilder(true);
                        }}
                        className="w-full p-5 rounded-xl border-2 border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 text-left transition-all duration-200 shadow-sm hover:border-primary hover:-translate-y-0.5 hover:shadow-lg"
                      >
                        <div className="flex items-center gap-4">
                          <span className="material-symbols-outlined text-4xl" style={{ color: 'var(--color-primary)' }}>
                            api
                          </span>
                          <div>
                            <h4 className="font-semibold text-base mb-1" style={{ color: 'var(--color-text-primary)' }}>
                              API Call
                            </h4>
                            <p className="text-xs" style={{ color: 'var(--color-text-muted)', lineHeight: '1.3' }}>
                              Make HTTP requests to external APIs, handle authentication, and process responses
                            </p>
                          </div>
                        </div>
                      </button>

                      <button
                        onClick={() => {
                          setEditingTool(null);
                          setSelectedItem({ type: 'template', category: 'tool' });
                          setToolTemplate({
                            toolType: 'notification',
                            name: 'Discord Notification',
                            description: 'Send messages to Discord channels via webhook',
                            category: 'Notifications',
                            tags: ['discord', 'notification', 'messaging'],
                            implementationConfig: {
                              webhook_url: 'https://discord.comhttp://localhost:8765/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN',
                              username: 'LangConfig Bot',
                              avatar_url: 'https://example.com/avatar.png'
                            },
                            inputSchema: {
                              type: 'object',
                              properties: {
                                content: {
                                  type: 'string',
                                  description: 'The message content to send to Discord'
                                },
                                embeds: {
                                  type: 'array',
                                  description: 'Optional embeds for rich formatting',
                                  items: {
                                    type: 'object',
                                    properties: {
                                      title: { type: 'string' },
                                      description: { type: 'string' },
                                      color: { type: 'number' }
                                    }
                                  }
                                }
                              },
                              required: ['content']
                            }
                          });
                          setShowToolBuilder(true);
                        }}
                        className="w-full p-5 rounded-xl border-2 border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 text-left transition-all duration-200 shadow-sm hover:border-primary hover:-translate-y-0.5 hover:shadow-lg"
                      >
                        <div className="flex items-center gap-4">
                          <span className="material-symbols-outlined text-4xl" style={{ color: 'var(--color-primary)' }}>
                            notifications
                          </span>
                          <div>
                            <h4 className="font-semibold text-base mb-1" style={{ color: 'var(--color-text-primary)' }}>
                              Notification
                            </h4>
                            <p className="text-xs" style={{ color: 'var(--color-text-muted)', lineHeight: '1.3' }}>
                              Send alerts and notifications via Slack, email, webhooks, or custom channels
                            </p>
                          </div>
                        </div>
                      </button>

                      <button
                        onClick={() => {
                          setEditingTool(null);
                          setSelectedItem({ type: 'template', category: 'tool' });
                          setToolTemplate({
                            toolType: 'database',
                            name: 'PostgreSQL Query',
                            description: 'Execute safe parameterized queries on PostgreSQL database',
                            category: 'Database',
                            tags: ['database', 'postgresql', 'sql'],
                            implementationConfig: {
                              db_type: 'postgresql',
                              host: 'localhost',
                              port: 5432,
                              database: 'myapp_db',
                              use_connection_pool: true,
                              max_connections: 10,
                              query_timeout: 30
                            },
                            inputSchema: {
                              type: 'object',
                              properties: {
                                query: {
                                  type: 'string',
                                  description: 'SQL query to execute (use $1, $2, etc. for parameters)'
                                },
                                parameters: {
                                  type: 'array',
                                  items: { type: 'string' },
                                  description: 'Query parameters to bind safely',
                                  default: []
                                },
                                max_rows: {
                                  type: 'number',
                                  description: 'Maximum number of rows to return',
                                  default: 100
                                }
                              },
                              required: ['query']
                            }
                          });
                          setShowToolBuilder(true);
                        }}
                        className="w-full p-5 rounded-xl border-2 border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 text-left transition-all duration-200 shadow-sm hover:border-primary hover:-translate-y-0.5 hover:shadow-lg"
                      >
                        <div className="flex items-center gap-4">
                          <span className="material-symbols-outlined text-4xl" style={{ color: 'var(--color-primary)' }}>
                            storage
                          </span>
                          <div>
                            <h4 className="font-semibold text-base mb-1" style={{ color: 'var(--color-text-primary)' }}>
                              Database Query
                            </h4>
                            <p className="text-xs" style={{ color: 'var(--color-text-muted)', lineHeight: '1.3' }}>
                              Execute queries on PostgreSQL, MySQL, and other databases securely
                            </p>
                          </div>
                        </div>
                      </button>
                    </div>

                    {/* Create Custom Tool Button */}
                    <div className="mt-6">
                      <button
                        onClick={() => {
                          setEditingTool(null);
                          setToolTemplate(null);
                          setSelectedItem({ type: 'template', category: 'tool' });
                          setShowToolBuilder(true);
                        }}
                        className="w-full py-3 rounded-xl text-sm font-semibold text-white flex items-center justify-center gap-2 transition-all shadow-lg"
                        style={{ backgroundColor: 'var(--color-primary)' }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.transform = 'translateY(-2px)';
                          e.currentTarget.style.boxShadow = '0 12px 24px rgba(0,0,0,0.15)';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.transform = 'translateY(0)';
                          e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)';
                        }}
                      >
                        <Plus size={20} />
                        Create Custom Tool
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ) : selectedItem.type === 'agent' ? (
            /* Agent Configuration View */
            <AgentConfigView
              agent={selectedItem.data}
              onSave={async (updatedConfig) => {
                // FIX: Pass the agent info for update instead of create
                await handleSaveAgentFromConfigView(selectedItem.data.id, updatedConfig);
                loadAgents(); // Refresh the list
              }}
              onDelete={() => handleDeleteAgent(selectedItem.data.id)}
              onClose={() => setSelectedItem(null)}
            />
          ) : selectedItem.type === 'skill' ? (
            /* Skill Configuration View */
            <SkillConfigView
              skill={selectedItem.data}
              onClose={() => setSelectedItem(null)}
              onDelete={async (skillId: string) => {
                try {
                  await apiClient.delete(`/api/skills/${skillId}`);
                  await loadSkills();
                  setSelectedItem(null);
                } catch (error) {
                  console.error('Failed to delete skill:', error);
                }
              }}
            />
          ) : (
            /* Tool Configuration View */
            <ToolConfigView
              tool={selectedItem.data}
              onSave={handleSaveTool}
              onDelete={() => handleDeleteTool(selectedItem.data.tool_id)}
              onClose={() => setSelectedItem(null)}
            />
          )}
        </div>

        {/* Right Sidebar - Custom Tools & Skills (25%) */}
        <div className="w-[25%] flex flex-col border-l border-gray-200 dark:border-border-dark bg-white dark:bg-panel-dark">
          {/* Sidebar Header with Tabs */}
          <div className="p-4 border-b border-gray-200 dark:border-border-dark bg-white/50 dark:bg-panel-dark/50 backdrop-blur-sm sticky top-0 z-10">
            {/* Tab Headers */}
            <div className="flex items-center gap-1 mb-4 p-1 rounded-lg" style={{ backgroundColor: 'var(--color-background-dark)' }}>
              <button
                onClick={() => setRightPanelTab('tools')}
                className={`flex-1 px-3 py-2 rounded-md text-sm font-medium transition-all ${rightPanelTab === 'tools'
                  ? 'bg-white dark:bg-gray-800 shadow-sm text-gray-900 dark:text-white'
                  : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
                  }`}
              >
                Custom Tools
              </button>
              <button
                onClick={() => setRightPanelTab('skills')}
                className={`flex-1 px-3 py-2 rounded-md text-sm font-medium transition-all ${rightPanelTab === 'skills'
                  ? 'bg-white dark:bg-gray-800 shadow-sm text-gray-900 dark:text-white'
                  : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
                  }`}
              >
                Claude Skills
              </button>
            </div>

            {/* Search Bar */}
            <div className="relative group">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 group-focus-within:text-primary transition-colors" size={16} />
              <input
                type="text"
                placeholder={rightPanelTab === 'tools' ? 'Search tools...' : 'Search skills...'}
                value={rightPanelTab === 'tools' ? toolSearchQuery : skillSearchQuery}
                onChange={(e) => rightPanelTab === 'tools' ? setToolSearchQuery(e.target.value) : setSkillSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all shadow-sm"
              />
            </div>
          </div>

          {/* Content Area */}
          <div className="flex-1 overflow-y-auto">
            {rightPanelTab === 'tools' ? (
              /* Tools List */
              <div className="px-4 py-3">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                      Custom Tools
                    </h3>
                    <span className="text-xs px-2 py-0.5 rounded-full" style={{
                      backgroundColor: 'var(--color-background-dark)',
                      color: 'var(--color-text-muted)'
                    }}>
                      {filteredTools.length}
                    </span>
                  </div>
                  <button
                    onClick={() => {
                      setEditingTool(null);
                      setToolTemplate(null);
                      setSelectedItem({ type: 'template', category: 'tool' });
                      setShowToolBuilder(true);
                    }}
                    className="px-3 py-1.5 rounded-lg text-xs font-medium text-white flex items-center gap-1.5"
                    style={{ backgroundColor: 'var(--color-primary)' }}
                    onMouseEnter={(e) => e.currentTarget.style.opacity = '0.9'}
                    onMouseLeave={(e) => e.currentTarget.style.opacity = '1'}
                  >
                    <Plus size={14} />
                    New Tool
                  </button>
                </div>

                {loading ? (
                  <div className="text-center py-8 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                    Loading...
                  </div>
                ) : filteredTools.length === 0 ? (
                  <div className="text-center py-8 px-4">
                    <span className="material-symbols-outlined text-3xl mb-2 block" style={{ color: 'var(--color-text-muted)' }}>
                      build
                    </span>
                    <p className="text-sm mb-3" style={{ color: 'var(--color-text-muted)' }}>
                      No tools yet
                    </p>
                    <button
                      onClick={() => setSelectedItem({ type: 'template', category: 'tool' })}
                      className="text-xs px-3 py-1.5 rounded-lg"
                      style={{ color: 'var(--color-primary)', backgroundColor: 'var(--color-background-dark)' }}
                    >
                      View Templates
                    </button>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 gap-2 px-2">
                    {filteredTools.map(tool => (
                      <div
                        key={tool.tool_id}
                        onClick={() => setSelectedItem({ type: 'tool', data: tool })}
                        className={`group p-3 rounded-xl border cursor-pointer transition-all duration-200 hover:shadow-md ${selectedItem?.type === 'tool' && selectedItem.data.tool_id === tool.tool_id
                          ? 'bg-white dark:bg-gray-800 border-primary shadow-sm ring-1 ring-primary/20'
                          : 'bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800 hover:border-primary/50'
                          }`}
                      >
                        <div className="flex items-start gap-3">
                          <div
                            className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 transition-colors ${selectedItem?.type === 'tool' && selectedItem.data.tool_id === tool.tool_id
                              ? 'bg-primary/10 text-primary'
                              : 'bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400 group-hover:text-primary group-hover:bg-primary/5'
                              }`}
                          >
                            <span className="material-symbols-outlined text-xl">
                              {getToolIcon(tool.tool_type)}
                            </span>
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between mb-0.5">
                              <h4 className="font-semibold text-sm truncate text-gray-900 dark:text-gray-100">
                                {tool.name}
                              </h4>
                            </div>
                            <p className="text-xs text-gray-500 dark:text-gray-400 line-clamp-2 leading-relaxed mb-1.5">
                              {tool.description}
                            </p>
                            <div className="flex items-center gap-1.5">
                              <span className="text-xs px-1.5 py-0.5 rounded bg-primary/10 text-primary text-[0.65rem]">
                                {tool.tool_type}
                              </span>
                              {tool.usage_count > 0 && (
                                <span className="text-xs text-gray-500 dark:text-gray-400 text-[0.65rem]">
                                  {tool.usage_count}x
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              /* Skills List */
              <div className="px-4 py-3">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                      Claude Skills
                    </h3>
                    <span className="text-xs px-2 py-0.5 rounded-full" style={{
                      backgroundColor: 'var(--color-background-dark)',
                      color: 'var(--color-text-muted)'
                    }}>
                      {filteredSkills.length}
                    </span>
                    <a
                      href="https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs hover:underline"
                      style={{ color: 'var(--color-primary)' }}
                      title="Learn about Claude Skills"
                    >
                      Docs ↗
                    </a>
                  </div>
                  <button
                    onClick={() => setShowSkillBuilder(true)}
                    className="p-1.5 rounded-lg transition-colors flex items-center gap-1"
                    style={{ backgroundColor: 'var(--color-primary)', color: 'white' }}
                    title="New Skill"
                  >
                    <Plus size={14} />
                    <span className="text-xs font-medium">New Skill</span>
                  </button>
                </div>

                {loading ? (
                  <div className="text-center py-8 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                    Loading...
                  </div>
                ) : filteredSkills.length === 0 ? (
                  <div className="text-center py-8 px-4">
                    <BookOpen className="w-8 h-8 mx-auto mb-2" style={{ color: 'var(--color-text-muted)' }} />
                    <p className="text-sm mb-3" style={{ color: 'var(--color-text-muted)' }}>
                      No skills found
                    </p>
                    <button
                      onClick={() => setShowSkillBuilder(true)}
                      className="text-xs px-3 py-1.5 rounded-lg flex items-center gap-1 mx-auto"
                      style={{ backgroundColor: 'var(--color-primary)', color: 'white' }}
                    >
                      <Plus size={12} />
                      New Skill
                    </button>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {Object.entries(skillsByCategory).map(([category, categorySkills]) => (
                      <div key={category}>
                        {/* Category Header */}
                        <div className="flex items-center gap-2 mb-2 px-2">
                          <span className="text-xs font-semibold uppercase tracking-wider text-gray-900 dark:text-gray-100">
                            {category}
                          </span>
                          <span className="text-xs px-1.5 py-0.5 rounded" style={{
                            backgroundColor: 'var(--color-background-dark)',
                            color: 'var(--color-text-muted)'
                          }}>
                            {categorySkills.length}
                          </span>
                        </div>
                        {/* Skills in Category */}
                        <div className="grid grid-cols-1 gap-2 px-2">
                          {categorySkills.map(skill => (
                            <div
                              key={skill.skill_id}
                              onClick={() => fetchSkillDetail(skill.skill_id)}
                              className={`group p-3 rounded-xl border cursor-pointer transition-all duration-200 hover:shadow-md ${selectedItem?.type === 'skill' && selectedItem.data.skill_id === skill.skill_id
                                ? 'bg-white dark:bg-gray-800 border-primary shadow-sm ring-1 ring-primary/20'
                                : 'bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800 hover:border-primary/50'
                                }`}
                            >
                              <div className="flex items-start gap-3">
                                <div
                                  className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 transition-colors ${selectedItem?.type === 'skill' && selectedItem.data.skill_id === skill.skill_id
                                    ? 'bg-primary/10 text-primary'
                                    : 'bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400 group-hover:text-primary group-hover:bg-primary/5'
                                    }`}
                                >
                                  <BookOpen className="w-5 h-5" />
                                </div>
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center justify-between mb-0.5">
                                    <h4 className="font-semibold text-sm truncate text-gray-900 dark:text-gray-100">
                                      {skill.name}
                                    </h4>
                                  </div>
                                  <p className="text-xs text-gray-500 dark:text-gray-400 line-clamp-2 leading-relaxed mb-1.5">
                                    {skill.description}
                                  </p>
                                  {skill.usage_count > 0 && (
                                    <span className="text-xs text-gray-500 dark:text-gray-400 text-[0.65rem]">
                                      {skill.usage_count} uses
                                    </span>
                                  )}
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Agent Type Selector Modal */}
      {
        showTypeSelector && (
          <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
            <div className="bg-white dark:bg-panel-dark border-2 rounded-xl w-full max-w-2xl shadow-2xl" style={{ borderColor: 'var(--color-primary)', boxShadow: '0 20px 25px -5px rgba(46, 92, 138, 0.3), 0 10px 10px -5px rgba(46, 92, 138, 0.15)' }}>
              {/* Header */}
              <div className="p-6 border-b" style={{
                backgroundColor: 'var(--color-primary)',
                borderBottomColor: 'var(--color-border-dark)'
              }}>
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <h2 className="text-2xl font-semibold text-white" style={{ textShadow: '0 1px 2px rgba(0, 0, 0, 0.25)' }}>Choose Agent Type</h2>
                    <p className="text-sm mt-1 text-white/90" style={{ textShadow: '0 1px 2px rgba(0, 0, 0, 0.15)' }}>
                      Select the type of agent you want to create
                    </p>
                  </div>
                  <button
                    onClick={() => setShowTypeSelector(false)}
                    className="p-2 transition-all text-white/90 hover:text-white hover:bg-white/15 rounded-lg"
                    style={{ textShadow: '0 1px 2px rgba(0, 0, 0, 0.15)' }}
                    title="Close"
                  >
                    <X className="w-6 h-6" />
                  </button>
                </div>
              </div>

              {/* Content */}
              <div className="p-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Regular Agent Card */}
                  <button
                    onClick={() => {
                      setAgentType('regular');
                      setShowTypeSelector(false);
                      setCameFromTypeSelector(true);
                      setShowAgentBuilder(true);
                    }}
                    className="p-4 border-2 border-gray-200 dark:border-border-dark rounded-lg transition-all duration-200 text-left hover:border-primary hover:shadow-md hover:scale-[1.02]"
                    style={{
                      backgroundColor: 'var(--color-panel-dark)'
                    }}
                  >
                    <div className="flex items-center gap-3 mb-3">
                      <div className="p-2 rounded-lg" style={{ backgroundColor: 'var(--color-input-background)' }}>
                        <span className="material-symbols-outlined text-xl" style={{ color: 'var(--color-primary)' }}>terminal</span>
                      </div>
                      <h3 className="text-lg font-semibold" style={{ color: 'var(--color-text-primary)' }}>Regular Agent</h3>
                    </div>
                    <p className="text-sm mb-4" style={{ color: 'var(--color-text-muted)' }}>
                      Standard LangChain agent with tool calling capabilities
                    </p>
                    <ul className="text-xs space-y-1" style={{ color: 'var(--color-text-muted)' }}>
                      <li>• Model selection</li>
                      <li>• System prompt</li>
                      <li>• Tool selection (MCP tools)</li>
                      <li>• Temperature control</li>
                      <li>• Memory & RAG support</li>
                    </ul>
                  </button>

                  {/* Deep Agent Card */}
                  <button
                    onClick={() => {
                      setAgentType('deep');
                      setShowTypeSelector(false);
                      setCameFromTypeSelector(true);
                      setShowAgentBuilder(true);
                    }}
                    className="p-4 border-2 border-gray-200 dark:border-border-dark rounded-lg transition-all duration-200 text-left hover:border-primary hover:shadow-md hover:scale-[1.02]"
                    style={{
                      backgroundColor: 'var(--color-panel-dark)'
                    }}
                  >
                    <div className="flex items-center gap-3 mb-3">
                      <div className="p-2 rounded-lg" style={{ backgroundColor: 'var(--color-input-background)' }}>
                        <span className="material-symbols-outlined text-xl" style={{ color: 'var(--color-primary)' }}>psychology</span>
                      </div>
                      <h3 className="text-lg font-semibold" style={{ color: 'var(--color-text-primary)' }}>Deep Agent</h3>
                    </div>
                    <p className="text-sm mb-4" style={{ color: 'var(--color-text-muted)' }}>
                      Advanced agent with planning, subagents, and middleware
                    </p>
                    <ul className="text-xs space-y-1" style={{ color: 'var(--color-text-muted)' }}>
                      <li>• Planning capabilities</li>
                      <li>• Subagent delegation</li>
                      <li>• Backend storage (Memory/SQLite/PostgreSQL)</li>
                      <li>• Middleware (RAG, validation, tool selection)</li>
                      <li>• Reflection & critique</li>
                    </ul>
                  </button>
                </div>
              </div>

              {/* Footer */}
              <div className="flex items-center justify-end gap-3 p-6 border-t border-gray-200 dark:border-border-dark">
                <button
                  onClick={() => setShowTypeSelector(false)}
                  className="px-4 py-2 transition-colors"
                  style={{ color: 'var(--color-text-muted)' }}
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )
      }

      {/* Agent Builder Modal */}
      {
        (showAgentBuilder || selectedAgent) && (
          <div
            className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4"
            onClick={() => {
              if (selectedAgent) {
                setSearchParams({});
              } else {
                setShowAgentBuilder(false);
                setEditingAgent(null);
                setCameFromTypeSelector(false);
              }
            }}
            role="dialog"
            aria-modal="true"
          >
            <div
              className="bg-white dark:bg-panel-dark border-2 rounded-xl w-full max-w-full md:max-w-6xl h-full md:h-[90vh] flex flex-col overflow-hidden"
              style={{ borderColor: 'var(--color-primary)', boxShadow: '0 20px 25px -5px rgba(46, 92, 138, 0.3), 0 10px 10px -5px rgba(46, 92, 138, 0.15)' }}
              onClick={(e) => e.stopPropagation()}
            >
              <DeepAgentBuilder
                initialConfig={selectedAgent ? selectedAgent.config : editingAgent?.config}
                agentType={agentType}
                onSave={async (config) => {
                  await handleSave(config);
                  if (selectedAgent) {
                    setSearchParams({});
                  } else {
                    setShowAgentBuilder(false);
                    setEditingAgent(null);
                  }
                }}
                onClose={() => {
                  if (selectedAgent) {
                    setSearchParams({});
                  } else {
                    setShowAgentBuilder(false);
                    setEditingAgent(null);
                    setCameFromTypeSelector(false);
                    setSelectedItem({ type: 'template', category: 'agent' });
                  }
                }}
                onBack={() => {
                  if (selectedAgent) {
                    setSearchParams({});
                  } else {
                    setShowAgentBuilder(false);
                    setEditingAgent(null);
                    if (cameFromTypeSelector) {
                      setShowTypeSelector(true);
                    } else {
                      setSelectedItem({ type: 'template', category: 'agent' });
                    }
                    setCameFromTypeSelector(false);
                  }
                }}
              />
            </div>
          </div>
        )
      }

      {/* Tool Builder Modal */}
      {
        showToolBuilder && (
          <div
            className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4"
            onClick={() => {
              setSelectedItem({ type: 'template', category: 'tool' });
              setShowToolBuilder(false);
              setEditingTool(null);
              setToolTemplate(null);
            }}
            role="dialog"
            aria-modal="true"
          >
            <div
              className="bg-white dark:bg-panel-dark border-2 rounded-xl w-full max-w-full md:max-w-6xl h-full md:h-[90vh] flex flex-col overflow-hidden"
              style={{ borderColor: 'var(--color-primary)', boxShadow: '0 20px 25px -5px rgba(46, 92, 138, 0.3), 0 10px 10px -5px rgba(46, 92, 138, 0.15)' }}
              onClick={(e) => e.stopPropagation()}
            >
              <CustomToolBuilder
                existingToolId={editingTool || undefined}
                skipTemplateStep={false}
                initialTemplate={toolTemplate}
                onClose={() => {
                  setSelectedItem({ type: 'template', category: 'tool' });
                  setShowToolBuilder(false);
                  setEditingTool(null);
                  setToolTemplate(null);
                  loadTools();
                }}
                onBack={() => {
                  setSelectedItem({ type: 'template', category: 'tool' });
                  setShowToolBuilder(false);
                  setEditingTool(null);
                  setToolTemplate(null);
                }}
              />
            </div>
          </div>
        )
      }


      {
        showConflictDialog && conflictData && (
          <ConflictDialog
            open={showConflictDialog}
            resourceType="Agent"
            resourceName={conflictData.agent.name}
            localData={conflictData.localData}
            remoteData={conflictData.remoteData}
            onResolve={handleConflictResolve}
            onClose={() => {
              setShowConflictDialog(false);
              setConflictData(null);
            }}
          />
        )
      }

      {/* Notification Modal */}
      <NotificationModal />

      {/* Skill Builder Modal */}
      {showSkillBuilder && (
        <SkillBuilderModal
          onClose={() => setShowSkillBuilder(false)}
          onSave={async (skill) => {
            await loadSkills();
            setSelectedItem({ type: 'skill', data: skill });
          }}
        />
      )}
    </div >
  );
};

export default AgentLoadouts;
