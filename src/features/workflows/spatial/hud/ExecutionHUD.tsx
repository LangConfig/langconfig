/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * ExecutionHUD — top-right DOM overlay during runs and replays:
 * phase chip, elapsed time, token/cost totals, per-node state dots,
 * follow-cam toggle, and an error banner. (Run/Stop live in SpatialToolbar.)
 *
 * Reads only React-visible execution state (statuses/totals/phase); all
 * per-frame data stays inside the scene components.
 */

import { useEffect, useMemo, useState } from 'react';
import { formatCost } from '@/utils/modelPricing';
import type { WorkflowNode } from '@/types/workflow';
import { useExecutionStore } from '../state/executionStore';
import { useSpatialWorkflowStore } from '../state/workflowStore';
import { useSceneStore } from '../state/sceneStore';
import type { NodeExecState } from '../lib/eventMapping';

function phaseChip(phase: string, replaying: boolean): { text: string; color: string } {
  if (replaying) return { text: 'Replay', color: 'var(--color-info)' };
  switch (phase) {
    case 'running':
      return { text: 'Running', color: 'var(--color-primary)' };
    case 'complete':
      return { text: 'Complete', color: 'var(--color-success)' };
    case 'error':
      return { text: 'Error', color: 'var(--color-error)' };
    default:
      return { text: 'Idle', color: 'var(--color-text-muted)' };
  }
}

const DOT_COLORS: Record<NodeExecState, string> = {
  idle: 'var(--border-strong)',
  running: 'var(--color-primary)',
  thinking: 'var(--color-info)',
  completed: 'var(--color-success)',
  error: 'var(--color-error)',
};

function nodeLabelOf(node: WorkflowNode): string {
  return (
    (typeof node.data?.label === 'string' && node.data.label) ||
    (typeof node.data?.name === 'string' && node.data.name) ||
    node.type ||
    node.id
  );
}

function formatElapsed(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return m > 0 ? `${m}m ${String(s).padStart(2, '0')}s` : `${s}s`;
}

export default function ExecutionHUD() {
  const executionPhase = useExecutionStore((s) => s.executionPhase);
  const totals = useExecutionStore((s) => s.totals);
  const statuses = useExecutionStore((s) => s.statuses);
  const subagents = useExecutionStore((s) => s.subagents);
  const errorMessage = useExecutionStore((s) => s.errorMessage);
  const taskId = useExecutionStore((s) => s.taskId);
  const runStartedAt = useExecutionStore((s) => s.runStartedAt);
  const runEndedAt = useExecutionStore((s) => s.runEndedAt);
  const animating = useExecutionStore((s) => s.animating);
  const replaying = useExecutionStore((s) => s.replay != null);

  const nodes = useSpatialWorkflowStore((s) => s.nodes);
  const followCam = useSceneStore((s) => s.followCam);
  const setFollowCam = useSceneStore((s) => s.setFollowCam);

  // Elapsed ticker (500ms) — only while the run is live.
  const [, setTick] = useState(0);
  useEffect(() => {
    if (!animating || runStartedAt == null) return;
    const interval = setInterval(() => setTick((t) => t + 1), 500);
    return () => clearInterval(interval);
  }, [animating, runStartedAt]);

  const runningSubagents = useMemo(
    () => Object.values(subagents).filter((s) => s.state === 'running').length,
    [subagents]
  );

  const visible =
    replaying || taskId != null || executionPhase !== 'idle' || runStartedAt != null;
  if (!visible) return null;

  const chip = phaseChip(executionPhase, replaying);
  const elapsedMs =
    runStartedAt != null ? (runEndedAt ?? Date.now()) - runStartedAt : null;

  return (
    <div className="absolute right-4 top-4 z-40 w-64">
      <div className="surface-card px-3 py-2.5">
        {/* Phase + elapsed + follow toggle */}
        <div className="flex items-center justify-between gap-2">
          <span
            className="badge-mono border"
            style={{ color: chip.color, borderColor: chip.color, background: 'var(--surface-2)' }}
          >
            <span className="inline-block h-1.5 w-1.5 rounded-full" style={{ background: chip.color }} />
            {chip.text}
          </span>
          {elapsedMs != null && (
            <span
              className="text-[0.7rem] font-semibold tabular-nums"
              style={{ color: 'var(--color-text-muted)', fontFamily: 'var(--font-family-mono)' }}
            >
              {formatElapsed(elapsedMs)}
            </span>
          )}
          <button
            onClick={() => setFollowCam(!followCam)}
            title={followCam ? 'Follow camera: on (any manual input cancels)' : 'Follow the running node with the camera'}
            className="flex items-center px-1.5 py-1 transition-colors hover:bg-black/5 dark:hover:bg-white/5"
            style={{
              background: followCam ? 'var(--color-primary)' : 'transparent',
              color: followCam ? 'var(--color-on-accent)' : 'var(--color-text-primary)',
              border: '1px solid var(--border-strong)',
              borderRadius: 'var(--radius-control)',
            }}
          >
            <span className="material-symbols-outlined text-sm">my_location</span>
          </button>
        </div>

        {/* Totals */}
        <div
          className="mt-2 flex items-center justify-between text-[0.7rem] font-semibold"
          style={{ color: 'var(--color-text-muted)', fontFamily: 'var(--font-family-mono)' }}
        >
          <span title="Total tokens (prompt + completion)">
            {totals.totalTokens.toLocaleString()} tok
          </span>
          <span title="Accumulated cost">{formatCost(totals.cost)}</span>
          {runningSubagents > 0 && (
            <span title="Running subagents" style={{ color: 'var(--color-info)' }}>
              {runningSubagents} sub
            </span>
          )}
        </div>

        {/* Per-node state dots */}
        {nodes.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {nodes.map((node) => {
              const label = nodeLabelOf(node);
              const state: NodeExecState = statuses[label]?.state ?? 'idle';
              return (
                <span
                  key={node.id}
                  title={`${label}: ${state}`}
                  className="inline-block h-2 w-2 rounded-full border"
                  style={{
                    background: DOT_COLORS[state],
                    borderColor: 'var(--border-strong)',
                  }}
                />
              );
            })}
          </div>
        )}

        {/* Error banner */}
        {errorMessage && (
          <div
            className="mt-2 border px-2 py-1.5 text-[0.7rem] font-semibold"
            style={{
              color: 'var(--color-error)',
              borderColor: 'var(--color-error)',
              background: 'var(--surface-2)',
              borderRadius: 'var(--radius-control)',
            }}
          >
            {errorMessage.slice(0, 160)}
          </div>
        )}
      </div>
    </div>
  );
}
