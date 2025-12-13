/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useCallback, useEffect, useMemo } from 'react';
import { Node, Edge } from 'reactflow';
import apiClient from '@/lib/api-client';

interface UseWorkflowManagementOptions {
  workflowId?: number;
  nodes: Node[];
  edges: Edge[];
  setNodes: (nodes: Node[] | ((nodes: Node[]) => Node[])) => void;
  setEdges: (edges: Edge[] | ((edges: Edge[]) => Edge[])) => void;
  setNodeIdCounter: (counter: number | ((prev: number) => number)) => void;
  showSuccess: (message: string) => void;
  showWarning: (message: string) => void;
  logError: (title: string, detail?: string) => void;
}

export function useWorkflowManagement({
  workflowId,
  nodes,
  edges,
  setNodes,
  setEdges,
  setNodeIdCounter,
  showSuccess,
  showWarning,
  logError,
}: UseWorkflowManagementOptions) {
  // Core workflow identity state
  const [currentWorkflowId, setCurrentWorkflowId] = useState<number | null>(workflowId || null);
  const [workflowName, setWorkflowName] = useState('Untitled Workflow');
  const [editedName, setEditedName] = useState('Untitled Workflow');

  // Available workflows for switching
  const [availableWorkflows, setAvailableWorkflows] = useState<any[]>([]);
  const [workflowSearchQuery, setWorkflowSearchQuery] = useState('');

  // Save workflow modal state
  const [showSaveModal, setShowSaveModal] = useState(false);
  const [saveWorkflowName, setSaveWorkflowName] = useState('');

  // Create workflow modal state
  const [showCreateWorkflowModal, setShowCreateWorkflowModal] = useState(false);
  const [newWorkflowName, setNewWorkflowName] = useState('');

  // Filtered workflows based on search
  const filteredWorkflows = useMemo(() => {
    if (!workflowSearchQuery.trim()) return availableWorkflows;
    const query = workflowSearchQuery.toLowerCase();
    return availableWorkflows.filter(w =>
      w.name?.toLowerCase().includes(query)
    );
  }, [availableWorkflows, workflowSearchQuery]);

  // Fetch available workflows
  const fetchWorkflows = useCallback(async () => {
    try {
      const response = await apiClient.listWorkflows();
      setAvailableWorkflows(response.data);
    } catch (error) {
      console.error('Failed to fetch workflows:', error);
    }
  }, []);

  // Load workflows on mount
  useEffect(() => {
    fetchWorkflows();
  }, [fetchWorkflows]);

  // Switch to a different workflow
  const handleWorkflowSwitch = useCallback(async (targetWorkflowId: number) => {
    try {
      const response = await apiClient.getWorkflow(targetWorkflowId);
      const workflow = response.data;

      // Clear search and close dropdown
      setWorkflowSearchQuery('');

      // Update workflow identity
      setCurrentWorkflowId(targetWorkflowId);
      setWorkflowName(workflow.name || 'Untitled Workflow');
      setEditedName(workflow.name || 'Untitled Workflow');

      // Load workflow configuration
      if (workflow.configuration) {
        const config = workflow.configuration;

        if (config.nodes && Array.isArray(config.nodes)) {
          const restoredNodes = config.nodes.map((n: any, index: number) => {
            // Validate position to prevent NaN coordinates
            let validPosition = { x: 250 + (index * 200), y: 250 };
            if (n.position && typeof n.position.x === 'number' && typeof n.position.y === 'number') {
              if (!isNaN(n.position.x) && !isNaN(n.position.y)) {
                validPosition = { x: n.position.x, y: n.position.y };
              }
            }

            return {
              id: n.id,
              type: 'custom',
              position: validPosition,
              data: n.data || {
                label: n.type,
                agentType: n.type,
                config: n.config || {}
              }
            };
          });
          setNodes(restoredNodes);

          // Update node ID counter to prevent collisions
          const maxId = Math.max(...restoredNodes.map((n: Node) => {
            const match = n.id.match(/node-(\d+)/);
            return match ? parseInt(match[1], 10) : 0;
          }), 0);
          setNodeIdCounter(maxId + 1);
        }

        if (config.edges && Array.isArray(config.edges)) {
          const restoredEdges = config.edges.map((e: any) => ({
            id: `e${e.source}-${e.target}`,
            source: e.source,
            target: e.target,
            type: 'smoothstep',
            animated: true
          }));
          setEdges(restoredEdges);
        }
      }

      showSuccess(`Loaded workflow: ${workflow.name}`);
    } catch (error: any) {
      console.error('Failed to load workflow:', error);
      logError('Failed to load workflow', error.response?.data?.detail || error.message);
    }
  }, [setNodes, setEdges, setNodeIdCounter, showSuccess, logError]);

  // Save workflow confirmation (for new workflows)
  const handleSaveWorkflowConfirm = useCallback(async () => {
    if (!saveWorkflowName.trim()) {
      showWarning('Please enter a workflow name');
      return;
    }

    try {
      const configuration = {
        nodes: nodes.map(n => {
          const nativeTools = n.data.config?.native_tools || n.data.config?.nativeTools || [];
          return {
            id: n.id,
            type: n.data.agentType || n.data.label.toLowerCase().replace(/\s+/g, '_'),
            data: n.data,
            position: n.position,
            config: {
              model: n.data.config?.model || 'gpt-4o-mini',
              temperature: n.data.config?.temperature ?? 0.7,
              system_prompt: n.data.config?.system_prompt || '',
              tools: n.data.config?.tools || [],
              native_tools: nativeTools,
              custom_tools: n.data.config?.custom_tools || [],
              enable_memory: (n.data.config?.enable_memory ?? nativeTools.includes('enable_memory')) || false,
              enable_rag: (n.data.config?.enable_rag ?? nativeTools.includes('enable_rag')) || false
            }
          };
        }),
        edges: edges.map(e => ({
          source: e.source,
          target: e.target
        }))
      };

      const response = await apiClient.createWorkflow({
        name: saveWorkflowName,
        configuration
      });

      setCurrentWorkflowId(response.data.id);
      setWorkflowName(saveWorkflowName);
      setShowSaveModal(false);
      setSaveWorkflowName('');

      showSuccess('Workflow saved successfully!');
    } catch (error: any) {
      console.error('Failed to save workflow:', error);
      logError('Failed to save workflow', error.response?.data?.detail || error.message);
    }
  }, [saveWorkflowName, nodes, edges, showSuccess, showWarning, logError]);

  // Create new workflow
  const handleCreateNewWorkflow = useCallback(async () => {
    if (!newWorkflowName.trim()) {
      showWarning('Please enter a workflow name');
      return;
    }

    try {
      // Create empty workflow
      const response = await apiClient.createWorkflow({
        name: newWorkflowName.trim(),
        configuration: { nodes: [], edges: [] }
      });

      // Switch to new workflow
      setCurrentWorkflowId(response.data.id);
      setWorkflowName(response.data.name);
      setEditedName(response.data.name);

      // Clear canvas
      setNodes([]);
      setEdges([]);
      setNodeIdCounter(1);

      // Refresh workflow list
      fetchWorkflows();

      // Close modal and reset
      setShowCreateWorkflowModal(false);
      setNewWorkflowName('');
      showSuccess(`Created workflow "${response.data.name}"`);
    } catch (error: any) {
      console.error('Failed to create workflow:', error);
      showWarning(`Failed to create workflow: ${error.response?.data?.detail || error.message || 'Unknown error'}`);
    }
  }, [newWorkflowName, setNodes, setEdges, setNodeIdCounter, fetchWorkflows, showSuccess, showWarning]);

  // Clear canvas
  const handleClear = useCallback(() => {
    const confirmed = confirm('Are you sure you want to clear the entire workflow? This cannot be undone.');
    if (!confirmed) return;

    setNodes([]);
    setEdges([]);
    setNodeIdCounter(1);
    localStorage.removeItem('langconfig-workflow');
  }, [setNodes, setEdges, setNodeIdCounter]);

  // Open save modal
  const openSaveModal = useCallback(() => {
    setShowSaveModal(true);
  }, []);

  // Close save modal
  const closeSaveModal = useCallback(() => {
    setShowSaveModal(false);
    setSaveWorkflowName('');
  }, []);

  // Open create workflow modal
  const openCreateWorkflowModal = useCallback(() => {
    setShowCreateWorkflowModal(true);
  }, []);

  // Close create workflow modal
  const closeCreateWorkflowModal = useCallback(() => {
    setShowCreateWorkflowModal(false);
    setNewWorkflowName('');
  }, []);

  return {
    // Core workflow identity
    currentWorkflowId,
    setCurrentWorkflowId,
    workflowName,
    setWorkflowName,
    editedName,
    setEditedName,

    // Workflow list
    availableWorkflows,
    filteredWorkflows,
    workflowSearchQuery,
    setWorkflowSearchQuery,
    fetchWorkflows,

    // Save modal
    showSaveModal,
    saveWorkflowName,
    setSaveWorkflowName,
    openSaveModal,
    closeSaveModal,
    handleSaveWorkflowConfirm,

    // Create modal
    showCreateWorkflowModal,
    newWorkflowName,
    setNewWorkflowName,
    openCreateWorkflowModal,
    closeCreateWorkflowModal,
    handleCreateNewWorkflow,

    // Actions
    handleWorkflowSwitch,
    handleClear,
  };
}
