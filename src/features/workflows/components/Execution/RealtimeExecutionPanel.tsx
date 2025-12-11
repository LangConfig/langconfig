/**
 * Copyright (c) 2025 Cade Russell
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * RealtimeExecutionPanel Component
 *
 * Sliding panel from left side that shows detailed real-time workflow execution.
 * Displays agent thinking, tool calls, and diagnostics in a typewriter-style chat interface.
 *
 * Usage:
 *   <RealtimeExecutionPanel
 *     isVisible={!showThinkingStream && executionStatus.state === 'running'}
 *     events={workflowEvents}
 *     onClose={() => setShowThinkingStream(true)}
 *   />
 */

import { useState, useEffect, useRef, useMemo } from 'react';
import { WorkflowEvent } from '../../../../types/events';
// import { ErrorDiagnosis } from '../utils/workflowErrorDetector';
import { PenLine, Wrench, CheckCircle, XCircle, X, ChevronDown, Copy, Check, Search, Activity, ArrowDown, History as HistoryIcon, Maximize2, Minimize2, DollarSign } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { calculateAndFormatCost } from '../../../../utils/modelPricing';
import { SubAgentPanelStack } from './SubAgentPanel';
import { ContentBlockRenderer } from '@/components/common/ContentBlockRenderer';
import type { ContentBlock } from '@/types/content-blocks';

// Helper component for code blocks with copy button
const CodeBlock = ({ language, children }: { language: string, children: string }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(children);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative group rounded-md overflow-hidden my-2">
      <div className="absolute right-2 top-2 z-10 opacity-0 group-hover:opacity-100 transition-opacity">
        <button
          onClick={handleCopy}
          className="p-1.5 rounded bg-gray-700 text-gray-300 hover:bg-gray-600 hover:text-white transition-colors"
          title="Copy code"
        >
          {copied ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4" />}
        </button>
      </div>
      <SyntaxHighlighter
        language={language}
        style={vscDarkPlus}
        customStyle={{ margin: 0, borderRadius: '0.375rem', fontSize: '0.85em' }}
        wrapLongLines={true}
      >
        {children}
      </SyntaxHighlighter>
    </div>
  );
};

// Helper component for collapsible tool calls - River Flow Style
// File icon helper
const getFileIcon = (filename: string): string => {
  const ext = filename.split('.').pop()?.toLowerCase() || '';
  const icons: Record<string, string> = {
    'md': '📝', 'txt': '📄', 'py': '🐍', 'js': '💛', 'ts': '💙', 'tsx': '⚛️', 'jsx': '⚛️',
    'json': '📋', 'html': '🌐', 'css': '🎨', 'sql': '🗃️', 'yaml': '⚙️', 'yml': '⚙️',
    'xml': '📰', 'sh': '💻', 'bash': '💻', 'csv': '📊', 'pdf': '📕', 'png': '🖼️',
    'jpg': '🖼️', 'jpeg': '🖼️', 'gif': '🖼️', 'svg': '🎨'
  };
  return icons[ext] || '📄';
};

// File card component for write_file results
const FileCreatedCard = ({ filename, result }: { filename: string; result: string }) => {
  // Extract file size info from result if available
  const sizeMatch = result.match(/(\d+)\s*characters/i);
  const charCount = sizeMatch ? sizeMatch[1] : null;

  return (
    <div
      className="flex items-center gap-3 p-3 rounded-lg border-2 mt-2"
      style={{
        backgroundColor: 'rgba(16, 185, 129, 0.08)',
        borderColor: 'rgba(16, 185, 129, 0.3)'
      }}
    >
      <div className="text-2xl">{getFileIcon(filename)}</div>
      <div className="flex-1 min-w-0">
        <div className="font-medium text-sm truncate" style={{ color: 'var(--color-text-primary)' }}>
          {filename}
        </div>
        <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
          {charCount ? `${parseInt(charCount).toLocaleString()} characters written` : 'File created successfully'}
        </div>
      </div>
      <CheckCircle className="w-5 h-5 text-emerald-500 flex-shrink-0" />
    </div>
  );
};

