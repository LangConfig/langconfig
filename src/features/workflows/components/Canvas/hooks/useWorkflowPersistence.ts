/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useCallback, useEffect } from 'react';
import { Node, Edge } from 'reactflow';
import apiClient from '../../../../../lib/api-client';
import { ConflictErrorClass } from '../../../../../lib/api-client';
import { validateWorkflow } from '../../../../../lib/workflow-validator';

interface UseWorkflowPersistenceOptions {
  nodes: Node[];
  edges: Edge[];
  currentWorkflowId: number | null;
  setNodes: (nodes: Node[] | ((nodes: Node[]) => Node[])) => void;
  setEdges: (edges: Edge[] | ((edges: Edge[]) => Edge[])) => void;
  setWorkflowName: (name: string) => void;
  setEditedName: (name: string) => void;
  showSuccess: (message: string) => void;
  logError: (title: string, detail?: string) => void;
  onShowSaveModal: () => void;
}

interface ConflictData {
  localData: any;
  remoteData: any;
}

export function useWorkflowPersistence({
  nodes,
  edges,
  currentWorkflowId,
  setNodes,
  setEdges,
  setWorkflowName,
  setEditedName,
  showSuccess,
  logError,
  onShowSaveModal,
}: UseWorkflowPersistenceOptions) {
  // Optimistic locking state
  const [currentLockVersion, setCurrentLockVersion] = useState<number>(1);
  const [showConflictDialog, setShowConflictDialog] = useState(false);
  const [conflictData, setConflictData] = useState<ConflictData | null>(null);

  // Unsaved changes tracking
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [lastSavedState, setLastSavedState] = useState<string>('');

  // Helper to generate a hash of the workflow state, excluding visual properties
  const getWorkflowStateHash = useCallback((nodes: Node[], edges: Edge[]) => {
    const sanitizedNodes = nodes.map(node => ({
      id: node.id,
      type: node.type,
      data: node.data,
    }));

    const sanitizedEdges = edges.map(edge => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
    }));

    return JSON.stringify({ nodes: sanitizedNodes, edges: sanitizedEdges });
  }, []);

  // Track changes to detect unsaved changes
  useEffect(() => {
    if (nodes.length === 0 && edges.length === 0) {
      return;
    }

    const currentState = getWorkflowStateHash(nodes, edges);

    if (lastSavedState && currentState !== lastSavedState) {
      setHasUnsavedChanges(true);
    } else if (!lastSavedState) {
      setLastSavedState(currentState);
    }
  }, [nodes, edges, lastSavedState, getWorkflowStateHash]);

  // Warn user before leaving page with unsaved changes
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (hasUnsavedChanges) {
        e.preventDefault();
        e.returnValue = 'You have unsaved changes. Are you sure you want to leave?';
        return e.returnValue;
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [hasUnsavedChanges]);

  // Fetch workflow details and lock_version when workflowId changes
  useEffect(() => {
    const fetchWorkflowDetails = async () => {
      if (!currentWorkflowId) return;

      try {
        const response = await apiClient.getWorkflow(currentWorkflowId);
        const workflow = response.data;

        if (workflow.lock_version !== undefined) {
          setCurrentLockVersion(workflow.lock_version);
        }

        if (workflow.name) {
          setWorkflowName(workflow.name);
          setEditedName(workflow.name);
        }
      } catch (error) {
        console.error('Failed to fetch workflow details:', error);
      }
    };

    fetchWorkflowDetails();
  }, [currentWorkflowId, setWorkflowName, setEditedName]);

  // Main save function
  const handleSave = useCallback(async (silent: boolean = false) => {
    if (nodes.length === 0) return;

    // Validate workflow before saving
    const validation = validateWorkflow(nodes, edges);

    if (!validation.isValid) {
      if (!silent) {
        const errorMessages = validation.errors.map((e) => e.message).join('\n');
        logError('Cannot save workflow', errorMessages);
      }
      return;
    }

    // Show warnings if any (only in manual save)
    if (!silent && validation.warnings.length > 0) {
      const warningMessages = validation.warnings.map((w) => w.message).join('\n');
      const proceed = confirm(
        `Workflow has warnings:\n\n${warningMessages}\n\nDo you want to continue?`
      );
      if (!proceed) return;
    }

    // Extract configuration from nodes
    const configuration = {
      nodes: nodes.map(n => {
        const nativeTools = n.data.config?.native_tools || n.data.config?.nativeTools || [];

        const nodeConfig = {
          model: n.data.config?.model || 'gpt-4o-mini',
          temperature: n.data.config?.temperature ?? 0.7,
          system_prompt: n.data.config?.system_prompt || '',
          tools: n.data.config?.tools || [],
          native_tools: nativeTools,
          custom_tools: n.data.config?.custom_tools || [],
          enable_memory: (n.data.config?.enable_memory ?? nativeTools.includes('enable_memory')) || false,
          enable_rag: (n.data.config?.enable_rag ?? nativeTools.includes('enable_rag')) || false
        };

        return {
          id: n.id,
          type: n.data.agentType || n.data.label.toLowerCase().replace(/\s+/g, '_'),
          data: n.data,
          position: n.position,
          config: nodeConfig
        };
      }),
      edges: edges.map(e => ({
        source: e.source,
        target: e.target
      }))
    };

    try {
      if (currentWorkflowId) {
        // UPDATE existing workflow
        const response = await apiClient.updateWorkflow(currentWorkflowId, {
          configuration,
          lock_version: currentLockVersion
        });

        const updatedWorkflow = response.data;
        if (updatedWorkflow.lock_version !== undefined) {
          setCurrentLockVersion(updatedWorkflow.lock_version);
        }

        setHasUnsavedChanges(false);
        setLastSavedState(getWorkflowStateHash(nodes, edges));

        if (!silent) {
          showSuccess('Workflow saved successfully!');
        }
      } else {
        // CREATE new workflow - show modal
        if (!silent) {
          onShowSaveModal();
        }
        return;
      }
    } catch (error: any) {
      console.error('Failed to save workflow:', error);

      // Handle optimistic lock conflicts
      if (error instanceof ConflictErrorClass) {
        if (!silent) {
          try {
            const latestResponse = await apiClient.getWorkflow(currentWorkflowId!);
            const remoteWorkflow = latestResponse.data;

            setConflictData({
              localData: { configuration, lock_version: currentLockVersion },
              remoteData: remoteWorkflow
            });
            setShowConflictDialog(true);
          } catch (fetchError) {
            console.error('Failed to fetch latest version:', fetchError);
            logError('Conflict detected', 'Unable to fetch latest workflow version');
          }
        }
        return;
      }

      if (!silent) {
        logError('Save failed', 'Unable to save workflow changes');
      }
    }
  }, [nodes, edges, currentWorkflowId, currentLockVersion, showSuccess, logError, onShowSaveModal, getWorkflowStateHash]);

  // Handle conflict resolution
  const handleConflictResolve = useCallback(async (resolution: 'reload' | 'force' | 'cancel') => {
    if (!conflictData || !currentWorkflowId) return;

    if (resolution === 'reload') {
      try {
        const response = await apiClient.getWorkflow(currentWorkflowId);
        const latestWorkflow = response.data;

        if (latestWorkflow.lock_version !== undefined) {
          setCurrentLockVersion(latestWorkflow.lock_version);
        }

        if (latestWorkflow.name) {
          setWorkflowName(latestWorkflow.name);
          setEditedName(latestWorkflow.name);
        }

        if (latestWorkflow.configuration) {
          const config = latestWorkflow.configuration;

          if (config.nodes) {
            const restoredNodes = config.nodes.map((n: any) => ({
              id: n.id,
              type: 'custom',
              position: n.position || { x: 0, y: 0 },
              data: n.data || {
                label: n.type,
                agentType: n.type,
                model: n.config?.model || 'gpt-4o-mini',
                config: n.config || {}
              }
            }));
            setNodes(restoredNodes);
          }

          if (config.edges) {
            const restoredEdges = config.edges.map((e: any) => ({
              id: `${e.source}-${e.target}`,
              source: e.source,
              target: e.target,
              type: 'smoothstep',
              animated: true
            }));
            setEdges(restoredEdges);
          }
        }

        setHasUnsavedChanges(false);
        showSuccess('Workflow reloaded with latest changes');
      } catch (error) {
        console.error('Failed to reload workflow:', error);
        logError('Failed to reload', 'Unable to fetch latest workflow');
      }
    } else if (resolution === 'force') {
      try {
        const latestResponse = await apiClient.getWorkflow(currentWorkflowId);
        const latestWorkflow = latestResponse.data;

        setCurrentLockVersion(latestWorkflow.lock_version);
        await handleSave(false);

        showSuccess('Workflow force-saved successfully');
      } catch (error) {
        console.error('Failed to force save:', error);
        logError('Force save failed', 'Unable to save workflow');
      }
    }

    setShowConflictDialog(false);
    setConflictData(null);
  }, [conflictData, currentWorkflowId, setNodes, setEdges, setWorkflowName, setEditedName, showSuccess, logError, handleSave]);

  // Update workflow name
  const handleWorkflowNameSave = useCallback(async (newName: string) => {
    if (!newName.trim()) return;

    setWorkflowName(newName);

    if (currentWorkflowId) {
      try {
        await apiClient.updateWorkflow(currentWorkflowId, { name: newName });
      } catch (error) {
        console.error('Failed to update workflow name:', error);
        logError('Failed to update name', 'Please try again.');
      }
    }
  }, [currentWorkflowId, setWorkflowName, logError]);

  // Mark state as saved (for use after creating new workflow)
  const markAsSaved = useCallback(() => {
    setHasUnsavedChanges(false);
    setLastSavedState(getWorkflowStateHash(nodes, edges));
  }, [nodes, edges, getWorkflowStateHash]);

  return {
    // State
    currentLockVersion,
    hasUnsavedChanges,
    showConflictDialog,
    conflictData,

    // Setters
    setCurrentLockVersion,
    setHasUnsavedChanges,

    // Handlers
    handleSave,
    handleConflictResolve,
    handleWorkflowNameSave,
    markAsSaved,
    getWorkflowStateHash,
  };
}
