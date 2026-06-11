/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * eventMapping — pure, table-driven fold of WorkflowEvents into execution
 * state for the 3D scene.
 *
 * PORTS THE SEMANTICS of src/hooks/useNodeExecutionStatus.ts (keep in sync!):
 * - statuses are keyed by agent_label (NOT node id); system/infrastructure
 *   labels (__start__, ping, runnablelambda, node-*, ...) are filtered out
 * - node_completed is THE node completion signal; on_chain_end only matters
 *   when data.name === 'workflow_execution' (inner sub-chains fire it
 *   constantly mid-stream)
 * - on_chain_start must NOT reset accumulated token costs
 * - workflow 'complete' resets; cancellation errors reset everything
 *
 * The fold is deliberately pure-ish: foldEvent mutates a FoldState draft but
 * always REPLACES per-label status objects (never mutates them), so a store
 * can shallow-copy the maps into zustand and per-label selectors see new
 * references only for labels that actually changed. Replay scrubbing refolds
 * events[0..cursor] through a fresh FoldState (the plan's pure-refold design).
 */

import type { WorkflowEvent } from '@/types/events';
import type { WorkflowNode, WorkflowEdge } from '@/types/workflow';
import { calculateCost, formatCost } from '@/utils/modelPricing';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type NodeExecState = 'idle' | 'running' | 'thinking' | 'completed' | 'error';
export type ExecutionPhase = 'idle' | 'running' | 'complete' | 'error';

export interface TokenCost {
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
  costString: string;
}

export interface NodeExecStatus {
  state: NodeExecState;
  /** Coalesced (<=10Hz live) tail of the model stream, cleaned + truncated. */
  thinkingPreview: string;
  /** Display name of the currently running tool, if any. */
  activeTool?: string;
  /** 0-100 (tool_progress percent_complete or coarse stage markers). */
  progress?: number;
  tokenCost?: TokenCost;
  durationMs?: number;
  error?: string;
  startTime?: string;
  /** Date.now() of the last state TRANSITION (drives flash/strobe decay). */
  stateChangedAt: number;
}

export interface SubagentInfo {
  runId: string;
  name: string;
  /** Node the orb orbits (resolved via parent_agent_label -> labelToNodeId). */
  parentNodeId: string | null;
  state: 'running' | 'done' | 'error';
  startedAt: number;
  endedAt?: number;
}

export interface ExecTotals {
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
  /** Accumulated numeric cost in USD (format with formatCost). */
  cost: number;
}

export interface PulseRequest {
  edgeId: string;
  kind: 'tool' | 'handoff';
}

/** label -> nodeId plus edge lookups, rebuilt from workflowStore nodes/edges. */
export interface LabelIndex {
  labelToNodeId: Record<string, string>;
  /** Incoming edge ids per node id. */
  edgesIn: Record<string, string[]>;
  /** Edge id by `${source}->${target}`. */
  edgeByPair: Record<string, string>;
}

export const EMPTY_INDEX: LabelIndex = { labelToNodeId: {}, edgesIn: {}, edgeByPair: {} };

export interface FoldState {
  statuses: Record<string, NodeExecStatus>;
  subagents: Record<string, SubagentInfo>;
  totals: ExecTotals;
  phase: ExecutionPhase;
  /** Most recently started (running) label — drives the follow-cam. */
  currentLabel: string | null;
  /** Workflow-level error message (HUD banner). */
  errorMessage: string | null;
  /** Internal: last completed node id, for handoff pulses. */
  lastCompletedNodeId: string | null;
  /** Internal: per-label stream accumulator + last flush time. */
  thinkingAcc: Record<string, { text: string; lastFlush: number }>;
  /** Set true by foldEvent whenever a React-visible field changed. */
  changed: boolean;
}

export interface FoldOptions {
  /** Min ms between thinkingPreview flushes per label (0 = every event). */
  coalesceMs: number;
  /** Clock for stateChangedAt / coalescing (Date.now in live mode). */
  now: number;
  /** When provided, foldEvent pushes edge-pulse requests here (live/play only). */
  pulses?: PulseRequest[];
}

// ---------------------------------------------------------------------------
// Label extraction (ported from useNodeExecutionStatus.getNodeLabelFromEvent)
// ---------------------------------------------------------------------------

const SYSTEM_LABEL_PARTS = [
  'build_graph',
  'langgraph',
  'node-', // node-1, node-15, ...
  '__start__',
  '__end__',
  'ping',
  'runnablelambda',
  'runnablesequence',
];

export function eventNodeLabel(event: WorkflowEvent): string | null {
  const data = event.data as Record<string, unknown> | undefined;
  if (!data) return null;
  const label = (data.agent_label || data.name || null) as string | null;
  if (!label) return null;
  const lower = label.toLowerCase();
  if (SYSTEM_LABEL_PARTS.some((p) => lower.includes(p))) return null;
  return label;
}

// ---------------------------------------------------------------------------
// Index building
// ---------------------------------------------------------------------------

function nodeLabelOf(node: WorkflowNode): string {
  const data = node.data as Record<string, unknown> | undefined;
  return (
    (typeof data?.label === 'string' && (data.label as string)) ||
    (typeof data?.name === 'string' && (data.name as string)) ||
    node.type ||
    node.id
  );
}

/** Build the label->nodeId index. Label collisions: last wins + console.warn. */
export function buildLabelIndex(nodes: WorkflowNode[], edges: WorkflowEdge[]): LabelIndex {
  const labelToNodeId: Record<string, string> = {};
  for (const node of nodes) {
    const label = nodeLabelOf(node);
    if (labelToNodeId[label] !== undefined) {
      console.warn(
        `[spatial] Duplicate node label "${label}" — execution statuses key by label; last node wins (${node.id})`
      );
    }
    labelToNodeId[label] = node.id;
  }

  const edgesIn: Record<string, string[]> = {};
  const edgeByPair: Record<string, string> = {};
  for (const edge of edges) {
    (edgesIn[edge.target] ??= []).push(edge.id);
    edgeByPair[`${edge.source}->${edge.target}`] = edge.id;
  }

  return { labelToNodeId, edgesIn, edgeByPair };
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

export function createFoldState(): FoldState {
  return {
    statuses: {},
    subagents: {},
    totals: { promptTokens: 0, completionTokens: 0, totalTokens: 0, cost: 0 },
    phase: 'idle',
    currentLabel: null,
    errorMessage: null,
    lastCompletedNodeId: null,
    thinkingAcc: {},
    changed: false,
  };
}

const IDLE_STATUS: NodeExecStatus = {
  state: 'idle',
  thinkingPreview: '',
  stateChangedAt: 0,
};

function getStatus(fs: FoldState, label: string): NodeExecStatus {
  return fs.statuses[label] ?? IDLE_STATUS;
}

function putStatus(fs: FoldState, label: string, next: NodeExecStatus): void {
  fs.statuses[label] = next;
  fs.changed = true;
}

/** Word-boundary truncation (ported from the 2D hook). */
export function truncatePreview(fullText: string, maxLength = 96): string {
  if (fullText.length <= maxLength) return fullText;
  let truncateAt = maxLength;
  const lastSpace = fullText.lastIndexOf(' ', maxLength);
  if (lastSpace > maxLength * 0.8) truncateAt = lastSpace;
  return fullText.substring(0, truncateAt).trim() + '…';
}

/** Cheap sanitation of streamed model text for the floating chip. */
function cleanStreamText(text: string): string {
  return text
    .replace(/<[^>]+>/g, '')
    .replace(/[{}[\]]/g, '')
    .replace(/\\[ntr]/g, ' ')
    .replace(/\s{2,}/g, ' ')
    .trim();
}

const TOOL_DISPLAY_NAMES: Record<string, string> = {
  web_search: 'Searching web',
  search_web: 'Searching web',
  web_fetch: 'Fetching webpage',
  browser: 'Browser automation',
  browser_navigate: 'Browser automation',
  read_file: 'Reading file',
  file_read: 'Reading file',
  write_file: 'Writing file',
  file_write: 'Writing file',
  edit_file: 'Editing file',
  ls: 'Listing files',
  file_list: 'Listing files',
  glob: 'Finding files',
  grep: 'Searching files',
  memory_store: 'Storing memory',
  memory_recall: 'Recalling memory',
  reasoning_chain: 'Reasoning',
  sequential_thinking: 'Reasoning',
  create_agent: 'Creating agent',
};

export function displayToolName(toolName: string): string {
  return TOOL_DISPLAY_NAMES[toolName] ?? toolName;
}

function isCancellation(message: string): boolean {
  return message.includes('cancelled') || message.includes('TaskCancelled');
}

// ---------------------------------------------------------------------------
// The fold
// ---------------------------------------------------------------------------

/**
 * Fold one event into the draft state. Mutates `fs` (replacing status
 * objects, never mutating them) and optionally emits pulse requests.
 */
export function foldEvent(fs: FoldState, event: WorkflowEvent, index: LabelIndex, opts: FoldOptions): void {
  const data = event.data as Record<string, any> | undefined;

  // ---- Workflow-level transitions (label-independent) ----------------------
  switch (event.type) {
    case 'complete': {
      fs.phase = 'complete';
      fs.currentLabel = null;
      fs.changed = true;
      break;
    }
    case 'error': {
      const message = (data?.error || data?.message || 'Unknown error') as string;
      if (isCancellation(message)) {
        // Cancellation resets ALL node statuses (2D hook parity).
        for (const label of Object.keys(fs.statuses)) {
          putStatus(fs, label, { ...IDLE_STATUS, stateChangedAt: opts.now });
        }
        fs.phase = 'idle';
        fs.currentLabel = null;
        fs.errorMessage = null;
        fs.changed = true;
        return;
      }
      fs.phase = 'error';
      fs.errorMessage = message;
      fs.changed = true;
      break; // fall through to per-label handling below (node error strobe)
    }
    case 'on_chain_end': {
      if (data?.name === 'workflow_execution') {
        fs.phase = 'complete';
        fs.currentLabel = null;
        fs.changed = true;
        return; // 'workflow_execution' is not a node label — never write a status
      }
      return; // inner sub-chain ends are noise (see hook comment)
    }
    case 'keepalive':
    case 'ping':
    case 'connected':
      return;
    default:
      break;
  }

  // ---- Per-node (agent_label keyed) handling --------------------------------
  const label = eventNodeLabel(event);
  if (!label) return;
  const current = getStatus(fs, label);
  const now = opts.now;

  switch (event.type) {
    case 'on_chain_start': {
      if (data?.name === 'ping' || data?.agent_label === 'ping') return;
      // Do NOT reset tokenCost (multiple chain_starts fire during execution).
      putStatus(fs, label, {
        ...current,
        state: 'running',
        thinkingPreview: '',
        startTime: current.startTime || event.timestamp,
        progress: 10,
        stateChangedAt: current.state === 'running' ? current.stateChangedAt : now,
      });
      if (fs.phase === 'idle') fs.phase = 'running';
      break;
    }

    case 'node_started': {
      putStatus(fs, label, {
        ...current,
        state: 'running',
        thinkingPreview: '',
        startTime: current.startTime || event.timestamp,
        progress: 10,
        stateChangedAt: now,
      });
      fs.currentLabel = label;
      if (fs.phase === 'idle') fs.phase = 'running';
      // Handoff pulse: previous node completed -> this node started.
      const nodeId = index.labelToNodeId[label];
      if (opts.pulses && nodeId && fs.lastCompletedNodeId) {
        const edgeId = index.edgeByPair[`${fs.lastCompletedNodeId}->${nodeId}`];
        if (edgeId) opts.pulses.push({ edgeId, kind: 'handoff' });
      }
      fs.changed = true;
      break;
    }

    case 'on_agent_action': {
      const reasoning = (data?.reasoning || data?.thought || data?.thinking || data?.message || '') as string;
      if (!reasoning) return;
      putStatus(fs, label, {
        ...current,
        state: 'thinking',
        thinkingPreview: truncatePreview(cleanStreamText(reasoning)),
        progress: 50,
        stateChangedAt: current.state === 'thinking' ? current.stateChangedAt : now,
      });
      break;
    }

    case 'on_chat_model_stream': {
      const chunk = (data?.content || data?.token || '') as string;
      if (!chunk) return;
      const acc = (fs.thinkingAcc[label] ??= { text: '', lastFlush: 0 });
      acc.text = (acc.text + chunk).slice(-600); // keep the tail only
      if (opts.coalesceMs > 0 && now - acc.lastFlush < opts.coalesceMs) return;
      acc.lastFlush = now;
      putStatus(fs, label, {
        ...current,
        state: 'thinking',
        thinkingPreview: truncatePreview(cleanStreamText(acc.text)),
        progress: 50,
        stateChangedAt: current.state === 'thinking' ? current.stateChangedAt : now,
      });
      break;
    }

    case 'on_tool_start':
    case 'tool_start': {
      const toolName = (data?.tool_name || data?.tool || data?.name || 'tool') as string;
      putStatus(fs, label, {
        ...current,
        state: 'running',
        activeTool: displayToolName(toolName),
        progress: 60,
        stateChangedAt: current.state === 'running' ? current.stateChangedAt : now,
      });
      // Pulse on edges into this node.
      const nodeId = index.labelToNodeId[label];
      if (opts.pulses && nodeId) {
        for (const edgeId of index.edgesIn[nodeId] ?? []) {
          opts.pulses.push({ edgeId, kind: 'tool' });
        }
      }
      break;
    }

    case 'on_tool_end': {
      putStatus(fs, label, {
        ...current,
        state: 'running',
        activeTool: undefined,
        progress: 80,
        stateChangedAt: current.stateChangedAt,
      });
      break;
    }

    case 'tool_progress': {
      const percent = data?.percent_complete;
      if (typeof percent !== 'number') return;
      putStatus(fs, label, { ...current, progress: percent });
      break;
    }

    case 'on_llm_end': {
      const usage = data?.token_usage || data?.usage;
      if (!usage) return;
      const promptTokens = usage.prompt_tokens || 0;
      const completionTokens = usage.completion_tokens || 0;
      const totalTokens = usage.total_tokens || promptTokens + completionTokens;
      const model = (data?.model || data?.model_name || 'gpt-5.4') as string;
      const cost = calculateCost(promptTokens, completionTokens, model);

      const prev = current.tokenCost ?? {
        promptTokens: 0,
        completionTokens: 0,
        totalTokens: 0,
        costString: '$0.00',
      };
      const nextPrompt = prev.promptTokens + promptTokens;
      const nextCompletion = prev.completionTokens + completionTokens;
      putStatus(fs, label, {
        ...current,
        tokenCost: {
          promptTokens: nextPrompt,
          completionTokens: nextCompletion,
          totalTokens: prev.totalTokens + totalTokens,
          costString: formatCost(calculateCost(nextPrompt, nextCompletion, model)),
        },
      });
      fs.totals = {
        promptTokens: fs.totals.promptTokens + promptTokens,
        completionTokens: fs.totals.completionTokens + completionTokens,
        totalTokens: fs.totals.totalTokens + totalTokens,
        cost: fs.totals.cost + cost,
      };
      break;
    }

    case 'node_completed': {
      delete fs.thinkingAcc[label];
      if (data?.status === 'error') {
        putStatus(fs, label, {
          ...current,
          state: 'error',
          error: (data?.error as string) || 'Node failed',
          thinkingPreview: '',
          activeTool: undefined,
          progress: 0,
          stateChangedAt: now,
        });
      } else {
        const durationMs =
          (data?.duration_ms as number | undefined) ??
          (current.startTime && event.timestamp
            ? new Date(event.timestamp).getTime() - new Date(current.startTime).getTime()
            : undefined);
        const eventCost = data?.tokenCost as
          | { promptTokens: number; completionTokens: number; totalTokens: number; costString?: string }
          | undefined;
        putStatus(fs, label, {
          ...current,
          state: 'completed',
          thinkingPreview: '',
          activeTool: undefined,
          progress: 100,
          durationMs,
          tokenCost: eventCost
            ? {
                ...eventCost,
                costString: eventCost.costString || current.tokenCost?.costString || '$0.00',
              }
            : current.tokenCost,
          stateChangedAt: now,
        });
        const nodeId = index.labelToNodeId[label];
        if (nodeId) fs.lastCompletedNodeId = nodeId;
      }
      if (fs.currentLabel === label) fs.currentLabel = null;
      break;
    }

    case 'error': {
      // Workflow phase handled above; mark the node itself if labeled.
      const message = (data?.error || data?.message || 'Unknown error') as string;
      putStatus(fs, label, {
        ...current,
        state: 'error',
        error: message,
        thinkingPreview: '',
        activeTool: undefined,
        progress: 0,
        stateChangedAt: now,
      });
      break;
    }

    case 'complete': {
      // Workflow completed: this node's status clears immediately (hook parity).
      putStatus(fs, label, { ...IDLE_STATUS, stateChangedAt: now });
      break;
    }

    case 'subagent_start': {
      const runId = data?.subagent_run_id as string | undefined;
      if (!runId) return;
      const parentLabel = (data?.parent_agent_label as string | undefined) || fs.currentLabel || label;
      fs.subagents[runId] = {
        runId,
        name: (data?.subagent_name as string) || 'subagent',
        parentNodeId: parentLabel ? (index.labelToNodeId[parentLabel] ?? null) : null,
        state: 'running',
        startedAt: now,
      };
      fs.changed = true;
      break;
    }

    case 'subagent_end':
    case 'subagent_error': {
      const runId = data?.subagent_run_id as string | undefined;
      if (!runId) return;
      const existing = fs.subagents[runId];
      if (!existing) return;
      fs.subagents[runId] = {
        ...existing,
        state: event.type === 'subagent_error' || data?.success === false ? 'error' : 'done',
        endedAt: now,
      };
      fs.changed = true;
      break;
    }

    case 'status':
    case 'node_status': {
      const statusThinking = (data?.thinking || data?.message || data?.status_message || '') as string;
      const statusTool = (data?.tool || data?.active_tool || data?.current_tool) as string | undefined;
      if (!statusThinking && !statusTool) return;
      putStatus(fs, label, {
        ...current,
        state: (data?.state as NodeExecState) || 'running',
        thinkingPreview: statusThinking
          ? truncatePreview(cleanStreamText(statusThinking))
          : current.thinkingPreview,
        activeTool: statusTool || current.activeTool,
      });
      break;
    }

    default:
      break;
  }
}

/** Pure refold of a prefix of events (replay scrubbing). */
export function foldEvents(
  events: WorkflowEvent[],
  count: number,
  index: LabelIndex,
  pulses?: PulseRequest[]
): FoldState {
  const fs = createFoldState();
  const end = Math.min(count, events.length);
  for (let i = 0; i < end; i++) {
    foldEvent(fs, events[i], index, { coalesceMs: 0, now: Date.now(), pulses });
  }
  return fs;
}