const ToolCallItem = ({
  status,
  toolName,
  renderedHeader,
  renderedInput,
  renderedResult,
  contentBlocks,
  artifacts,
  hasMultimodal
}: {
  status: 'running' | 'completed' | 'error';
  toolName: string;
  renderedHeader: string;
  renderedInput: string;
  renderedResult: string;
  /** Multimodal content blocks from MCP tools */
  contentBlocks?: ContentBlock[];
  /** Artifacts for UI display only */
  artifacts?: ContentBlock[];
  /** Whether the result contains multimodal content */
  hasMultimodal?: boolean;
}) => {
  const [isOpen, setIsOpen] = useState(true);

  // Auto-open if completed or error to show result
  useEffect(() => {
    if (status === 'completed' || status === 'error') {
      setIsOpen(true);
    }
  }, [status]);

  return (
    <div
      className="group border-2 rounded-lg overflow-hidden transition-all duration-200 mb-2 shadow-md hover:shadow-lg"
      style={{
        borderColor: status === 'error' ? '#ef4444' : status === 'completed' ? '#6ee7b7' : '#f59e0b',
        background: status === 'error'
          ? 'linear-gradient(135deg, rgba(239, 68, 68, 0.08) 0%, rgba(239, 68, 68, 0.03) 100%)'
          : status === 'completed'
            ? 'linear-gradient(135deg, rgba(110, 231, 183, 0.08) 0%, rgba(110, 231, 183, 0.03) 100%)'
            : 'linear-gradient(135deg, rgba(245, 158, 11, 0.08) 0%, rgba(245, 158, 11, 0.03) 100%)',
        boxShadow: status === 'running' ? '0 0 20px rgba(245, 158, 11, 0.15)' : undefined
      }}
    >
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center gap-2 p-2 hover:bg-gray-50 transition-all duration-200 text-left"
      >
        <div className="flex-shrink-0 p-1 rounded" style={{
          backgroundColor: status === 'error' ? 'rgba(239, 68, 68, 0.2)' : status === 'completed' ? 'rgba(16, 185, 129, 0.2)' : 'rgba(245, 158, 11, 0.2)'
        }}>
          {status === 'running' && <Wrench className="w-3 h-3 animate-spin text-amber-600" />}
          {status === 'completed' && <CheckCircle className="w-3 h-3 text-emerald-600" />}
          {status === 'error' && <XCircle className="w-3 h-3 text-red-600" />}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="font-mono text-xs uppercase tracking-wider" style={{ color: '#000000' }}>Tool</span>
            <span className={`text-xs font-medium ${status === 'running' ? 'text-amber-500' : status === 'completed' ? 'text-emerald-500' : 'text-red-500'}`}>
              {status === 'running' ? 'Running' : status === 'completed' ? 'Done' : 'Failed'}
            </span>
          </div>
          <div className="font-medium text-xs truncate" style={{ color: 'var(--color-text-primary)' }}>
            {renderedHeader}
          </div>
        </div>
        <ChevronDown
          className={`w-3 h-3 transition-transform duration-200 opacity-50 group-hover:opacity-100 ${isOpen ? 'rotate-180' : ''}`}
          style={{ color: 'var(--color-text-muted)' }}
        />
      </button>

      {isOpen && (
        <div className="px-2 pb-2 space-y-2 animate-in slide-in-from-top-1 duration-200 border-t border-white/5 pt-2">
          {renderedInput && (
            <div className="text-xs">
              <div className="font-medium mb-0.5 text-xs" style={{ color: '#000000' }}>Input</div>
              <div className="relative">
                <pre
                  className="code-snippet p-2 rounded-md overflow-x-auto custom-scrollbar text-xs"
                  style={{
                    fontFamily: 'var(--font-family-mono)',
                    color: '#000000'
                  }}
                >
                  {renderedInput}
                </pre>
              </div>
            </div>
          )}

          {(renderedResult || hasMultimodal) && (
            <div className="text-xs">
              <div className="flex items-center gap-1 mb-0.5">
                <ArrowDown className="w-3 h-3 opacity-30" />
                <span className="font-medium text-xs" style={{ color: '#000000' }}>Result</span>
                {hasMultimodal && (
                  <span className="text-xs px-1.5 py-0.5 rounded bg-purple-100 text-purple-700 ml-1">
                    Multimodal
                  </span>
                )}
              </div>

              {/* Render multimodal content blocks first (images, audio, etc.) */}
              {hasMultimodal && contentBlocks && contentBlocks.length > 0 && (
                <div className="my-2">
                  <ContentBlockRenderer blocks={contentBlocks} />
                </div>
              )}

              {/* Render artifacts (UI-only content) */}
              {artifacts && artifacts.length > 0 && (
                <div className="my-2 pt-2 border-t border-gray-200 dark:border-gray-700">
                  <p className="text-xs text-gray-500 dark:text-gray-400 mb-1 font-medium">Generated Content:</p>
                  <ContentBlockRenderer blocks={artifacts} />
                </div>
              )}

              {/* Show file card for write_file completions */}
              {!hasMultimodal && status === 'completed' && ['write_file', 'edit_file', 'file_write', 'create_file'].includes(toolName.toLowerCase()) ? (
                (() => {
                  // Extract filename from input
                  try {
                    const inputJson = JSON.parse(renderedInput);
                    const filename = inputJson.file_path || inputJson.path || inputJson.filename || 'file';
                    // Get just the filename without path
                    const displayName = filename.split('/').pop()?.split('\\').pop() || filename;
                    return <FileCreatedCard filename={displayName} result={renderedResult} />;
                  } catch {
                    return <FileCreatedCard filename="file" result={renderedResult} />;
                  }
                })()
              ) : renderedResult && !hasMultimodal ? (
                <div className="relative">
                  <pre
                    className="p-2 rounded-md overflow-x-auto custom-scrollbar text-xs"
                    style={{
                      backgroundColor: status === 'error' ? 'rgba(239, 68, 68, 0.05)' : 'rgba(16, 185, 129, 0.05)',
                      color: '#000000',
                      fontFamily: 'var(--font-family-mono)',
                      border: '1px solid',
                      borderColor: status === 'error' ? 'rgba(239, 68, 68, 0.2)' : 'rgba(16, 185, 129, 0.2)',
                      maxHeight: '300px'
                    }}
                  >
                    {renderedResult}
                  </pre>
                </div>
              ) : null}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export interface RealtimeExecutionPanelProps {
  /** Whether the panel should be visible */
  isVisible: boolean;

  /** All workflow events to display */
  events: WorkflowEvent[];

  /** Latest event (for live updates) */
  latestEvent?: WorkflowEvent | null;

  /** Callback when panel is closed */
  onClose?: () => void;

  /** Whether this is replay mode (historical events) */
  isReplay?: boolean;

  /** Execution status */
  executionStatus?: {
    state: 'idle' | 'running' | 'completed' | 'failed';
    currentNode?: string;
  };

  /** Live workflow metrics computed from events */
  workflowMetrics?: {
    totalEvents: number;
    chainEnds: number;
    toolCalls: number;
    agentActions: number;
    llmCalls: number;
    totalTokens: number;
    errors: number;
    duration: string;
  };

  /** User's original prompt/query */
  userPrompt?: string | null;

  /** Name of the workflow being executed */
  workflowName?: string;
}

interface SectionItem {
  type: 'thinking' | 'tool_call' | 'output';
  // Clean text used for normal display while streaming
  content?: string;
  // Raw text (includes internal blocks) used in Diagnostics mode
  rawContent?: string;
  finalized?: boolean; // when true, safe to render as Markdown with highlighting
  tool?: {
    toolName: string;
    input: string;
    result?: string;
    status: 'running' | 'completed' | 'error';
    runId?: string; // LangChain run_id for unique tool call matching
    // Multimodal content support from MCP tools
    contentBlocks?: ContentBlock[];
    artifacts?: ContentBlock[];
    hasMultimodal?: boolean;
  };
  id: string;
}

interface AgentSection {
  agentLabel: string;
  nodeId: string;
  items: SectionItem[];
  startTime: string;
  endTime?: string;
}

// Lightweight token sanitizer for normal (non-diagnostics) view
// Only strips well-known hidden tags - be conservative to avoid cutting off content
const stripHiddenTagsFromToken = (t: string): string => {
  // Strip XML thinking/function tags (original behavior)
  return t.replace(/<\/?(?:think|function_results|function_calls|tool_response|system)[^>]*>?/g, '');
};

// Smart truncation for tool inputs - especially for file write operations with large content
const formatToolInput = (toolName: string, input: string | Record<string, any>): string => {
  const MAX_CONTENT_LENGTH = 500; // Max chars to show for file content
  const MAX_TOTAL_LENGTH = 1000; // Max total input length

  // Parse input if it's a string that looks like JSON
  let parsed = input;
  if (typeof input === 'string') {
    try {
      parsed = JSON.parse(input);
    } catch {
      // Not JSON, keep as string
      if (input.length > MAX_TOTAL_LENGTH) {
        return input.slice(0, MAX_TOTAL_LENGTH) + `\n... (${input.length - MAX_TOTAL_LENGTH} more characters)`;
      }
      return input;
    }
  }

  // Handle file write tools specially - truncate content field
  if (typeof parsed === 'object' && parsed !== null) {
    const fileWriteTools = ['write_file', 'edit_file', 'file_write', 'create_file'];
    if (fileWriteTools.includes(toolName.toLowerCase())) {
      const truncated = { ...parsed };
      if (truncated.content && typeof truncated.content === 'string' && truncated.content.length > MAX_CONTENT_LENGTH) {
        const lines = truncated.content.split('\n');
        const lineCount = lines.length;
        const preview = lines.slice(0, 10).join('\n');
        truncated.content = `${preview}\n... (${lineCount} total lines, ${truncated.content.length} characters)`;
      }
      return JSON.stringify(truncated, null, 2);
    }

    // For other tools, just truncate if too long
    const str = JSON.stringify(parsed, null, 2);
    if (str.length > MAX_TOTAL_LENGTH) {
      return str.slice(0, MAX_TOTAL_LENGTH) + `\n... (truncated)`;
    }
    return str;
  }

  return String(input);
};

interface MemorySnapshot {
  timestamp: string;
  eventCount: number;
  estimatedBytes: number;
  agentCount: number;
}

const useMemoryProfiler = (events: WorkflowEvent[]) => {
  const [snapshots, setSnapshots] = useState<MemorySnapshot[]>([]);

  useEffect(() => {
    const estimateSize = (obj: any): number => {
      return JSON.stringify(obj).length; // Rough estimate
    };

    const totalBytes = events.reduce((sum, event) => sum + estimateSize(event), 0);
    const agentCount = new Set(events.map(e => e.data?.agent_label)).size;

    const snapshot: MemorySnapshot = {
      timestamp: new Date().toISOString(),
      eventCount: events.length,
      estimatedBytes: totalBytes,
      agentCount
    };

    setSnapshots(prev => {
      const recent = prev.slice(-100); // Keep last 100 snapshots
      return [...recent, snapshot];
    });
  }, [events.length]);

  return {
    snapshots,
    currentMemoryMB: (snapshots[snapshots.length - 1]?.estimatedBytes || 0) / (1024 * 1024),
    maxMemoryMB: Math.max(...snapshots.map(s => s.estimatedBytes / (1024 * 1024)), 0),
    memoryTrend: snapshots.length > 1
      ? snapshots[snapshots.length - 1].estimatedBytes > snapshots[snapshots.length - 2].estimatedBytes
        ? 'increasing'
        : 'stable'
      : 'unknown'
  };
};

export default function RealtimeExecutionPanel({
  isVisible,
  events,
  latestEvent,
  onClose,
  isReplay = false,
  executionStatus,
  workflowMetrics,
  userPrompt,
  workflowName,
}: RealtimeExecutionPanelProps) {
  // Removed visibleCharCount state - we now always show all content immediately
  const contentRef = useRef<HTMLDivElement>(null);
  const [currentTipIndex, setCurrentTipIndex] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterType, setFilterType] = useState<'all' | 'tool_call' | 'thinking' | 'output'>('all');
  const [isFullScreen, setIsFullScreen] = useState(false); // New Full Screen State
  const [dismissedErrors, setDismissedErrors] = useState<Set<string>>(new Set()); // Track dismissed error IDs

  // Extract workflow errors from events for prominent display
  const workflowErrors = useMemo(() => {
    const errorEvents = events.filter(e => e.type === 'error');
    return errorEvents.map(e => ({
      id: e.idempotency_key || `error-${e.timestamp}`,
      message: (e.data as any)?.error || (e.data as any)?.message || 'Unknown error occurred',
      errorType: (e.data as any)?.error_type || 'Error',
      timestamp: e.timestamp,
      workflowId: (e.data as any)?.workflow_id,
      taskId: (e.data as any)?.task_id
    })).filter(e => !dismissedErrors.has(e.id));
  }, [events, dismissedErrors]);

  // Check if workflow completed with error status
  const workflowFailed = useMemo(() => {
    const completeEvent = events.find(e => e.type === 'complete');
    return completeEvent?.data?.status === 'error';
  }, [events]);

  // Track active subagents from subagent_start/end events
  const activeSubagents = useMemo(() => {
    const subagentMap = new Map<string, {
      id: string;
      label: string;
      parentRunId: string;
      events: WorkflowEvent[];
      status: 'running' | 'completed' | 'error';
      inputPreview: string;
      outputPreview: string;
    }>();

    for (const event of events) {
      // DEBUG: Log all subagent-related events
      if (event.type === 'subagent_start' || event.type === 'subagent_end') {
        console.log('[SUBAGENT EVENT]', event.type, event.data);
      }

      if (event.type === 'subagent_start') {
        const { subagent_name, subagent_run_id, parent_agent_label, parent_run_id, input_preview } = event.data as any;
        console.log('[SUBAGENT PANEL] Creating panel for:', subagent_name, 'run_id:', subagent_run_id);
        subagentMap.set(subagent_run_id, {
          id: subagent_run_id,
          label: subagent_name || 'Subagent',
          parentRunId: parent_run_id || '',
          events: [],
          status: 'running',
          inputPreview: input_preview || '',
          outputPreview: ''
        });
      } else if (event.type === 'subagent_end') {
        const { subagent_run_id, success, output_preview, full_output } = event.data as any;
        const subagent = subagentMap.get(subagent_run_id);
        if (subagent) {
          subagent.status = success ? 'completed' : 'error';
          // Use full_output for complete result, fallback to output_preview
          subagent.outputPreview = full_output || output_preview || '';
        }
      }
      // SUBAGENT EVENT ROUTING: Route events using subagent_run_id field from backend
      // This is the primary routing mechanism - backend now includes subagent_run_id in all events
      else {
        const subagentRunId = (event.data as any)?.subagent_run_id;
        if (subagentRunId && subagentMap.has(subagentRunId)) {
          // This event belongs to a subagent - add to its events array
          subagentMap.get(subagentRunId)!.events.push(event);
          console.log('[SUBAGENT EVENT ROUTED]', event.type, 'to', subagentRunId);
        }
        // Fallback: Route events by parent_run_id matching (legacy behavior)
        else if ((event.data as any)?.parent_run_id) {
          const parentId = (event.data as any).parent_run_id;
          for (const [subId, sub] of subagentMap) {
            if (sub.parentRunId === parentId || subId === parentId) {
              sub.events.push(event);
            }
          }
        }
      }
    }

    console.log('[SUBAGENT SUMMARY]', subagentMap.size, 'subagents,',
      Array.from(subagentMap.values()).map(s => `${s.label}: ${s.events.length} events`).join(', '));

    return Array.from(subagentMap.values());
  }, [events]);

  // Knowledge tips that rotate when panel is idle
  const knowledgeTips = [
    { title: 'Agent Templates', tip: 'LangConfig includes 15 pre-configured agent templates built with LangChain tools. Each specializes in specific tasks like coding, research, testing, or documentation.' },
    { title: 'Workflow Connections', tip: 'Connect agents to create sophisticated pipelines. Information flows through LangGraph\'s state management, allowing agents to collaborate on complex tasks.' },
    { title: 'Knowledge Base RAG', tip: 'Upload PDFs, DOCX files, or code to the Knowledge Base. Agents use LangChain retrievers to search your documents with semantic embeddings during execution.' },
    { title: 'Native Tools', tip: 'Built-in native tools extend agent capabilities: filesystem operations, git integration, github access, web search, sequential thinking, time utilities, memory management, and browser automation.' },
    { title: 'Export Workflows', tip: 'Export workflows as .langconfig files to share with your team, or generate production-ready LangGraph Python code to deploy in your apps.' },
    { title: 'Multi-Model Support', tip: 'Use OpenAI, Anthropic, Google, or local models. Each agent can use a different model, and automatic fallbacks can reduce costs by 40-60%.' },
    { title: 'Real-time Streaming', tip: 'Watch agents think in real-time. The panel displays agent reasoning, tool calls, and outputs as they happen with zero artificial delay.' },
    { title: 'Visual LangGraph', tip: 'Every workflow is a LangGraph state graph. The visual canvas helps you understand agent orchestration patterns before writing code.' },
    { title: 'Local-First Privacy', tip: 'All data stays on your machine. PostgreSQL runs locally via Docker, and only LLM API calls reach external servers. You control everything.' }
  ];

  // Track last processed event index for incremental processing
  const lastProcessedIndexRef = useRef(0);
  const sectionsRef = useRef<Map<string, AgentSection>>(new Map());
  const MAX_VISIBLE_EVENTS = 500; // Circular buffer size

  // Memory profiling
  const memoryProfile = useMemoryProfiler(events);

  // Reset state when events array is cleared (new workflow)
  useEffect(() => {
    if (events.length === 0) {
      lastProcessedIndexRef.current = 0;
      sectionsRef.current.clear();
    } else if (events.length < lastProcessedIndexRef.current) {
      // Events array was replaced with fewer events (e.g., historical load)
      lastProcessedIndexRef.current = 0;
      sectionsRef.current.clear();
    }
  }, [events.length]);

  // Parse events into agent sections (INCREMENTAL - only process new events)
  const agentSections = useMemo(() => {
    const sections = sectionsRef.current;

    // Only process events we haven't seen yet
    const startIndex = lastProcessedIndexRef.current;
    const newEvents = events.slice(startIndex);

    // Circular buffer logic: Trim old sections if we have too many events
    if (events.length > MAX_VISIBLE_EVENTS) {
      // Logic to trim old sections if needed, but for now we rely on maxEvents in useWorkflowStream
      // to keep the events array size manageable. The sections map will grow but it's less memory intensive than the raw events.
      // If we really need to trim sections, we can do it here.
      if (sections.size > 50) {
        const keys = Array.from(sections.keys());
        for (let i = 0; i < keys.length - 20; i++) {
          sections.delete(keys[i]);
        }
      }
    }

    if (newEvents.length === 0) {
      return Array.from(sections.values());
    }

    for (const event of newEvents) {
      // Skip events without proper agent identification
      const agentLabel = event.data?.agent_label;
      const nodeId = event.data?.node_id;

      if (!agentLabel && !nodeId) {
        // Debug warning - always log for tool events since they should always have context
        if (event.type === 'on_tool_start' || event.type === 'on_tool_end') {
          console.warn(
            `[RealtimeExecutionPanel] TOOL EVENT MISSING AGENT CONTEXT - this is a bug:`,
            {
              type: event.type,
              timestamp: event.timestamp,
              tool_name: event.data?.tool_name,
              data: event.data
            }
          );
        } else if (isReplay) {
          console.warn(
            `[RealtimeExecutionPanel] Skipping event without agent context:`,
            {
              type: event.type,
              timestamp: event.timestamp,
              data: event.data
            }
          );
        }
        continue; // Skip events without agent context
      }

      const displayLabel = agentLabel || 'Agent';
      const sectionKey = nodeId || agentLabel || 'default';

      if (!sections.has(sectionKey)) {
        sections.set(sectionKey, {
          agentLabel: displayLabel,
          nodeId: sectionKey,
          items: [],
          startTime: event.timestamp || new Date().toISOString(),
        });
      }

      const section = sections.get(sectionKey)!;

      // Handle different event types
      switch (event.type) {
        case 'on_chain_start':
          section.startTime = event.timestamp || section.startTime;
          break;

        case 'on_chat_model_stream':
          // Add streaming tokens to current thinking item
          const token = event.data?.token || event.data?.content || '';
          const cleaned = stripHiddenTagsFromToken(token);
          const lastItem = section.items[section.items.length - 1];

          if (lastItem?.type === 'thinking') {
            lastItem.rawContent = (lastItem.rawContent || '') + token;
            lastItem.content = (lastItem.content || '') + cleaned;
          } else if (token) {
            section.items.push({
              type: 'thinking',
              content: cleaned,
              rawContent: token,
              finalized: false,
              id: `thinking-${section.items.length}`
            });
          }
          break;

        case 'on_chat_model_end':
          // Mark current thinking item as finalized for markdown render
          let foundThinking = false;
          for (let i = section.items.length - 1; i >= 0; i--) {
            const item = section.items[i];
            if (item.type === 'thinking' && !item.finalized) {
              item.finalized = true;
              foundThinking = true;
              break;
            }
          }

          // FIX FOR HISTORY RECALL: If no thinking item exists (e.g. missing stream events), create one from the end event
          if (!foundThinking && (event.data?.output || event.data?.content)) {
            const content = typeof event.data?.output === 'string'
              ? event.data.output
              : event.data?.content || JSON.stringify(event.data?.output, null, 2);

            if (content) {
              section.items.push({
                type: 'thinking',
                content: stripHiddenTagsFromToken(content),
                rawContent: content,
                finalized: true,
                id: `thinking-restored-${section.items.length}`
              });
            }
          }
          break;

        case 'tool_preparing':
          // Early notification that a tool call is being prepared (JSON streaming)
          // This fires immediately when we detect a tool_use, before the full JSON is ready
          {
            // Finalize any in-progress thinking block
            for (let i = section.items.length - 1; i >= 0; i--) {
              const thinkingItem = section.items[i];
              if (thinkingItem.type === 'thinking' && !thinkingItem.finalized) {
                thinkingItem.finalized = true;
                break;
              }
            }

            const prepToolName = event.data?.tool_name || 'tool';
            const prepRunId = event.data?.run_id;

            // Check if we already have a tool_call for this run_id (avoid duplicates)
            const existingPrep = section.items.find(
              item => item.type === 'tool_call' && item.tool?.runId === prepRunId
            );

            if (!existingPrep) {
              section.items.push({
                type: 'tool_call',
                tool: {
                  toolName: prepToolName,
                  input: 'Preparing...',
                  status: 'running',
                  runId: prepRunId,
                },
                id: `tool-prep-${prepRunId || section.items.length}`
              });
            }
          }
          break;

        case 'on_tool_start':
        case 'tool_start':
          // Full tool start event - update the preparing entry or create new one
          // IMPORTANT: Finalize any in-progress thinking block BEFORE adding tool call
          // This ensures tool calls appear AFTER the thinking content, not in the middle
          for (let i = section.items.length - 1; i >= 0; i--) {
            const thinkingItem = section.items[i];
            if (thinkingItem.type === 'thinking' && !thinkingItem.finalized) {
              thinkingItem.finalized = true;
              break;
            }
          }

          {
            const toolName = event.data?.tool_name || event.data?.name || 'Unknown Tool';
            const rawInput = event.data?.input || (event.data as any)?.inputs || event.data?.input_preview || '';
            const toolRunId = event.data?.run_id; // Unique ID for this tool call

            // Check if we have a "preparing" entry to update
            const existingToolIdx = section.items.findIndex(
              item => item.type === 'tool_call' && item.tool?.runId === toolRunId && item.tool?.input === 'Preparing...'
            );

            if (existingToolIdx >= 0) {
              // Update the existing preparing entry with full info
              const existingTool = section.items[existingToolIdx];
              if (existingTool.tool) {
                existingTool.tool.toolName = toolName;
                existingTool.tool.input = formatToolInput(toolName, rawInput);
              }
            } else {
              // No preparing entry, create new one
              section.items.push({
                type: 'tool_call',
                tool: {
                  toolName,
                  // Use smart formatting to truncate large inputs (especially file content)
                  input: formatToolInput(toolName, rawInput),
                  status: 'running',
                  runId: toolRunId, // Store for matching on_tool_end
                },
                id: `tool-${toolRunId || section.items.length}`
              });
            }
          }
          break;

        case 'on_tool_end':
          // Find the running tool item to update
          // PRIMARY: Match by run_id (unique) if available
          // FALLBACK: Match by tool_name for backwards compatibility
          const endRunId = event.data?.run_id;
          const endToolName = event.data?.tool_name;
          let foundTool = false;

          // Extract multimodal content from MCP tool results
          const eventContentBlocks = event.data?.content_blocks as ContentBlock[] | undefined;
          const eventArtifacts = event.data?.artifacts as ContentBlock[] | undefined;
          const eventHasMultimodal = event.data?.has_multimodal === true;

          for (let i = section.items.length - 1; i >= 0; i--) {
            const item = section.items[i];
            if (item.type === 'tool_call' && item.tool?.status === 'running') {
              // Match by run_id if available (most accurate)
              const matchByRunId = endRunId && item.tool.runId === endRunId;
              // Fallback to tool_name if no run_id match (legacy events or missing run_id)
              const matchByName = !matchByRunId && item.tool.toolName === endToolName;

              if (matchByRunId || matchByName) {
                item.tool.status = 'completed';
                // Truncate large results
                const rawResult = typeof event.data?.output === 'string'
                  ? event.data.output
                  : event.data?.output != null
                    ? JSON.stringify(event.data.output, null, 2)
                    : '';
                const MAX_RESULT_LENGTH = 2000;
                item.tool.result = rawResult && rawResult.length > MAX_RESULT_LENGTH
                  ? rawResult.slice(0, MAX_RESULT_LENGTH) + `\n... (${rawResult.length - MAX_RESULT_LENGTH} more characters)`
                  : rawResult || '';

                // Add multimodal content if present
                if (eventHasMultimodal) {
                  item.tool.contentBlocks = eventContentBlocks;
                  item.tool.artifacts = eventArtifacts;
                  item.tool.hasMultimodal = true;
                }

                foundTool = true;
                break;
              }
            }
          }

          // DEBUG: Log if we couldn't find a matching tool
          if (!foundTool) {
            console.warn('[RealtimeExecutionPanel] on_tool_end could not find matching running tool:', {
              run_id: endRunId,
              tool_name: endToolName,
              section: section.agentLabel,
              runningTools: section.items.filter(i => i.type === 'tool_call' && i.tool?.status === 'running').map(i => ({ name: i.tool?.toolName, runId: i.tool?.runId }))
            });
          }
          break;

        case 'on_agent_finish':
        case 'on_chain_end':
          section.endTime = event.timestamp || new Date().toISOString();
          if (event.data?.output) {
            const outputContent = typeof event.data.output === 'string'
              ? event.data.output
              : JSON.stringify(event.data.output, null, 2);

            section.items.push({
              type: 'output',
              content: outputContent,
              id: `output-${section.items.length}`
            });
          }
          break;

        case 'error':
          // Mark any running tool calls as errored
          section.items.forEach(item => {
            if (item.type === 'tool_call' && item.tool?.status === 'running') {
              item.tool.status = 'error';
              item.tool.result = event.data?.error || 'Unknown error';
            }
          });
          break;
      }
    }

    // Update last processed index
    lastProcessedIndexRef.current = events.length;

    return Array.from(sections.values());
  }, [events]);

  // Filter and Search Logic
  const filteredSections = useMemo(() => {
    let result = agentSections;

    // Apply Type Filter
    if (filterType !== 'all') {
      result = result.map(section => ({
        ...section,
        items: section.items.filter(item => item.type === filterType)
      })).filter(section => section.items.length > 0);
    }

    // Apply Search
    if (searchQuery) {
      const lowerQuery = searchQuery.toLowerCase();
      result = result.map(section => ({
        ...section,
        items: section.items.filter(item => {
          if (item.type === 'thinking') return (item.content || '').toLowerCase().includes(lowerQuery);
          if (item.type === 'tool_call') return (item.tool?.toolName || '').toLowerCase().includes(lowerQuery) || (item.tool?.input || '').toLowerCase().includes(lowerQuery);
          if (item.type === 'output') return (item.content || '').toLowerCase().includes(lowerQuery);
          return false;
        })
      })).filter(section => section.items.length > 0);
    }

    return result;
  }, [agentSections, filterType, searchQuery]);

  // Calculate total text length for typewriter effect
  const totalTextLength = useMemo(() => {
    let length = 0;
    for (const section of filteredSections) {
      length += section.agentLabel.length + 20; // Agent header
      for (const item of section.items) {
        if (item.type === 'thinking' && item.content) {
          length += item.content.length;
        } else if (item.type === 'tool_call' && item.tool) {
          length += item.tool.toolName.length + (item.tool.input?.length || 0) + (item.tool.result?.length || 0) + 50;
        } else if (item.type === 'output' && item.content) {
          length += item.content.length + 20;
        }
      }
    }
    return length;
  }, [filteredSections]);

  // Rotate tips every 5 seconds when idle
  useEffect(() => {
    if (agentSections.length === 0) {
      const interval = setInterval(() => {
        setCurrentTipIndex((prev) => (prev + 1) % knowledgeTips.length);
      }, 5000);
      return () => clearInterval(interval);
    }
  }, [agentSections.length, knowledgeTips.length]);

  // Content is now always shown immediately - no artificial delays or typewriter effect

  // Auto-scroll state
  const [isAutoScroll, setIsAutoScroll] = useState(!isReplay); // Default to false for replay
  const wasAtBottomRef = useRef(!isReplay); // Track if we were at bottom
  const [isScrollable, setIsScrollable] = useState(false); // Track if content is scrollable
  const hasScrolledToTopRef = useRef(false); // Track if we've scrolled to top for replay

  // Handle scroll events to detect user scrolling up
  const handleScroll = () => {
    if (!contentRef.current) return;

    const { scrollTop, scrollHeight, clientHeight } = contentRef.current;
    // More tolerant threshold - 150px instead of 50px for better stickiness
    const isAtBottom = Math.abs(scrollHeight - clientHeight - scrollTop) < 150;

    wasAtBottomRef.current = isAtBottom;
    setIsAutoScroll(isAtBottom);
    setIsScrollable(scrollHeight > clientHeight);
  };

  // Check if content is scrollable whenever content changes
  useEffect(() => {
    if (contentRef.current) {
      const { scrollHeight, clientHeight } = contentRef.current;
      setIsScrollable(scrollHeight > clientHeight);
    }
  }, [totalTextLength, agentSections]);

  // Auto-scroll to bottom (only for live mode)
  useEffect(() => {
    // Always auto-scroll if isAutoScroll is true and we are visible
    if (contentRef.current && isVisible && isAutoScroll) {
      // Use requestAnimationFrame for smoother, more reliable scrolling
      requestAnimationFrame(() => {
        if (contentRef.current) {
          contentRef.current.scrollTop = contentRef.current.scrollHeight;
        }
      });
    }
  }, [isVisible, isAutoScroll, totalTextLength, agentSections]);

  // Scroll to top when in replay mode (historical view)
  useEffect(() => {
    if (isReplay && isVisible && contentRef.current && agentSections.length > 0 && !hasScrolledToTopRef.current) {
      requestAnimationFrame(() => {
        if (contentRef.current) {
          contentRef.current.scrollTop = 0;
          hasScrolledToTopRef.current = true;
        }
      });
    }
  }, [isReplay, isVisible, agentSections.length]);

  // Reset scroll flag when switching modes or content changes
  useEffect(() => {
    if (!isReplay) {
      hasScrolledToTopRef.current = false;
    }
  }, [isReplay]);

  const scrollToBottom = () => {
    if (contentRef.current) {
      contentRef.current.scrollTo({
        top: contentRef.current.scrollHeight,
        behavior: 'smooth'
      });
      setIsAutoScroll(true);
    }
  };


  if (!isVisible) {
    return null;
  }

  // Render text immediately without any character limiting
  const renderTextWithLimit = (text: string, _startIndex: number): { rendered: string; charsUsed: number } => {
    // Always show all content immediately - no artificial typewriter delays
    return { rendered: text, charsUsed: text.length };
  };

  let charIndex = 0;

  return (
    <div
      className={`fixed left-0 top-0 h-full z-50 transition-all duration-300 ease-out shadow-2xl flex flex-col ${isFullScreen ? 'w-full' : 'w-[750px] md:w-[850px]'} ${!isFullScreen ? 'border-r' : ''}`}
      style={{
        transform: isVisible ? 'translateX(0)' : 'translateX(-100%)',
        backgroundColor: 'var(--color-background-light)',
        borderColor: 'var(--color-border-dark)'
      }}
    >
      {/* Header */}
      <div className="flex flex-col border-b flex-shrink-0" style={{
        backgroundColor: 'var(--color-primary)',
        borderBottomColor: 'var(--color-border-dark)'
      }}>
        <div className="flex items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg" style={{
              backgroundColor: 'rgba(255, 255, 255, 0.2)',
              border: '1px solid rgba(255, 255, 255, 0.3)'
            }}>
              {isReplay ? <HistoryIcon className="w-5 h-5 text-white" /> : <Activity className="w-5 h-5 text-white" />}
            </div>
            <div>
              <h2 className="text-lg font-bold flex items-center gap-2 text-white font-display" style={{ textShadow: '0 1px 2px rgba(0, 0, 0, 0.25)' }}>
                {workflowName || (isReplay ? 'Execution History' : 'Live Execution')}
                {isFullScreen && <span className="text-xs px-2 py-0.5 rounded-full text-white" style={{
                  backgroundColor: 'rgba(255, 255, 255, 0.2)',
                  border: '1px solid rgba(255, 255, 255, 0.3)'
                }}>First Person View</span>}
              </h2>
              <div className="text-sm flex items-center gap-2 text-white/90" style={{ textShadow: '0 1px 2px rgba(0, 0, 0, 0.15)' }}>
                {isReplay ? (
                  <span className="flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-white/60"></span>
                    Historical View
                  </span>
                ) : (
                  executionStatus?.state === 'running' ? (
                    <>
                      <span className="relative flex h-2 w-2">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 bg-white"></span>
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-white"></span>
                      </span>
                      {latestEvent?.type === 'on_tool_start' ? `Running tool: ${latestEvent.data.tool_name}...` :
                        latestEvent?.type === 'on_chat_model_stream' ? 'Thinking...' :
                          'Active'}
                    </>
                  ) : (
                    <span className="flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-green-300"></span>
                      Completed
                    </span>
                  )
                )}
              </div>
            </div>
          </div>

          {/* Full Screen Metrics Display */}
          {isFullScreen && workflowMetrics && (
            <div className="hidden md:flex items-center gap-6 px-8 animate-in fade-in duration-300">
              <div className="flex flex-col items-center">
                <span className="text-xs uppercase tracking-wider text-white/60">Duration</span>
                <span className="text-xl font-mono font-bold text-white">{workflowMetrics.duration}</span>
              </div>
              <div className="w-px h-8 bg-white/20" />
              <div className="flex flex-col items-center">
                <span className="text-xs uppercase tracking-wider text-white/60">Tokens</span>
                <span className="text-xl font-mono font-bold text-white">{workflowMetrics.totalTokens.toLocaleString()}</span>
              </div>
              <div className="w-px h-8 bg-white/20" />
              <div className="flex flex-col items-center">
                <span className="text-xs uppercase tracking-wider text-white/60">Est. Cost</span>
                <span className="text-xl font-mono font-bold text-white">
                  {(() => {
                    // Estimate 75% prompt, 25% completion tokens
                    const promptTokens = Math.round(workflowMetrics.totalTokens * 0.75);
                    const completionTokens = Math.round(workflowMetrics.totalTokens * 0.25);
                    return calculateAndFormatCost(promptTokens, completionTokens, 'gpt-4o');
                  })()}
                </span>
              </div>
              <div className="w-px h-8 bg-white/20" />
              <div className="flex flex-col items-center">
                <span className="text-xs uppercase tracking-wider text-white/60">Tools</span>
                <span className="text-xl font-mono font-bold text-white">{workflowMetrics.toolCalls}</span>
              </div>
            </div>
          )}

          <div className="flex items-center gap-2">
            {/* Full Screen Toggle */}
            <button
              onClick={() => setIsFullScreen(!isFullScreen)}
              className="p-2 rounded-md transition-colors text-white/90 hover:text-white hover:bg-white/15"
              style={{ textShadow: '0 1px 2px rgba(0, 0, 0, 0.15)' }}
              title={isFullScreen ? "Exit Full Screen" : "First Person View"}
            >
              {isFullScreen ? <Minimize2 className="w-5 h-5" /> : <Maximize2 className="w-5 h-5" />}
            </button>
            {/* Workflow Metrics */}
            {workflowMetrics && (
              <div className="flex items-center gap-2">
                {workflowMetrics.totalTokens > 0 && (
                  <>
                    <div className="flex items-center gap-1.5 px-2 py-1 rounded text-xs text-white" style={{ backgroundColor: 'rgba(255, 255, 255, 0.15)' }} title="Estimated Cost">
                      <DollarSign className="w-3 h-3" />
                      <span>{(() => {
                        const promptTokens = Math.round(workflowMetrics.totalTokens * 0.75);
                        const completionTokens = Math.round(workflowMetrics.totalTokens * 0.25);
                        return calculateAndFormatCost(promptTokens, completionTokens, 'gpt-4o');
                      })()}</span>
                    </div>
                    <div className="flex items-center gap-1.5 px-2 py-1 rounded text-xs text-white" style={{ backgroundColor: 'rgba(255, 255, 255, 0.15)' }} title="Total Tokens">
                      <span>💬</span>
                      <span>{workflowMetrics.totalTokens.toLocaleString()}</span>
                    </div>
                  </>
                )}
                {workflowMetrics.toolCalls > 0 && (
                  <div className="flex items-center gap-1.5 px-2 py-1 rounded text-xs text-white" style={{ backgroundColor: 'rgba(255, 255, 255, 0.15)' }} title="Tool Calls">
                    <Wrench className="w-3 h-3" />
                    <span>{workflowMetrics.toolCalls}</span>
                  </div>
                )}
                {workflowMetrics.duration !== '0s' && (
                  <div className="flex items-center gap-1.5 px-2 py-1 rounded text-xs text-white" style={{ backgroundColor: 'rgba(255, 255, 255, 0.15)' }} title="Duration">
                    <span>⏱️</span>
                    <span>{workflowMetrics.duration}</span>
                  </div>
                )}
                {workflowMetrics.errors > 0 && (
                  <div className="flex items-center gap-1.5 px-2 py-1 rounded text-xs" style={{ backgroundColor: 'rgba(220,38,38,0.3)', color: '#fca5a5' }} title="Errors">
                    <XCircle className="w-3 h-3" />
                    <span>{workflowMetrics.errors}</span>
                  </div>
                )}
              </div>
            )}

            {/* Memory Indicator */}
            <div className="flex items-center gap-1.5 px-2 py-1 rounded text-xs text-white" style={{ backgroundColor: 'rgba(255, 255, 255, 0.15)' }} title="Memory Usage">
              <Activity className="w-3 h-3" />
              <span>{memoryProfile.currentMemoryMB.toFixed(1)} MB</span>
              {memoryProfile.memoryTrend === 'increasing' && <span className="text-yellow-300">↑</span>}
            </div>

            {onClose && (
              <button
                onClick={onClose}
                className="p-2 rounded-md transition-colors text-white/90 hover:text-white hover:bg-white/15"
                style={{ textShadow: '0 1px 2px rgba(0, 0, 0, 0.15)' }}
                title="Close"
              >
                <X className="w-5 h-5" />
              </button>
            )}
          </div>
        </div>

        {/* User Prompt Display */}
        {
          userPrompt && (
            <div className="px-6 py-3 border-t" style={{ borderColor: 'var(--color-border-dark)', backgroundColor: 'var(--color-panel-dark)' }}>
              <p className="text-xs font-semibold uppercase tracking-wide mb-1" style={{ color: 'var(--color-text-muted)' }}>
                Original Query
              </p>
              <p className="text-sm leading-relaxed" style={{ color: 'var(--color-text-primary)' }}>
                {userPrompt}
              </p>
            </div>
          )
        }

        {/* Search and Filter Bar */}
        <div className="px-6 py-2 flex items-center gap-2 border-t" style={{ borderColor: 'var(--color-border-dark)', backgroundColor: 'var(--color-background-dark)' }}>
          <div className="relative flex-1">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: 'var(--color-text-muted)' }} />
            <input
              type="text"
              placeholder="Search execution logs..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 text-sm rounded-md focus:outline-none focus:ring-1"
              style={{
                backgroundColor: 'var(--color-input-background, rgba(0,0,0,0.2))',
                border: '1px solid var(--color-border-dark)',
                color: 'var(--color-text-primary)',
                borderColor: 'var(--color-border-dark)',
              }}
            />
          </div>
          <div className="flex items-center rounded-md p-0.5 border" style={{ backgroundColor: 'var(--color-input-background, rgba(0,0,0,0.2))', borderColor: 'var(--color-border-dark)' }}>
            {(['all', 'tool_call', 'thinking', 'output'] as const).map((type) => (
              <button
                key={type}
                onClick={() => setFilterType(type)}
                className={`px-2.5 py-1 text-xs font-medium rounded-sm transition-colors`}
                style={{
                  backgroundColor: filterType === type ? 'var(--color-primary)' : 'transparent',
                  color: filterType === type ? 'white' : 'var(--color-text-muted)',
                }}
              >
                {type === 'all' ? 'All' : type === 'tool_call' ? 'Tools' : type.charAt(0).toUpperCase() + type.slice(1)}
              </button>
            ))}
          </div>
        </div>
      </div >

      {/* Error Banner - Prominent dismissable error display */}
      {workflowErrors.length > 0 && (
        <div className="flex-shrink-0 px-4 py-3 space-y-2" style={{ backgroundColor: 'rgba(239, 68, 68, 0.1)', borderBottom: '1px solid rgba(239, 68, 68, 0.3)' }}>
          {workflowErrors.map((error) => (
            <div
              key={error.id}
              className="flex items-start gap-3 p-3 rounded-lg"
              style={{
                backgroundColor: 'rgba(239, 68, 68, 0.15)',
                border: '1px solid rgba(239, 68, 68, 0.4)'
              }}
            >
              <XCircle className="w-5 h-5 flex-shrink-0 mt-0.5" style={{ color: '#ef4444' }} />
              <div className="flex-1 min-w-0">
                <div className="font-semibold text-sm" style={{ color: '#fca5a5' }}>
                  Workflow {error.errorType}
                </div>
                <div className="text-sm mt-1 break-words" style={{ color: 'var(--color-text-primary)' }}>
                  {error.message}
                </div>
              </div>
              <button
                onClick={() => setDismissedErrors(prev => new Set([...prev, error.id]))}
                className="p-1 rounded hover:bg-red-500/20 transition-colors flex-shrink-0"
                title="Dismiss error"
              >
                <X className="w-4 h-4" style={{ color: '#fca5a5' }} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Workflow Failed Banner - Shows when workflow completed with error status */}
      {workflowFailed && workflowErrors.length === 0 && (
        <div className="flex-shrink-0 px-4 py-3" style={{ backgroundColor: 'rgba(239, 68, 68, 0.1)', borderBottom: '1px solid rgba(239, 68, 68, 0.3)' }}>
          <div
            className="flex items-center gap-3 p-3 rounded-lg"
            style={{
              backgroundColor: 'rgba(239, 68, 68, 0.15)',
              border: '1px solid rgba(239, 68, 68, 0.4)'
            }}
          >
            <XCircle className="w-5 h-5 flex-shrink-0" style={{ color: '#ef4444' }} />
            <div className="text-sm font-medium" style={{ color: '#fca5a5' }}>
              Workflow execution failed. Check the logs above for details.
            </div>
          </div>
        </div>
      )}

      {/* Content */}
      < div
        ref={contentRef}
        onScroll={handleScroll}
        className={`flex-1 overflow-y-auto px-6 py-4 space-y-6 custom-scrollbar pb-32 ${isFullScreen ? 'max-w-5xl mx-auto w-full' : ''}`}
        style={{
          scrollBehavior: 'smooth',
        }}
      >
        {
          filteredSections.length === 0 ? (
            <div className="flex flex-col h-full text-left px-8 py-12 space-y-6">
              {searchQuery ? (
                <div className="text-center mt-20" style={{ color: 'var(--color-text-muted)' }}>
                  <Search className="w-12 h-12 mx-auto mb-4 opacity-20" />
                  <p>No results found for "{searchQuery}"</p>
                  <button
                    onClick={() => setSearchQuery('')}
                    className="mt-2 text-sm hover:underline"
                    style={{ color: 'var(--color-primary)' }}
                  >
                    Clear search
                  </button>
                </div>
              ) : (
                <>
                  <div>
                    <h3 className="text-2xl font-bold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                      Live Execution Panel
                    </h3>
                    <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
                      Real-time workflow execution monitoring and debugging
                    </p>
                  </div>

                  <div className="space-y-4">
                    <div className="p-4 rounded-lg" style={{ backgroundColor: 'var(--color-panel-dark)', border: '1px solid var(--color-border-dark)' }}>
                      <h4 className="text-sm font-semibold mb-2 flex items-center gap-2" style={{ color: 'var(--color-text-primary)' }}>
                        <span className="material-symbols-outlined text-base" style={{ color: 'var(--color-primary)' }}>help</span>
                        What does this panel show?
                      </h4>
                      <p className="text-xs leading-relaxed" style={{ color: 'var(--color-text-muted)' }}>
                        This panel displays live execution details as your workflow runs, including agent reasoning, tool calls, and outputs in real-time.
                      </p>
                    </div>

                    <div className="p-4 rounded-lg" style={{ backgroundColor: 'var(--color-panel-dark)', border: '1px solid var(--color-border-dark)' }}>
                      <h4 className="text-sm font-semibold mb-2 flex items-center gap-2" style={{ color: 'var(--color-text-primary)' }}>
                        <span className="material-symbols-outlined text-base" style={{ color: 'var(--color-primary)' }}>play_circle</span>
                        How do I start?
                      </h4>
                      <p className="text-xs leading-relaxed" style={{ color: 'var(--color-text-muted)' }}>
                        Click the green <strong>Run Workflow</strong> button in the toolbar to execute your workflow. The panel will automatically populate with execution details.
                      </p>
                    </div>

                    <div className="p-4 rounded-lg" style={{ backgroundColor: 'var(--color-panel-dark)', border: '1px solid var(--color-border-dark)' }}>
                      <h4 className="text-sm font-semibold mb-2 flex items-center gap-2" style={{ color: 'var(--color-text-primary)' }}>
                        <span className="material-symbols-outlined text-base" style={{ color: 'var(--color-primary)' }}>psychology</span>
                        Thinking vs Panel
                      </h4>
                      <p className="text-xs leading-relaxed" style={{ color: 'var(--color-text-muted)' }}>
                        <strong>Thinking toasts</strong> show brief status updates on the canvas. This <strong>Panel</strong> shows complete, detailed execution logs with full context.
                      </p>
                    </div>
                  </div>

                  {/* Rotating Knowledge Tips */}
                  <div className="mt-auto pt-6 border-t" style={{ borderColor: 'var(--color-border-dark)' }}>
                    <div className="mb-4">
                      <p className="text-xs font-semibold mb-1" style={{ color: 'var(--color-text-primary)' }}>
                        Did you know?
                      </p>
                      <div
                        key={currentTipIndex}
                        className="p-4 rounded-lg animate-in fade-in slide-in-from-bottom-2 duration-500"
                        style={{
                          backgroundColor: 'var(--color-background-light)',
                          border: '1px solid var(--color-border-dark)'
                        }}
                      >
                        <div>
                          <h5 className="text-sm font-bold mb-1" style={{ color: 'var(--color-text-primary)' }}>
                            {knowledgeTips[currentTipIndex].title}
                          </h5>
                          <p className="text-xs leading-relaxed" style={{ color: 'var(--color-text-muted)' }}>
                            {knowledgeTips[currentTipIndex].tip}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center justify-center gap-1.5 mt-3">
                        {knowledgeTips.map((tip, index) => (
                          <button
                            key={tip.title}
                            onClick={() => setCurrentTipIndex(index)}
                            className="transition-all duration-300"
                            style={{
                              width: currentTipIndex === index ? '24px' : '6px',
                              height: '6px',
                              borderRadius: '3px',
                              backgroundColor: currentTipIndex === index ? 'var(--color-primary)' : 'var(--color-border-dark)',
                              opacity: currentTipIndex === index ? 1 : 0.5
                            }}
                            aria-label={`Go to tip ${index + 1}`}
                          />
                        ))}
                      </div>
                    </div>
                    <p className="text-xs text-center" style={{ color: 'var(--color-text-muted)' }}>
                      <strong>Tip:</strong> You can auto-scroll by staying at the bottom, or scroll up to pause and review earlier steps.
                    </p>
                  </div>
                </>
              )}
            </div>
          ) : (
            <>
            {filteredSections.map((section, sectionIdx) => {
              return (
                <div
                  key={`${section.nodeId}-${sectionIdx}`}
                  className="space-y-2 p-3 mb-3 rounded-lg last:mb-0 transition-all duration-200 shadow-sm"
                  style={{
                    backgroundColor: 'white',
                    border: '1px solid var(--color-border-dark)'
                  }}
                >
                  {/* Agent Header */}
                  <div className="flex items-center gap-2 pb-2 border-b" style={{ borderColor: 'var(--color-border-dark)' }}>
                    <div
                      className="w-7 h-7 rounded-md flex items-center justify-center"
                      style={{
                        background: section.endTime ? '#10b981' : 'var(--color-primary)'
                      }}
                    >
                      <PenLine className="w-4 h-4 text-white" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="font-semibold text-sm truncate" style={{
                        color: 'var(--color-text-primary)',
                        fontFamily: 'var(--font-family-display)'
                      }}>
                        {(() => {
                          const headerText = section.agentLabel;
                          const result = renderTextWithLimit(headerText, charIndex);
                          charIndex += result.charsUsed;
                          return result.rendered;
                        })()}
                      </h3>
                      <p className="text-xs flex items-center gap-1 truncate" style={{ color: 'var(--color-text-muted)' }}>
                        <span className="inline-block w-1 h-1 rounded-full" style={{
                          backgroundColor: section.endTime ? '#10b981' : 'var(--color-primary)',
                          animation: section.endTime ? 'none' : 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite'
                        }}></span>
                        {new Date(section.startTime).toLocaleTimeString()}
                      </p>
                    </div>
                    {section.endTime && (
                      <CheckCircle className="w-4 h-4" style={{ color: '#10b981' }} />
                    )}
                  </div>

                  {/* Stream Items (Interleaved Thinking, Tools, Output) */}
                  <div className="space-y-2">
                    {section.items.map((item) => {
                      // Thinking & Output
                      if (item.type === 'thinking' || item.type === 'output') {
                        if (!item.content && !item.rawContent) return null;

                        const base = item.content || '';
                        const result = renderTextWithLimit(base, charIndex);
                        charIndex += result.charsUsed;
                        if (!result.rendered) return null;

                        // Always render markdown - modern browsers handle re-parsing well
                        // This gives a much better live preview experience
                        return (
                          <div
                            key={item.id}
                            className="prose prose-slate max-w-none"
                            style={{
                              color: 'var(--color-text-primary)',
                              fontFamily: 'var(--font-family-sans)'
                            }}
                          >
                            <ReactMarkdown
                              remarkPlugins={[remarkGfm]}
                              components={{
                                code: ({ node, inline, className, children, ...props }: any) => {
                                  const match = /language-(\w+)/.exec(className || '');
                                  const language = match ? match[1] : 'text';
                                  if (!inline && match) {
                                    return <CodeBlock language={language}>{String(children).replace(/\n$/, '')}</CodeBlock>;
                                  }
                                  return (
                                    <code className="px-1.5 py-0.5 rounded text-sm font-mono" style={{
                                      backgroundColor: 'var(--color-background-light)',
                                      color: 'var(--color-primary)'
                                    }} {...props}>
                                      {children}
                                    </code>
                                  );
                                },
                                h1: ({ children }: any) => (
                                  <h1 className="text-3xl font-bold mt-8 mb-4 border-b-2 pb-2" style={{ color: 'var(--color-text-primary)', borderColor: 'var(--color-border-dark)' }}>
                                    {children}
                                  </h1>
                                ),
                                h2: ({ children }: any) => (
                                  <h2 className="text-2xl font-bold mt-6 mb-3" style={{ color: 'var(--color-text-primary)' }}>
                                    {children}
                                  </h2>
                                ),
                                h3: ({ children }: any) => (
                                  <h3 className="text-xl font-bold mt-4 mb-2" style={{ color: 'var(--color-text-primary)' }}>
                                    {children}
                                  </h3>
                                ),
                                p: ({ children }: any) => (
                                  <p className="mb-4 leading-relaxed" style={{ color: 'var(--color-text-primary)' }}>
                                    {children}
                                  </p>
                                ),
                                ul: ({ children }: any) => (
                                  <ul className="list-disc mb-4 space-y-1.5 pl-6" style={{ color: 'var(--color-text-primary)' }}>
                                    {children}
                                  </ul>
                                ),
                                ol: ({ children }: any) => (
                                  <ol className="list-decimal mb-4 space-y-1.5 pl-6" style={{ color: 'var(--color-text-primary)' }}>
                                    {children}
                                  </ol>
                                ),
                                li: ({ children }: any) => (
                                  <li className="pl-1" style={{ color: 'var(--color-text-primary)' }}>
                                    {children}
                                  </li>
                                ),
                                blockquote: ({ children }: any) => (
                                  <blockquote className="border-l-4 pl-4 py-2 my-4 italic" style={{
                                    borderColor: 'var(--color-primary)',
                                    backgroundColor: 'var(--color-panel-dark)',
                                    color: 'var(--color-text-primary)'
                                  }}>
                                    {children}
                                  </blockquote>
                                ),
                              }}
                            >
                              {result.rendered}
                            </ReactMarkdown>
                          </div>
                        );
                      }

                      // Tool Calls
                      if (item.type === 'tool_call' && item.tool) {
                        // Check if tool matches filter/search
                        const matches = !searchQuery ||
                          item.tool.toolName.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          (item.tool.input || '').toLowerCase().includes(searchQuery.toLowerCase());

                        if (!matches) return null;

                        const renderedHeader = renderTextWithLimit(item.tool.toolName, charIndex).rendered;
                        charIndex += item.tool.toolName.length;

                        const renderedInput = renderTextWithLimit(item.tool.input, charIndex).rendered;
                        charIndex += item.tool.input.length;

                        const renderedResult = item.tool.result ? renderTextWithLimit(item.tool.result, charIndex).rendered : '';
                        if (item.tool.result) charIndex += item.tool.result.length;

                        return (
                          <ToolCallItem
                            key={item.id}
                            status={item.tool.status}
                            toolName={item.tool.toolName}
                            renderedHeader={renderedHeader}
                            renderedInput={renderedInput}
                            renderedResult={renderedResult}
                            contentBlocks={item.tool.contentBlocks}
                            artifacts={item.tool.artifacts}
                            hasMultimodal={item.tool.hasMultimodal}
                          />
                        );
                      }

                      return null;
                    })}
                  </div>
                </div>
              );
            })}
            </>
          )
        }
      </div >

      {/* Scroll to Bottom Button - Only show when content is scrollable */}
      {
        isScrollable && (
          <button
            onClick={scrollToBottom}
            className="absolute bottom-6 right-6 p-2.5 rounded-full shadow-md text-white transition-all hover:scale-110 hover:shadow-lg"
            title="Scroll to bottom"
            style={{
              zIndex: 50,
              backgroundColor: 'var(--color-primary)',
              opacity: isAutoScroll ? 0.3 : 1
            }}
          >
            <ArrowDown className="w-4 h-4" />
          </button>
        )
      }

      {/* Subagent Panels - Slide out from right when subagents are active */}
      {activeSubagents.length > 0 && (
        <div
          className="fixed top-0 h-full z-40 transition-all duration-300 ease-out"
          style={{
            left: isFullScreen ? '66.666%' : '850px',
            width: isFullScreen ? '33.333%' : '400px',
            backgroundColor: 'transparent'
          }}
        >
          <SubAgentPanelStack
            subagents={activeSubagents}
            isVisible={true}
          />
        </div>
      )}
    </div >

  );
}
