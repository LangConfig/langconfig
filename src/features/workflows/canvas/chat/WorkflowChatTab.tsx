/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { Node } from 'reactflow';
import { Activity, ArrowUp, Ban, Bot, CheckCircle2, ChevronDown, CornerDownRight, FileImage, Loader2, MessageSquare, PanelRightClose, PanelRightOpen, Play, RotateCcw, Send, Sparkles, Square, Trash2, Wrench } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import ContentBlockRenderer from '@/components/common/ContentBlockRenderer';
import { useChatStreaming } from '@/features/chat/hooks/useChatStreaming';
import { useChat } from '@/features/chat/state/ChatContext';
import type { ChatMessage, ChatStreamEvent } from '@/features/chat/types/chat';
import apiClient from '@/lib/api-client';
import type { ContentBlock } from '@/types/content-blocks';
import type { WorkflowEvent } from '@/types/events';
import type { NodeExecutionStatus } from '@/hooks/useNodeExecutionStatus';
import type { TaskHistoryEntry } from '../types';

interface ExecutionStatus {
  state: 'idle' | 'running' | 'completed' | 'failed';
  currentNode?: string;
  progress?: number;
  startTime?: string;
  duration?: string;
}

interface WorkflowChatTabProps {
  workflowName: string;
  workflowId: number | null;
  taskHistory: TaskHistoryEntry[];
  workflowEvents: WorkflowEvent[];
  workflowMetrics?: any;
  executionStatus: ExecutionStatus;
  currentTaskId: number | null;
  nodes?: Node[];
  nodeStatuses?: Record<string, NodeExecutionStatus>;
  preferredAgentId?: number | null;
  onSendPrompt: (prompt: string, continueFromTaskId?: number) => void;
  onStop: () => void;
}

interface ChatAgentOption {
  id: number;
  name: string;
  description?: string;
  category?: string;
}

function getTaskPrompt(task: TaskHistoryEntry): string {
  return (
    task.user_input ||
    task.formatted_input ||
    task.input_data?.query ||
    task.input_data?.task ||
    task.input_data?.input ||
    'Workflow run'
  );
}

function stringifyValue(value: unknown): string {
  if (value == null) return '';
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) return value.map(stringifyValue).filter(Boolean).join('\n\n');
  if (typeof value === 'object') {
    const record = value as Record<string, any>;
    const candidate =
      record.formatted_content ||
      record.final_output ||
      record.output ||
      record.summary ||
      record.content ||
      record.message ||
      record.text;
    if (candidate) return stringifyValue(candidate);
    try {
      return JSON.stringify(value, null, 2);
    } catch {
      return String(value);
    }
  }
  return String(value);
}

function getTaskOutput(task: TaskHistoryEntry): string {
  const output = stringifyValue(task.result);
  if (output.length > 4500) return `${output.slice(0, 4500)}...`;
  return output || task.error || 'No output captured yet.';
}

function getTaskArtifacts(task: TaskHistoryEntry): ContentBlock[] {
  const result = task.result || {};
  const candidates = [
    result.artifacts,
    result.content_blocks,
    result.collected_artifacts,
    result.output?.artifacts,
    result.final_output?.artifacts,
  ];
  for (const candidate of candidates) {
    if (Array.isArray(candidate) && candidate.length > 0) {
      return candidate.filter((item) => item && typeof item === 'object' && typeof item.type === 'string') as ContentBlock[];
    }
  }
  return [];
}

function eventLabel(event: WorkflowEvent): string {
  const data = event.data || {};
  switch (event.type) {
    case 'node_started':
      return `${data.agent_label || data.node_id || 'Node'} started`;
    case 'node_completed':
      return `${data.agent_label || data.node_id || 'Node'} ${data.status === 'error' ? 'failed' : 'completed'}`;
    case 'on_tool_start':
    case 'tool_start':
      return `${data.tool_name || data.name || 'Tool'} started`;
    case 'on_tool_end':
      return `${data.tool_name || data.name || 'Tool'} completed`;
    case 'tool_progress':
      return data.message || `${data.tool_name || 'Tool'} progress`;
    case 'subagent_start':
      return `${data.subagent_name || 'Subagent'} started`;
    case 'subagent_end':
      return `${data.subagent_name || 'Subagent'} completed`;
    case 'error':
      return data.message || data.error || 'Execution error';
    case 'complete':
      return 'Workflow completed';
    case 'status':
      return data.message || data.status || 'Workflow status';
    default:
      return data.agent_label || event.type.replace(/_/g, ' ');
  }
}

function tokenFromEvent(event: WorkflowEvent): string {
  if (event.type !== 'on_chat_model_stream' && event.type !== 'token' && event.type !== 'on_llm_stream') return '';
  return event.data?.token || event.data?.content || '';
}

function nodeDisplayLabel(node: Node): string {
  return String(node.data?.label || node.data?.name || node.id || 'Node');
}

