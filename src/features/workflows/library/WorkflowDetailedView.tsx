/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useEffect, useRef } from 'react';
import apiClient from '@/lib/api-client';
import type { Workflow, WorkflowNode, WorkflowEdge, CostMetrics, AgentConfig } from '@/types/workflow';

interface WorkflowDetailedViewProps {
  workflow: Workflow;
  onOpenStudio: () => void;
  onDuplicate: () => void;
  onDelete: () => void;
  onExportCode: () => void;
  onExportPackage?: () => void;
  onExportLangConfig?: () => void;
}

export default function WorkflowDetailedView({
  workflow,
  onOpenStudio,
  onDuplicate,
  onDelete,
  onExportCode,
  onExportPackage,
  onExportLangConfig
}: WorkflowDetailedViewProps) {
  const [expandedSections, setExpandedSections] = useState<Set<string>>(
    new Set(['preview', 'agents', 'metrics'])
  );
  const [showExportMenu, setShowExportMenu] = useState(false);
  const [exportLoading, setExportLoading] = useState(false);
  const exportMenuRef = useRef<HTMLDivElement>(null);

  // Close export menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (exportMenuRef.current && !exportMenuRef.current.contains(event.target as Node)) {
        setShowExportMenu(false);
      }
    };

    if (showExportMenu) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [showExportMenu]);

  const handleExportPackage = async () => {
    setExportLoading(true);
    setShowExportMenu(false);

    try {
      const response = await fetch(`/api/workflows/${workflow.id}/export/package`, {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error('Failed to export package');
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `workflow_${workflow.name.replace(/\s+/g, '_')}_${workflow.id}.zip`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Failed to export package:', error);
      alert('Failed to export workflow package. Please try again.');
    } finally {
      setExportLoading(false);
    }
  };

  const handleExportLangConfig = async () => {
    setExportLoading(true);
    setShowExportMenu(false);

    try {
      const response = await fetch(`/api/workflows/${workflow.id}/export/config`);

      if (!response.ok) {
        throw new Error('Failed to export config');
      }

      const config = await response.json();
      const blob = new Blob([JSON.stringify(config, null, 2)], { type: 'application/json' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${workflow.name.replace(/\s+/g, '_')}.langconfig`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Failed to export config:', error);
      alert('Failed to export workflow config. Please try again.');
    } finally {
      setExportLoading(false);
    }
  };

  const [costMetrics, setCostMetrics] = useState<CostMetrics>({
    totalCost: 0,
    totalTokens: 0,
    promptTokens: 0,
    completionTokens: 0,
    executionCount: 0,
    agents: [],
    tools: []
  });
  const [loadingMetrics, setLoadingMetrics] = useState(false);

  // Fetch cost metrics from API
  useEffect(() => {
    const abortController = new AbortController();

    const fetchCostMetrics = async () => {
      setLoadingMetrics(true);
      try {
        const response = await apiClient.getWorkflowCostMetrics(workflow.id, 30);
        setCostMetrics(response.data);
      } catch (error) {
        console.error('Failed to fetch cost metrics:', error);
      } finally {
        setLoadingMetrics(false);
      }
    };

    fetchCostMetrics();

    return () => {
      abortController.abort();
    };
  }, [workflow.id]);

  const toggleSection = (section: string) => {
    setExpandedSections(prev => {
      const next = new Set(prev);
      if (next.has(section)) {
        next.delete(section);
      } else {
        next.add(section);
      }
      return next;
    });
  };

  // Extract nodes and edges from configuration (where Studio saves) or blueprint as fallback
  const nodes = (workflow.configuration?.nodes as WorkflowNode[]) || workflow.blueprint?.nodes || [];
  const edges = (workflow.configuration?.edges as WorkflowEdge[]) || workflow.blueprint?.edges || [];

  // Calculate metrics
  const nodeCount = nodes.length;
  const edgeCount = edges.length;
  const agentTypes = new Set(nodes.map((n: WorkflowNode) => n.type || 'agent')).size;

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className="h-full flex flex-col overflow-hidden bg-background-light dark:bg-background-dark">
      {/* Header */}
      <div className="border-b border-gray-200 dark:border-border-dark bg-white dark:bg-panel-dark px-6 py-4">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-2">
              <h2 className="text-2xl font-bold" style={{ color: 'var(--color-text-primary)' }}>
                {workflow.name}
              </h2>
              <span className="px-2 py-1 text-xs font-medium rounded-md bg-green-100 dark:bg-green-500/20 text-green-700 dark:text-green-400">
                Active
              </span>
            </div>
            {workflow.description && (
              <p className="text-sm mb-2" style={{ color: 'var(--color-text-muted)' }}>
                {workflow.description}
              </p>
            )}
            <div className="flex items-center gap-4 text-xs" style={{ color: 'var(--color-text-muted)' }}>
              <span>Created: {formatDate(workflow.created_at)}</span>
              <span>•</span>
              <span>Modified: {formatDate(workflow.updated_at)}</span>
            </div>
          </div>

          {/* Quick Actions */}
          <div className="flex items-center gap-2">
            {/* Export Dropdown */}
            <div className="relative" ref={exportMenuRef}>
              <button
                onClick={() => setShowExportMenu(!showExportMenu)}
                disabled={exportLoading}
                className="px-3 py-2 text-sm font-medium rounded-lg border border-gray-300 dark:border-border-dark hover:bg-gray-50 dark:hover:bg-white/5 transition-colors flex items-center gap-2 disabled:opacity-50"
                style={{ color: 'var(--color-text-primary)' }}
              >
                {exportLoading ? (
                  <>
                    <span className="inline-block animate-spin rounded-full h-4 w-4 border-b-2 border-current"></span>
                    Exporting...
                  </>
                ) : (
                  <>
                    <span className="material-symbols-outlined text-base">download</span>
                    Export
                    <span className="material-symbols-outlined text-sm">expand_more</span>
                  </>
                )}
              </button>

              {/* Export Menu Dropdown */}
              {showExportMenu && (
                <div className="absolute right-0 mt-1 w-64 rounded-lg border border-gray-200 dark:border-border-dark bg-white dark:bg-panel-dark shadow-xl z-50">
                  <div className="p-1">
                    <button
                      onClick={handleExportPackage}
                      className="w-full px-3 py-2.5 text-left text-sm rounded-md hover:bg-gray-100 dark:hover:bg-white/10 transition-colors flex items-start gap-3"
                    >
                      <span className="material-symbols-outlined text-primary text-lg mt-0.5">folder_zip</span>
                      <div>
                        <p className="font-medium" style={{ color: 'var(--color-text-primary)' }}>
                          Python Package
                        </p>
                        <p className="text-xs mt-0.5" style={{ color: 'var(--color-text-muted)' }}>
                          Standalone executable code with requirements.txt
                        </p>
                      </div>
                    </button>
                    <button
                      onClick={handleExportLangConfig}
                      className="w-full px-3 py-2.5 text-left text-sm rounded-md hover:bg-gray-100 dark:hover:bg-white/10 transition-colors flex items-start gap-3"
                    >
                      <span className="material-symbols-outlined text-primary text-lg mt-0.5">share</span>
                      <div>
                        <p className="font-medium" style={{ color: 'var(--color-text-primary)' }}>
                          LangConfig File
                        </p>
                        <p className="text-xs mt-0.5" style={{ color: 'var(--color-text-muted)' }}>
                          Share with other LangConfig users
                        </p>
                      </div>
                    </button>
                    <div className="border-t border-gray-200 dark:border-border-dark my-1"></div>
                    <button
                      onClick={() => {
                        setShowExportMenu(false);
                        onExportCode();
                      }}
                      className="w-full px-3 py-2.5 text-left text-sm rounded-md hover:bg-gray-100 dark:hover:bg-white/10 transition-colors flex items-start gap-3"
                    >
                      <span className="material-symbols-outlined text-primary text-lg mt-0.5">code</span>
                      <div>
                        <p className="font-medium" style={{ color: 'var(--color-text-primary)' }}>
                          View Code
                        </p>
                        <p className="text-xs mt-0.5" style={{ color: 'var(--color-text-muted)' }}>
                          Preview generated LangGraph code
                        </p>
                      </div>
                    </button>
                  </div>
                </div>
              )}
            </div>
            <button
              onClick={onDuplicate}
              className="px-3 py-2 text-sm font-medium rounded-lg border border-gray-300 dark:border-border-dark hover:bg-gray-50 dark:hover:bg-white/5 transition-colors flex items-center gap-2"
              style={{ color: 'var(--color-text-primary)' }}
            >
              <span className="material-symbols-outlined text-base">content_copy</span>
              Duplicate
            </button>
            <button
              onClick={onDelete}
              className="px-3 py-2 text-sm font-medium rounded-lg border border-red-300 dark:border-red-500/30 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-500/10 transition-colors flex items-center gap-2"
            >
              <span className="material-symbols-outlined text-base">delete</span>
              Delete
            </button>
            <button
              onClick={onOpenStudio}
              className="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:opacity-90 transition-opacity flex items-center gap-2"
            >
              <span className="material-symbols-outlined text-base">edit</span>
              Open in Studio
            </button>
          </div>
        </div>
      </div>

      {/* Scrollable Content */}
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
        {/* High-Level Overview */}
        <div className="grid grid-cols-3 gap-4">
          <div className="p-4 rounded-lg border border-gray-200 dark:border-border-dark bg-white dark:bg-panel-dark">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-gray-100 dark:bg-background-dark border border-gray-200 dark:border-border-dark flex items-center justify-center">
                <span className="material-symbols-outlined text-primary">hub</span>
              </div>
              <div>
                <p className="text-2xl font-bold" style={{ color: 'var(--color-text-primary)' }}>
                  {nodeCount}
                </p>
                <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                  Agent Nodes
                </p>
              </div>
            </div>
          </div>

          <div className="p-4 rounded-lg border border-gray-200 dark:border-border-dark bg-white dark:bg-panel-dark">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-gray-100 dark:bg-background-dark border border-gray-200 dark:border-border-dark flex items-center justify-center">
                <span className="material-symbols-outlined text-primary">cable</span>
              </div>
              <div>
                <p className="text-2xl font-bold" style={{ color: 'var(--color-text-primary)' }}>
                  {edgeCount}
                </p>
                <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                  Connections
                </p>
              </div>
            </div>
          </div>

          <div className="p-4 rounded-lg border border-gray-200 dark:border-border-dark bg-white dark:bg-panel-dark">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-gray-100 dark:bg-background-dark border border-gray-200 dark:border-border-dark flex items-center justify-center">
                <span className="material-symbols-outlined text-primary">category</span>
              </div>
              <div>
                <p className="text-2xl font-bold" style={{ color: 'var(--color-text-primary)' }}>
                  {agentTypes}
                </p>
                <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                  Agent Types
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Cost Metrics Section */}
        <div className="border border-gray-200 dark:border-border-dark rounded-lg overflow-hidden bg-white dark:bg-panel-dark">
          <button
            onClick={() => toggleSection('metrics')}
            className="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
          >
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-primary">payments</span>
              <h3 className="text-lg font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                Cost Metrics
              </h3>
            </div>
            <span
              className={`material-symbols-outlined transition-transform ${expandedSections.has('metrics') ? 'rotate-180' : ''
                }`}
              style={{ color: 'var(--color-text-muted)' }}
            >
              expand_more
            </span>
          </button>

          {expandedSections.has('metrics') && (
            <div className="border-t border-gray-200 dark:border-border-dark p-4">
              {/* Overall Cost Summary */}
              <div className="grid grid-cols-3 gap-4 mb-6">
                <div className="p-4 rounded-lg border border-gray-200 dark:border-border-dark bg-white dark:bg-panel-dark">
                  <p className="text-xs font-medium mb-1" style={{ color: 'var(--color-text-muted)' }}>
                    Total Cost
                  </p>
                  <p className="text-2xl font-bold text-primary">
                    ${loadingMetrics ? '...' : costMetrics.totalCost.toFixed(4)}
                  </p>
                  <p className="text-xxs mt-1" style={{ color: 'var(--color-text-muted)' }}>
                    Last 30 days
                  </p>
                </div>

                <div className="p-4 rounded-lg border border-gray-200 dark:border-border-dark bg-white dark:bg-panel-dark">
                  <p className="text-xs font-medium mb-1" style={{ color: 'var(--color-text-muted)' }}>
                    Total Tokens
                  </p>
                  <p className="text-2xl font-bold text-primary">
                    {loadingMetrics ? '...' : costMetrics.totalTokens.toLocaleString()}
                  </p>
                  <p className="text-xxs mt-1" style={{ color: 'var(--color-text-muted)' }}>
                    {costMetrics.promptTokens.toLocaleString()} prompt + {costMetrics.completionTokens.toLocaleString()} completion
                  </p>
                </div>

                <div className="p-4 rounded-lg border border-gray-200 dark:border-border-dark bg-white dark:bg-panel-dark">
                  <p className="text-xs font-medium mb-1" style={{ color: 'var(--color-text-muted)' }}>
                    Executions
                  </p>
                  <p className="text-2xl font-bold text-primary">
                    {loadingMetrics ? '...' : costMetrics.executionCount}
                  </p>
                  <p className="text-xxs mt-1" style={{ color: 'var(--color-text-muted)' }}>
                    Successful runs
                  </p>
                </div>
              </div>

              {/* Cost by Agent */}
              <div className="mb-6">
                <h4 className="text-sm font-semibold mb-3 flex items-center gap-2" style={{ color: 'var(--color-text-primary)' }}>
                  <span className="material-symbols-outlined text-base">smart_toy</span>
                  Cost by Agent
                </h4>
                <div className="space-y-2">
                  {costMetrics.agents.length > 0 ? (
                    costMetrics.agents.map((agent: { name: string; cost: number; tokens: number }, index: number) => (
                      <div
                        key={index}
                        className="flex items-center justify-between p-3 rounded-lg border border-gray-200 dark:border-border-dark bg-white dark:bg-panel-dark"
                      >
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-lg bg-gray-100 dark:bg-background-dark border border-gray-200 dark:border-border-dark flex items-center justify-center">
                            <span className="material-symbols-outlined text-primary text-sm">smart_toy</span>
                          </div>
                          <div>
                            <p className="text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>
                              {agent.name}
                            </p>
                          </div>
                        </div>
                        <div className="text-right">
                          <p className="text-sm font-bold" style={{ color: 'var(--color-primary)' }}>
                            ${agent.cost.toFixed(4)}
                          </p>
                          <p className="text-xxs" style={{ color: 'var(--color-text-muted)' }}>
                            {agent.tokens.toLocaleString()} tokens
                          </p>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="text-sm text-center py-4" style={{ color: 'var(--color-text-muted)' }}>
                      {loadingMetrics ? 'Loading...' : 'No agent cost data available'}
                    </div>
                  )}
                </div>
              </div>

              {/* Tool Usage */}
              <div className="mb-6">
                <h4 className="text-sm font-semibold mb-3 flex items-center gap-2" style={{ color: 'var(--color-text-primary)' }}>
                  <span className="material-symbols-outlined text-base">build</span>
                  Tool Usage
                </h4>
                {costMetrics.tools.length > 0 ? (
                  <div className="grid grid-cols-2 gap-3">
                    {costMetrics.tools.map((tool: { name: string; count: number }, index: number) => (
                      <div key={index} className="flex items-center gap-2 p-2 rounded-lg border border-gray-200 dark:border-border-dark bg-white dark:bg-panel-dark">
                        <span className="material-symbols-outlined text-primary text-sm">build</span>
                        <div className="flex-1">
                          <p className="text-xs font-medium" style={{ color: 'var(--color-text-primary)' }}>{tool.name}</p>
                          <p className="text-xxs" style={{ color: 'var(--color-text-muted)' }}>{tool.count} calls</p>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-sm text-center py-4" style={{ color: 'var(--color-text-muted)' }}>
                    {loadingMetrics ? 'Loading...' : 'No tool usage data available'}
                  </div>
                )}
              </div>

              {/* View Full Report Link */}
              <div className="pt-4 border-t border-gray-200 dark:border-border-dark">
                <button
                  className="w-full py-2.5 text-sm font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
                  style={{
                    backgroundColor: 'var(--color-primary)',
                    color: 'white'
                  }}
                  onClick={() => alert('Project Dashboard coming soon with full cost analytics!')}
                >
                  <span className="material-symbols-outlined text-base">analytics</span>
                  View Full Project Dashboard
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Visual Preview Section */}
        <div className="border border-gray-200 dark:border-border-dark rounded-lg overflow-hidden bg-white dark:bg-panel-dark">
          <button
            onClick={() => toggleSection('preview')}
            className="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
          >
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-primary">visibility</span>
              <h3 className="text-lg font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                Visual Preview
              </h3>
            </div>
            <span
              className={`material-symbols-outlined transition-transform ${expandedSections.has('preview') ? 'rotate-180' : ''
                }`}
              style={{ color: 'var(--color-text-muted)' }}
            >
              expand_more
            </span>
          </button>

          {expandedSections.has('preview') && (
            <div className="border-t border-gray-200 dark:border-border-dark p-6 bg-gray-50 dark:bg-background-dark">
              {nodes.length > 0 ? (
                <div className="flex items-center justify-center gap-4 overflow-x-auto pb-4">
                  {(() => {
                    // Build ordered node list by following edges from START_NODE
                    const orderedNodes: WorkflowNode[] = [];
                    const visited = new Set<string>();

                    // Find START_NODE or first node
                    let startNode = nodes.find((n: WorkflowNode) => n.type === 'START_NODE');
                    if (!startNode) {
                      // If no START_NODE, find first node (one that has no incoming edges)
                      const nodeIds = new Set(nodes.map((n: WorkflowNode) => n.id));
                      const targetIds = new Set(edges.map((e: WorkflowEdge) => e.target));
                      for (const node of nodes) {
                        if (!targetIds.has(node.id)) {
                          startNode = node;
                          break;
                        }
                      }
                    }

                    // Follow edges to build ordered list
                    let currentNodeId = startNode?.id;
                    while (currentNodeId && orderedNodes.length < nodes.length) {
                      visited.add(currentNodeId);
                      const currentNode = nodes.find((n: WorkflowNode) => n.id === currentNodeId);

                      // Only add non-START_NODE and non-END_NODE nodes
                      if (currentNode && currentNode.type !== 'START_NODE' && currentNode.type !== 'END_NODE') {
                        orderedNodes.push(currentNode);
                      }

                      // Find next node via edges
                      const nextEdge = edges.find((e: WorkflowEdge) => e.source === currentNodeId && !visited.has(e.target));
                      currentNodeId = nextEdge?.target;
                    }

                    // Add any remaining nodes not in the flow
                    for (const node of nodes) {
                      if (!visited.has(node.id) && node.type !== 'START_NODE' && node.type !== 'END_NODE') {
                        orderedNodes.push(node);
                      }
                    }

                    return orderedNodes.map((node: WorkflowNode, index: number) => {
                      const config: AgentConfig = (node.data?.config || node.config || {}) as AgentConfig;
                      const model = config.model || 'Not configured';
                      const allTools = [
                        ...(config.tools || []),
                        ...(config.native_tools || []),
                        ...(config.custom_tools || [])
                      ];

                      return (
                        <div key={node.id || index} className="flex items-center gap-4">
                          {/* Agent Node Card */}
                          <div className="w-64 p-4 rounded-lg border-2 border-primary bg-white dark:bg-panel-dark shadow-lg flex-shrink-0">
                            {/* Header */}
                            <div className="flex items-center gap-2 mb-3 pb-2 border-b border-gray-200 dark:border-border-dark">
                              <div className="w-8 h-8 rounded bg-primary/10 flex items-center justify-center">
                                <span className="material-symbols-outlined text-primary text-sm">smart_toy</span>
                              </div>
                              <div className="flex-1 min-w-0">
                                <p className="font-semibold text-sm truncate" style={{ color: 'var(--color-text-primary)' }}>
                                  {node.data?.name || node.data?.label || `Agent ${index + 1}`}
                                </p>
                                <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                                  {node.type || 'agent'}
                                </p>
                              </div>
                            </div>

                            {/* Details */}
                            <div className="space-y-2 text-xs">
                              <div>
                                <span style={{ color: 'var(--color-text-muted)' }}>Model: </span>
                                <span className="font-medium" style={{ color: 'var(--color-text-primary)' }}>{model}</span>
                              </div>
                              {allTools.length > 0 && (
                                <div>
                                  <span style={{ color: 'var(--color-text-muted)' }}>Tools: </span>
                                  <span className="font-medium" style={{ color: 'var(--color-text-primary)' }}>{allTools.length}</span>
                                </div>
                              )}
                              <div className="flex gap-1 flex-wrap mt-2">
                                {config.enable_memory && (
                                  <span className="px-1.5 py-0.5 rounded text-xs bg-purple-100 dark:bg-purple-500/20 text-purple-700 dark:text-purple-400">
                                    Memory
                                  </span>
                                )}
                                {config.enable_rag && (
                                  <span className="px-1.5 py-0.5 rounded text-xs bg-green-100 dark:bg-green-500/20 text-green-700 dark:text-green-400">
                                    RAG
                                  </span>
                                )}
                              </div>
                            </div>
                          </div>

                          {/* Arrow between nodes */}
                          {index < orderedNodes.length - 1 && (
                            <div className="flex items-center text-primary">
                              <span className="material-symbols-outlined text-3xl">arrow_forward</span>
                            </div>
                          )}
                        </div>
                      );
                    });
                  })()}
                </div>
              ) : (
                <div className="h-32 flex items-center justify-center">
                  <div className="text-center">
                    <span className="material-symbols-outlined text-4xl mb-2" style={{ color: 'var(--color-text-muted)' }}>
                      account_tree
                    </span>
                    <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
                      No workflow structure available
                    </p>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Agents in Workflow Section */}
        <div className="border border-gray-200 dark:border-border-dark rounded-lg overflow-hidden bg-white dark:bg-panel-dark">
          <button
            onClick={() => toggleSection('agents')}
            className="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
          >
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-primary">smart_toy</span>
              <h3 className="text-lg font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                Agents in Workflow ({nodeCount})
              </h3>
            </div>
            <span
              className={`material-symbols-outlined transition-transform ${expandedSections.has('agents') ? 'rotate-180' : ''
                }`}
              style={{ color: 'var(--color-text-muted)' }}
            >
              expand_more
            </span>
          </button>

          {expandedSections.has('agents') && (
            <div className="border-t border-gray-200 dark:border-border-dark p-4">
              {nodes.length === 0 ? (
                <p className="text-sm text-center py-4" style={{ color: 'var(--color-text-muted)' }}>
                  No agents configured
                </p>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {nodes.map((node: WorkflowNode, index: number) => {
                    const config: AgentConfig = (node.data?.config || node.config || {}) as AgentConfig;
                    const model = config.model || 'Not configured';
                    const temperature = config.temperature !== undefined ? config.temperature : 'N/A';
                    const systemPrompt = config.system_prompt || 'No prompt set';
                    // Combine tools, native_tools (MCP), and custom_tools
                    const allTools = [
                      ...(config.tools || []),
                      ...(config.native_tools || []),
                      ...(config.custom_tools || [])
                    ];
                    const hasMemory = config.enable_memory || false;
                    const hasRAG = config.enable_rag || false;

                    return (
                      <div
                        key={node.id || index}
                        className="p-4 rounded-lg border border-gray-200 dark:border-border-dark bg-white dark:bg-panel-dark"
                      >
                        {/* Agent Header */}
                        <div className="flex items-start gap-3 mb-3">
                          <div className="w-10 h-10 rounded-lg bg-gray-100 dark:bg-background-dark border border-gray-200 dark:border-border-dark flex items-center justify-center flex-shrink-0">
                            <span className="material-symbols-outlined text-primary text-xl">smart_toy</span>
                          </div>
                          <div className="flex-1 min-w-0">
                            <h4 className="font-semibold text-sm truncate" style={{ color: 'var(--color-text-primary)' }}>
                              {node.data?.name || node.data?.label || `Agent ${index + 1}`}
                            </h4>
                            <p className="text-xs mt-0.5" style={{ color: 'var(--color-text-muted)' }}>
                              {node.type || 'agent'}
                            </p>
                          </div>
                        </div>

                        {/* Model & Temperature */}
                        <div className="space-y-2 text-xs mb-3">
                          <div className="flex items-center justify-between">
                            <span style={{ color: 'var(--color-text-muted)' }}>Model:</span>
                            <span className="font-medium" style={{ color: 'var(--color-text-primary)' }}>
                              {model}
                            </span>
                          </div>
                          <div className="flex items-center justify-between">
                            <span style={{ color: 'var(--color-text-muted)' }}>Temperature:</span>
                            <span className="font-medium" style={{ color: 'var(--color-text-primary)' }}>
                              {temperature}
                            </span>
                          </div>
                        </div>

                        {/* System Prompt */}
                        <div className="mb-3">
                          <p className="text-xs font-medium mb-1" style={{ color: 'var(--color-text-muted)' }}>
                            System Prompt:
                          </p>
                          <div className="text-xs p-2 rounded bg-gray-50 dark:bg-white/5 max-h-32 overflow-y-auto" style={{ color: 'var(--color-text-primary)' }}>
                            <pre className="whitespace-pre-wrap font-sans">{systemPrompt}</pre>
                          </div>
                        </div>

                        {/* Capabilities */}
                        <div className="space-y-2">
                          {/* Tools List */}
                          {allTools.length > 0 && (
                            <div>
                              <p className="text-xs font-medium mb-1.5" style={{ color: 'var(--color-text-muted)' }}>
                                Tools ({allTools.length}):
                              </p>
                              <div className="flex flex-wrap gap-1">
                                {allTools.map((tool: string, idx: number) => (
                                  <span
                                    key={idx}
                                    className="px-2 py-0.5 text-xs rounded bg-blue-100 dark:bg-blue-500/20 text-blue-700 dark:text-blue-400"
                                  >
                                    {tool}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Features */}
                          <div className="flex flex-wrap gap-1.5">
                            {hasMemory && (
                              <span className="px-2 py-1 text-xs rounded-md bg-purple-100 dark:bg-purple-500/20 text-purple-700 dark:text-purple-400 flex items-center gap-1">
                                <span className="material-symbols-outlined text-xs">memory</span>
                                Memory
                              </span>
                            )}
                            {hasRAG && (
                              <span className="px-2 py-1 text-xs rounded-md bg-green-100 dark:bg-green-500/20 text-green-700 dark:text-green-400 flex items-center gap-1">
                                <span className="material-symbols-outlined text-xs">description</span>
                                RAG
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Configuration Details Section */}
        <div className="border border-gray-200 dark:border-border-dark rounded-lg overflow-hidden bg-white dark:bg-panel-dark">
          <button
            onClick={() => toggleSection('config')}
            className="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
          >
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-primary">settings</span>
              <h3 className="text-lg font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                Configuration Details
              </h3>
            </div>
            <span
              className={`material-symbols-outlined transition-transform ${expandedSections.has('config') ? 'rotate-180' : ''
                }`}
              style={{ color: 'var(--color-text-muted)' }}
            >
              expand_more
            </span>
          </button>

          {expandedSections.has('config') && (
            <div className="border-t border-gray-200 dark:border-border-dark p-4">
              <pre className="text-xs p-4 rounded-lg bg-gray-50 dark:bg-white/5 overflow-x-auto" style={{ color: 'var(--color-text-primary)' }}>
                {JSON.stringify(workflow.configuration, null, 2)}
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
