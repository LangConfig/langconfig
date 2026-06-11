/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * Palette catalog — the node kinds the 3D builder can place.
 *
 * Mirrors the node types the 2D canvas supports:
 * - Control nodes copy the CONTROL_NODES defaults from
 *   src/features/agents/ui/ModernAgentLibrary.tsx (START/END/CONDITIONAL/
 *   LOOP/APPROVAL/TOOL), plus CHECKPOINT_NODE/OUTPUT_NODE which CustomNode.tsx
 *   recognizes.
 * - The generic agent copies the default config shape WorkflowCanvas.tsx
 *   builds when an agent is added (newNode data.config, ~line 1391).
 *
 * agentType doubles as the persisted `type` (useWorkflowPersistence.ts:177
 * saves `n.data.agentType || label...`), so these ids must match the 2D
 * conventions exactly.
 */

export interface SpatialNodeKind {
  /** data.agentType — also becomes the persisted node `type`. */
  agentType: string;
  /** Default data.label (and panel display name). */
  label: string;
  /** Material symbol name (matches CustomNode.tsx iconography). */
  icon: string;
  description: string;
  /** data.model for the node. */
  model: string;
  /** Fresh default data.config for a newly placed node. */
  buildConfig: () => Record<string, unknown>;
}

/** Shared shape for control-node configs (model 'none', no tools). */
function controlConfig(systemPrompt: string, extra: Record<string, unknown> = {}) {
  return {
    model: 'none',
    fallback_models: [],
    temperature: 0,
    system_prompt: systemPrompt,
    native_tools: [],
    tools: [],
    cli_tools: [],
    custom_tools: [],
    timeout_seconds: 0,
    max_retries: 0,
    enable_model_routing: false,
    enable_parallel_tools: false,
    enable_memory: false,
    enable_rag: false,
    requires_human_approval: false,
    use_deepagents: false,
    subagents: [],
    deep_agent_template_id: null,
    tool_type: null,
    tool_id: null,
    tool_params: {},
    ...extra,
  };
}

export const SPATIAL_NODE_KINDS: SpatialNodeKind[] = [
  {
    agentType: 'agent',
    label: 'Agent',
    icon: 'smart_toy',
    description: 'LLM agent node with tools and memory.',
    model: 'gpt-5.4-mini',
    buildConfig: () => ({
      model: 'gpt-5.4-mini',
      fallback_models: [],
      temperature: 0.7,
      max_tokens: 4000,
      system_prompt: '',
      native_tools: [],
      tools: [],
      cli_tools: [],
      custom_tools: [],
      timeout_seconds: 300,
      max_retries: 3,
      enable_model_routing: false,
      enable_parallel_tools: true,
      enable_memory: false,
      enable_rag: false,
      requires_human_approval: false,
      use_deepagents: false,
      subagents: [],
      deep_agent_template_id: null,
      tool_type: null,
      tool_id: null,
      tool_params: {},
    }),
  },
  {
    agentType: 'TOOL_NODE',
    label: 'Tool',
    icon: 'construction',
    description: 'Direct tool execution. Runs a single tool without an agent wrapper.',
    model: 'none',
    buildConfig: () => controlConfig('TOOL node: Direct tool execution.'),
  },
  {
    agentType: 'CONDITIONAL_NODE',
    label: 'Conditional',
    icon: 'call_split',
    description: 'Branching logic. Routes workflow based on conditions.',
    model: 'none',
    buildConfig: () =>
      controlConfig('CONDITIONAL node: Routes execution based on conditions.', {
        condition: '',
      }),
  },
  {
    agentType: 'LOOP_NODE',
    label: 'Loop',
    icon: 'sync',
    description: 'Iteration control. Repeats until a condition or max iterations.',
    model: 'none',
    buildConfig: () =>
      controlConfig('LOOP node: Repeats execution with iteration tracking.', {
        max_iterations: 10,
        exit_condition: '',
      }),
  },
  {
    agentType: 'APPROVAL_NODE',
    label: 'Human Approval',
    icon: 'how_to_reg',
    description: 'Human-in-the-loop gate. Pauses for review and approval.',
    model: 'none',
    buildConfig: () =>
      controlConfig('APPROVAL node: Pauses for human-in-the-loop approval.', {
        requires_human_approval: true,
      }),
  },
  {
    agentType: 'CHECKPOINT_NODE',
    label: 'Checkpoint',
    icon: 'bookmark',
    description: 'Marks a checkpoint in workflow execution state.',
    model: 'none',
    buildConfig: () => controlConfig('CHECKPOINT node: Marks a workflow checkpoint.'),
  },
  {
    agentType: 'OUTPUT_NODE',
    label: 'Output',
    icon: 'output',
    description: 'Collects and emits workflow output.',
    model: 'none',
    buildConfig: () => controlConfig('OUTPUT node: Emits workflow output.'),
  },
  {
    agentType: 'START_NODE',
    label: 'Start',
    icon: 'play_circle',
    description: 'Workflow entry point.',
    model: 'none',
    buildConfig: () => controlConfig('START node: Entry point for workflow execution.'),
  },
  {
    agentType: 'END_NODE',
    label: 'End',
    icon: 'stop_circle',
    description: 'Workflow exit point.',
    model: 'none',
    buildConfig: () => controlConfig('END node: Exit point for workflow execution.'),
  },
];

export function getSpatialKind(agentType: string): SpatialNodeKind | undefined {
  return SPATIAL_NODE_KINDS.find((k) => k.agentType === agentType);
}