function isWorkflowNode(node: Node): boolean {
  const label = nodeDisplayLabel(node).toUpperCase();
  const type = String(node.data?.agentType || node.type || '').toUpperCase();
  return !['START', 'END', '__START__', '__END__', 'START_NODE', 'END_NODE'].includes(label) &&
    !['START_NODE', 'END_NODE'].includes(type);
}

function deepAgentIdFromNode(node: Node): number | null {
  const data = node.data as any;
  const raw =
    data?.deepAgentId ||
    data?.deep_agent_template_id ||
    data?.config?.deepAgentId ||
    data?.config?.deep_agent_template_id;
  const parsed = Number(raw);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

const markdownComponents = {
  p: ({ children }: any) => <p className="mb-3 last:mb-0 leading-relaxed">{children}</p>,
  ul: ({ children }: any) => <ul className="mb-3 list-disc pl-5 leading-relaxed">{children}</ul>,
  ol: ({ children }: any) => <ol className="mb-3 list-decimal pl-5 leading-relaxed">{children}</ol>,
  code: ({ children }: any) => (
    <code className="border border-border-dark bg-background-light px-1 py-0.5 font-mono text-[0.85em]">
      {children}
    </code>
  ),
  pre: ({ children }: any) => (
    <pre className="mb-3 overflow-x-auto border-2 border-border-dark bg-background-dark p-3 font-mono text-xs text-text-primary shadow-[3px_3px_0_var(--color-border-dark)]">
      {children}
    </pre>
  ),
};

function WorkflowProgressRail({
  nodes,
  nodeStatuses,
  isRunning,
}: {
  nodes: Node[];
  nodeStatuses: Record<string, NodeExecutionStatus>;
  isRunning: boolean;
}) {
  const workflowNodes = nodes.filter(isWorkflowNode);
  if (workflowNodes.length === 0) return null;

  return (
    <aside className="hidden w-56 flex-none overflow-y-auto border-r-2 border-border-dark bg-panel-dark px-3 py-4 lg:block">
      <div className="mb-3 flex items-center gap-2 font-mono text-[11px] font-black uppercase tracking-[0.14em] text-text-muted">
        <Activity className="h-4 w-4 text-primary" />
        Progress
      </div>
      <div className="space-y-1">
        {workflowNodes.map((node, index) => {
          const label = nodeDisplayLabel(node);
          const status = nodeStatuses[label] || (node.data as any)?.executionStatus;
          const rawState = status?.state || 'idle';
          const state = !isRunning && ['running', 'thinking'].includes(rawState) ? 'completed' : rawState;
          const active = state === 'running' || state === 'thinking';
          const completed = state === 'completed';
          const errored = state === 'error';

          return (
            <div key={node.id}>
              {index > 0 && <div className="ml-[13px] h-3 w-0.5 bg-border-dark" />}
              <div className="border-2 border-border-dark bg-background-light px-2.5 py-2 shadow-[2px_2px_0_var(--color-border-dark)]">
                <div className="flex items-start gap-2">
                  <span
                    className={`mt-0.5 flex h-4 w-4 flex-none items-center justify-center border border-border-dark ${
                      completed ? 'bg-primary text-white' : errored ? 'bg-red-600 text-white' : active ? 'bg-accent-light text-text-primary' : 'bg-panel-dark'
                    }`}
                  >
                    {completed ? <CheckCircle2 className="h-3 w-3" /> : active ? <Loader2 className="h-3 w-3 animate-spin" /> : errored ? <Ban className="h-3 w-3" /> : null}
                  </span>
                  <div className="min-w-0">
                    <div className="truncate text-xs font-black text-text-primary">{label}</div>
                    <div className="mt-0.5 truncate font-mono text-[10px] font-bold uppercase tracking-[0.08em] text-text-muted">
                      {active && status?.activeTool ? status.activeTool : state}
                    </div>
                  </div>
                </div>
                {active && status?.thinkingPreview && (
                  <div className="mt-2 line-clamp-3 border-t border-border-dark pt-2 text-[11px] leading-snug text-text-muted">
                    {status.thinkingPreview}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </aside>
  );
}

function MessageBubble({
  message,
  isStreaming,
  onDelete,
}: {
  message: ChatMessage;
  isStreaming?: boolean;
  onDelete?: () => void;
}) {
  const isUser = message.role === 'user';

  return (
    <div className={`group flex flex-col gap-1 ${isUser ? 'items-end' : 'items-start'}`}>
      <div className={`flex max-w-[92%] items-start gap-2 ${isUser ? 'flex-row-reverse' : ''}`}>
        {isUser && onDelete && (
          <button
            type="button"
            onClick={() => {
              if (window.confirm('Delete this message? The live chat runtime will reset for this session.')) {
                onDelete();
              }
            }}
            className="mt-1 border-2 border-border-dark bg-background-light p-1.5 text-text-muted opacity-0 shadow-[2px_2px_0_var(--color-border-dark)] transition-opacity hover:text-red-700 group-hover:opacity-100"
            title="Delete message"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        )}
        <div
          className={
            isUser
              ? 'border-2 border-border-dark bg-primary px-4 py-3 text-white shadow-[4px_4px_0_var(--color-border-dark)]'
              : 'border-2 border-border-dark bg-panel-dark px-4 py-3 text-text-primary shadow-[4px_4px_0_var(--color-border-dark)]'
          }
        >
          <div className="mb-1 font-mono text-[11px] font-black uppercase tracking-[0.14em] opacity-75">
            {isUser ? 'You' : 'Agent'}
          </div>
          <div className="prose prose-sm max-w-none text-inherit">
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
              {message.content || (message.artifacts?.length ? '' : 'Working...')}
            </ReactMarkdown>
          </div>
          {message.artifacts && message.artifacts.length > 0 && (
            <div className="mt-3 border-t-2 border-border-dark pt-3">
              <div className="mb-2 flex items-center gap-2 font-mono text-[10px] font-black uppercase tracking-[0.12em] text-text-muted">
                <FileImage className="h-3.5 w-3.5 text-primary" />
                Artifacts
              </div>
              <ContentBlockRenderer blocks={message.artifacts} />
            </div>
          )}
          {isStreaming && <span className="ml-1 inline-block h-3 w-2 animate-pulse bg-primary align-middle" />}
        </div>
      </div>
      {message.timestamp && (
        <span className="px-2 font-mono text-[10px] font-bold uppercase tracking-[0.1em] text-text-muted">
          {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </span>
      )}
    </div>
  );
}

function WorkflowChatSidePanel({
  collapsed,
  onToggle,
  workflowName,
  agents,
  selectedAgentId,
  onAgentChange,
  sessionId,
  taskCount,
  capturedCount,
}: {
  collapsed: boolean;
  onToggle: () => void;
  workflowName: string;
  agents: ChatAgentOption[];
  selectedAgentId: number | null;
  onAgentChange: (agentId: number) => void;
  sessionId: string | null;
  taskCount: number;
  capturedCount: number;
}) {
  if (collapsed) {
    return (
      <button
        type="button"
        onClick={onToggle}
        className="hidden w-11 flex-none items-center justify-center border-l-2 border-border-dark bg-panel-dark text-text-muted hover:text-text-primary xl:flex"
        title="Open chat context"
      >
        <PanelRightOpen className="h-4 w-4" />
      </button>
    );
  }

  return (
    <aside className="hidden w-72 flex-none overflow-y-auto border-l-2 border-border-dark bg-panel-dark xl:block">
      <div className="flex items-center justify-between border-b-2 border-border-dark px-4 py-3">
        <div className="font-mono text-[11px] font-black uppercase tracking-[0.14em] text-text-muted">Context</div>
        <button type="button" onClick={onToggle} className="text-text-muted hover:text-text-primary" title="Collapse context">
          <PanelRightClose className="h-4 w-4" />
        </button>
      </div>
      <div className="space-y-4 p-4">
        <section className="border-2 border-border-dark bg-background-light p-3 shadow-[3px_3px_0_var(--color-border-dark)]">
          <div className="font-mono text-[10px] font-black uppercase tracking-[0.12em] text-text-muted">Workflow</div>
          <div className="mt-1 text-sm font-black text-text-primary">{workflowName}</div>
          <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
            <div className="border border-border-dark bg-panel-dark px-2 py-1.5">
              <div className="font-mono text-[10px] font-bold uppercase text-text-muted">Runs</div>
              <div className="font-black text-text-primary">{taskCount}</div>
            </div>
            <div className="border border-border-dark bg-panel-dark px-2 py-1.5">
              <div className="font-mono text-[10px] font-bold uppercase text-text-muted">Traces</div>
              <div className="font-black text-text-primary">{capturedCount}</div>
            </div>
          </div>
        </section>

        <section className="border-2 border-border-dark bg-background-light p-3 shadow-[3px_3px_0_var(--color-border-dark)]">
          <div className="mb-2 flex items-center gap-2 font-mono text-[10px] font-black uppercase tracking-[0.12em] text-text-muted">
            <Bot className="h-3.5 w-3.5 text-primary" />
            Chat Agent
          </div>
          {agents.length === 0 ? (
            <div className="text-xs leading-relaxed text-text-muted">No saved agents are available yet. Workflow runs still work from the composer.</div>
          ) : (
            <div className="space-y-2">
              {agents.map((agent) => (
                <button
                  key={agent.id}
                  type="button"
                  onClick={() => onAgentChange(agent.id)}
                  className={`w-full border-2 border-border-dark px-3 py-2 text-left shadow-[2px_2px_0_var(--color-border-dark)] transition-transform active:translate-x-[2px] active:translate-y-[2px] active:shadow-none ${
                    selectedAgentId === agent.id ? 'bg-accent-light' : 'bg-panel-dark'
                  }`}
                >
                  <div className="truncate text-xs font-black text-text-primary">{agent.name}</div>
                  {agent.description && <div className="mt-0.5 line-clamp-2 text-[11px] leading-snug text-text-muted">{agent.description}</div>}
                </button>
              ))}
            </div>
          )}
          {sessionId && <div className="mt-3 truncate font-mono text-[10px] font-bold uppercase tracking-[0.08em] text-text-muted">Session {sessionId}</div>}
        </section>
      </div>
    </aside>
  );
}

const WorkflowChatTab = memo(function WorkflowChatTab({
  workflowName,
  workflowId,
  taskHistory,
  workflowEvents,
  workflowMetrics,
  executionStatus,
  currentTaskId,
  nodes = [],
  nodeStatuses = {},
  preferredAgentId = null,
  onSendPrompt,
  onStop,
}: WorkflowChatTabProps) {
  const {
    currentSessionId,
    sessions,
    startSession,
    switchSession,
    getCompletedExecutions,
    appendCompletedExecution,
    clearCompletedExecutions,
  } = useChat();
  const [draft, setDraft] = useState('');
  const [manualContinuationTaskId, setManualContinuationTaskId] = useState<number | null>(null);
  const [continuationDisabled, setContinuationDisabled] = useState(false);
  const [expandedTraces, setExpandedTraces] = useState<Set<number | string>>(new Set());
  const [agents, setAgents] = useState<ChatAgentOption[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState<number | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(currentSessionId);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [activeToolCalls, setActiveToolCalls] = useState<Array<{ name: string; status: 'running' | 'completed' | 'error' }>>([]);
  const [sidePanelCollapsed, setSidePanelCollapsed] = useState(false);
  const initializedTaskIdsRef = useRef(false);
  const capturedTaskIdsRef = useRef(new Set<number>());
  const chatKey = `workflow:${workflowId ?? 'draft'}`;
  const { sendMessage, isStreaming, error: streamError, clearError: clearStreamError } = useChatStreaming(sessionId);

  const orderedTasks = useMemo(
    () => [...taskHistory].sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()),
    [taskHistory]
  );

  const latestCompletedTask = useMemo(
    () => [...orderedTasks].reverse().find((task) => task.status === 'completed' || task.status === 'success'),
    [orderedTasks]
  );

  const continuationTaskId = continuationDisabled
    ? undefined
    : manualContinuationTaskId ?? latestCompletedTask?.id;

  const liveText = useMemo(
    () => workflowEvents.map(tokenFromEvent).filter(Boolean).join('').trim(),
    [workflowEvents]
  );

  const visibleEvents = useMemo(
    () => workflowEvents
      .filter((event) => !['on_chat_model_stream', 'token', 'on_llm_stream', 'ping', 'keepalive'].includes(event.type))
      .slice(-8),
    [workflowEvents]
  );

  const completedExecutions = getCompletedExecutions(chatKey);
  const executionByTaskId = useMemo(() => {
    const byTaskId = new Map<number, typeof completedExecutions[number]>();
    completedExecutions.forEach((snapshot) => {
      if (snapshot.taskId) byTaskId.set(snapshot.taskId, snapshot);
    });
    return byTaskId;
  }, [completedExecutions]);

  useEffect(() => {
    const controller = new AbortController();
    apiClient.listDeepAgents({ signal: controller.signal })
      .then((response) => {
        const fetched = (response.data || []).map((agent: any) => ({
          id: agent.id,
          name: agent.name || 'Unnamed Agent',
          description: agent.description,
          category: agent.category,
        }));
        setAgents(fetched);

        setSelectedAgentId((current) => {
          if (current && fetched.some((agent: ChatAgentOption) => agent.id === current)) return current;
          if (preferredAgentId && fetched.some((agent: ChatAgentOption) => agent.id === preferredAgentId)) return preferredAgentId;
          const linkedNodeAgent = nodes.map(deepAgentIdFromNode).find((id): id is number => Boolean(id));
          if (linkedNodeAgent && fetched.some((agent: ChatAgentOption) => agent.id === linkedNodeAgent)) return linkedNodeAgent;
          return fetched[0]?.id ?? null;
        });
      })
      .catch((error) => {
        if (error?.name !== 'CanceledError' && error?.name !== 'AbortError') {
          console.warn('Failed to load chat agents for workflow chat:', error);
        }
      });
    return () => controller.abort();
  }, [nodes, preferredAgentId]);

  useEffect(() => {
    if (!preferredAgentId || agents.length === 0) return;
    if (agents.some((agent) => agent.id === preferredAgentId)) {
      setSelectedAgentId(preferredAgentId);
    }
  }, [agents, preferredAgentId]);

  useEffect(() => {
    setSessionId(currentSessionId);
  }, [currentSessionId]);

  useEffect(() => {
    if (!selectedAgentId) return;
    let cancelled = false;

    const ensureSession = async () => {
      try {
        const currentSession = currentSessionId
          ? sessions.find((item) => item.session_id === currentSessionId)
          : null;
        const session: string = currentSession && currentSession.agent_id === selectedAgentId && currentSessionId
          ? currentSessionId
          : await startSession(selectedAgentId);
        if (cancelled) return;
        setSessionId(session);
        switchSession(session);

        const history = await apiClient.getChatHistory(session);
        if (cancelled) return;
        setChatMessages(Array.isArray(history.data?.messages) ? history.data.messages : []);
      } catch (error) {
        if (!cancelled) {
          console.warn('Failed to initialize workflow chat session:', error);
        }
      }
    };

    ensureSession();
    return () => {
      cancelled = true;
    };
  }, [currentSessionId, selectedAgentId, sessions, startSession, switchSession]);

  useEffect(() => {
    if (!initializedTaskIdsRef.current) {
      taskHistory.forEach((task) => capturedTaskIdsRef.current.add(task.id));
      initializedTaskIdsRef.current = true;
      return;
    }

    for (const task of taskHistory) {
      const isComplete = task.status === 'completed' || task.status === 'success';
      if (!isComplete || capturedTaskIdsRef.current.has(task.id)) continue;

      capturedTaskIdsRef.current.add(task.id);
      appendCompletedExecution(chatKey, {
        taskId: task.id,
        prompt: getTaskPrompt(task),
        events: workflowEvents.slice(-500),
        metrics: workflowMetrics || null,
        completedAt: task.completed_at || new Date().toISOString(),
      });
    }
  }, [appendCompletedExecution, chatKey, taskHistory, workflowEvents, workflowMetrics]);

  const toggleTrace = (taskId: number | string) => {
    setExpandedTraces((prev) => {
      const next = new Set(prev);
      if (next.has(taskId)) next.delete(taskId);
      else next.add(taskId);
      return next;
    });
  };

  const updateLastAssistantMessage = useCallback((content: string, patch?: Partial<ChatMessage>) => {
    setChatMessages((prev) => {
      const updated = [...prev];
      for (let i = updated.length - 1; i >= 0; i -= 1) {
        if (updated[i].role === 'assistant') {
          updated[i] = { ...updated[i], content, ...patch };
          return updated;
        }
      }
      return [
        ...updated,
        {
          role: 'assistant',
          content,
          timestamp: new Date().toISOString(),
          ...patch,
        },
      ];
    });
  }, []);

  const handleToolEvent = useCallback((event: ChatStreamEvent) => {
    const toolName = event.tool_name || event.data?.tool_name || 'tool';
    if (event.type === 'tool_start') {
      setActiveToolCalls((prev) => [...prev, { name: toolName, status: 'running' }]);
      return;
    }
    if (event.type === 'tool_end') {
      setActiveToolCalls((prev) =>
        prev.map((tool) => tool.name === toolName ? { ...tool, status: 'completed' } : tool)
      );
      window.setTimeout(() => {
        setActiveToolCalls((prev) => prev.filter((tool) => tool.status !== 'completed'));
      }, 2000);
    }
  }, []);

  const handleAgentChange = useCallback(async (agentId: number) => {
    setSelectedAgentId(agentId);
    setChatMessages([]);
    setActiveToolCalls([]);
    clearStreamError();
    try {
      const newSessionId = await startSession(agentId);
      setSessionId(newSessionId);
      switchSession(newSessionId);
    } catch (error) {
      console.warn('Failed to switch workflow chat agent:', error);
    }
  }, [clearStreamError, startSession, switchSession]);

  const handleChatSubmit = useCallback(async () => {
    const prompt = draft.trim();
    if (!prompt || isStreaming || !sessionId || !selectedAgentId) return;
    setDraft('');
    await sendMessage(
      prompt,
      (message) => setChatMessages((prev) => [...prev, message]),
      updateLastAssistantMessage,
      () => {},
      handleToolEvent,
      handleToolEvent
    );
  }, [draft, handleToolEvent, isStreaming, selectedAgentId, sendMessage, sessionId, updateLastAssistantMessage]);

  const handleRunSubmit = () => {
    const prompt = draft.trim();
    if (!prompt || executionStatus.state === 'running') return;
    onSendPrompt(prompt, continuationTaskId);
    setDraft('');
  };

  const handleDeleteChatMessage = useCallback(async (index: number) => {
    if (!sessionId) return;
    await apiClient.deleteChatMessage(sessionId, index);
    setChatMessages((prev) => prev.filter((_, itemIndex) => itemIndex !== index));
  }, [sessionId]);

  const selectedAgent = agents.find((agent) => agent.id === selectedAgentId);
  const canChat = Boolean(sessionId && selectedAgentId) && !isStreaming && executionStatus.state !== 'running';
  const canRunWorkflow = Boolean(draft.trim()) && executionStatus.state !== 'running';

  return (
    <div className="flex h-full flex-col bg-background-light">
      <div className="border-b-2 border-border-dark bg-panel-dark px-5 py-4 shadow-[0_4px_0_var(--color-border-dark)]">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 text-xs font-black uppercase tracking-[0.16em] text-text-muted">
              <MessageSquare className="h-4 w-4" />
              Workflow Chat
            </div>
            <h2 className="mt-1 text-xl font-black text-text-primary">{workflowName}</h2>
          </div>
          <div className="flex items-center gap-2 border-2 border-border-dark bg-background-light px-3 py-2 font-mono text-xs font-bold text-text-primary shadow-[3px_3px_0_var(--color-border-dark)]">
            {executionStatus.state === 'running' ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin text-primary" />
                Task #{currentTaskId || 'new'}
              </>
            ) : workflowId ? (
              <>Workflow #{workflowId}</>
            ) : (
              <>Unsaved workflow</>
            )}
          </div>
        </div>
      </div>

      <div className="flex min-h-0 flex-1">
        <WorkflowProgressRail nodes={nodes} nodeStatuses={nodeStatuses} isRunning={executionStatus.state === 'running'} />

        <div className="min-w-0 flex-1 overflow-y-auto px-5 py-5">
        <div className="mx-auto flex max-w-5xl flex-col gap-5">
          {orderedTasks.length === 0 && chatMessages.length === 0 && executionStatus.state !== 'running' && (
            <div className="border-2 border-border-dark bg-panel-dark p-6 shadow-[5px_5px_0_var(--color-border-dark)]">
              <div className="mb-3 flex h-10 w-10 items-center justify-center border-2 border-border-dark bg-background-light shadow-[3px_3px_0_var(--color-border-dark)]">
                <Sparkles className="h-5 w-5 text-primary" />
              </div>
              <h3 className="text-lg font-black text-text-primary">Start with a prompt.</h3>
              <p className="mt-2 max-w-2xl text-sm leading-relaxed text-text-muted">
                Chat with a saved agent, run this workflow conversationally, then keep going from completed tasks.
              </p>
            </div>
          )}

          {chatMessages.map((message, index) => (
            <MessageBubble
              key={`chat-message-${index}-${message.timestamp}`}
              message={message}
              isStreaming={isStreaming && index === chatMessages.length - 1 && message.role === 'assistant'}
              onDelete={message.role === 'user' ? () => handleDeleteChatMessage(index) : undefined}
            />
          ))}

          {activeToolCalls.map((tool, index) => (
            <div
              key={`${tool.name}-${index}`}
              className="w-fit border-2 border-border-dark bg-panel-dark px-3 py-2 font-mono text-xs font-black uppercase tracking-[0.12em] text-text-primary shadow-[3px_3px_0_var(--color-border-dark)]"
            >
              <span className="inline-flex items-center gap-2">
                {tool.status === 'running' ? <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" /> : <CheckCircle2 className="h-3.5 w-3.5 text-primary" />}
                {tool.name} {tool.status}
              </span>
            </div>
          ))}

          {orderedTasks.map((task) => (
            <div key={task.id} className="space-y-3">
              <div className="ml-auto max-w-3xl border-2 border-border-dark bg-primary px-4 py-3 text-white shadow-[4px_4px_0_var(--color-border-dark)]">
                <div className="mb-1 font-mono text-[11px] font-black uppercase tracking-[0.14em] opacity-80">
                  You
                </div>
                <div className="whitespace-pre-wrap text-sm font-semibold leading-relaxed">{getTaskPrompt(task)}</div>
              </div>

              <div className="max-w-4xl border-2 border-border-dark bg-panel-dark p-4 text-text-primary shadow-[4px_4px_0_var(--color-border-dark)]">
                {(() => {
                  const executionSnapshot = executionByTaskId.get(task.id);
                  const traceEvents = executionSnapshot?.events || [];
                  const traceOpen = expandedTraces.has(task.id);
                  return (
                    <>
                <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2 font-mono text-[11px] font-black uppercase tracking-[0.14em] text-text-muted">
                    {task.status === 'completed' || task.status === 'success' ? (
                      <CheckCircle2 className="h-4 w-4 text-primary" />
                    ) : (
                      <Loader2 className="h-4 w-4 animate-spin text-primary" />
                    )}
                    Task #{task.id} · {task.status}
                  </div>
                  {(task.status === 'completed' || task.status === 'success') && (
                    <button
                      type="button"
                      onClick={() => {
                        setManualContinuationTaskId(task.id);
                        setContinuationDisabled(false);
                      }}
                      className="inline-flex items-center gap-1.5 border-2 border-border-dark bg-background-light px-2.5 py-1.5 font-mono text-xs font-bold text-text-primary shadow-[2px_2px_0_var(--color-border-dark)] transition-transform hover:-translate-y-0.5 active:translate-x-[2px] active:translate-y-[2px] active:shadow-none"
                    >
                      <CornerDownRight className="h-3.5 w-3.5" />
                      Continue
                      </button>
                  )}
                </div>
                <div className="prose prose-sm max-w-none text-text-primary">
                  <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                    {getTaskOutput(task)}
                  </ReactMarkdown>
                </div>
                {getTaskArtifacts(task).length > 0 && (
                  <div className="mt-4 border-t-2 border-border-dark pt-3">
                    <div className="mb-2 flex items-center gap-2 font-mono text-[10px] font-black uppercase tracking-[0.12em] text-text-muted">
                      <FileImage className="h-3.5 w-3.5 text-primary" />
                      Artifacts
                    </div>
                    <ContentBlockRenderer blocks={getTaskArtifacts(task)} />
                  </div>
                )}
                {executionSnapshot && (
                  <div className="mt-4 border-t-2 border-border-dark pt-3">
                    <button
                      type="button"
                      onClick={() => toggleTrace(task.id)}
                      className="flex w-full items-center justify-between border-2 border-border-dark bg-background-light px-3 py-2 font-mono text-xs font-black uppercase tracking-[0.12em] text-text-primary shadow-[2px_2px_0_var(--color-border-dark)] transition-transform hover:-translate-y-0.5 active:translate-x-[2px] active:translate-y-[2px] active:shadow-none"
                    >
                      <span className="flex items-center gap-2">
                        <Activity className="h-4 w-4 text-primary" />
                        Execution Trace
                      </span>
                      <ChevronDown className={`h-4 w-4 transition-transform ${traceOpen ? 'rotate-180' : ''}`} />
                    </button>
                    {traceOpen && (
                      <div className="mt-3 space-y-2">
                        {executionSnapshot.metrics && (
                          <div className="grid grid-cols-2 gap-2 text-xs md:grid-cols-4">
                            {Object.entries(executionSnapshot.metrics).slice(0, 4).map(([key, value]) => (
                              <div key={key} className="border border-border-dark bg-background-light px-2 py-1.5">
                                <div className="font-mono font-bold uppercase tracking-[0.1em] text-text-muted">{key}</div>
                                <div className="mt-1 truncate font-semibold text-text-primary">{String(value)}</div>
                              </div>
                            ))}
                          </div>
                        )}
                        {traceEvents.length === 0 ? (
                          <div className="border border-border-dark bg-background-light px-3 py-2 text-xs text-text-muted">
                            No stream events captured for this run.
                          </div>
                        ) : (
                          traceEvents
                            .filter((event: WorkflowEvent) => !['on_chat_model_stream', 'token', 'on_llm_stream', 'ping', 'keepalive'].includes(event.type))
                            .slice(-12)
                            .map((event: WorkflowEvent, index: number) => (
                              <div
                                key={`${event.idempotency_key || event.event_id || event.type}-trace-${index}`}
                                className="flex items-start gap-2 border border-border-dark bg-background-light px-3 py-2 text-xs text-text-primary"
                              >
                                <Wrench className="mt-0.5 h-3.5 w-3.5 flex-none text-primary" />
                                <span className="font-mono font-semibold">{eventLabel(event)}</span>
                              </div>
                            ))
                        )}
                      </div>
                    )}
                  </div>
                )}
                    </>
                  );
                })()}
              </div>
            </div>
          ))}

          {executionStatus.state === 'running' && (
            <div className="max-w-4xl border-2 border-border-dark bg-panel-dark p-4 text-text-primary shadow-[4px_4px_0_var(--color-border-dark)]">
              <div className="mb-3 flex items-center gap-2 font-mono text-[11px] font-black uppercase tracking-[0.14em] text-text-muted">
                <Loader2 className="h-4 w-4 animate-spin text-primary" />
                Running {executionStatus.currentNode ? `· ${executionStatus.currentNode}` : ''}
              </div>

              {liveText && (
                <div className="mb-4 border-2 border-border-dark bg-background-light p-3 text-sm leading-relaxed shadow-[3px_3px_0_var(--color-border-dark)]">
                  {liveText}
                </div>
              )}

              <div className="space-y-2">
                {visibleEvents.map((event, index) => (
                  <div
                    key={`${event.idempotency_key || event.event_id || event.type}-${index}`}
                    className="flex items-start gap-2 border border-border-dark bg-background-light px-3 py-2 text-xs text-text-primary"
                  >
                    <Wrench className="mt-0.5 h-3.5 w-3.5 flex-none text-primary" />
                    <span className="font-mono font-semibold">{eventLabel(event)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
        </div>

        <WorkflowChatSidePanel
          collapsed={sidePanelCollapsed}
          onToggle={() => setSidePanelCollapsed((value) => !value)}
          workflowName={workflowName}
          agents={agents}
          selectedAgentId={selectedAgentId}
          onAgentChange={handleAgentChange}
          sessionId={sessionId}
          taskCount={orderedTasks.length}
          capturedCount={completedExecutions.length}
        />
      </div>

      <div className="border-t-2 border-border-dark bg-panel-dark px-5 py-4">
        <div className="mx-auto max-w-5xl">
          {streamError && (
            <div className="mb-2 w-fit border-2 border-border-dark bg-red-50 px-3 py-1.5 font-mono text-xs font-bold text-red-700 shadow-[2px_2px_0_var(--color-border-dark)]">
              {streamError}
            </div>
          )}
          {completedExecutions.length > 0 && executionStatus.state !== 'running' && (
            <div className="mb-2 flex w-fit items-center gap-2 border-2 border-border-dark bg-background-light px-3 py-1.5 font-mono text-xs font-bold text-text-primary shadow-[2px_2px_0_var(--color-border-dark)]">
              <Activity className="h-3.5 w-3.5 text-primary" />
              {completedExecutions.length} captured execution{completedExecutions.length === 1 ? '' : 's'}
              <button
                type="button"
                onClick={() => clearCompletedExecutions(chatKey)}
                className="ml-1 text-text-muted hover:text-text-primary"
                title="Clear captured execution traces"
              >
                clear traces
              </button>
            </div>
          )}
          {continuationTaskId && executionStatus.state !== 'running' && (
            <div className="mb-2 flex w-fit items-center gap-2 border-2 border-border-dark bg-background-light px-3 py-1.5 font-mono text-xs font-bold text-text-primary shadow-[2px_2px_0_var(--color-border-dark)]">
              <RotateCcw className="h-3.5 w-3.5 text-primary" />
              Continuing from task #{continuationTaskId}
              <button
                type="button"
                onClick={() => {
                  setManualContinuationTaskId(null);
                  setContinuationDisabled(true);
                }}
                className="ml-1 text-text-muted hover:text-text-primary"
                title="Stop continuing from a prior task"
              >
                clear
              </button>
            </div>
          )}

          <div className="mb-2 flex flex-wrap items-center gap-2">
            {agents.length > 0 && (
              <label className="flex items-center gap-2 border-2 border-border-dark bg-background-light px-3 py-1.5 shadow-[2px_2px_0_var(--color-border-dark)]">
                <Bot className="h-3.5 w-3.5 text-primary" />
                <select
                  value={selectedAgentId ?? ''}
                  onChange={(event) => handleAgentChange(Number(event.target.value))}
                  className="bg-transparent font-mono text-xs font-black uppercase tracking-[0.08em] text-text-primary outline-none"
                >
                  {agents.map((agent) => (
                    <option key={agent.id} value={agent.id}>{agent.name}</option>
                  ))}
                </select>
              </label>
            )}
            {selectedAgent && (
              <div className="max-w-md truncate border-2 border-border-dark bg-panel-dark px-3 py-1.5 font-mono text-xs font-bold text-text-muted shadow-[2px_2px_0_var(--color-border-dark)]">
                Chatting with {selectedAgent.name}
              </div>
            )}
          </div>

          <div className="flex gap-3">
            <textarea
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
                  event.preventDefault();
                  if (canChat) void handleChatSubmit();
                  else handleRunSubmit();
                }
              }}
              disabled={executionStatus.state === 'running' || isStreaming}
              rows={3}
              placeholder={selectedAgent ? 'Chat with the agent, or run the workflow from this prompt...' : 'Run or continue this workflow...'}
              className="min-h-[82px] flex-1 resize-none border-2 border-border-dark bg-input-background px-4 py-3 text-sm font-semibold leading-relaxed text-text-primary shadow-[4px_4px_0_var(--color-border-dark)] outline-none placeholder:text-text-muted focus:border-primary disabled:opacity-60"
            />
            {executionStatus.state === 'running' ? (
              <button
                type="button"
                onClick={onStop}
                className="flex h-[82px] w-24 items-center justify-center border-2 border-border-dark bg-background-light font-mono text-xs font-black uppercase tracking-wide text-text-primary shadow-[4px_4px_0_var(--color-border-dark)] transition-transform hover:-translate-y-0.5 active:translate-x-[4px] active:translate-y-[4px] active:shadow-none"
              >
                <Ban className="mr-1 h-4 w-4" />
                Stop
              </button>
            ) : isStreaming ? (
              <button
                type="button"
                disabled
                className="flex h-[82px] w-24 items-center justify-center border-2 border-border-dark bg-background-light font-mono text-xs font-black uppercase tracking-wide text-text-primary opacity-80 shadow-[4px_4px_0_var(--color-border-dark)]"
              >
                <Square className="mr-1 h-4 w-4" />
                Chat
              </button>
            ) : (
              <div className="flex flex-col gap-2">
                <button
                  type="button"
                  onClick={() => void handleChatSubmit()}
                  disabled={!draft.trim() || !canChat}
                  className="flex h-[37px] w-28 items-center justify-center border-2 border-border-dark bg-primary font-mono text-xs font-black uppercase tracking-wide text-white shadow-[3px_3px_0_var(--color-border-dark)] transition-transform hover:-translate-y-0.5 active:translate-x-[3px] active:translate-y-[3px] active:shadow-none disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Send className="mr-1 h-4 w-4" />
                  Chat
                </button>
                <button
                  type="button"
                  onClick={handleRunSubmit}
                  disabled={!canRunWorkflow}
                  className="flex h-[37px] w-28 items-center justify-center border-2 border-border-dark bg-accent-light font-mono text-xs font-black uppercase tracking-wide text-text-primary shadow-[3px_3px_0_var(--color-border-dark)] transition-transform hover:-translate-y-0.5 active:translate-x-[3px] active:translate-y-[3px] active:shadow-none disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Play className="mr-1 h-4 w-4" />
                  Run
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
});

export default WorkflowChatTab;
