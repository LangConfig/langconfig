/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { memo } from 'react';
import { Node } from 'reactflow';
import { Download, Copy, Check, Eye, EyeOff, List, Database, FolderOpen, History as HistoryIcon, FileText as FileIcon } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeHighlight from 'rehype-highlight';
import rehypeKatex from 'rehype-katex';
import { MemoryView } from '../../../../memory/components/MemoryView';
import { getFileIcon } from '../../../utils/fileHelpers';
import InlineFilePreview, { FileContent } from '../../Execution/InlineFilePreview';
import RealtimeExecutionPanel from '../../Execution/RealtimeExecutionPanel';
import { ContentBlockRenderer } from '../../../../../components/common/ContentBlockRenderer';
import { TaskHistoryEntry } from '../types';
import { exportToPDF } from '../../../../../utils/exportHelpers';
import apiClient from '../../../../../lib/api-client';

// Types
interface TaskFile {
  filename: string;
  path: string;
  size_bytes: number;
  size_human: string;
  modified_at: string;
  extension: string;
}


interface WorkflowVersion {
  id: number;
  version_number: number;
  created_at: string;
  notes?: string;
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

interface ExecutionStatus {
  state: 'idle' | 'running' | 'completed' | 'failed';
  currentNode?: string;
  progress?: number;
  startTime?: string;
  duration?: string;
}

interface WorkflowResultsProps {
  // Core data
  currentWorkflowId: number | null;
  workflowName: string;
  nodes: Node[];

  // Subtab state
  resultsSubTab: 'output' | 'memory' | 'files';
  setResultsSubTab: (tab: 'output' | 'memory' | 'files') => void;

  // Task history
  taskHistory: TaskHistoryEntry[];
  loadingHistory: boolean;
  selectedHistoryTask: TaskHistoryEntry | null;
  setSelectedHistoryTask: (task: TaskHistoryEntry | null) => void;
  isHistoryCollapsed: boolean;
  setIsHistoryCollapsed: (collapsed: boolean) => void;

  // Task context menu
  taskContextMenu: { taskId: number; x: number; y: number } | null;
  setTaskContextMenu: (menu: { taskId: number; x: number; y: number } | null) => void;
  handleDeleteTask: (taskId: number) => void;

  // Replay panel
  showReplayPanel: boolean;
  setShowReplayPanel: (show: boolean) => void;
  replayTaskId: number | null;
  setReplayTaskId: (id: number | null) => void;
  replayEvents: any[];
  executionStatus: ExecutionStatus;

  // Output display
  copiedToClipboard: boolean;
  setCopiedToClipboard: (copied: boolean) => void;
  showRawOutput: boolean;
  setShowRawOutput: (show: boolean) => void;
  showAnimatedReveal: boolean;
  setShowAnimatedReveal: (show: boolean) => void;

  // Version comparison
  versions: WorkflowVersion[];
  compareMode: boolean;
  setCompareMode: (mode: boolean) => void;
  compareVersion1: WorkflowVersion | null;
  setCompareVersion1: (version: WorkflowVersion | null) => void;
  compareVersion2: WorkflowVersion | null;
  setCompareVersion2: (version: WorkflowVersion | null) => void;
  loadingComparison: boolean;
  versionComparison: VersionComparison | null;
  handleCompareVersions: () => void;

  // Files
  files: TaskFile[];
  filesLoading: boolean;
  filesError: string | null;
  fetchFiles: () => void;
  selectedPreviewFile: TaskFile | null;
  filePreviewContent: FileContent | null;
  filePreviewLoading: boolean;
  handleFileSelect: (file: TaskFile) => void;
  handleDownloadFile: (filename: string) => void;
  closeFilePreview: () => void;

