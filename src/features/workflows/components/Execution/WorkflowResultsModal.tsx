/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * Workflow Results Modal
 *
 * Large, beautiful modal that displays workflow execution results.
 * Auto-opens when workflow completes successfully.
 *
 * Features:
 * - Full-screen modal with formatted output
 * - Tabs for Output, Events, and Metrics
 * - Copy output button
 * - Download as markdown
 * - Close/minimize to monitoring panel
 */

import { useState, useEffect, useMemo } from 'react';
import { X, Minimize2, Download, Copy, Check, Activity, BarChart3, FileText, Eye, FileText as FileIcon, FolderOpen, Trash2, Edit3, Search, ArrowUpDown, ClipboardCopy } from 'lucide-react';
import FormattedOutputViewer, { FormattedOutput } from './output/FormattedOutputViewer';
import { WorkflowEvent } from '../types/events';
import ExecutionEventLog from './ExecutionEventLog';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';

interface WorkflowResultsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onMinimize?: () => void;
  onViewLiveExecution?: () => void; // New: Navigate to live execution panel
  formattedOutput: FormattedOutput | null;
  events: WorkflowEvent[];
  metrics: {
    totalEvents: number;
    chainEnds: number;
    toolCalls: number;
    agentActions: number;
    llmCalls: number;
    totalTokens: number;
    duration: string;
    errors: number;
  };
  workflowSummary?: {
    tool_calls_by_agent: Record<string, Array<{ tool: string; timestamp: string | null }>>;
    tokens_by_agent: Record<string, { tokens: number; model: string; calls: number; estimated_cost_usd: number }>;
    total_tool_calls: number;
    total_tokens: number;
    total_cost_usd: number;
  };
  workflowName?: string;
  taskId?: number;
}

type TabType = 'output' | 'events' | 'metrics' | 'diagnostics' | 'files';

interface TaskFile {
  filename: string;
  path: string;
  size_bytes: number;
  size_human: string;
  modified_at: string;
  extension: string;
  task_id?: number;
}

interface FileContent {
  filename: string;
  content: string | null;
  mime_type: string;
  is_binary: boolean;
  truncated: boolean;
  size_bytes: number;
}

// File type icons
const getFileIcon = (extension: string): string => {
  const ext = extension.toLowerCase().replace('.', '');
  const icons: Record<string, string> = {
    md: '📝',
    txt: '📄',
    json: '📊',
    csv: '📊',
    py: '🐍',
    js: '💛',
    ts: '💙',
    tsx: '💙',
    jsx: '💛',
    html: '🌐',
    css: '🎨',
    sql: '🗃️',
    yaml: '⚙️',
    yml: '⚙️',
    xml: '📋',
    log: '📜',
    pdf: '📕',
    png: '🖼️',
    jpg: '🖼️',
    jpeg: '🖼️',
    gif: '🖼️',
    svg: '🎨',
  };
  return icons[ext] || '📄';
};

// Get language for syntax highlighting
const getLanguage = (extension: string): string => {
  const ext = extension.toLowerCase().replace('.', '');
  const languages: Record<string, string> = {
    py: 'python',
    js: 'javascript',
    ts: 'typescript',
    tsx: 'tsx',
    jsx: 'jsx',
    json: 'json',
    html: 'html',
    css: 'css',
    sql: 'sql',
    yaml: 'yaml',
    yml: 'yaml',
    xml: 'xml',
    sh: 'bash',
    bash: 'bash',
  };
  return languages[ext] || 'text';
};

