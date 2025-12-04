/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useEffect } from 'react';
import { ChevronDown, ChevronRight, Plus, X } from 'lucide-react';
import { getModelDisplayName } from '../../../lib/modelDisplayNames';
import DeepAgentBuilder from './DeepAgentBuilder';
import apiClient from '../../../lib/api-client';
import { useNotification } from '../../../hooks/useNotification';

interface Agent {
  id: string;
  name: string;
  description: string;
  icon: string;
  model: string;
  fallback_models?: string[];
  temperature: number;
  max_tokens?: number;
  system_prompt: string;
  native_tools: string[];
  cli_tools?: string[];
  custom_tools?: string[];  // FIX: Add custom_tools field
  timeout_seconds: number;
  max_retries: number;
  enable_model_routing: boolean;
  enable_parallel_tools: boolean;
  enable_memory: boolean;
  enable_rag?: boolean;
  requires_human_approval?: boolean;
  tags?: string[];
}

interface AgentCategory {
  id: string;
  name: string;
  icon: string;
  agents: Agent[];
}

// Workflow recipe type for multi-node templates
export interface WorkflowRecipe {
  recipe_id: string;
  name: string;
  description: string;
  category: string;
  icon: string;
  tags: string[];
  nodes: any[];
  edges: any[];
  node_count: number;
  edge_count: number;
}

interface ModernAgentLibraryProps {
  onSelectAgent: (agent: Agent) => void;
  onSelectRecipe?: (recipe: WorkflowRecipe) => void;
}

// Category name mappings for UI display
const CATEGORY_DISPLAY_NAMES: Record<string, string> = {
  'code_generation': 'Code Generation',
  'code_review': 'Quality & Testing',
  'testing': 'Quality & Testing',
  'devops': 'DevOps',
  'research': 'Research',
  'architecture': 'Code Generation',
  'documentation': 'Research',
  'planning': 'Research',
  'qa_validation': 'Quality & Testing',
  'content_generation': 'Content Generation'
};

const CATEGORY_ICONS: Record<string, string> = {
  'code_generation': 'code',
  'code_review': 'verified',
  'testing': 'verified',
  'devops': 'cloud',
  'research': 'search',
  'architecture': 'code',
  'documentation': 'search',
  'planning': 'search',
  'qa_validation': 'verified',
  'content_generation': 'image'
};

const CATEGORY_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  'Agents': { bg: '#fffbeb', border: '#fbbf24', text: '#fbbf24' },
  'Code Generation': { bg: '#f0f1ff', border: '#6366f1', text: '#6366f1' },
  'Quality & Testing': { bg: '#f0fdf4', border: '#22c55e', text: '#22c55e' },
  'DevOps': { bg: '#fff7ed', border: '#ea580c', text: '#ea580c' },
  'Research': { bg: '#faf5ff', border: '#a855f7', text: '#a855f7' },
  'Content Generation': { bg: '#fef3c7', border: '#f59e0b', text: '#f59e0b' },
  'Control Nodes': { bg: '#f9fafb', border: '#6b7280', text: '#6b7280' }
};

