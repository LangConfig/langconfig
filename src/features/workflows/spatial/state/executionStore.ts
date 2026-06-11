/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * Execution store (zustand) — event-fed visualization state for the 3D scene.
 *
 * Design (see the architecture plan, D4):
 * - ONE event source feeds ingestEvents() (state/useSpatialExecution.ts);
 *   useNodeExecutionStatus is never mounted here (double-EventSource trap).
 * - The fold itself lives in lib/eventMapping.ts and is shared between live
 *   ingest and replay refolds. Live folding keeps a module-level draft
 *   (liveFold) between batches; each batch commits one shallow-copied set()
 *   so per-label selectors only see new references for labels that changed.
 * - Per-frame data (edge pulses, subagent orbit phases) is read transiently
 *   via getState() inside useFrame — scene components do NOT subscribe to it.
 * - Replay: replayTo(cursor) refolds events[0..cursor] through a fresh
 *   FoldState (pure refold). Forward scrubs fold only the delta (and emit
 *   pulses so playback feels live); backward scrubs do a full refold.
 */

import { create } from 'zustand';
import type { WorkflowEvent } from '@/types/events';
import type { WorkflowNode, WorkflowEdge } from '@/types/workflow';
import {
  buildLabelIndex,
  createFoldState,
  foldEvent,
  foldEvents,
  EMPTY_INDEX,
  type ExecutionPhase,
  type ExecTotals,
  type FoldState,
  type LabelIndex,
  type NodeExecStatus,
  type PulseRequest,
  type SubagentInfo,
} from '../lib/eventMapping';

/** Lifetime of one pulse traveling along an edge (ms). */
export const PULSE_DURATION_MS = 900;

/** How long completed/error glows linger before statuses reset to idle. */
const LINGER_MS = 3200;

/** Ended subagent orbs are kept this long for the absorb animation. */
export const SUBAGENT_FADE_MS = 1600;

/** Upper bound on simultaneously live edge pulses (InstancedMesh capacity). */
export const MAX_PULSES = 64;

/** Upper bound on simultaneously rendered subagent orbs. */
export const MAX_SUBAGENTS = 32;

export interface EdgePulse {
  id: number;
  edgeId: string;
  kind: 'tool' | 'handoff';
  bornAt: number;
}

export interface ReplayState {
  taskId: number;
  events: WorkflowEvent[];
  /** Events [0..cursor) are folded into the current view. */
  cursor: number;
  playing: boolean;
  speed: number;
}

export interface ExecutionState {
  // Folded view (React-visible)
  statuses: Record<string, NodeExecStatus>;
  subagents: Record<string, SubagentInfo>;
  totals: ExecTotals;
  executionPhase: ExecutionPhase;
  currentLabel: string | null;
  errorMessage: string | null;

  /** Live task being executed (null when idle / replaying). */
  taskId: number | null;
  runStartedAt: number | null;
  runEndedAt: number | null;
  /** True from run start until the post-completion linger ends (frameloop). */
  animating: boolean;

  /** Transient edge pulses — consumed via getState() in useFrame. */
  pulses: EdgePulse[];

  /** label -> nodeId (+edge lookups); rebuilt from workflowStore. */
  index: LabelIndex;

  replay: ReplayState | null;

  // Actions
  rebuildIndex: (nodes: WorkflowNode[], edges: WorkflowEdge[]) => void;
  beginRun: (taskId: number) => void;
  /** Cancel/stop: reset everything to idle immediately. */
  stopRun: () => void;
  ingestEvents: (events: WorkflowEvent[]) => void;
  /** Drop expired pulses (called from useFrame when some expired). */
  prunePulses: (now: number) => void;
  /** Drop fully-faded ended subagents (called from useFrame occasionally). */
  pruneSubagents: (now: number) => void;

  enterReplay: (taskId: number) => void;
  setReplayEvents: (events: WorkflowEvent[]) => void;
  replayTo: (cursor: number) => void;
  setReplayPlaying: (playing: boolean) => void;
  setReplaySpeed: (speed: number) => void;
  exitReplay: () => void;
}

// Module-level fold drafts (never read by React directly).
let liveFold: FoldState = createFoldState();
let replayFold: FoldState = createFoldState();
let replayFoldCursor = 0;
let pulseSeq = 0;
let lingerTimer: ReturnType<typeof setTimeout> | null = null;

function clearLinger() {
  if (lingerTimer !== null) {
    clearTimeout(lingerTimer);
    lingerTimer = null;
  }
}

function toPulses(requests: PulseRequest[], now: number): EdgePulse[] {
  return requests.map((r) => ({ id: ++pulseSeq, edgeId: r.edgeId, kind: r.kind, bornAt: now }));
}