export default function WorkflowResultsModal({
  isOpen,
  onClose,
  onMinimize,
  onViewLiveExecution,
  formattedOutput,
  events,
  metrics,
  workflowSummary,
  workflowName,
  taskId
}: WorkflowResultsModalProps) {
  const [activeTab, setActiveTab] = useState<TabType>('output');
  const [copied, setCopied] = useState(false);
  const [files, setFiles] = useState<TaskFile[]>([]);
  const [filesLoading, setFilesLoading] = useState(false);
  const [filesError, setFilesError] = useState<string | null>(null);

  // Enhanced Files tab state
  const [selectedFile, setSelectedFile] = useState<TaskFile | null>(null);
  const [fileContent, setFileContent] = useState<FileContent | null>(null);
  const [fileContentLoading, setFileContentLoading] = useState(false);
  const [fileSearch, setFileSearch] = useState('');
  const [fileSortBy, setFileSortBy] = useState<'name' | 'date' | 'size'>('date');
  const [fileSortDesc, setFileSortDesc] = useState(true);
  const [renamingFile, setRenamingFile] = useState<string | null>(null);
  const [newFileName, setNewFileName] = useState('');
  const [deleteConfirmFile, setDeleteConfirmFile] = useState<string | null>(null);
  const [pathCopied, setPathCopied] = useState(false);

  // Fetch files when modal opens and taskId is available
  useEffect(() => {
    if (isOpen && taskId) {
      fetchFiles();
    }
  }, [isOpen, taskId]);

  const fetchFiles = async () => {
    if (!taskId) return;

    setFilesLoading(true);
    setFilesError(null);

    try {
      const response = await fetch(`/api/workspace/tasks/${taskId}/files`);
      if (!response.ok) {
        throw new Error('Failed to fetch files');
      }

      const data = await response.json();
      setFiles(data.files || []);
    } catch (error) {
      console.error('Error fetching files:', error);
      setFilesError(error instanceof Error ? error.message : 'Failed to load files');
    } finally {
      setFilesLoading(false);
    }
  };

  const handleDownloadFile = (filename: string) => {
    if (!taskId) return;
    window.open(`/api/workspace/tasks/${taskId}/files/${filename}`, '_blank');
  };

  // Fetch file content for preview
  const fetchFileContent = async (file: TaskFile) => {
    if (!taskId) return;

    setFileContentLoading(true);
    try {
      const response = await fetch(`/api/workspace/tasks/${taskId}/files/${file.filename}/content`);
      if (!response.ok) throw new Error('Failed to fetch content');
      const data = await response.json();
      setFileContent(data);
    } catch (error) {
      console.error('Error fetching file content:', error);
      setFileContent(null);
    } finally {
      setFileContentLoading(false);
    }
  };

  // Handle file selection
  const handleFileSelect = (file: TaskFile) => {
    setSelectedFile(file);
    fetchFileContent(file);
  };

  // Rename file
  const handleRenameFile = async (oldName: string, newName: string) => {
    if (!taskId || !newName.trim()) return;

    try {
      const response = await fetch(`/api/workspace/tasks/${taskId}/files/${oldName}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ new_name: newName.trim() })
      });

      if (!response.ok) throw new Error('Failed to rename file');

      // Refresh file list
      await fetchFiles();
      setRenamingFile(null);
      setNewFileName('');

      // Update selected file if it was renamed
      if (selectedFile?.filename === oldName) {
        setSelectedFile(prev => prev ? { ...prev, filename: newName.trim() } : null);
      }
    } catch (error) {
      console.error('Error renaming file:', error);
      alert('Failed to rename file. The new name may already exist.');
    }
  };

  // Delete file
  const handleDeleteFile = async (filename: string) => {
    if (!taskId) return;

    try {
      const response = await fetch(`/api/workspace/tasks/${taskId}/files/${filename}`, {
        method: 'DELETE'
      });

      if (!response.ok) throw new Error('Failed to delete file');

      // Refresh file list
      await fetchFiles();
      setDeleteConfirmFile(null);

      // Clear selection if deleted file was selected
      if (selectedFile?.filename === filename) {
        setSelectedFile(null);
        setFileContent(null);
      }
    } catch (error) {
      console.error('Error deleting file:', error);
      alert('Failed to delete file.');
    }
  };

  // Copy file path
  const handleCopyPath = async (path: string) => {
    await navigator.clipboard.writeText(path);
    setPathCopied(true);
    setTimeout(() => setPathCopied(false), 2000);
  };

  // Filter and sort files
  const filteredAndSortedFiles = useMemo(() => {
    let result = [...files];

    // Filter by search
    if (fileSearch.trim()) {
      const search = fileSearch.toLowerCase();
      result = result.filter(f => f.filename.toLowerCase().includes(search));
    }

    // Sort
    result.sort((a, b) => {
      let comparison = 0;
      switch (fileSortBy) {
        case 'name':
          comparison = a.filename.localeCompare(b.filename);
          break;
        case 'date':
          comparison = new Date(a.modified_at).getTime() - new Date(b.modified_at).getTime();
          break;
        case 'size':
          comparison = a.size_bytes - b.size_bytes;
          break;
      }
      return fileSortDesc ? -comparison : comparison;
    });

    return result;
  }, [files, fileSearch, fileSortBy, fileSortDesc]);

  if (!isOpen) return null;

  const handleCopy = async () => {
    if (formattedOutput?.formatted_content) {
      await navigator.clipboard.writeText(formattedOutput.formatted_content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleDownload = () => {
    if (formattedOutput?.formatted_content) {
      const blob = new Blob([formattedOutput.formatted_content], { type: 'text/markdown' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${workflowName || 'workflow'}-result-${taskId || Date.now()}.md`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-background-light dark:bg-background-dark rounded-xl shadow-2xl w-full max-w-6xl max-h-[90vh] flex flex-col border border-gray-200 dark:border-border-dark">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-border-dark">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-green-500/10 flex items-center justify-center">
              <Check className="w-6 h-6 text-green-600 dark:text-green-400" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-gray-900 dark:text-white">
                Workflow Completed
              </h2>
              <p className="text-sm text-gray-600 dark:text-text-muted">
                {workflowName || 'Untitled Workflow'} {taskId && `(Task #${taskId})`}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Action Buttons */}
            <button
              onClick={handleCopy}
              className="px-3 py-2 rounded-lg bg-gray-100 dark:bg-white/5 hover:bg-gray-200 dark:hover:bg-white/10 transition-colors flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-text-muted"
              title="Copy to clipboard"
            >
              {copied ? (
                <>
                  <Check className="w-4 h-4 text-green-600" />
                  Copied!
                </>
              ) : (
                <>
                  <Copy className="w-4 h-4" />
                  Copy
                </>
              )}
            </button>

            <button
              onClick={handleDownload}
              className="px-3 py-2 rounded-lg bg-gray-100 dark:bg-white/5 hover:bg-gray-200 dark:hover:bg-white/10 transition-colors flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-text-muted"
              title="Download as markdown"
            >
              <Download className="w-4 h-4" />
              Download
            </button>

            {onViewLiveExecution && (
              <button
                onClick={onViewLiveExecution}
                className="px-3 py-2 rounded-lg bg-primary/10 hover:bg-primary/20 transition-colors flex items-center gap-2 text-sm font-medium"
                style={{ color: 'var(--color-primary)' }}
                title="View detailed execution with agent reasoning and tool calls"
              >
                <Eye className="w-4 h-4" />
                View Live Execution
              </button>
            )}

            {onMinimize && (
              <button
                onClick={onMinimize}
                className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-white/5 transition-colors"
                title="Minimize to monitoring panel"
              >
                <Minimize2 className="w-5 h-5 text-gray-600 dark:text-text-muted" />
              </button>
            )}

            <button
              onClick={onClose}
              className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-white/5 transition-colors"
              title="Close"
            >
              <X className="w-5 h-5 text-gray-600 dark:text-text-muted" />
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-gray-200 dark:border-border-dark px-6 bg-background-light dark:bg-panel-dark">
          <button
            onClick={() => setActiveTab('output')}
            className={`px-4 py-3 text-sm font-semibold border-b-2 transition-all ${activeTab === 'output'
              ? 'border-primary text-primary'
              : 'border-transparent text-gray-600 dark:text-text-muted hover:text-gray-900 dark:hover:text-white hover:border-gray-300 dark:hover:border-white/20'
              }`}
          >
            <FileText className="w-4 h-4 inline mr-2" />
            Output
          </button>
          <button
            onClick={() => setActiveTab('events')}
            className={`px-4 py-3 text-sm font-semibold border-b-2 transition-all ${activeTab === 'events'
              ? 'border-primary text-primary'
              : 'border-transparent text-gray-600 dark:text-text-muted hover:text-gray-900 dark:hover:text-white hover:border-gray-300 dark:hover:border-white/20'
              }`}
          >
            <Activity className="w-4 h-4 inline mr-2" />
            Events ({events.length})
          </button>
          <button
            onClick={() => setActiveTab('metrics')}
            className={`px-4 py-3 text-sm font-semibold border-b-2 transition-all ${activeTab === 'metrics'
              ? 'border-primary text-primary'
              : 'border-transparent text-gray-600 dark:text-text-muted hover:text-gray-900 dark:hover:text-white hover:border-gray-300 dark:hover:border-white/20'
              }`}
          >
            <BarChart3 className="w-4 h-4 inline mr-2" />
            Metrics
          </button>
          <button
            onClick={() => setActiveTab('diagnostics')}
            className={`px-4 py-3 text-sm font-semibold border-b-2 transition-all ${activeTab === 'diagnostics'
              ? 'border-primary text-primary'
              : 'border-transparent text-gray-600 dark:text-text-muted hover:text-gray-900 dark:hover:text-white hover:border-gray-300 dark:hover:border-white/20'
              }`}
          >
            <FileText className="w-4 h-4 inline mr-2" />
            Diagnostics
          </button>
          <button
            onClick={() => setActiveTab('files')}
            className={`px-4 py-3 text-sm font-semibold border-b-2 transition-all ${activeTab === 'files'
              ? 'border-primary text-primary'
              : 'border-transparent text-gray-600 dark:text-text-muted hover:text-gray-900 dark:hover:text-white hover:border-gray-300 dark:hover:border-white/20'
              }`}
          >
            <FolderOpen className="w-4 h-4 inline mr-2" />
            Files ({files.length})
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {activeTab === 'output' && (
            <div>
              {formattedOutput ? (
                <FormattedOutputViewer
                  output={formattedOutput}
                  showMetadata={true}
                  showNavigation={true}
                  className="shadow-none"
                />
              ) : (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <FileText className="w-16 h-16 text-gray-300 dark:text-text-muted/30 mb-4" />
                  <p className="text-lg font-medium text-gray-600 dark:text-text-muted">
                    No output available
                  </p>
                  <p className="text-sm text-gray-500 dark:text-text-muted/70 mt-2">
                    The workflow completed but did not produce any output.
                  </p>
                </div>
              )}
            </div>
          )}

          {activeTab === 'events' && (
            <ExecutionEventLog events={events} />
          )}

          {activeTab === 'diagnostics' && (
            <div className="space-y-4">
              <p className="text-sm text-gray-600 dark:text-text-muted">
                Raw streamed content (including internal reasoning and tool blocks). For auditing and debugging only.
              </p>
              <pre className="text-xs bg-gray-50 dark:bg-white/5 p-3 rounded border border-gray-200 dark:border-border-dark overflow-auto max-h-[60vh] whitespace-pre-wrap break-words">
                {events
                  .filter(e => e.type === 'on_chat_model_stream')
                  .map(e => e.data?.token || e.data?.content || '')
                  .join('')}
              </pre>
            </div>
          )}

          {activeTab === 'metrics' && (
            <div className="space-y-6">
              {/* Summary Cards */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-purple-50 dark:bg-purple-900/20 rounded-lg p-4 border border-purple-100 dark:border-purple-800/30">
                  <div className="text-xs font-semibold text-purple-600 dark:text-purple-400 mb-2 uppercase tracking-wide">
                    Total Tool Calls
                  </div>
                  <div className="text-3xl font-bold text-purple-900 dark:text-purple-100">
                    {workflowSummary?.total_tool_calls || metrics.toolCalls}
                  </div>
                </div>

                <div className="bg-orange-50 dark:bg-orange-900/20 rounded-lg p-4 border border-orange-100 dark:border-orange-800/30">
                  <div className="text-xs font-semibold text-orange-600 dark:text-orange-400 mb-2 uppercase tracking-wide">
                    Total Tokens
                  </div>
                  <div className="text-3xl font-bold text-orange-900 dark:text-orange-100">
                    {(workflowSummary?.total_tokens || metrics.totalTokens).toLocaleString()}
                  </div>
                </div>

                <div className="bg-green-50 dark:bg-green-900/20 rounded-lg p-4 border border-green-100 dark:border-green-800/30">
                  <div className="text-xs font-semibold text-green-600 dark:text-green-400 mb-2 uppercase tracking-wide">
                    Estimated Cost
                  </div>
                  <div className="text-3xl font-bold text-green-900 dark:text-green-100">
                    ${workflowSummary?.total_cost_usd?.toFixed(4) || '0.0000'}
                  </div>
                </div>

                <div className="bg-gray-50 dark:bg-white/5 rounded-lg p-4 border border-gray-200 dark:border-border-dark">
                  <div className="text-xs font-semibold text-gray-600 dark:text-text-muted mb-2 uppercase tracking-wide">
                    Duration
                  </div>
                  <div className="text-3xl font-bold text-gray-900 dark:text-white">
                    {metrics.duration}
                  </div>
                </div>
              </div>

              {/* Agent Breakdown */}
              {workflowSummary && (
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Execution Breakdown by Agent</h3>

                  {Object.entries(workflowSummary.tokens_by_agent).map(([agentName, data]) => {
                    const toolCalls = workflowSummary.tool_calls_by_agent[agentName] || [];

                    return (
                      <div key={agentName} className="bg-white dark:bg-panel-dark rounded-lg p-4 border border-gray-200 dark:border-border-dark">
                        <div className="flex items-start justify-between mb-3">
                          <div>
                            <h4 className="font-semibold text-gray-900 dark:text-white">{agentName}</h4>
                            <p className="text-sm text-gray-600 dark:text-text-muted">{data.model}</p>
                          </div>
                          <div className="text-right">
                            <div className="text-lg font-bold text-green-600 dark:text-green-400">
                              ${data.estimated_cost_usd.toFixed(4)}
                            </div>
                            <div className="text-xs text-gray-600 dark:text-text-muted">
                              {data.tokens.toLocaleString()} tokens
                            </div>
                          </div>
                        </div>

                        {/* Tool Calls */}
                        {toolCalls.length > 0 && (
                          <div className="mt-3 pt-3 border-t border-gray-200 dark:border-border-dark">
                            <div className="text-xs font-semibold text-gray-600 dark:text-text-muted mb-2 uppercase tracking-wide">
                              Tool Calls ({toolCalls.length})
                            </div>
                            <div className="flex flex-wrap gap-2">
                              {toolCalls.map((call, idx) => (
                                <div
                                  key={idx}
                                  className="inline-flex items-center gap-1 px-2 py-1 bg-purple-50 dark:bg-purple-900/20 text-purple-700 dark:text-purple-300 rounded text-xs font-medium"
                                >
                                  <span className="material-symbols-outlined text-sm">build</span>
                                  {call.tool}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Stats */}
                        <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                          <div className="bg-gray-50 dark:bg-white/5 rounded px-2 py-1">
                            <span className="text-gray-600 dark:text-text-muted">LLM Calls:</span>{' '}
                            <span className="font-semibold text-gray-900 dark:text-white">{data.calls}</span>
                          </div>
                          <div className="bg-gray-50 dark:bg-white/5 rounded px-2 py-1">
                            <span className="text-gray-600 dark:text-text-muted">Avg Tokens/Call:</span>{' '}
                            <span className="font-semibold text-gray-900 dark:text-white">{Math.round(data.tokens / data.calls)}</span>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {activeTab === 'files' && (
            <div className="h-full">
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
                <div className="flex h-[calc(60vh-2rem)] gap-4">
                  {/* File List Sidebar */}
                  <div className="w-80 flex flex-col border-r border-gray-200 dark:border-border-dark pr-4">
                    {/* Search and Sort */}
                    <div className="flex gap-2 mb-3">
                      <div className="relative flex-1">
                        <Search className="absolute left-2.5 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
                        <input
                          type="text"
                          placeholder="Search files..."
                          value={fileSearch}
                          onChange={(e) => setFileSearch(e.target.value)}
                          className="w-full pl-8 pr-3 py-1.5 text-sm rounded-lg border border-gray-200 dark:border-border-dark bg-white dark:bg-panel-dark focus:outline-none focus:ring-2 focus:ring-primary/50"
                        />
                      </div>
                      <select
                        value={`${fileSortBy}-${fileSortDesc ? 'desc' : 'asc'}`}
                        onChange={(e) => {
                          const [sort, order] = e.target.value.split('-');
                          setFileSortBy(sort as 'name' | 'date' | 'size');
                          setFileSortDesc(order === 'desc');
                        }}
                        className="px-2 py-1.5 text-xs rounded-lg border border-gray-200 dark:border-border-dark bg-white dark:bg-panel-dark focus:outline-none focus:ring-2 focus:ring-primary/50"
                      >
                        <option value="date-desc">Newest</option>
                        <option value="date-asc">Oldest</option>
                        <option value="name-asc">A-Z</option>
                        <option value="name-desc">Z-A</option>
                        <option value="size-desc">Largest</option>
                        <option value="size-asc">Smallest</option>
                      </select>
                    </div>

                    {/* File List */}
                    <div className="flex-1 overflow-y-auto space-y-1">
                      {filteredAndSortedFiles.map((file, index) => (
                        <div
                          key={index}
                          onClick={() => handleFileSelect(file)}
                          className={`p-2.5 rounded-lg cursor-pointer transition-colors ${
                            selectedFile?.filename === file.filename
                              ? 'bg-primary/10 border border-primary/30'
                              : 'hover:bg-gray-50 dark:hover:bg-white/5 border border-transparent'
                          }`}
                        >
                          <div className="flex items-center gap-2">
                            <span className="text-lg">{getFileIcon(file.extension)}</span>
                            <div className="flex-1 min-w-0">
                              <p className="font-medium text-sm text-gray-900 dark:text-white truncate">
                                {file.filename}
                              </p>
                              <p className="text-xs text-gray-500 dark:text-text-muted">
                                {file.size_human} • {new Date(file.modified_at).toLocaleDateString()}
                              </p>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Preview Panel */}
                  <div className="flex-1 flex flex-col min-w-0">
                    {selectedFile ? (
                      <>
                        {/* File Header */}
                        <div className="flex items-center justify-between pb-3 border-b border-gray-200 dark:border-border-dark mb-3">
                          <div className="flex items-center gap-2 min-w-0">
                            <span className="text-xl">{getFileIcon(selectedFile.extension)}</span>
                            {renamingFile === selectedFile.filename ? (
                              <div className="flex items-center gap-2">
                                <input
                                  type="text"
                                  value={newFileName}
                                  onChange={(e) => setNewFileName(e.target.value)}
                                  onKeyDown={(e) => {
                                    if (e.key === 'Enter') handleRenameFile(selectedFile.filename, newFileName);
                                    if (e.key === 'Escape') { setRenamingFile(null); setNewFileName(''); }
                                  }}
                                  autoFocus
                                  className="px-2 py-1 text-sm rounded border border-gray-300 dark:border-border-dark bg-white dark:bg-panel-dark focus:outline-none focus:ring-2 focus:ring-primary/50"
                                />
                                <button
                                  onClick={() => handleRenameFile(selectedFile.filename, newFileName)}
                                  className="px-2 py-1 text-xs bg-primary text-white rounded hover:bg-primary/90"
                                >
                                  Save
                                </button>
                                <button
                                  onClick={() => { setRenamingFile(null); setNewFileName(''); }}
                                  className="px-2 py-1 text-xs text-gray-600 dark:text-text-muted hover:bg-gray-100 dark:hover:bg-white/10 rounded"
                                >
                                  Cancel
                                </button>
                              </div>
                            ) : (
                              <h3 className="font-semibold text-gray-900 dark:text-white truncate">
                                {selectedFile.filename}
                              </h3>
                            )}
                          </div>

                          <div className="flex items-center gap-1">
                            <button
                              onClick={() => { setRenamingFile(selectedFile.filename); setNewFileName(selectedFile.filename); }}
                              className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-white/10 transition-colors"
                              title="Rename"
                            >
                              <Edit3 className="w-4 h-4 text-gray-600 dark:text-text-muted" />
                            </button>
                            <button
                              onClick={() => handleCopyPath(selectedFile.path)}
                              className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-white/10 transition-colors"
                              title="Copy path"
                            >
                              {pathCopied ? (
                                <Check className="w-4 h-4 text-green-600" />
                              ) : (
                                <ClipboardCopy className="w-4 h-4 text-gray-600 dark:text-text-muted" />
                              )}
                            </button>
                            <button
                              onClick={() => handleDownloadFile(selectedFile.filename)}
                              className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-white/10 transition-colors"
                              title="Download"
                            >
                              <Download className="w-4 h-4 text-gray-600 dark:text-text-muted" />
                            </button>
                            {deleteConfirmFile === selectedFile.filename ? (
                              <div className="flex items-center gap-1 ml-2">
                                <span className="text-xs text-red-600">Delete?</span>
                                <button
                                  onClick={() => handleDeleteFile(selectedFile.filename)}
                                  className="px-2 py-1 text-xs bg-red-600 text-white rounded hover:bg-red-700"
                                >
                                  Yes
                                </button>
                                <button
                                  onClick={() => setDeleteConfirmFile(null)}
                                  className="px-2 py-1 text-xs text-gray-600 dark:text-text-muted hover:bg-gray-100 dark:hover:bg-white/10 rounded"
                                >
                                  No
                                </button>
                              </div>
                            ) : (
                              <button
                                onClick={() => setDeleteConfirmFile(selectedFile.filename)}
                                className="p-1.5 rounded hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                                title="Delete"
                              >
                                <Trash2 className="w-4 h-4 text-red-500" />
                              </button>
                            )}
                          </div>
                        </div>

                        {/* File Content Preview */}
                        <div className="flex-1 overflow-auto rounded-lg border border-gray-200 dark:border-border-dark bg-gray-50 dark:bg-black/20">
                          {fileContentLoading ? (
                            <div className="flex items-center justify-center h-full">
                              <div className="animate-spin rounded-full h-8 w-8 border-b-2" style={{ borderColor: 'var(--color-primary)' }}></div>
                            </div>
                          ) : fileContent?.is_binary ? (
                            <div className="flex flex-col items-center justify-center h-full text-center p-6">
                              <span className="text-4xl mb-3">{getFileIcon(selectedFile.extension)}</span>
                              <p className="text-gray-600 dark:text-text-muted">Binary file - preview not available</p>
                              <p className="text-sm text-gray-500 dark:text-text-muted/70 mt-1">
                                {selectedFile.size_human}
                              </p>
                              <button
                                onClick={() => handleDownloadFile(selectedFile.filename)}
                                className="mt-4 px-4 py-2 rounded-lg bg-primary/10 hover:bg-primary/20 transition-colors text-sm font-medium flex items-center gap-2"
                                style={{ color: 'var(--color-primary)' }}
                              >
                                <Download className="w-4 h-4" />
                                Download to view
                              </button>
                            </div>
                          ) : fileContent?.content ? (
                            <div className="p-4">
                              {selectedFile.extension === '.md' ? (
                                <div className="prose prose-sm max-w-none" style={{ color: '#1f2937' }}>
                                  <ReactMarkdown>{fileContent.content}</ReactMarkdown>
                                </div>
                              ) : ['json', 'py', 'js', 'ts', 'tsx', 'jsx', 'html', 'css', 'sql', 'yaml', 'yml', 'xml', 'sh', 'bash'].includes(selectedFile.extension.replace('.', '').toLowerCase()) ? (
                                <SyntaxHighlighter
                                  language={getLanguage(selectedFile.extension)}
                                  style={oneDark}
                                  customStyle={{ margin: 0, borderRadius: '0.5rem', fontSize: '0.8rem' }}
                                  showLineNumbers
                                >
                                  {fileContent.content}
                                </SyntaxHighlighter>
                              ) : (
                                <pre className="text-sm whitespace-pre-wrap break-words font-mono" style={{ color: '#1f2937' }}>
                                  {fileContent.content}
                                </pre>
                              )}
                              {fileContent.truncated && (
                                <div className="mt-4 p-2 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800/30 rounded text-sm text-yellow-800 dark:text-yellow-200">
                                  File content truncated. Download to see full content.
                                </div>
                              )}
                            </div>
                          ) : (
                            <div className="flex items-center justify-center h-full text-gray-500 dark:text-text-muted">
                              Unable to load file content
                            </div>
                          )}
                        </div>
                      </>
                    ) : (
                      <div className="flex flex-col items-center justify-center h-full text-center">
                        <FileIcon className="w-16 h-16 text-gray-300 dark:text-text-muted/30 mb-4" />
                        <p className="text-gray-600 dark:text-text-muted">
                          Select a file to preview
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