// Control nodes (workflow primitives - kept frontend-only as they're UI-specific)
const CONTROL_NODES: Agent[] = [
  {
    id: 'START_NODE',
    name: 'Start',
    description: 'Workflow entry point. Defines where execution begins and initial input.',
    icon: 'play_circle',
    model: 'none',
    fallback_models: [],
    temperature: 0,
    system_prompt: 'START node: Entry point for workflow execution.',
    native_tools: [],
    cli_tools: [],
    timeout_seconds: 0,
    max_retries: 0,
    enable_model_routing: false,
    enable_parallel_tools: false,
    enable_memory: false,
    enable_rag: false,
    requires_human_approval: false,
    tags: ['control', 'system', 'start']
  },
  {
    id: 'END_NODE',
    name: 'End',
    description: 'Workflow exit point. Marks successful completion and final output.',
    icon: 'stop_circle',
    model: 'none',
    fallback_models: [],
    temperature: 0,
    system_prompt: 'END node: Exit point for workflow execution.',
    native_tools: [],
    cli_tools: [],
    timeout_seconds: 0,
    max_retries: 0,
    enable_model_routing: false,
    enable_parallel_tools: false,
    enable_memory: false,
    enable_rag: false,
    requires_human_approval: false,
    tags: ['control', 'system', 'end']
  },
  {
    id: 'CHECKPOINT_NODE',
    name: 'Checkpoint',
    description: 'State persistence point. Saves workflow state for recovery and resume capabilities.',
    icon: 'bookmark',
    model: 'none',
    fallback_models: [],
    temperature: 0,
    system_prompt: 'CHECKPOINT node: Persists workflow state for recovery.',
    native_tools: [],
    cli_tools: [],
    timeout_seconds: 0,
    max_retries: 0,
    enable_model_routing: false,
    enable_parallel_tools: false,
    enable_memory: false,
    enable_rag: false,
    requires_human_approval: false,
    tags: ['control', 'system', 'persistence']
  },
  {
    id: 'OUTPUT_NODE',
    name: 'Output',
    description: 'Output handler. Formats and returns workflow results to the user.',
    icon: 'output',
    model: 'none',
    fallback_models: [],
    temperature: 0,
    system_prompt: 'OUTPUT node: Formats and returns workflow results.',
    native_tools: [],
    cli_tools: [],
    timeout_seconds: 0,
    max_retries: 0,
    enable_model_routing: false,
    enable_parallel_tools: false,
    enable_memory: false,
    enable_rag: false,
    requires_human_approval: false,
    tags: ['control', 'system', 'output']
  },
  {
    id: 'CONDITIONAL_NODE',
    name: 'Conditional',
    description: 'Branching logic. Routes workflow based on conditions or validation results.',
    icon: 'call_split',
    model: 'none',
    fallback_models: [],
    temperature: 0,
    system_prompt: 'CONDITIONAL node: Routes execution based on conditions.',
    native_tools: [],
    cli_tools: [],
    timeout_seconds: 0,
    max_retries: 0,
    enable_model_routing: false,
    enable_parallel_tools: false,
    enable_memory: false,
    enable_rag: false,
    requires_human_approval: false,
    tags: ['control', 'system', 'branching']
  },
  {
    id: 'LOOP_NODE',
    name: 'Loop',
    description: 'Iteration control. Repeats execution until condition met or max iterations reached.',
    icon: 'sync',
    model: 'none',
    fallback_models: [],
    temperature: 0,
    system_prompt: 'LOOP node: Repeats execution with iteration tracking.',
    native_tools: [],
    cli_tools: [],
    timeout_seconds: 0,
    max_retries: 0,
    enable_model_routing: false,
    enable_parallel_tools: false,
    enable_memory: false,
    enable_rag: false,
    requires_human_approval: false,
    tags: ['control', 'system', 'loop', 'iteration']
  },
  {
    id: 'APPROVAL_NODE',
    name: 'Human Approval',
    description: 'Human-in-the-loop gate. Pauses workflow for human review and approval.',
    icon: 'how_to_reg',
    model: 'none',
    fallback_models: [],
    temperature: 0,
    system_prompt: 'APPROVAL node: Pauses for human-in-the-loop approval.',
    native_tools: [],
    cli_tools: [],
    timeout_seconds: 0,
    max_retries: 0,
    enable_model_routing: false,
    enable_parallel_tools: false,
    enable_memory: false,
    enable_rag: false,
    requires_human_approval: true,
    tags: ['control', 'system', 'hitl', 'approval']
  },
  {
    id: 'TOOL_NODE',
    name: 'Tool',
    description: 'Direct tool execution. Runs a single tool without an agent wrapper.',
    icon: 'construction',
    model: 'none',
    fallback_models: [],
    temperature: 0,
    system_prompt: 'TOOL node: Direct tool execution.',
    native_tools: [],
    cli_tools: [],
    timeout_seconds: 0,
    max_retries: 0,
    enable_model_routing: false,
    enable_parallel_tools: false,
    enable_memory: false,
    enable_rag: false,
    requires_human_approval: false,
    tags: ['control', 'system', 'tool', 'direct-execution']
  }
];

// Control nodes category
const CONTROL_NODES_CATEGORY: AgentCategory = {
  id: 'control-nodes',
  name: 'Control Nodes',
  icon: 'settings',
  agents: CONTROL_NODES
};

