/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * ReplayTimeline — bottom DOM panel for replaying finished executions.
 *
 * - Task list from GET /api/orchestration/workflows/{id}/history (the same
 *   history endpoint the 2D results view's data comes from); picking a task
 *   calls executionStore.enterReplay, which flips useSpatialExecution's
 *   stream to {taskId, loadHistorical} so the events arrive via the existing
 *   GET /api/tasks/{task_id}/events path inside useWorkflowStream.
 * - Scrubber maps directly to executionStore.replayTo(cursor) — a pure
 *   refold of events[0..cursor] (forward scrubs fold the delta; backward
 *   scrubs refold from scratch).
 * - Play advances a virtual clock scaled by event timestamps (dead-air gaps
 *   are capped) and folds events as their timestamps pass.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import apiClient from '@/lib/api-client';
import { useExecutionStore } from '../state/executionStore';

interface HistoryTask {
  id: number;
  user_input: string;
  status: string;
  created_at: string | null;
  completed_at: string | null;
  duration_seconds?: number;
  error_message?: string | null;
}

/** Gaps between events longer than this are skipped during playback. */
const MAX_GAP_MS = 1200;
const SPEEDS = [1, 2, 4];

function statusColor(status: string): string {
  switch (status.toLowerCase()) {
    case 'completed':
      return 'var(--color-success)';
    case 'failed':
    case 'error':
      return 'var(--color-error)';
    case 'in_progress':
    case 'queued':
      return 'var(--color-info)';
    default:
      return 'var(--color-text-muted)';
  }
}

export default function ReplayTimeline({
  workflowId,
  onClose,
}: {
  workflowId: number;
  onClose: () => void;
}) {
  const replay = useExecutionStore((s) => s.replay);
  const liveTaskId = useExecutionStore((s) => s.taskId);

  const [tasks, setTasks] = useState<HistoryTask[]>([]);
  const [loading, setLoading] = useState(true);

  // Load the task history when the panel opens / workflow changes.
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    (async () => {
      try {
        const response = await apiClient.getWorkflowHistory(workflowId, 25);
        if (!cancelled) setTasks(response.data?.tasks ?? []);
      } catch (err) {
        console.error('Failed to load workflow history:', err);
        if (!cancelled) setTasks([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [workflowId]);

  // ---- Playback loop --------------------------------------------------------
  // Virtual clock in event-timestamp space; reads the store transiently so
  // the loop never closes over stale cursors.
  const rafRef = useRef<number | null>(null);
  useEffect(() => {
    const playing = replay?.playing ?? false;
    if (!playing) return;

    let last = performance.now();
    let virtual: number | null = null;

    const tick = (now: number) => {
      const store = useExecutionStore.getState();
      const r = store.replay;
      if (!r || !r.playing) return;
      const events = r.events;
      if (r.cursor >= events.length) {
        store.setReplayPlaying(false);
        return;
      }

      if (virtual == null) {
        // Anchor the clock at the next unplayed event.
        virtual = new Date(events[r.cursor].timestamp).getTime();
      }
      virtual += (now - last) * r.speed;
      last = now;

      let next = r.cursor;
      while (next < events.length) {
        const eventTime = new Date(events[next].timestamp).getTime();
        if (eventTime <= virtual) {
          next += 1;
        } else {
          // Cap dead air so quiet stretches don't stall playback.
          if (eventTime - virtual > MAX_GAP_MS) virtual = eventTime - MAX_GAP_MS;
          break;
        }
      }
      if (next !== r.cursor) store.replayTo(next);
      rafRef.current = requestAnimationFrame(tick);
    };

    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    };
    // Restart the loop when play/speed toggles or a new task loads.
  }, [replay?.playing, replay?.speed, replay?.taskId]);

  const exec = useExecutionStore.getState();

  const handlePick = useCallback((taskId: number) => {
    useExecutionStore.getState().enterReplay(taskId);
  }, []);

  const handleClose = useCallback(() => {
    useExecutionStore.getState().exitReplay();
    onClose();
  }, [onClose]);

  const total = replay?.events.length ?? 0;
  const cursor = replay?.cursor ?? 0;
  const eventsLoaded = replay != null && total > 0;

  return (
    <div className="absolute bottom-20 left-1/2 z-40 w-[min(680px,90vw)] -translate-x-1/2">
      <div className="surface-card px-4 py-3">
        <div className="flex items-center justify-between">
          <span
            className="text-xs font-bold uppercase tracking-wider"
            style={{ color: 'var(--color-text-primary)', fontFamily: 'var(--font-family-mono)' }}
          >
            Replay
          </span>
          <button
            onClick={handleClose}
            title="Close replay"
            className="flex items-center px-1 py-0.5 transition-colors hover:bg-black/5 dark:hover:bg-white/5"
            style={{ color: 'var(--color-text-muted)' }}
          >
            <span className="material-symbols-outlined text-base">close</span>
          </button>
        </div>

        {/* Task picker */}
        <div className="mt-2 max-h-36 overflow-auto border" style={{ borderColor: 'var(--border-strong)' }}>
          {loading ? (
            <p className="px-3 py-2 text-xs" style={{ color: 'var(--color-text-muted)' }}>
              Loading history…
            </p>
          ) : tasks.length === 0 ? (
            <p className="px-3 py-2 text-xs" style={{ color: 'var(--color-text-muted)' }}>
              No past executions for this workflow yet.
            </p>
          ) : (
            tasks.map((task) => {
              const active = replay?.taskId === task.id;
              return (
                <button
                  key={task.id}
                  onClick={() => handlePick(task.id)}
                  disabled={liveTaskId != null}
                  className="flex w-full items-center gap-2 px-3 py-1.5 text-left transition-colors hover:bg-black/5 disabled:opacity-50 dark:hover:bg-white/5"
                  style={{ background: active ? 'var(--surface-2)' : 'transparent' }}
                >
                  <span
                    className="inline-block h-1.5 w-1.5 shrink-0 rounded-full"
                    style={{ background: statusColor(task.status) }}
                  />
                  <span
                    className="shrink-0 text-[0.68rem] font-bold tabular-nums"
                    style={{ color: 'var(--color-text-muted)', fontFamily: 'var(--font-family-mono)' }}
                  >
                    #{task.id}
                  </span>
                  <span
                    className="min-w-0 flex-1 truncate text-xs"
                    style={{ color: 'var(--color-text-primary)' }}
                    title={task.user_input}
                  >
                    {task.user_input || '(no prompt)'}
                  </span>
                  {task.created_at && (
                    <span
                      className="shrink-0 text-[0.65rem]"
                      style={{ color: 'var(--color-text-muted)', fontFamily: 'var(--font-family-mono)' }}
                    >
                      {new Date(task.created_at).toLocaleString(undefined, {
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </span>
                  )}
                </button>
              );
            })
          )}
        </div>

        {/* Scrubber + transport */}
        {replay != null && (
          <div className="mt-2.5 flex items-center gap-3">
            <button
              onClick={() => exec.setReplayPlaying(!(replay.playing ?? false))}
              disabled={!eventsLoaded}
              title={replay.playing ? 'Pause' : 'Play'}
              className="btn-brutal flex items-center px-2 py-1 disabled:opacity-50"
            >
              <span className="material-symbols-outlined text-base">
                {replay.playing ? 'pause' : 'play_arrow'}
              </span>
            </button>

            <input
              type="range"
              min={0}
              max={Math.max(total, 1)}
              step={1}
              value={cursor}
              disabled={!eventsLoaded}
              onChange={(e) => useExecutionStore.getState().replayTo(Number(e.target.value))}
              className="min-w-0 flex-1"
              style={{ accentColor: 'var(--color-primary)' }}
            />

            <span
              className="shrink-0 text-[0.68rem] font-semibold tabular-nums"
              style={{ color: 'var(--color-text-muted)', fontFamily: 'var(--font-family-mono)' }}
            >
              {eventsLoaded ? `${cursor}/${total}` : 'loading…'}
            </span>

            <div
              className="flex shrink-0 items-center overflow-hidden border"
              style={{ borderColor: 'var(--border-strong)', borderRadius: 'var(--radius-control)' }}
            >
              {SPEEDS.map((speed) => (
                <button
                  key={speed}
                  onClick={() => useExecutionStore.getState().setReplaySpeed(speed)}
                  className="px-1.5 py-0.5 text-[0.65rem] font-bold"
                  style={{
                    background: replay.speed === speed ? 'var(--color-primary)' : 'transparent',
                    color:
                      replay.speed === speed
                        ? 'var(--color-on-accent)'
                        : 'var(--color-text-primary)',
                    fontFamily: 'var(--font-family-mono)',
                  }}
                >
                  {speed}×
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