  // Tool/Action display data (computed in parent)
  toolsAndActions: {
    tools: any[];
    actions: string[];
    toolCount: number;
    actionCount: number;
  };
  tokenCostInfo: {
    totalTokens: number;
    costString: string;
  };
  nodeTokenCosts: Record<string, any>;
  expandedToolCalls: Set<number>;
  setExpandedToolCalls: (expanded: Set<number>) => void;
}

/**
 * WorkflowResults component - Displays workflow execution results with subtabs
 * for Output, Memory, and Files
 */
const WorkflowResults = memo(function WorkflowResults({
  currentWorkflowId,
  workflowName,
  nodes,
  resultsSubTab,
  setResultsSubTab,
  taskHistory,
  loadingHistory,
  selectedHistoryTask,
  setSelectedHistoryTask,
  isHistoryCollapsed,
  setIsHistoryCollapsed,
  taskContextMenu,
  setTaskContextMenu,
  handleDeleteTask,
  showReplayPanel,
  setShowReplayPanel,
  replayTaskId: _replayTaskId,
  setReplayTaskId,
  replayEvents,
  executionStatus,
  copiedToClipboard,
  setCopiedToClipboard,
  showRawOutput,
  setShowRawOutput,
  showAnimatedReveal,
  setShowAnimatedReveal,
  versions: _versions,
  compareMode,
  setCompareMode,
  compareVersion1: _compareVersion1,
  setCompareVersion1: _setCompareVersion1,
  compareVersion2: _compareVersion2,
  setCompareVersion2: _setCompareVersion2,
  loadingComparison: _loadingComparison,
  versionComparison: _versionComparison,
  handleCompareVersions: _handleCompareVersions,
  files,
  filesLoading,
  filesError,
  fetchFiles,
  selectedPreviewFile,
  filePreviewContent,
  filePreviewLoading,
  handleFileSelect,
  handleDownloadFile,
  closeFilePreview,
  toolsAndActions,
  tokenCostInfo,
  nodeTokenCosts,
  expandedToolCalls,
  setExpandedToolCalls,
}: WorkflowResultsProps) {

  // Get the task to display (selected or latest)
  const displayTask = selectedHistoryTask || taskHistory[0];
  const taskOutput = displayTask?.result;
  const isLatestTask = displayTask?.id === taskHistory[0]?.id;

  // Extract prompt from task
  const getTaskPrompt = (task: TaskHistoryEntry): string => {
    if (task.input_data?.query) return task.input_data.query;
    if (task.input_data?.task) return task.input_data.task;
    if (task.input_data?.directive) return task.input_data.directive;

    if (task.result) {
      if (task.result.query) return task.result.query;
      if (task.result.task) return task.result.task;
      if (task.result.directive) return task.result.directive;
      if (task.result.input_data) {
        const inputData = task.result.input_data;
        if (inputData.query) return inputData.query;
        if (inputData.task) return inputData.task;
        if (inputData.directive) return inputData.directive;
        if (typeof inputData === 'string') {
          const cleanContent = inputData.replace(/```json\n?|\n?```/g, '').trim();
          if (cleanContent && cleanContent !== '{}' && cleanContent !== '[]') {
            return cleanContent;
          }
        }
      }
    }

    if (task.formatted_input && typeof task.formatted_input === 'string') {
      return task.formatted_input;
    }

    return 'No prompt available';
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="w-full h-full flex flex-col">
        {/* Results Subtabs */}
        <div className="flex items-center justify-between border-b" style={{ borderColor: 'var(--color-border-dark)' }}>
          <div className="flex">
            <button
              onClick={() => setResultsSubTab('output')}
              className={`px-6 py-3 text-sm font-medium transition-colors border-b-2 ${resultsSubTab === 'output'
                ? 'border-primary text-primary'
                : 'border-transparent hover:text-primary'
              }`}
              style={resultsSubTab !== 'output' ? { color: 'var(--color-text-muted)' } : {}}
            >
              Workflow Output
            </button>
            <button
              onClick={() => setResultsSubTab('memory')}
              className={`px-6 py-3 text-sm font-medium transition-colors border-b-2 ${resultsSubTab === 'memory'
                ? 'border-primary text-primary'
                : 'border-transparent hover:text-primary'
              }`}
              style={resultsSubTab !== 'memory' ? { color: 'var(--color-text-muted)' } : {}}
            >
              <Database className="w-4 h-4 inline mr-2" />
              Memory
            </button>
            <button
              onClick={() => setResultsSubTab('files')}
              className={`px-6 py-3 text-sm font-medium transition-colors border-b-2 ${resultsSubTab === 'files'
                ? 'border-primary text-primary'
                : 'border-transparent hover:text-primary'
              }`}
              style={resultsSubTab !== 'files' ? { color: 'var(--color-text-muted)' } : {}}
            >
              <FolderOpen className="w-4 h-4 inline mr-2" />
              Files {files.length > 0 && `(${files.length})`}
            </button>
          </div>

          {/* View Execution Log Button */}
          {taskHistory.length > 0 && (
            <button
              onClick={() => {
                const taskToView = selectedHistoryTask || taskHistory[0];
                setReplayTaskId(taskToView.id);
                setShowReplayPanel(true);
              }}
              className="inline-flex items-center gap-2 px-4 py-2 mr-4 text-sm font-medium rounded-lg transition-all hover:opacity-90"
              style={{
                backgroundColor: 'var(--color-primary)',
                color: 'white'
              }}
              title="View detailed execution log"
            >
              <List className="w-4 h-4" />
              <span>View Execution Log</span>
            </button>
          )}
        </div>

        {/* Subtab Content */}
        <div className="flex-1 overflow-hidden flex">
          {/* Output Subtab */}
          {resultsSubTab === 'output' && (
            <div className="flex-1 overflow-y-auto p-6">
              {loadingHistory ? (
                <div className="flex items-center justify-center py-16">
                  <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
                </div>
              ) : taskHistory.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <HistoryIcon className="w-16 h-16 text-gray-300 dark:text-text-muted/30 mb-4" />
                  <p className="text-lg font-medium text-gray-600 dark:text-text-muted">
                    No results yet
                  </p>
                  <p className="text-sm text-gray-500 dark:text-text-muted/70 mt-2">
                    Execute this workflow to see results here.
                  </p>
                </div>
              ) : (
                <div className="w-full px-4">
                  {!taskOutput ? (
                    <div className="flex flex-col items-center justify-center py-16 text-center">
                      <span className="material-symbols-outlined text-6xl text-gray-300 dark:text-text-muted/30 mb-4">
                        pending_actions
                      </span>
                      <p className="text-lg font-medium text-gray-600 dark:text-text-muted">
                        No output data available
                      </p>
                      <p className="text-sm text-gray-500 dark:text-text-muted/70 mt-2">
                        Task #{displayTask?.id} has no result data.
                      </p>
                    </div>
                  ) : (
                    <div className="bg-white dark:bg-panel-dark border-2 border-primary dark:border-primary/50 rounded-lg p-6 shadow-lg">
                      {/* Task Header */}
                      <div className="flex items-center justify-between mb-4">
                        <div className="flex-1 min-w-0 mr-4">
                          <div className="flex items-center gap-3">
                            <span className="text-xs font-mono text-gray-500 dark:text-text-muted">
                              Task #{displayTask.id}
                            </span>
                            {!isLatestTask && (
                              <span className="text-xs px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400">
                                Historical
                              </span>
                            )}
                            {isLatestTask && (
                              <span className="text-xs px-2 py-0.5 rounded bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 font-semibold">
                                Latest
                              </span>
                            )}
                          </div>
                          <h3 className="text-lg font-bold mt-1" style={{ color: 'var(--color-text-primary)' }}>
                            Workflow Results
                          </h3>
                        </div>
                        <div className="flex items-center gap-2 flex-shrink-0">
                          {displayTask?.created_at && (
                            <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                              {new Date(displayTask.created_at).toLocaleString()}
                            </span>
                          )}

                          {/* Toggle Animation Button */}
                          <button
                            onClick={() => setShowAnimatedReveal(!showAnimatedReveal)}
                            className="p-2 rounded-md hover:bg-gray-100 dark:hover:bg-white/10"
                            title={showAnimatedReveal ? "Show static view" : "Show animated reveal"}
                          >
                            <span className="material-symbols-outlined text-lg">
                              {showAnimatedReveal ? 'auto_awesome' : 'text_fields'}
                            </span>
                          </button>

                          {/* Compare Versions Button */}
                          {currentWorkflowId && _versions.length > 1 && (
                            <button
                              onClick={() => setCompareMode(!compareMode)}
                              className={`p-2 rounded-md ${compareMode
                                ? 'bg-primary text-white'
                                : 'hover:bg-gray-100 dark:hover:bg-white/10'
                              }`}
                              title="Compare workflow versions"
                            >
                              <span className="material-symbols-outlined text-lg">
                                compare_arrows
                              </span>
                            </button>
                          )}

                          {/* Copy Results Button */}
                          <button
                            onClick={() => {
                              const textToCopy = taskOutput?.formatted_content || '';
                              navigator.clipboard.writeText(textToCopy);
                              setCopiedToClipboard(true);
                              setTimeout(() => setCopiedToClipboard(false), 2000);
                            }}
                            className="p-2 rounded-md hover:bg-gray-100 dark:hover:bg-white/10"
                            title="Copy results to clipboard"
                          >
                            {copiedToClipboard ? (
                              <Check className="w-4 h-4 text-green-600 dark:text-green-400" />
                            ) : (
                              <Copy className="w-4 h-4 text-gray-600 dark:text-text-muted" />
                            )}
                          </button>

                          {/* Export to PDF Button */}
                          <button
                            onClick={async () => {
                              try {
                                const content = taskOutput?.formatted_content || '';
                                const metadata = {
                                  date: new Date().toLocaleString(),
                                  duration: selectedHistoryTask?.duration_seconds || taskHistory[0]?.duration_seconds,
                                  tokens: selectedHistoryTask?.result?.workflow_summary?.total_tokens || taskHistory[0]?.result?.workflow_summary?.total_tokens,
                                  cost: selectedHistoryTask?.result?.workflow_summary?.total_cost_usd || taskHistory[0]?.result?.workflow_summary?.total_cost_usd,
                                };
                                await exportToPDF(content, workflowName || 'Workflow_Results', metadata);
                              } catch (error) {
                                console.error('Failed to export PDF:', error);
                                alert('Failed to export PDF. Please try again.');
                              }
                            }}
                            className="p-2 rounded-md hover:bg-gray-100 dark:hover:bg-white/10"
                            title="Export to PDF"
                          >
                            <Download className="w-4 h-4 text-gray-600 dark:text-text-muted" />
                          </button>

                          {/* Export to Word Button */}
                          <button
                            onClick={async () => {
                              try {
                                const executionId = selectedHistoryTask?.id || taskHistory[0]?.id;
                                if (!executionId) {
                                  alert('No execution found to export');
                                  return;
                                }
                                const response = await apiClient.exportWorkflowExecutionDocx(executionId);
                                const url = window.URL.createObjectURL(new Blob([response.data]));
                                const link = document.createElement('a');
                                link.href = url;
                                const filename = `${workflowName?.replace(/\s+/g, '_') || 'workflow_results'}_${executionId}.docx`;
                                link.setAttribute('download', filename);
                                document.body.appendChild(link);
                                link.click();
                                link.parentNode?.removeChild(link);
                                window.URL.revokeObjectURL(url);
                              } catch (error) {
                                console.error('Failed to export Word document:', error);
                                alert('Failed to export Word document. Please try again.');
                              }
                            }}
                            className="p-2 rounded-md hover:bg-gray-100 dark:hover:bg-white/10"
                            title="Export to Word (.docx)"
                          >
                            <span className="material-symbols-outlined text-base text-gray-600 dark:text-text-muted">
                              description
                            </span>
                          </button>

                          {/* View Raw Output Toggle */}
                          <button
                            onClick={() => setShowRawOutput(!showRawOutput)}
                            className="p-2 rounded-md hover:bg-gray-100 dark:hover:bg-white/10"
                            title={showRawOutput ? "Hide raw output" : "Show raw output"}
                          >
                            {showRawOutput ? (
                              <EyeOff className="w-4 h-4 text-gray-600 dark:text-text-muted" />
                            ) : (
                              <Eye className="w-4 h-4 text-gray-600 dark:text-text-muted" />
                            )}
                          </button>
                        </div>
                      </div>

                      {/* 3-Column Layout */}
                      <div className="flex gap-6 w-full">
                        {/* LEFT SIDEBAR - Agent Activity Timeline */}
                        <div className="w-80 flex-shrink-0">
                          <div className="space-y-3">
                            {/* Compact Stats */}
                            <div className="grid grid-cols-2 gap-2">
                              <div className="px-3 py-2 rounded border text-center"
                                style={{
                                  backgroundColor: 'var(--color-panel-dark)',
                                  borderColor: 'var(--color-border-dark)'
                                }}>
                                <div className="text-xl font-bold" style={{ color: 'var(--color-primary)' }}>
                                  {toolsAndActions.toolCount}
                                </div>
                                <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                                  Tools
                                </div>
                              </div>
                              <div className="px-3 py-2 rounded border text-center"
                                style={{
                                  backgroundColor: 'var(--color-panel-dark)',
                                  borderColor: 'var(--color-border-dark)'
                                }}>
                                <div className="text-xl font-bold" style={{ color: 'var(--color-primary)' }}>
                                  {toolsAndActions.actionCount}
                                </div>
                                <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                                  Actions
                                </div>
                              </div>
                            </div>

                            {/* Tool Calls List */}
                            {toolsAndActions.tools.length > 0 && (
                              <div>
                                <h4 className="text-xs font-semibold uppercase tracking-wider mb-2"
                                  style={{ color: 'var(--color-text-muted)' }}>
                                  Tool Calls
                                </h4>
                                <div className="rounded border"
                                  style={{
                                    backgroundColor: 'var(--color-panel-dark)',
                                    borderColor: 'var(--color-border-dark)'
                                  }}>
                                  <div className="max-h-96 overflow-y-auto">
                                    {toolsAndActions.tools.map((tool: any, idx: number) => {
                                      const isExpanded = expandedToolCalls.has(idx);
                                      return (
                                        <div key={idx} className="border-b last:border-b-0" style={{ borderColor: 'var(--color-border-dark)' }}>
                                          <button
                                            onClick={() => {
                                              const newExpanded = new Set(expandedToolCalls);
                                              if (isExpanded) {
                                                newExpanded.delete(idx);
                                              } else {
                                                newExpanded.add(idx);
                                              }
                                              setExpandedToolCalls(newExpanded);
                                            }}
                                            className="w-full px-2 py-1.5 flex items-center gap-2 hover:bg-white/5 transition-colors text-left"
                                          >
                                            <span className="material-symbols-outlined text-xs" style={{ color: 'var(--color-primary)' }}>
                                              {isExpanded ? 'expand_more' : 'chevron_right'}
                                            </span>
                                            <span className="material-symbols-outlined text-xs" style={{ color: 'var(--color-primary)' }}>
                                              build
                                            </span>
                                            <span className="text-xs font-medium flex-1" style={{ color: 'var(--color-text-primary)' }}>
                                              {tool.name}
                                            </span>
                                          </button>
                                          {isExpanded && (
                                            <div className="px-8 py-2 space-y-2 text-xs" style={{ backgroundColor: 'rgba(0,0,0,0.1)' }}>
                                              {tool.args && (
                                                <div>
                                                  <div className="font-semibold mb-1" style={{ color: 'var(--color-text-muted)' }}>Arguments:</div>
                                                  <pre className="font-mono text-xs p-2 rounded overflow-x-auto"
                                                    style={{ backgroundColor: 'rgba(0,0,0,0.2)', color: 'var(--color-text-primary)' }}>
                                                    {typeof tool.args === 'string' ? tool.args : JSON.stringify(tool.args, null, 2)}
                                                  </pre>
                                                </div>
                                              )}
                                              {tool.result && (
                                                <div>
                                                  <div className="font-semibold mb-1" style={{ color: 'var(--color-text-muted)' }}>Result:</div>
                                                  <pre className="font-mono text-xs p-2 rounded overflow-x-auto max-h-40"
                                                    style={{ backgroundColor: 'rgba(0,0,0,0.2)', color: 'var(--color-text-primary)' }}>
                                                    {typeof tool.result === 'string' ? tool.result.substring(0, 500) : JSON.stringify(tool.result, null, 2).substring(0, 500)}
                                                    {(typeof tool.result === 'string' && tool.result.length > 500) || (typeof tool.result !== 'string' && JSON.stringify(tool.result).length > 500) ? '...' : ''}
                                                  </pre>
                                                </div>
                                              )}
                                            </div>
                                          )}
                                        </div>
                                      );
                                    })}
                                  </div>
                                </div>
                              </div>
                            )}

                            {/* Actions List */}
                            {toolsAndActions.actions.length > 0 && (
                              <div>
                                <h4 className="text-xs font-semibold uppercase tracking-wider mb-2"
                                  style={{ color: 'var(--color-text-muted)' }}>
                                  Key Actions
                                </h4>
                                <div className="rounded border"
                                  style={{
                                    backgroundColor: 'var(--color-panel-dark)',
                                    borderColor: 'var(--color-border-dark)'
                                  }}>
                                  <div className="max-h-60 overflow-y-auto">
                                    {toolsAndActions.actions.map((action: string, idx: number) => (
                                      <div key={idx} className="px-2 py-1.5 border-b last:border-b-0" style={{ borderColor: 'var(--color-border-dark)' }}>
                                        <span className="text-xs" style={{ color: 'var(--color-text-primary)' }}>{action}</span>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              </div>
                            )}

                            {toolsAndActions.tools.length === 0 && toolsAndActions.actions.length === 0 && (
                              <div className="text-center py-8 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                                No activity recorded
                              </div>
                            )}

                            {/* Task Summary */}
                            <div className="p-3 rounded-lg border"
                              style={{
                                backgroundColor: 'var(--color-panel-dark)',
                                borderColor: 'var(--color-border-dark)'
                              }}>
                              <div className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: 'var(--color-text-muted)' }}>
                                Task Summary
                              </div>
                              <div className="space-y-1.5 text-xs">
                                {displayTask?.id && (
                                  <div className="flex justify-between">
                                    <span style={{ color: 'var(--color-text-muted)' }}>Task ID</span>
                                    <span className="font-mono font-medium" style={{ color: 'var(--color-text-primary)' }}>#{displayTask.id}</span>
                                  </div>
                                )}
                                {displayTask?.duration_seconds && (
                                  <div className="flex justify-between">
                                    <span style={{ color: 'var(--color-text-muted)' }}>Duration</span>
                                    <span className="font-medium" style={{ color: 'var(--color-text-primary)' }}>{Math.round(displayTask.duration_seconds)}s</span>
                                  </div>
                                )}
                                {displayTask?.status && (
                                  <div className="flex justify-between">
                                    <span style={{ color: 'var(--color-text-muted)' }}>Status</span>
                                    <span className="font-medium capitalize" style={{ color: 'var(--color-text-primary)' }}>{displayTask.status}</span>
                                  </div>
                                )}
                                {tokenCostInfo.totalTokens > 0 && (
                                  <>
                                    <div className="flex justify-between">
                                      <span style={{ color: 'var(--color-text-muted)' }}>Tokens</span>
                                      <span className="font-mono font-medium" style={{ color: 'var(--color-text-primary)' }}>
                                        {tokenCostInfo.totalTokens.toLocaleString()}
                                      </span>
                                    </div>
                                    <div className="flex justify-between">
                                      <span style={{ color: 'var(--color-text-muted)' }}>Cost</span>
                                      <span className="font-mono font-medium" style={{ color: 'var(--color-text-primary)' }}>
                                        {tokenCostInfo.costString}
                                      </span>
                                    </div>
                                    <div className="flex justify-between text-xxs" style={{ opacity: 0.7 }}>
                                      <span style={{ color: 'var(--color-text-muted)' }}>Model</span>
                                      <span style={{ color: 'var(--color-text-muted)' }}>
                                        {Object.keys(nodeTokenCosts).length > 1 ? 'Multi-agent' : 'Single agent'}
                                      </span>
                                    </div>
                                  </>
                                )}
                              </div>
                            </div>
                          </div>
                        </div>

                        {/* CENTER - Main Output Content */}
                        <div className="flex-1">
                          <div className="prose dark:prose-invert max-w-none">
                            {/* Content Blocks */}
                            {taskOutput?.content_blocks && taskOutput.content_blocks.length > 0 && (
                              <div className="mb-6">
                                <ContentBlockRenderer blocks={taskOutput.content_blocks} />
                              </div>
                            )}

                            {/* Formatted Content */}
                            {taskOutput?.formatted_content && (
                              <ReactMarkdown
                                remarkPlugins={[remarkGfm, remarkMath]}
                                rehypePlugins={[rehypeHighlight, rehypeKatex]}
                                components={{
                                  img: ({ src, alt }) => (
                                    <img
                                      src={src}
                                      alt={alt || 'Generated image'}
                                      className="max-w-full h-auto rounded-lg shadow-md my-4"
                                      style={{ maxHeight: '600px' }}
                                    />
                                  ),
                                }}
                              >
                                {taskOutput.formatted_content}
                              </ReactMarkdown>
                            )}

                            {/* Raw Output */}
                            {showRawOutput && (
                              <div className="mt-6 p-4 bg-gray-100 dark:bg-gray-900 rounded-lg">
                                <h4 className="text-sm font-semibold mb-2">Raw Output</h4>
                                <pre className="text-xs overflow-auto whitespace-pre-wrap">
                                  {JSON.stringify(taskOutput, null, 2)}
                                </pre>
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Task History Sidebar */}
              {taskHistory.length > 0 && resultsSubTab === 'output' && (
                <div className="fixed right-0 top-0 h-full z-40 flex">
                  {/* Collapse Toggle */}
                  <button
                    onClick={() => {
                      const newValue = !isHistoryCollapsed;
                      setIsHistoryCollapsed(newValue);
                      localStorage.setItem('workflow-history-collapsed', JSON.stringify(newValue));
                    }}
                    className="absolute -left-6 top-1/2 transform -translate-y-1/2 w-6 h-12 rounded-l-lg flex items-center justify-center transition-colors"
                    style={{
                      backgroundColor: 'var(--color-panel-dark)',
                      borderTop: '1px solid var(--color-border-dark)',
                      borderBottom: '1px solid var(--color-border-dark)',
                      borderLeft: '1px solid var(--color-border-dark)',
                    }}
                    title={isHistoryCollapsed ? "Expand history" : "Collapse history"}
                  >
                    <span className="material-symbols-outlined text-sm" style={{ color: 'var(--color-text-muted)' }}>
                      {isHistoryCollapsed ? 'chevron_left' : 'chevron_right'}
                    </span>
                  </button>

                  {/* History Panel */}
                  <div
                    className={`h-full border-l overflow-y-auto transition-all duration-200 ${isHistoryCollapsed ? 'w-16' : 'w-72'}`}
                    style={{
                      backgroundColor: 'var(--color-background-dark)',
                      borderColor: 'var(--color-border-dark)',
                    }}
                  >
                    <div className={`sticky top-0 z-10 ${isHistoryCollapsed ? 'p-2' : 'p-4'} border-b`} style={{
                      backgroundColor: 'var(--color-background-dark)',
                      borderColor: 'var(--color-border-dark)'
                    }}>
                      {isHistoryCollapsed ? (
                        <HistoryIcon className="w-5 h-5 mx-auto" style={{ color: 'var(--color-text-muted)' }} />
                      ) : (
                        <h3 className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                          Task History ({taskHistory.length})
                        </h3>
                      )}
                    </div>

                    <div className={isHistoryCollapsed ? 'p-2 space-y-2' : 'p-4 space-y-3'}>
                      {taskHistory.map((task) => {
                        const isSelected = selectedHistoryTask?.id === task.id || (!selectedHistoryTask && task.id === taskHistory[0]?.id);
                        const prompt = getTaskPrompt(task);

                        return (
                          <button
                            key={task.id}
                            onClick={() => {
                              setSelectedHistoryTask(task);
                              if (showReplayPanel) {
                                setReplayTaskId(task.id);
                              }
                            }}
                            onContextMenu={(e) => {
                              e.preventDefault();
                              setTaskContextMenu({
                                taskId: task.id,
                                x: e.clientX,
                                y: e.clientY
                              });
                            }}
                            className={`w-full text-left ${isHistoryCollapsed ? 'p-2' : 'p-3'} rounded-lg border transition-all ${isSelected
                              ? 'bg-primary/10 dark:bg-primary/20 border-primary shadow-md'
                              : 'bg-white dark:bg-panel-dark border-gray-200 dark:border-gray-700 hover:border-primary/50'
                            } hover:shadow-md`}
                            title={isHistoryCollapsed ? `Task #${task.id}: ${prompt.substring(0, 50)}...` : ''}
                          >
                            {isHistoryCollapsed ? (
                              <div className="flex flex-col items-center gap-1">
                                <span className={`text-xs px-1.5 py-0.5 rounded-full ${task.status === 'COMPLETED' ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400' :
                                  task.status === 'FAILED' ? 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400' :
                                    'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400'
                                }`}>
                                  {task.status === 'COMPLETED' ? '✓' : task.status === 'FAILED' ? '✗' : '•'}
                                </span>
                                <span className="text-[10px] font-mono" style={{ color: 'var(--color-text-muted)' }}>
                                  #{task.id}
                                </span>
                              </div>
                            ) : (
                              <>
                                <div className="flex items-center justify-between mb-2">
                                  <span className="text-sm font-bold" style={{ color: 'var(--color-text-primary)' }}>
                                    Task #{task.id}
                                  </span>
                                  <span className={`text-xs px-2 py-0.5 rounded-full ${task.status === 'COMPLETED' ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400' :
                                    task.status === 'FAILED' ? 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400' :
                                      'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400'
                                  }`}>
                                    {task.status === 'COMPLETED' ? '✓' : task.status === 'FAILED' ? '✗' : '•'}
                                  </span>
                                </div>
                                <div className="mb-2">
                                  <div className="text-xs font-medium mb-1" style={{ color: 'var(--color-text-muted)' }}>
                                    Prompt:
                                  </div>
                                  <div className="text-xs line-clamp-2 italic" style={{ color: 'var(--color-text-primary)', opacity: 0.9 }}>
                                    "{prompt.substring(0, 100)}{prompt.length > 100 ? '...' : ''}"
                                  </div>
                                </div>
                                <div className="flex items-center justify-between text-xs" style={{ color: 'var(--color-text-muted)' }}>
                                  {task.created_at && (
                                    <div>
                                      {new Date(task.created_at).toLocaleDateString()} {new Date(task.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                    </div>
                                  )}
                                  {task.duration_seconds && (
                                    <div className="font-medium">
                                      {task.duration_seconds < 60
                                        ? `${Math.round(task.duration_seconds)}s`
                                        : `${Math.floor(task.duration_seconds / 60)}m ${Math.round(task.duration_seconds % 60)}s`
                                      }
                                    </div>
                                  )}
                                </div>
                              </>
                            )}
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  {/* Task Context Menu */}
                  {taskContextMenu && (
                    <>
                      <div
                        className="fixed inset-0 z-50"
                        onClick={() => setTaskContextMenu(null)}
                      />
                      <div
                        className="fixed z-50 rounded-lg shadow-xl border py-1 min-w-[160px]"
                        style={{
                          left: taskContextMenu.x,
                          top: taskContextMenu.y,
                          backgroundColor: 'var(--color-panel-dark)',
                          borderColor: 'var(--color-border-dark)',
                        }}
                      >
                        <button
                          onClick={() => {
                            handleDeleteTask(taskContextMenu.taskId);
                            setTaskContextMenu(null);
                          }}
                          className="w-full px-4 py-2 text-left text-sm hover:bg-red-500/10 text-red-500 flex items-center gap-2"
                        >
                          <span className="material-symbols-outlined text-base">delete</span>
                          Delete Task
                        </button>
                      </div>
                    </>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Memory Subtab */}
          {resultsSubTab === 'memory' && currentWorkflowId && (
            <div className="flex-1 overflow-hidden">
              <MemoryView workflowId={currentWorkflowId} nodes={nodes} />
            </div>
          )}

          {/* Files Subtab */}
          {resultsSubTab === 'files' && (
            <div className="flex-1 overflow-hidden flex">
              <div className={`${selectedPreviewFile ? 'w-1/2' : 'w-full'} overflow-y-auto p-6 transition-all duration-200`}>
                {filesLoading ? (
                  <div className="flex items-center justify-center py-16">
                    <div className="text-center">
                      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4" style={{ borderColor: 'var(--color-primary)' }}></div>
                      <p className="text-sm text-gray-600 dark:text-text-muted">Loading files...</p>
                    </div>
                  </div>
                ) : filesError ? (
                  <div className="flex flex-col items-center justify-center py-16 text-center">
                    <FileIcon className="w-16 h-16 text-red-300 dark:text-red-900/30 mb-4" />
                    <p className="text-lg font-medium text-red-600 dark:text-red-400">
                      Failed to load files
                    </p>
                    <p className="text-sm text-gray-500 dark:text-text-muted/70 mt-2">
                      {filesError}
                    </p>
                    <button
                      onClick={fetchFiles}
                      className="mt-4 px-4 py-2 rounded-lg bg-primary/10 hover:bg-primary/20 transition-colors text-sm font-medium"
                      style={{ color: 'var(--color-primary)' }}
                    >
                      Retry
                    </button>
                  </div>
                ) : files.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-16 text-center">
                    <FolderOpen className="w-16 h-16 text-gray-300 dark:text-text-muted/30 mb-4" />
                    <p className="text-lg font-medium text-gray-600 dark:text-text-muted">
                      No files generated
                    </p>
                    <p className="text-sm text-gray-500 dark:text-text-muted/70 mt-2">
                      This workflow didn't create any output files.
                    </p>
                  </div>
                ) : (
                  <>
                    <div className="mb-4">
                      <p className="text-sm text-gray-600 dark:text-text-muted">
                        Click a file to preview. {files.length} file{files.length !== 1 ? 's' : ''} generated.
                      </p>
                    </div>
                    <div className="space-y-2">
                      {files.map((file, index) => (
                        <div
                          key={index}
                          onClick={() => handleFileSelect(file)}
                          className={`flex items-center justify-between p-4 rounded-lg border cursor-pointer transition-all ${
                            selectedPreviewFile?.path === file.path
                              ? 'border-primary/50 bg-primary/5 ring-2 ring-primary/20'
                              : 'border-gray-200 dark:border-border-dark hover:bg-gray-50 dark:hover:bg-white/5'
                          }`}
                        >
                          <div className="flex items-center gap-3 flex-1 min-w-0">
                            <span className="text-2xl flex-shrink-0">{getFileIcon(file.extension)}</span>
                            <div className="flex-1 min-w-0">
                              <p className="font-medium text-gray-900 dark:text-white truncate">
                                {file.filename}
                              </p>
                              <div className="flex items-center gap-3 text-xs text-gray-500 dark:text-text-muted mt-1">
                                <span>{file.size_human}</span>
                                <span>•</span>
                                <span>{new Date(file.modified_at).toLocaleDateString()}</span>
                                {file.extension && (
                                  <>
                                    <span>•</span>
                                    <span className="uppercase">{file.extension.replace('.', '')}</span>
                                  </>
                                )}
                              </div>
                            </div>
                          </div>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDownloadFile(file.filename);
                            }}
                            className="ml-4 px-3 py-2 rounded-lg bg-gray-100 dark:bg-white/5 hover:bg-gray-200 dark:hover:bg-white/10 transition-colors flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-text-muted"
                            title="Download file"
                          >
                            <Download className="w-4 h-4" />
                            {!selectedPreviewFile && 'Download'}
                          </button>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </div>

              {/* Preview Panel */}
              {selectedPreviewFile && (
                <InlineFilePreview
                  file={selectedPreviewFile}
                  content={filePreviewContent}
                  loading={filePreviewLoading}
                  onClose={closeFilePreview}
                  onDownload={handleDownloadFile}
                />
              )}
            </div>
          )}
        </div>

        {/* Execution Log Replay Panel */}
        <RealtimeExecutionPanel
          isVisible={showReplayPanel}
          events={replayEvents}
          latestEvent={replayEvents.length > 0 ? replayEvents[replayEvents.length - 1] : null}
          onClose={() => {
            setShowReplayPanel(false);
            setReplayTaskId(null);
          }}
          isReplay={true}
          executionStatus={executionStatus}
          workflowMetrics={undefined}
          userPrompt={undefined}
          workflowName={workflowName}
        />
      </div>
    </div>
  );
});

export default WorkflowResults;