export default function ModernAgentLibrary({ onSelectAgent, onSelectRecipe }: ModernAgentLibraryProps) {
  const { showSuccess, logError, showWarning, NotificationModal } = useNotification();
  const [categories, setCategories] = useState<AgentCategory[]>([CONTROL_NODES_CATEGORY]);
  const [recipes, setRecipes] = useState<WorkflowRecipe[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(
    new Set(['workflow-recipes', 'code-generation', 'control-nodes', 'quality-testing', 'devops', 'research', 'data-processing', 'content-generation'])
  );
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [selectedRecipe, setSelectedRecipe] = useState<WorkflowRecipe | null>(null);
  const [showTypeSelector, setShowTypeSelector] = useState(false);
  const [showAgentBuilder, setShowAgentBuilder] = useState(false);
  const [agentType, setAgentType] = useState<'regular' | 'deep'>('deep');
  const [newlyCreatedAgent, setNewlyCreatedAgent] = useState<any>(null);

  // Fetch agent templates from backend
  useEffect(() => {
    const abortController = new AbortController();

    const fetchAgentTemplates = async () => {
      try {
        setLoading(true);

        // Fetch templates, custom agents, and workflow recipes
        const [templates, customAgentsResponse, recipesResponse] = await Promise.all([
          apiClient.apiFetch(`${apiClient.baseURL}/api/agents/templates`, { signal: abortController.signal }),
          apiClient.listDeepAgents({ public_only: false }),
          apiClient.apiFetch(`${apiClient.baseURL}/api/agents/recipes`, { signal: abortController.signal }).catch(() => [])
        ]);

        const customAgents = customAgentsResponse.data || [];

        // Store workflow recipes
        setRecipes(recipesResponse || []);

        // Group templates by display name (to merge similar categories like code_review, testing, qa_validation)
        const categoriesMap = new Map<string, { agents: Agent[], categoryKeys: Set<string> }>();

        templates.forEach((template: any) => {
          const categoryKey = template.category;
          const displayName = CATEGORY_DISPLAY_NAMES[categoryKey] || categoryKey;

          if (!categoriesMap.has(displayName)) {
            categoriesMap.set(displayName, { agents: [], categoryKeys: new Set() });
          }

          // Map API response to frontend Agent interface
          const agent: Agent = {
            id: template.id,
            name: template.name,
            description: template.description,
            icon: template.icon,
            model: template.model,
            fallback_models: template.fallback_models,
            temperature: template.temperature,
            max_tokens: template.max_tokens,
            system_prompt: template.system_prompt,
            native_tools: template.native_tools || template.mcp_tools || [],
            cli_tools: template.cli_tools,
            custom_tools: template.custom_tools || [],  // FIX: Include custom_tools from API
            timeout_seconds: template.timeout_seconds,
            max_retries: template.max_retries,
            enable_model_routing: template.enable_model_routing,
            enable_parallel_tools: template.enable_parallel_tools,
            enable_memory: template.enable_memory,
            enable_rag: template.enable_rag,
            requires_human_approval: template.requires_human_approval,
            tags: template.tags
          };

          const category = categoriesMap.get(displayName)!;
          category.agents.push(agent);
          category.categoryKeys.add(categoryKey);
        });

        // Convert to AgentCategory array
        const agentCategories: AgentCategory[] = Array.from(categoriesMap.entries()).map(
          ([displayName, { agents, categoryKeys }]) => {
            // Use the first category key for ID and icon lookup
            const firstKey = Array.from(categoryKeys)[0];
            return {
              id: firstKey,
              name: displayName,
              icon: CATEGORY_ICONS[firstKey] || 'psychology',
              agents
            };
          }
        );

        // Add Custom Agents category if there are any
        if (customAgents.length > 0) {
          const customAgentsList: Agent[] = customAgents.map((ca: any) => ({
            id: `custom_${ca.id}`,
            name: ca.name,
            description: ca.description || '',
            icon: 'person',
            model: ca.config.model,
            fallback_models: ca.config.fallback_models || [],
            temperature: ca.config.temperature,
            max_tokens: ca.config.max_tokens,
            system_prompt: ca.config.system_prompt,
            native_tools: ca.config.native_tools || ca.config.mcp_tools || [],
            cli_tools: ca.config.cli_tools || [],
            custom_tools: ca.config.custom_tools || [],  // FIX: Include custom_tools from custom agents
            timeout_seconds: 600,
            max_retries: 2,
            enable_model_routing: false,
            enable_parallel_tools: false,
            enable_memory: true,
            enable_rag: false,
            requires_human_approval: false,
            tags: ['custom']
          }));

          agentCategories.unshift({
            id: 'custom',
            name: 'Agents',
            icon: 'star',
            agents: customAgentsList
          });
        }

        // Sort categories alphabetically (except Control Nodes which goes last)
        agentCategories.sort((a, b) => a.name.localeCompare(b.name));

        // Add control nodes category at the end
        agentCategories.push(CONTROL_NODES_CATEGORY);

        setCategories(agentCategories);
        setError(null);
      } catch (err) {
        // Ignore abort errors
        if (err instanceof Error && err.name === 'AbortError') {
          return;
        }
        console.error('Failed to fetch agent templates:', err);
        setError(err instanceof Error ? err.message : 'Failed to load agent templates');
        // Fallback to just control nodes if API fails
        setCategories([CONTROL_NODES_CATEGORY]);
      } finally {
        setLoading(false);
      }
    };

    fetchAgentTemplates();

    return () => {
      abortController.abort();
    };
  }, []);

  const toggleCategory = (categoryId: string) => {
    setExpandedCategories(prev => {
      const next = new Set(prev);
      if (next.has(categoryId)) {
        next.delete(categoryId);
      } else {
        next.add(categoryId);
      }
      return next;
    });
  };

  const handleAgentClick = (agent: Agent) => {
    setSelectedAgent(agent);
    setSelectedRecipe(null); // Clear recipe selection when agent is selected
  };

  const handleRecipeClick = (recipe: WorkflowRecipe) => {
    setSelectedRecipe(recipe);
    setSelectedAgent(null); // Clear agent selection when recipe is selected
  };

  const handleAddToWorkflow = () => {
    if (selectedAgent) {
      onSelectAgent(selectedAgent);
      setSelectedAgent(null); // Close detail panel after adding
    }
  };

  const handleInsertRecipe = () => {
    if (selectedRecipe && onSelectRecipe) {
      onSelectRecipe(selectedRecipe);
      setSelectedRecipe(null); // Close detail panel after inserting
    }
  };

  const handleSaveNewAgent = async (config: any) => {
    try {
      const requestData = {
        name: config.name || 'Untitled Agent',
        description: config.description || '',
        category: config.category || 'Custom',
        config
      };

      const response = await apiClient.createDeepAgent(requestData);

      setShowAgentBuilder(false);
      setNewlyCreatedAgent(response.data);

      // Show success notification
      showSuccess('Agent created successfully!');

      // Refresh categories to include the new agent
      // Note: This assumes the backend returns the agent in a compatible format
    } catch (error: any) {
      console.error('Failed to save agent:', error);
      const errorMsg = error.response?.data?.detail || error.message || 'Failed to save agent';
      logError('Failed to save agent', errorMsg);
    }
  };

  const handleAddNewAgentToWorkflow = () => {
    if (newlyCreatedAgent) {
      // Convert the saved agent to Agent format and add to workflow
      const agent: Agent = {
        id: newlyCreatedAgent.config.id || `agent_${newlyCreatedAgent.id}`,
        name: newlyCreatedAgent.name,
        description: newlyCreatedAgent.description,
        icon: newlyCreatedAgent.config.icon || 'psychology',
        model: newlyCreatedAgent.config.model,
        fallback_models: newlyCreatedAgent.config.fallback_models || [],
        temperature: newlyCreatedAgent.config.temperature,
        max_tokens: newlyCreatedAgent.config.max_tokens,
        system_prompt: newlyCreatedAgent.config.system_prompt,
        native_tools: newlyCreatedAgent.config.native_tools || newlyCreatedAgent.config.mcp_tools || [],
        cli_tools: newlyCreatedAgent.config.cli_tools || [],
        timeout_seconds: newlyCreatedAgent.config.timeout_seconds || 600,
        max_retries: newlyCreatedAgent.config.max_retries || 2,
        enable_model_routing: newlyCreatedAgent.config.enable_model_routing || false,
        enable_parallel_tools: newlyCreatedAgent.config.enable_parallel_tools || false,
        enable_memory: newlyCreatedAgent.config.enable_memory || false,
        enable_rag: newlyCreatedAgent.config.enable_rag || false,
        requires_human_approval: newlyCreatedAgent.config.requires_human_approval || false,
        tags: newlyCreatedAgent.config.tags || []
      };
      onSelectAgent(agent);
    }
    setNewlyCreatedAgent(null);
  };

  const filteredCategories = categories.map(category => ({
    ...category,
    agents: category.agents.filter(agent =>
      agent.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      agent.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      agent.tags?.some(tag => tag.toLowerCase().includes(searchQuery.toLowerCase()))
    )
  })).filter(category => category.agents.length > 0);

  return (
    <aside className="w-80 flex flex-col bg-white dark:bg-panel-dark border-r border-gray-200 dark:border-border-dark overflow-hidden relative">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 dark:border-border-dark">
        <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--color-text-primary, #1a1a1a)' }}>
          Agent Library
        </h2>

        {/* Search */}
        <div className="relative">
          <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-sm" style={{ color: 'var(--color-text-muted, #6b7280)' }}>
            search
          </span>
          <input
            type="text"
            placeholder="Search agents..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-2 bg-gray-50 dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
            style={{ color: 'var(--color-text-primary, #1a1a1a)' }}
          />
        </div>
      </div>

      {/* Agent Categories */}
      <div className="flex-1 overflow-y-auto">
        {/* Workflow Recipes Section */}
        {recipes.length > 0 && (
          <div className="border-b border-gray-200 dark:border-border-dark">
            {/* Recipe Category Header */}
            <button
              onClick={() => toggleCategory('workflow-recipes')}
              className="w-full flex items-center justify-between px-3 py-2 transition-colors hover:opacity-90"
              style={{
                borderLeft: '3px solid var(--color-primary)',
                backgroundColor: 'var(--color-primary)',
                borderBottom: '1px solid var(--color-border-dark)',
              }}
            >
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-base text-white">
                  auto_awesome
                </span>
                <span className="text-sm font-semibold text-white">
                  Workflow Recipes
                </span>
                <span className="text-xs text-white/80">
                  ({recipes.length})
                </span>
                <span className="inline-flex items-center px-1.5 py-0.5 text-[9px] font-bold bg-white/20 text-white rounded uppercase">
                  Experimental
                </span>
              </div>
              {expandedCategories.has('workflow-recipes') ? (
                <ChevronDown className="w-4 h-4 text-white" />
              ) : (
                <ChevronRight className="w-4 h-4 text-white" />
              )}
            </button>

            {/* Recipes List */}
            {expandedCategories.has('workflow-recipes') && (
              <div className="bg-gray-50 dark:bg-background-dark divide-y divide-gray-200 dark:divide-border-dark p-2">
                {recipes.map(recipe => (
                  <button
                    key={recipe.recipe_id}
                    onClick={() => handleRecipeClick(recipe)}
                    className={`w-full px-4 py-3 text-left transition-all duration-200 border rounded-xl mb-2 ${
                      selectedRecipe?.recipe_id === recipe.recipe_id
                        ? 'bg-white dark:bg-gray-800 border-primary shadow-sm ring-1 ring-primary/20'
                        : 'bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800 hover:border-primary/50 hover:shadow-md'
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <span className="material-symbols-outlined text-primary text-lg mt-0.5">
                        {recipe.icon}
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <p className="text-sm font-medium" style={{ color: 'var(--color-text-primary, #1a1a1a)' }}>
                            {recipe.name}
                          </p>
                          <span className="inline-flex items-center px-1.5 py-0.5 text-[10px] font-medium bg-primary/10 text-primary rounded">
                            {recipe.node_count} nodes
                          </span>
                        </div>
                        <p className="text-xs line-clamp-2" style={{ color: 'var(--color-text-muted, #6b7280)' }}>
                          {recipe.description}
                        </p>
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {filteredCategories.map(category => (
          <div key={category.id} className="border-b border-gray-200 dark:border-border-dark">
            {/* Category Header */}
            <button
              onClick={() => toggleCategory(category.id)}
              className="w-full flex items-center justify-between px-3 py-2 transition-colors hover:opacity-90"
              style={{
                borderLeft: `3px solid var(--color-primary)`,
                backgroundColor: 'var(--color-primary)',
                borderBottom: '1px solid var(--color-border-dark)',
              }}
            >
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-base text-white">
                  {category.icon}
                </span>
                <span className="text-sm font-semibold text-white">
                  {category.name}
                </span>
                <span className="text-xs text-white/80">
                  ({category.agents.length})
                </span>
              </div>
              {expandedCategories.has(category.id) ? (
                <ChevronDown className="w-4 h-4 text-white" />
              ) : (
                <ChevronRight className="w-4 h-4 text-white" />
              )}
            </button>

            {/* Agents List */}
            {expandedCategories.has(category.id) && (
              <div className="bg-gray-50 dark:bg-background-dark divide-y divide-gray-200 dark:divide-border-dark">
                {category.agents.map(agent => (
                  <button
                    key={agent.id}
                    onClick={() => handleAgentClick(agent)}
                    className={`w-full px-4 py-3 text-left transition-all duration-200 border rounded-xl mb-2 ${selectedAgent?.id === agent.id
                      ? 'bg-white dark:bg-gray-800 border-primary shadow-sm ring-1 ring-primary/20'
                      : 'bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800 hover:border-primary/50 hover:shadow-md'
                      }`}
                  >
                    <div className="flex items-start gap-3">
                      <span className="material-symbols-outlined text-primary text-lg mt-0.5">
                        {agent.icon}
                      </span>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary, #1a1a1a)' }}>
                          {agent.name}
                        </p>
                        <p className="text-xs line-clamp-2" style={{ color: 'var(--color-text-muted, #6b7280)' }}>
                          {agent.description}
                        </p>
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}

        {filteredCategories.length === 0 && (
          <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
            <span className="material-symbols-outlined text-4xl mb-2" style={{ color: 'var(--color-text-muted, #6b7280)' }}>
              search_off
            </span>
            <p className="text-sm" style={{ color: 'var(--color-text-muted, #6b7280)' }}>
              No agents found matching "{searchQuery}"
            </p>
          </div>
        )}
      </div>

      {/* Footer with Stats and Create Button */}
      <div className="p-4 border-t border-gray-200 dark:border-border-dark bg-gray-50 dark:bg-background-dark">
        {loading && (
          <div className="text-center text-sm mb-3" style={{ color: 'var(--color-text-muted, #6b7280)' }}>
            Loading agents...
          </div>
        )}
        {error && (
          <div className="text-center text-sm text-red-500 mb-3">
            {error}
          </div>
        )}
        <button
          onClick={() => setShowTypeSelector(true)}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-primary text-white rounded-lg hover:opacity-90 transition-opacity mb-3"
        >
          <Plus className="w-4 h-4" />
          Create Custom Agent
        </button>
        <div className="flex items-center justify-between text-xs" style={{ color: 'var(--color-text-muted, #6b7280)' }}>
          <span>{categories.reduce((sum, cat) => sum + cat.agents.length, 0)} Total Agents</span>
          <span>{categories.length} Categories</span>
        </div>
      </div>

      {/* Agent Detail Panel (Slide-over) */}
      {selectedAgent && (
        <div className="absolute inset-0 z-50 flex flex-col bg-white dark:bg-panel-dark border-l border-gray-200 dark:border-border-dark">
          {/* Detail Header */}
          <div className="p-4 border-b border-gray-200 dark:border-border-dark flex items-center justify-between">
            <h3 className="text-lg font-semibold" style={{ color: 'var(--color-text-primary, #1a1a1a)' }}>
              Agent Details
            </h3>
            <button
              onClick={() => setSelectedAgent(null)}
              className="p-1 hover:bg-gray-100 dark:hover:bg-background-dark rounded transition-colors"
            >
              <X className="w-5 h-5" style={{ color: 'var(--color-text-muted, #6b7280)' }} />
            </button>
          </div>

          {/* Detail Content */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-white dark:bg-panel-dark">
            {/* Icon & Name */}
            <div className="flex items-start gap-3">
              <div className="w-12 h-12 rounded-lg bg-gray-100 dark:bg-background-dark border border-gray-200 dark:border-border-dark flex items-center justify-center flex-shrink-0">
                <span className="material-symbols-outlined text-primary" style={{ fontSize: '24px' }}>
                  {selectedAgent.icon}
                </span>
              </div>
              <div className="flex-1">
                <h4 className="text-base font-semibold mb-1" style={{ color: 'var(--color-text-primary, #1a1a1a)' }}>
                  {selectedAgent.name}
                </h4>
                <p className="text-sm" style={{ color: 'var(--color-text-muted, #6b7280)' }}>
                  {selectedAgent.description}
                </p>
              </div>
            </div>

            {/* Configuration */}
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium mb-2 uppercase" style={{ color: 'var(--color-text-primary, #1a1a1a)' }}>Model</label>
                <p className="text-sm mt-0.5" style={{ color: 'var(--color-text-primary, #1a1a1a)' }}>{getModelDisplayName(selectedAgent.model)}</p>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium mb-2 uppercase" style={{ color: 'var(--color-text-primary, #1a1a1a)' }}>Temperature</label>
                  <p className="text-sm mt-0.5" style={{ color: 'var(--color-text-primary, #1a1a1a)' }}>{selectedAgent.temperature}</p>
                </div>
                <div>
                  <label className="block text-xs font-medium mb-2 uppercase" style={{ color: 'var(--color-text-primary, #1a1a1a)' }}>Timeout</label>
                  <p className="text-sm mt-0.5" style={{ color: 'var(--color-text-primary, #1a1a1a)' }}>{selectedAgent.timeout_seconds}s</p>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium mb-2 uppercase" style={{ color: 'var(--color-text-primary, #1a1a1a)' }}>Tools</label>
                <div className="flex flex-wrap gap-1 mt-1">
                  {selectedAgent.native_tools.map(tool => (
                    <span
                      key={tool}
                      className="inline-block px-2 py-0.5 text-xs font-medium rounded"
                      style={{ backgroundColor: 'var(--color-background-dark, #f3f4f6)', color: 'var(--color-text-muted, #6b7280)' }}
                    >
                      {tool}
                    </span>
                  ))}
                </div>
              </div>

              {selectedAgent.tags && selectedAgent.tags.length > 0 && (
                <div>
                  <label className="block text-xs font-medium mb-2 uppercase" style={{ color: 'var(--color-text-primary, #1a1a1a)' }}>Tags</label>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {selectedAgent.tags.map(tag => (
                      <span
                        key={tag}
                        className="inline-block px-2 py-0.5 text-xs font-medium bg-gray-100 dark:bg-background-dark text-primary rounded border border-gray-200 dark:border-border-dark"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <div>
                <label className="block text-xs font-medium mb-2 uppercase" style={{ color: 'var(--color-text-primary, #1a1a1a)' }}>Features</label>
                <div className="mt-1 space-y-1">
                  {selectedAgent.enable_model_routing && (
                    <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--color-text-muted, #6b7280)' }}>
                      <span className="material-symbols-outlined text-green-500" style={{ fontSize: '16px' }}>check_circle</span>
                      Model Routing
                    </div>
                  )}
                  {selectedAgent.enable_parallel_tools && (
                    <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--color-text-muted, #6b7280)' }}>
                      <span className="material-symbols-outlined text-green-500" style={{ fontSize: '16px' }}>check_circle</span>
                      Parallel Tools
                    </div>
                  )}
                  {selectedAgent.enable_memory && (
                    <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--color-text-muted, #6b7280)' }}>
                      <span className="material-symbols-outlined text-green-500" style={{ fontSize: '16px' }}>check_circle</span>
                      Memory Enabled
                    </div>
                  )}
                  {selectedAgent.requires_human_approval && (
                    <div className="flex items-center gap-2 text-xs text-orange-600 dark:text-orange-400">
                      <span className="material-symbols-outlined" style={{ fontSize: '16px' }}>warning</span>
                      Requires Human Approval
                    </div>
                  )}
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium mb-2 uppercase" style={{ color: 'var(--color-text-primary, #1a1a1a)' }}>System Prompt</label>
                <div className="mt-1 p-3 bg-gray-50 dark:bg-background-dark rounded-lg border border-gray-200 dark:border-border-dark">
                  <pre className="text-xs whitespace-pre-wrap font-mono" style={{ color: 'var(--color-text-primary, #1a1a1a)' }}>
                    {selectedAgent.system_prompt}
                  </pre>
                </div>
              </div>
            </div>
          </div>

          {/* Detail Footer - Add Button */}
          <div className="p-4 border-t border-gray-200 dark:border-border-dark bg-gray-50 dark:bg-background-dark">
            <button
              onClick={handleAddToWorkflow}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-primary rounded-lg hover:opacity-90 transition-opacity font-medium text-white"
            >
              <Plus className="w-4 h-4" />
              Add to Workflow
            </button>
          </div>
        </div>
      )}

      {/* Recipe Detail Panel (Slide-over) */}
      {selectedRecipe && (
        <div className="absolute inset-0 z-50 flex flex-col bg-white dark:bg-panel-dark border-l border-gray-200 dark:border-border-dark">
          {/* Detail Header */}
          <div className="p-4 border-b border-gray-200 dark:border-border-dark flex items-center justify-between" style={{ backgroundColor: 'var(--color-primary)' }}>
            <div className="flex items-center gap-2">
              <h3 className="text-lg font-semibold text-white">
                Workflow Recipe
              </h3>
              <span className="inline-flex items-center px-1.5 py-0.5 text-[9px] font-bold bg-white/20 text-white rounded uppercase">
                Experimental
              </span>
            </div>
            <button
              onClick={() => setSelectedRecipe(null)}
              className="p-1 hover:bg-white/20 rounded transition-colors"
            >
              <X className="w-5 h-5 text-white" />
            </button>
          </div>

          {/* Detail Content */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-white dark:bg-panel-dark">
            {/* Icon & Name */}
            <div className="flex items-start gap-3">
              <div className="w-12 h-12 rounded-lg bg-gray-100 dark:bg-background-dark border border-gray-200 dark:border-border-dark flex items-center justify-center flex-shrink-0">
                <span className="material-symbols-outlined text-primary" style={{ fontSize: '24px' }}>
                  {selectedRecipe.icon}
                </span>
              </div>
              <div className="flex-1">
                <h4 className="text-base font-semibold mb-1" style={{ color: 'var(--color-text-primary, #1a1a1a)' }}>
                  {selectedRecipe.name}
                </h4>
                <p className="text-sm" style={{ color: 'var(--color-text-muted, #6b7280)' }}>
                  {selectedRecipe.description}
                </p>
              </div>
            </div>

            {/* Recipe Stats */}
            <div className="grid grid-cols-2 gap-3">
              <div className="p-3 rounded-lg bg-primary/5 dark:bg-primary/10 border border-primary/20">
                <div className="flex items-center gap-2 mb-1">
                  <span className="material-symbols-outlined text-primary" style={{ fontSize: '18px' }}>account_tree</span>
                  <span className="text-xs font-medium" style={{ color: 'var(--color-text-muted, #6b7280)' }}>NODES</span>
                </div>
                <p className="text-2xl font-bold text-primary">{selectedRecipe.node_count}</p>
              </div>
              <div className="p-3 rounded-lg bg-primary/5 dark:bg-primary/10 border border-primary/20">
                <div className="flex items-center gap-2 mb-1">
                  <span className="material-symbols-outlined text-primary" style={{ fontSize: '18px' }}>arrow_forward</span>
                  <span className="text-xs font-medium" style={{ color: 'var(--color-text-muted, #6b7280)' }}>EDGES</span>
                </div>
                <p className="text-2xl font-bold text-primary">{selectedRecipe.edge_count}</p>
              </div>
            </div>

            {/* Tags */}
            {selectedRecipe.tags && selectedRecipe.tags.length > 0 && (
              <div>
                <label className="block text-xs font-medium mb-2 uppercase" style={{ color: 'var(--color-text-primary, #1a1a1a)' }}>Tags</label>
                <div className="flex flex-wrap gap-1 mt-1">
                  {selectedRecipe.tags.map(tag => (
                    <span
                      key={tag}
                      className="inline-block px-2 py-0.5 text-xs font-medium bg-gray-100 dark:bg-background-dark text-primary rounded border border-gray-200 dark:border-border-dark"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Nodes Preview */}
            <div>
              <label className="block text-xs font-medium mb-2 uppercase" style={{ color: 'var(--color-text-primary, #1a1a1a)' }}>Included Agents</label>
              <div className="space-y-2">
                {selectedRecipe.nodes.map((node: any) => (
                  <div
                    key={node.id}
                    className="flex items-center gap-2 p-2 rounded-lg bg-gray-50 dark:bg-background-dark border border-gray-200 dark:border-border-dark"
                  >
                    <span className="material-symbols-outlined text-sm text-primary">smart_toy</span>
                    <span className="text-sm font-medium" style={{ color: 'var(--color-text-primary, #1a1a1a)' }}>
                      {node.data?.label || node.id}
                    </span>
                    {node.data?.config?.native_tools?.length > 0 && (
                      <span className="text-xs px-1.5 py-0.5 rounded bg-primary/10 text-primary">
                        {node.data.config.native_tools.length} tools
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Info Box */}
            <div className="p-3 rounded-lg bg-primary/5 dark:bg-primary/10 border border-primary/20">
              <div className="flex items-start gap-2">
                <span className="material-symbols-outlined text-primary" style={{ fontSize: '18px' }}>science</span>
                <div>
                  <p className="text-xs font-medium text-primary mb-1">Experimental Feature</p>
                  <p className="text-xs" style={{ color: 'var(--color-text-muted, #6b7280)' }}>
                    This will insert all {selectedRecipe.node_count} nodes and their connections to your canvas. 
                    You can customize each node individually after insertion.
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Detail Footer - Insert Button */}
          <div className="p-4 border-t border-gray-200 dark:border-border-dark bg-gray-50 dark:bg-background-dark">
            <button
              onClick={handleInsertRecipe}
              disabled={!onSelectRecipe}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-primary rounded-lg hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-opacity font-medium text-white"
            >
              <Plus className="w-4 h-4" />
              Insert Recipe ({selectedRecipe.node_count} nodes)
            </button>
          </div>
        </div>
      )}

      {/* Agent Type Selector Modal */}
      {showTypeSelector && (
        <div className="fixed inset-0 flex items-center justify-center z-[60] p-4" style={{ backgroundColor: 'rgba(0, 0, 0, 0.7)' }}>
          <div className="border border-gray-200 dark:border-border-dark rounded-xl w-full max-w-2xl shadow-2xl" style={{ backgroundColor: 'var(--color-panel-dark)' }}>

            {/* Header */}
            <div className="p-6 border-b border-gray-200 dark:border-gray-800">
              <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">Choose Agent Type</h2>
              <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                Select the type of agent you want to create
              </p>
            </div>

            {/* Content */}
            <div className="p-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Regular Agent Card */}
                <button
                  onClick={() => {
                    setAgentType('regular');
                    setShowTypeSelector(false);
                    setShowAgentBuilder(true);
                  }}
                  className="p-4 border-2 border-gray-200 dark:border-gray-700 rounded-lg hover:border-primary dark:hover:border-blue-500 hover:bg-gray-50 dark:hover:bg-blue-600/20 transition-all text-left"
                >
                  <div className="flex items-center gap-3 mb-3">
                    <div className="p-2 bg-blue-100 dark:bg-blue-600/20 rounded-lg">
                      <span className="material-symbols-outlined text-blue-600 dark:text-blue-400 text-xl">terminal</span>
                    </div>
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Regular Agent</h3>
                  </div>
                  <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                    Standard LangChain agent with tool calling and execution control
                  </p>
                  <ul className="text-xs text-gray-500 dark:text-gray-400 space-y-1">
                    <li>• Model selection & temperature</li>
                    <li>• System prompt customization</li>
                    <li>• Tool selection (MCP tools)</li>
                    <li>• Execution controls (max iterations, error handling)</li>
                    <li>• Simple memory (buffer, summary)</li>
                    <li>• Verbose logging & debugging</li>
                  </ul>
                </button>

                {/* Deep Agent Card */}
                <button
                  onClick={() => {
                    setAgentType('deep');
                    setShowTypeSelector(false);
                    setShowAgentBuilder(true);
                  }}
                  className="p-4 border-2 border-gray-200 dark:border-gray-700 rounded-lg hover:border-primary dark:hover:border-purple-500 hover:bg-gray-50 dark:hover:bg-purple-600/20 transition-all text-left"
                >
                  <div className="flex items-center gap-3 mb-3">
                    <div className="p-2 bg-purple-100 dark:bg-purple-600/20 rounded-lg">
                      <span className="material-symbols-outlined text-purple-600 dark:text-purple-400 text-xl">psychology</span>
                    </div>
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Deep Agent</h3>
                  </div>
                  <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                    Advanced agent with planning, subagents, and middleware
                  </p>
                  <ul className="text-xs text-gray-500 dark:text-gray-400 space-y-1">
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
            <div className="flex items-center justify-end gap-3 p-6 border-t border-gray-200 dark:border-gray-800">
              <button
                onClick={() => setShowTypeSelector(false)}
                className="px-4 py-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors"
              >
                Cancel
              </button>
            </div>

          </div>
        </div>
      )}

      {/* Agent Builder Modal */}
      {showAgentBuilder && (
        <div className="fixed inset-0 flex items-center justify-center z-[60] p-4" style={{ backgroundColor: 'rgba(0, 0, 0, 0.7)' }}>
          <div className="border border-gray-200 dark:border-border-dark rounded-xl w-full max-w-6xl h-[90vh] shadow-2xl flex flex-col" style={{ backgroundColor: 'var(--color-panel-dark)' }}>
            <DeepAgentBuilder
              initialConfig={undefined}
              agentType={agentType}
              onSave={handleSaveNewAgent}
              onClose={() => setShowAgentBuilder(false)}
              onBack={() => {
                setShowAgentBuilder(false);
                setShowTypeSelector(true);
              }}
            />
          </div>
        </div>
      )}

      {/* Post-Creation Prompt Modal */}
      {newlyCreatedAgent && (
        <div className="fixed inset-0 flex items-center justify-center z-[60] p-4" style={{ backgroundColor: 'rgba(0, 0, 0, 0.7)' }}>
          <div className="border border-gray-200 dark:border-border-dark rounded-xl w-full max-w-md shadow-2xl" style={{ backgroundColor: 'var(--color-panel-dark)' }}>

            {/* Header */}
            <div className="p-6 border-b border-gray-200 dark:border-gray-800">
              <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Agent Created!</h2>
              <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                {newlyCreatedAgent.name} has been saved successfully
              </p>
            </div>

            {/* Content */}
            <div className="p-6">
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                Would you like to add this agent to your workflow now?
              </p>
            </div>

            {/* Footer */}
            <div className="flex items-center justify-end gap-3 p-6 border-t border-gray-200 dark:border-gray-800">
              <button
                onClick={() => setNewlyCreatedAgent(null)}
                className="px-4 py-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors"
              >
                No, Just Save
              </button>
              <button
                onClick={handleAddNewAgentToWorkflow}
                className="px-4 py-2 bg-primary text-white rounded-lg hover:opacity-90 transition-opacity"
              >
                Yes, Add to Workflow
              </button>
            </div>

          </div>
        </div>
      )}

      {/* Notification Modal */}
      <NotificationModal />
    </aside>
  );
}
