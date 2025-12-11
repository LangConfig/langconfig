/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useCallback } from 'react';
import { Node, Edge } from 'reactflow';

interface NodeTokenCost {
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
  costString: string;
}

interface UseNodeManagementOptions {
  setNodes: React.Dispatch<React.SetStateAction<Node[]>>;
  setEdges: React.Dispatch<React.SetStateAction<Edge[]>>;
  setNodeTokenCosts: React.Dispatch<React.SetStateAction<Record<string, NodeTokenCost>>>;
  onNodeSelect?: (nodeId: string, nodeData: any) => void;
  onNodeDelete?: (nodeId: string) => void;
}

interface UseNodeManagementReturn {
  handleNodeClick: (event: React.MouseEvent, node: Node) => void;
  handleNodeDelete: (nodeId: string) => void;
  updateNodeConfig: (nodeId: string, newConfig: any) => void;
}

/**
 * Hook for managing node operations (click, delete, config updates)
 */
export function useNodeManagement({
  setNodes,
  setEdges,
  setNodeTokenCosts,
  onNodeSelect,
  onNodeDelete,
}: UseNodeManagementOptions): UseNodeManagementReturn {
  // Handle node selection
  const handleNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      if (onNodeSelect) {
        onNodeSelect(node.id, node.data);
      }
    },
    [onNodeSelect]
  );

  // Handle node deletion
  const handleNodeDelete = useCallback((nodeId: string) => {
    setNodes((nds) => nds.filter((node) => node.id !== nodeId));
    setEdges((eds) => eds.filter((edge) => edge.source !== nodeId && edge.target !== nodeId));

    // Notify parent if callback provided
    if (onNodeDelete) {
      onNodeDelete(nodeId);
    }
  }, [onNodeDelete, setNodes, setEdges]);

  // Update node config function
  const updateNodeConfig = useCallback((nodeId: string, newConfig: any) => {
    console.log(`[useNodeManagement] updateNodeConfig called for node ${nodeId}:`, {
      native_tools: newConfig.native_tools,
      custom_tools: newConfig.custom_tools
    });

    setNodes((nds) =>
      nds.map((node) => {
        if (node.id === nodeId) {
          const oldLabel = node.data.label;
          const newLabel = newConfig.label || newConfig.name || oldLabel;

          // If label changed, transfer token costs to new label
          if (newLabel !== oldLabel && oldLabel) {
            setNodeTokenCosts(prev => {
              const tokenCost = prev[oldLabel];
              if (tokenCost) {
                const updated = { ...prev };
                delete updated[oldLabel];
                updated[newLabel] = tokenCost;
                return updated;
              }
              return prev;
            });
          }

          // Create a completely new node object to force React Flow to detect the change
          return {
            ...node,
            // Force re-render by creating new data object
            data: {
              ...node.data,
              label: newLabel,
              agentType: newConfig.agentType || node.data.agentType,
              model: newConfig.model || node.data.model,
              config: {
                ...node.data.config,
                ...newConfig,
                model: newConfig.model || node.data.config?.model,
                temperature: newConfig.temperature !== undefined ? newConfig.temperature : node.data.config?.temperature,
                max_tokens: newConfig.max_tokens !== undefined ? newConfig.max_tokens : node.data.config?.max_tokens,
                max_retries: newConfig.max_retries !== undefined ? newConfig.max_retries : node.data.config?.max_retries,
                recursion_limit: newConfig.recursion_limit !== undefined ? newConfig.recursion_limit : node.data.config?.recursion_limit,
                system_prompt: newConfig.system_prompt !== undefined ? newConfig.system_prompt : node.data.config?.system_prompt,
                native_tools: newConfig.native_tools !== undefined ? newConfig.native_tools : node.data.config?.native_tools,
                tools: newConfig.tools !== undefined ? newConfig.tools : node.data.config?.tools,
                custom_tools: newConfig.custom_tools !== undefined ? newConfig.custom_tools : node.data.config?.custom_tools,
                enable_memory: newConfig.enable_memory !== undefined ? newConfig.enable_memory : node.data.config?.enable_memory,
                enable_rag: newConfig.enable_rag !== undefined ? newConfig.enable_rag : node.data.config?.enable_rag,
              },
              // Add a timestamp to ensure React Flow sees this as a new object
              _lastUpdated: Date.now()
            }
          };
        }
        return node;
      })
    );
  }, [setNodes, setNodeTokenCosts]);

  return {
    handleNodeClick,
    handleNodeDelete,
    updateNodeConfig,
  };
}
