/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useCallback } from 'react';
import { Node } from 'reactflow';
import apiClient from '@/lib/api-client';

interface NodeData {
  label: string;
  config: {
    model?: string;
    temperature?: number;
    max_tokens?: number;
    system_prompt?: string;
    tools?: string[];
    native_tools?: string[];
    cli_tools?: string[];
    custom_tools?: any[];
    middleware?: any[];
    subagents?: any[];
    deep_agent_template_id?: number;
    deepAgentId?: number;
  };
}

interface SaveToLibraryData {
  nodeId: string;
  nodeData: NodeData;
}

interface UseSaveToLibraryOptions {
  setNodes: React.Dispatch<React.SetStateAction<Node[]>>;
  setNodeContextMenu: (menu: any) => void;
  showWarning: (message: string) => void;
  showSuccess: (message: string) => void;
  logError: (title: string, message: string) => void;
}

interface UseSaveToLibraryReturn {
  // State
  showSaveToLibraryModal: boolean;
  saveToLibraryData: SaveToLibraryData | null;
  agentLibraryName: string;
  agentLibraryDescription: string;

  // Setters for controlled inputs
  setAgentLibraryName: (name: string) => void;
  setAgentLibraryDescription: (desc: string) => void;

  // Handlers
  handleSaveToAgentLibrary: (nodeId: string, nodeData: NodeData) => void;
  handleConfirmSaveToLibrary: (saveAsCopy?: boolean) => Promise<void>;
  handleCloseSaveToLibraryModal: () => void;
}

/**
 * Hook for managing save to agent library functionality
 */
export function useSaveToLibrary({
  setNodes,
  setNodeContextMenu,
  showWarning,
  showSuccess,
  logError,
}: UseSaveToLibraryOptions): UseSaveToLibraryReturn {
  const [showSaveToLibraryModal, setShowSaveToLibraryModal] = useState(false);
  const [saveToLibraryData, setSaveToLibraryData] = useState<SaveToLibraryData | null>(null);
  const [agentLibraryName, setAgentLibraryName] = useState('');
  const [agentLibraryDescription, setAgentLibraryDescription] = useState('');

  // Handle saving node as agent template to library
  const handleSaveToAgentLibrary = useCallback((nodeId: string, nodeData: NodeData) => {
    const suggestedName = `${nodeData.label} (Copy)`;
    setAgentLibraryName(suggestedName);
    setAgentLibraryDescription('');
    setSaveToLibraryData({ nodeId, nodeData });
    setShowSaveToLibraryModal(true);
    setNodeContextMenu(null);
  }, [setNodeContextMenu]);

  const handleConfirmSaveToLibrary = useCallback(async (saveAsCopy: boolean = false) => {
    if (!saveToLibraryData || !agentLibraryName.trim()) return;

    const { nodeId, nodeData } = saveToLibraryData;

    // Check if this agent came from the library (has deep_agent_template_id)
    const existingAgentId = nodeData.config?.deep_agent_template_id;
    const shouldUpdate = existingAgentId && !saveAsCopy;

    try {
      const configPayload = {
        model: nodeData.config.model,
        temperature: nodeData.config.temperature ?? 0.7,
        max_tokens: nodeData.config.max_tokens || 4000,
        system_prompt: nodeData.config.system_prompt || '',
        tools: nodeData.config.tools || [],
        native_tools: nodeData.config.native_tools || [],
        cli_tools: nodeData.config.cli_tools || [],
        custom_tools: nodeData.config.custom_tools || [],
        middleware: nodeData.config.middleware || [],
        subagents: nodeData.config.subagents || [],
        backend: {
          type: 'state',
          config: {},
          mappings: null
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
          long_term_memory: false
        }
      };

      let savedAgentId: number;

      if (shouldUpdate) {
        // UPDATE existing agent - preserves chat context
        await apiClient.updateDeepAgent(existingAgentId, {
          name: agentLibraryName.trim(),
          description: agentLibraryDescription.trim() || 'Custom agent template',
          config: configPayload
        });
        savedAgentId = existingAgentId;

        // Show warning that this affects other workflows
        showWarning(`Agent updated. This change affects all workflows using "${agentLibraryName}".`);
      } else {
        // CREATE new agent copy
        const agentTemplate = {
          name: agentLibraryName.trim(),
          description: agentLibraryDescription.trim() || 'Custom agent template',
          category: 'workflow',
          config: configPayload
        };

        const response = await apiClient.createDeepAgent(agentTemplate);
        savedAgentId = response.data?.id;
        showSuccess(`Agent "${agentLibraryName}" saved to library!`);
      }

      // Update the node with the saved agent ID and new name
      setNodes((nds) =>
        nds.map((node) => {
          if (node.id === nodeId) {
            return {
              ...node,
              data: {
                ...node.data,
                label: agentLibraryName.trim(),
                deepAgentId: savedAgentId,
                config: {
                  ...node.data.config,
                  deepAgentId: savedAgentId,
                  deep_agent_template_id: savedAgentId,
                }
              }
            };
          }
          return node;
        })
      );

      setShowSaveToLibraryModal(false);
      setSaveToLibraryData(null);
      setAgentLibraryName('');
      setAgentLibraryDescription('');
    } catch (error: any) {
      console.error('Failed to save agent to library:', error);
      logError('Failed to save agent', error.response?.data?.detail || error.message);
    }
  }, [saveToLibraryData, agentLibraryName, agentLibraryDescription, setNodes, showWarning, showSuccess, logError]);

  const handleCloseSaveToLibraryModal = useCallback(() => {
    setShowSaveToLibraryModal(false);
    setSaveToLibraryData(null);
    setAgentLibraryName('');
    setAgentLibraryDescription('');
  }, []);

  return {
    showSaveToLibraryModal,
    saveToLibraryData,
    agentLibraryName,
    agentLibraryDescription,
    setAgentLibraryName,
    setAgentLibraryDescription,
    handleSaveToAgentLibrary,
    handleConfirmSaveToLibrary,
    handleCloseSaveToLibraryModal,
  };
}
