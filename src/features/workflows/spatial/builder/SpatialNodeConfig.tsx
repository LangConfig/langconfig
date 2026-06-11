/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * SpatialNodeConfig — right-side DOM overlay that REUSES the 2D
 * NodeConfigPanel for the node selected in the 3D scene.
 *
 * The selectedNode mapping is a copy of the 2D path in App.tsx:
 * - handleNodeSelect (~278-312): flatten nested data.config to the top level
 *   while preserving tool arrays from both levels
 * - the NodeConfigPanel feed (~467-496): per-field fallbacks across the
 *   flattened object and the nested config
 *
 * onSave merges the panel's fullConfig back via workflowStore.updateNodeConfig
 * (parity with useNodeManagement.updateNodeConfig), which schedules the
 * debounced PUT. onDelete removes the node plus its attached edges.
 */

import { lazy, Suspense, useMemo } from 'react';
import type { WorkflowNode } from '@/types/workflow';
import { useSceneStore } from '../state/sceneStore';
import { useSpatialWorkflowStore } from '../state/workflowStore';

const NodeConfigPanel = lazy(
  () => import('@/features/workflows/node-config/NodeConfigPanel')
);

/** Copy of the App.tsx flatten/normalize + panel-feed mapping (2D parity). */
function buildPanelNode(node: WorkflowNode) {
  const nodeData = (node.data ?? {}) as Record<string, any>;

  // Normalize data structure: flatten nested config if it exists
  // (NodeConfigPanel expects model, system_prompt, etc. at the top level).
  let d: Record<string, any>;
  if (nodeData.config && typeof nodeData.config === 'object') {
    d = {
      id: node.id,
      ...nodeData,
      ...nodeData.config, // Spread config fields to top level
      // Preserve arrays from both levels
      tools: nodeData.config.tools || nodeData.tools || [],
      native_tools:
        nodeData.config.native_tools || nodeData.config.mcp_tools || nodeData.native_tools || [],
      custom_tools: nodeData.config.custom_tools || nodeData.custom_tools || [],
    };
  } else {
    d = {
      id: node.id,
      ...nodeData,
      tools: nodeData.tools || [],
      native_tools: nodeData.native_tools || [],
      custom_tools: nodeData.custom_tools || [],
    };
  }

  return {
    id: node.id,
    name: d.label || d.name || d.config?.name || node.id,
    agentType: d.agentType,
    model: d.model || d.config?.model,
    system_prompt: d.system_prompt || d.config?.system_prompt || '',
    temperature: d.temperature ?? d.config?.temperature ?? 0.7,
    max_tokens: d.max_tokens || d.config?.max_tokens || 4000,
    max_retries: d.max_retries || d.config?.max_retries || 3,
    recursion_limit: d.recursion_limit || d.config?.recursion_limit || 300,
    tools: d.tools || d.config?.tools || [],
    native_tools: d.native_tools || d.config?.native_tools || [],
    custom_tools: d.custom_tools || d.config?.custom_tools || [],
    middleware: d.middleware || d.config?.middleware || [],
    condition: d.condition || d.config?.condition,
    max_iterations: d.max_iterations || d.config?.max_iterations,
    exit_condition: d.exit_condition || d.config?.exit_condition,
    // DeepAgent subagents
    subagents: d.subagents || d.config?.subagents || [],
    use_deepagents: d.use_deepagents || d.config?.use_deepagents || false,
    // Tool node configuration
    tool_type: d.tool_type || d.config?.tool_type,
    tool_id: d.tool_id || d.config?.tool_id,
    tool_params: d.tool_params || d.config?.tool_params,
  };
}

export default function SpatialNodeConfig() {
  const selection = useSceneStore((s) => s.selection);
  const clearSelection = useSceneStore((s) => s.clearSelection);
  const nodeId = selection?.kind === 'node' ? selection.id : null;

  const node = useSpatialWorkflowStore((s) =>
    nodeId ? s.nodes.find((n) => n.id === nodeId) ?? null : null
  );
  const updateNodeConfig = useSpatialWorkflowStore((s) => s.updateNodeConfig);
  const removeNode = useSpatialWorkflowStore((s) => s.removeNode);

  const selectedNode = useMemo(() => (node ? buildPanelNode(node) : null), [node]);

  if (!nodeId || !selectedNode) return null;

  return (
    <div className="absolute bottom-0 right-0 top-0 z-50 flex">
      <Suspense fallback={null}>
        <NodeConfigPanel
          selectedNode={selectedNode as any}
          onClose={clearSelection}
          onSave={(id: string, fullConfig: any) => updateNodeConfig(id, fullConfig)}
          onDelete={(id: string) => {
            removeNode(id);
            clearSelection();
          }}
        />
      </Suspense>
    </div>
  );
}
