/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useCallback, useEffect } from 'react';
import { Node, Edge } from 'reactflow';
import apiClient from '@/lib/api-client';

interface WorkflowVersion {
  id: number;
  version_number: number;
  created_at: string;
  notes?: string;
  is_current?: boolean;
  created_by?: string;
  config_snapshot?: any;
}

interface VersionComparison {
  version1: WorkflowVersion & { config_snapshot: any };
  version2: WorkflowVersion & { config_snapshot: any };
  diff: {
    modified?: Record<string, any>;
    added?: Record<string, any>;
    removed?: Record<string, any>;
  };
}

interface UseVersionManagementOptions {
  currentWorkflowId: number | null;
  nodes: Node[];
  edges: Edge[];
  setNodes: (nodes: Node[] | ((nodes: Node[]) => Node[])) => void;
  setEdges: (edges: Edge[] | ((edges: Edge[]) => Edge[])) => void;
  showSuccess: (message: string) => void;
  showWarning: (message: string) => void;
  logError: (title: string, detail?: string) => void;
}

export function useVersionManagement({
  currentWorkflowId,
  nodes,
  edges,
  setNodes,
  setEdges,
  showSuccess,
  showWarning,
  logError,
}: UseVersionManagementOptions) {
  // Version state
  const [versions, setVersions] = useState<WorkflowVersion[]>([]);
  const [currentVersion, setCurrentVersion] = useState<WorkflowVersion | null>(null);
  const [loadingVersions, setLoadingVersions] = useState(false);

  // Version modal state
  const [showVersionModal, setShowVersionModal] = useState(false);
  const [versionNotes, setVersionNotes] = useState('');
  const [showVersionDropdown, setShowVersionDropdown] = useState(false);

  // Version comparison state
  const [compareMode, setCompareMode] = useState(false);
  const [compareVersion1, setCompareVersion1] = useState<WorkflowVersion | null>(null);
  const [compareVersion2, setCompareVersion2] = useState<WorkflowVersion | null>(null);
  const [versionComparison, setVersionComparison] = useState<VersionComparison | null>(null);
  const [loadingComparison, setLoadingComparison] = useState(false);

  // Load versions for workflow
  const loadVersions = useCallback(async (workflowId: number) => {
    setLoadingVersions(true);
    try {
      const response = await apiClient.getWorkflowVersions(workflowId);
      setVersions(response.data);

      const current = response.data.find((v: WorkflowVersion) => v.is_current);
      if (current) {
        setCurrentVersion(current);
      }
    } catch (error) {
      console.error('Failed to load versions:', error);
    } finally {
      setLoadingVersions(false);
    }
  }, []);

  // Load versions when workflow changes
  useEffect(() => {
    if (currentWorkflowId) {
      loadVersions(currentWorkflowId);
    }
  }, [currentWorkflowId, loadVersions]);

  // Open save version modal
  const handleSaveVersion = useCallback(() => {
    if (!currentWorkflowId) {
      showWarning('Please save the workflow first');
      return;
    }
    setShowVersionModal(true);
  }, [currentWorkflowId, showWarning]);

  // Confirm and create version
  const handleSaveVersionConfirm = useCallback(async () => {
    if (!currentWorkflowId) return;

    try {
      const configuration = {
        nodes: nodes.map(n => {
          const nativeTools = n.data.config?.native_tools || n.data.config?.nativeTools || [];
          const normalizedConfig = {
            ...n.data.config,
            native_tools: nativeTools,
            enable_memory: (n.data.config?.enable_memory ?? nativeTools.includes('enable_memory')) || false,
            enable_rag: (n.data.config?.enable_rag ?? nativeTools.includes('enable_rag')) || false,
          };
          return {
            id: n.id,
            type: n.data.agentType || n.data.label.toLowerCase().replace(/\s+/g, '_'),
            data: n.data,
            position: n.position,
            config: normalizedConfig
          };
        }),
        edges: edges.map(e => ({
          source: e.source,
          target: e.target
        }))
      };

      const response = await apiClient.createWorkflowVersion(currentWorkflowId, {
        config_snapshot: configuration,
        notes: versionNotes || 'Manual save',
        created_by: 'user'
      });

      setShowVersionModal(false);
      setVersionNotes('');

      await loadVersions(currentWorkflowId);

      showSuccess(`Version ${response.data.version_number} created successfully!`);
    } catch (error) {
      console.error('Failed to create version:', error);
      logError('Failed to create version. Please try again.');
    }
  }, [currentWorkflowId, nodes, edges, versionNotes, loadVersions, showSuccess, logError]);

  // Load a specific version
  const handleLoadVersion = useCallback(async (versionId: number) => {
    if (!currentWorkflowId) return;

    try {
      const response = await apiClient.getWorkflowVersion(currentWorkflowId, versionId);
      const versionData = response.data;

      const config = versionData.config_snapshot;

      if (config.nodes && config.edges) {
        // Restore nodes with validated positions
        const restoredNodes = config.nodes.map((n: any, index: number) => {
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

        // Restore edges
        const restoredEdges = config.edges.map((e: any) => ({
          id: `e${e.source}-${e.target}`,
          source: e.source,
          target: e.target,
          type: 'smoothstep',
          animated: true
        }));

        setNodes(restoredNodes);
        setEdges(restoredEdges);
        setCurrentVersion(versionData);
        setShowVersionDropdown(false);

        showSuccess(`Loaded Version ${versionData.version_number}`);
      }
    } catch (error) {
      console.error('Failed to load version:', error);
      logError('Failed to load version. Please try again.');
    }
  }, [currentWorkflowId, setNodes, setEdges, showSuccess, logError]);

  // Compare two versions
  const handleCompareVersions = useCallback(async () => {
    if (!compareVersion1 || !compareVersion2 || !currentWorkflowId) {
      showWarning('Please select two versions to compare');
      return;
    }

    setLoadingComparison(true);
    try {
      const response = await apiClient.compareWorkflowVersions(
        currentWorkflowId,
        compareVersion1.version_number,
        compareVersion2.version_number
      );
      setVersionComparison(response.data);
      setCompareMode(true);
    } catch (error) {
      console.error('Failed to compare versions:', error);
      logError('Failed to compare versions. Please try again.');
    } finally {
      setLoadingComparison(false);
    }
  }, [currentWorkflowId, compareVersion1, compareVersion2, showWarning, logError]);

  // Close version modal
  const handleCloseVersionModal = useCallback(() => {
    setShowVersionModal(false);
    setVersionNotes('');
  }, []);

  return {
    // State
    versions,
    currentVersion,
    loadingVersions,
    showVersionModal,
    versionNotes,
    showVersionDropdown,
    compareMode,
    compareVersion1,
    compareVersion2,
    versionComparison,
    loadingComparison,

    // Setters
    setVersionNotes,
    setShowVersionDropdown,
    setCompareMode,
    setCompareVersion1,
    setCompareVersion2,

    // Handlers
    loadVersions,
    handleSaveVersion,
    handleSaveVersionConfirm,
    handleLoadVersion,
    handleCompareVersions,
    handleCloseVersionModal,
  };
}