export const useExecutionStore = create<ExecutionState>((set, get) => {
  /** Commit a fold draft into React-visible state (shallow copies). */
  const commitFold = (fs: FoldState, extra?: Partial<ExecutionState>) => {
    fs.changed = false;
    set({
      statuses: { ...fs.statuses },
      subagents: { ...fs.subagents },
      totals: fs.totals,
      executionPhase: fs.phase,
      currentLabel: fs.currentLabel,
      errorMessage: fs.errorMessage,
      ...extra,
    });
  };

  const scheduleLinger = () => {
    clearLinger();
    lingerTimer = setTimeout(() => {
      lingerTimer = null;
      // Reset node statuses to idle (2D hook parity: 3s after complete/error),
      // keeping totals + phase for the HUD summary.
      const now = Date.now();
      for (const label of Object.keys(liveFold.statuses)) {
        liveFold.statuses[label] = { state: 'idle', thinkingPreview: '', stateChangedAt: now };
      }
      liveFold.subagents = {};
      commitFold(liveFold, { animating: false, pulses: [] });
    }, LINGER_MS);
  };

  return {
    statuses: {},
    subagents: {},
    totals: { promptTokens: 0, completionTokens: 0, totalTokens: 0, cost: 0 },
    executionPhase: 'idle',
    currentLabel: null,
    errorMessage: null,

    taskId: null,
    runStartedAt: null,
    runEndedAt: null,
    animating: false,

    pulses: [],
    index: EMPTY_INDEX,
    replay: null,

    rebuildIndex: (nodes, edges) => {
      set({ index: buildLabelIndex(nodes, edges) });
    },

    beginRun: (taskId) => {
      clearLinger();
      liveFold = createFoldState();
      liveFold.phase = 'running';
      commitFold(liveFold, {
        taskId,
        runStartedAt: Date.now(),
        runEndedAt: null,
        animating: true,
        pulses: [],
        replay: null,
      });
    },

    stopRun: () => {
      clearLinger();
      liveFold = createFoldState();
      commitFold(liveFold, {
        taskId: null,
        runEndedAt: Date.now(),
        animating: false,
        pulses: [],
      });
    },

    ingestEvents: (events) => {
      if (events.length === 0) return;
      const state = get();
      if (state.replay) return; // live events are ignored while replaying

      const now = Date.now();
      const pulseRequests: PulseRequest[] = [];
      const phaseBefore = liveFold.phase;
      for (const event of events) {
        foldEvent(liveFold, event, state.index, {
          coalesceMs: 100, // thinking text <=10Hz per node
          now,
          pulses: pulseRequests,
        });
      }
      if (!liveFold.changed && pulseRequests.length === 0 && liveFold.phase === phaseBefore) return;

      const extra: Partial<ExecutionState> = {};
      if (pulseRequests.length > 0) {
        extra.pulses = [...state.pulses, ...toPulses(pulseRequests, now)].slice(-MAX_PULSES);
      }
      const ended = liveFold.phase === 'complete' || liveFold.phase === 'error';
      if (ended && (phaseBefore === 'running' || phaseBefore === 'idle')) {
        extra.runEndedAt = now;
        extra.taskId = null;
        scheduleLinger();
      }
      commitFold(liveFold, extra);
    },

    prunePulses: (now) => {
      const { pulses } = get();
      const alive = pulses.filter((p) => now - p.bornAt < PULSE_DURATION_MS);
      if (alive.length !== pulses.length) set({ pulses: alive });
    },

    pruneSubagents: (now) => {
      const fold = get().replay ? replayFold : liveFold;
      let removed = false;
      for (const runId of Object.keys(fold.subagents)) {
        const sub = fold.subagents[runId];
        if (sub.endedAt !== undefined && now - sub.endedAt > SUBAGENT_FADE_MS) {
          delete fold.subagents[runId];
          removed = true;
        }
      }
      if (removed) set({ subagents: { ...fold.subagents } });
    },

    // ---- Replay -------------------------------------------------------------

    enterReplay: (taskId) => {
      clearLinger();
      replayFold = createFoldState();
      replayFoldCursor = 0;
      commitFold(replayFold, {
        replay: { taskId, events: [], cursor: 0, playing: false, speed: 1 },
        taskId: null,
        animating: false,
        pulses: [],
        runStartedAt: null,
        runEndedAt: null,
      });
    },

    setReplayEvents: (events) => {
      const replay = get().replay;
      if (!replay) return;
      replayFold = createFoldState();
      replayFoldCursor = 0;
      commitFold(replayFold, {
        replay: { ...replay, events, cursor: 0, playing: false },
        pulses: [],
      });
    },

    replayTo: (cursor) => {
      const state = get();
      const replay = state.replay;
      if (!replay) return;
      const clamped = Math.max(0, Math.min(cursor, replay.events.length));

      const extra: Partial<ExecutionState> = { replay: { ...replay, cursor: clamped } };
      if (clamped >= replayFoldCursor) {
        // Forward: fold only the delta, emitting pulses for the live feel.
        const now = Date.now();
        const pulseRequests: PulseRequest[] = [];
        for (let i = replayFoldCursor; i < clamped; i++) {
          foldEvent(replayFold, replay.events[i], state.index, {
            coalesceMs: 0,
            now,
            pulses: pulseRequests,
          });
        }
        if (pulseRequests.length > 0) {
          extra.pulses = [...state.pulses, ...toPulses(pulseRequests, now)].slice(-MAX_PULSES);
        }
      } else {
        // Backward: pure refold of the prefix.
        replayFold = foldEvents(replay.events, clamped, state.index);
        extra.pulses = [];
      }
      replayFoldCursor = clamped;
      if (clamped >= replay.events.length && replay.playing) {
        extra.replay = { ...replay, cursor: clamped, playing: false };
      }
      commitFold(replayFold, extra);
    },

    setReplayPlaying: (playing) => {
      const replay = get().replay;
      if (!replay) return;
      // Restart from the top when playing a fully-scrubbed timeline.
      if (playing && replay.cursor >= replay.events.length) {
        replayFold = createFoldState();
        replayFoldCursor = 0;
        commitFold(replayFold, {
          replay: { ...replay, cursor: 0, playing: true },
          pulses: [],
        });
        return;
      }
      set({ replay: { ...replay, playing } });
    },

    setReplaySpeed: (speed) => {
      const replay = get().replay;
      if (!replay) return;
      set({ replay: { ...replay, speed } });
    },

    exitReplay: () => {
      replayFold = createFoldState();
      replayFoldCursor = 0;
      liveFold = createFoldState();
      commitFold(liveFold, {
        replay: null,
        pulses: [],
        animating: false,
        taskId: null,
        runStartedAt: null,
        runEndedAt: null,
      });
    },
  };
});
