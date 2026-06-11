/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * SpatialToolbar — bottom-center DOM HUD: interaction mode buttons
 * (select / place / connect), Run/Stop, Replay, fit-view, open-in-2D,
 * workflow name, and the save-status chip (debounced autosave with
 * lock_version handling lives in workflowStore).
 */

import { useSceneStore } from '../state/sceneStore';
import { useSpatialWorkflowStore } from '../state/workflowStore';
import { useExecutionStore } from '../state/executionStore';
import type { SaveStatus } from '../types';

function saveChip(status: SaveStatus, dirty: boolean): { text: string; color: string } {
  if (status === 'saving') return { text: 'Saving…', color: 'var(--color-info)' };
  if (status === 'error') return { text: 'Save failed', color: 'var(--color-error)' };
  if (status === 'conflict') return { text: 'Reloaded', color: 'var(--color-warning)' };
  if (dirty) return { text: 'Unsaved', color: 'var(--color-warning)' };
  if (status === 'saved') return { text: 'Saved', color: 'var(--color-success)' };
  return { text: 'Synced', color: 'var(--color-text-muted)' };
}

export default function SpatialToolbar({
  onOpenIn2D,
  onRun,
  onStop,
  onToggleReplay,
  replayOpen,
}: {
  onOpenIn2D: () => void;
  /** Open the goal dialog (the actual POST happens in useSpatialExecution). */
  onRun: () => void;
  onStop: () => void;
  onToggleReplay: () => void;
  replayOpen: boolean;
}) {
  const mode = useSceneStore((s) => s.mode);
  const resetInteraction = useSceneStore((s) => s.resetInteraction);
  const startPlacing = useSceneStore((s) => s.startPlacing);
  const startConnecting = useSceneStore((s) => s.startConnecting);
  const requestFit = useSceneStore((s) => s.requestFit);

  const workflowName = useSpatialWorkflowStore((s) => s.workflowName);
  const workflowId = useSpatialWorkflowStore((s) => s.workflowId);
  const saveStatus = useSpatialWorkflowStore((s) => s.saveStatus);
  const dirty = useSpatialWorkflowStore((s) => s.dirty);
  const nodeCount = useSpatialWorkflowStore((s) => s.nodes.length);

  const running = useExecutionStore((s) => s.taskId != null);
  const replaying = useExecutionStore((s) => s.replay != null);

  if (workflowId == null) return null;

  const chip = saveChip(saveStatus, dirty);

  const modeButton = (
    label: string,
    icon: string,
    active: boolean,
    onClick: () => void,
    title: string
  ) => (
    <button
      onClick={onClick}
      title={title}
      className="flex items-center gap-1 px-2.5 py-1.5 text-[0.66rem] font-semibold uppercase tracking-wider transition-colors hover:bg-black/5 dark:hover:bg-white/5"
      style={{
        background: active ? 'var(--color-primary)' : 'transparent',
        color: active ? 'var(--color-on-accent)' : 'var(--color-text-primary)',
        fontFamily: 'var(--font-family-mono)',
      }}
    >
      <span className="material-symbols-outlined text-sm">{icon}</span>
      {label}
    </button>
  );

  return (
    <div className="absolute bottom-4 left-1/2 z-40 -translate-x-1/2">
      <div className="surface-card flex items-center gap-3 px-3 py-2">
        {/* Workflow name */}
        <span
          className="max-w-48 truncate text-xs font-bold uppercase tracking-wide"
          style={{ color: 'var(--color-text-primary)' }}
          title={workflowName}
        >
          {workflowName}
        </span>

        <span className="h-5 w-px" style={{ background: 'var(--border-strong)' }} />

        {/* Mode buttons */}
        <div
          className="flex items-center overflow-hidden border"
          style={{ borderColor: 'var(--border-strong)', borderRadius: 'var(--radius-control)' }}
        >
          {modeButton('Select', 'arrow_selector_tool', mode === 'idle', resetInteraction, 'Select / move nodes (Esc)')}
          {modeButton('Place', 'add_box', mode === 'placing', () => startPlacing('agent'), 'Place a node (pick a kind in the palette)')}
          {modeButton('Connect', 'conversion_path', mode === 'connecting', () => startConnecting(null), 'Connect: click a source node, then a target')}
        </div>

        {/* Run / Stop */}
        {running ? (
          <button
            onClick={onStop}
            className="flex items-center gap-1 px-2.5 py-1.5 text-[0.66rem] font-bold uppercase tracking-wider"
            title="Cancel the current run"
            style={{
              background: 'var(--color-error)',
              color: 'var(--color-on-accent)',
              border: 'var(--border-w) solid var(--border-strong)',
              borderRadius: 'var(--radius-control)',
              boxShadow: 'var(--shadow-card-sm)',
              fontFamily: 'var(--font-family-mono)',
            }}
          >
            <span className="material-symbols-outlined text-sm">stop</span>
            Stop
          </button>
        ) : (
          <button
            onClick={onRun}
            disabled={nodeCount === 0 || replaying}
            className="flex items-center gap-1 px-2.5 py-1.5 text-[0.66rem] font-bold uppercase tracking-wider transition-opacity disabled:opacity-50"
            title={replaying ? 'Close the replay first' : 'Run this workflow'}
            style={{
              background: 'var(--color-primary)',
              color: 'var(--color-on-accent)',
              border: 'var(--border-w) solid var(--border-strong)',
              borderRadius: 'var(--radius-control)',
              boxShadow: 'var(--shadow-card-sm)',
              fontFamily: 'var(--font-family-mono)',
            }}
          >
            <span className="material-symbols-outlined text-sm">play_arrow</span>
            Run
          </button>
        )}

        {/* Replay panel toggle */}
        <button
          onClick={onToggleReplay}
          disabled={running}
          className="btn-brutal flex items-center gap-1 px-2.5 py-1.5 disabled:opacity-50"
          title="Replay past executions"
          style={replayOpen ? { background: 'var(--color-primary)', color: 'var(--color-on-accent)' } : undefined}
        >
          <span className="material-symbols-outlined text-sm">history</span>
          Replay
        </button>

        <button onClick={requestFit} className="btn-brutal flex items-center gap-1 px-2.5 py-1.5" title="Fit view to graph">
          <span className="material-symbols-outlined text-sm">fit_screen</span>
          Fit
        </button>

        <button onClick={onOpenIn2D} className="btn-brutal flex items-center gap-1 px-2.5 py-1.5" title="Open this workflow in the 2D Studio canvas">
          <span className="material-symbols-outlined text-sm">design_services</span>
          2D
        </button>

        {/* Save status chip */}
        <span
          className="badge-mono border"
          style={{
            color: chip.color,
            borderColor: chip.color,
            background: 'var(--surface-2)',
          }}
        >
          <span
            className="inline-block h-1.5 w-1.5 rounded-full"
            style={{ background: chip.color }}
          />
          {chip.text}
        </span>
      </div>
    </div>
  );
}
