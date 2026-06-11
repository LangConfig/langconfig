/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * useSpatialExecution — THE single SSE subscription for the 3D view.
 *
 * Mounts exactly ONE useWorkflowStream(workflowId) connection and feeds new
 * events into executionStore.ingestEvents. NEVER also mount
 * useNodeExecutionStatus here — it opens a second EventSource for the same
 * workflow (the double-EventSource trap called out in the architecture plan);
 * lib/eventMapping.ts ports its fold semantics instead.
 *
 * Event consumption uses the processed-index pattern from the 2D hook (an
 * effect over the accumulated `events` array) rather than onEvent, because
 * useWorkflowStream intentionally does NOT invoke onEvent for micro-batched
 * on_chat_model_stream tokens — the thinking shimmer would never fire.
 *
 * Also owns the execute/stop path:
 * - run(): flush pending workflowStore saves (saveNow — the 3D path never
 *   uses the lossy 2D execute PUT), then POST /api/orchestration/execute via
 *   apiClient.executeWorkflow with the same input_data shape the 2D canvas
 *   sends, capture task_id, mark the run in executionStore.
 * - stop(): apiClient.cancelTask + reset.
 *
 * Replay: when executionStore.replay is active the stream's taskId switches
 * to the historical task and loadHistorical kicks in; once loaded the events
 * are handed to the store for scrubbing. Live events are not ingested while
 * replaying.
 */

import { useCallback, useEffect, useRef } from 'react';
import apiClient from '@/lib/api-client';
import { useWorkflowStream } from '@/hooks/useWorkflowStream';
import { useSpatialWorkflowStore } from './workflowStore';
import { useExecutionStore } from './executionStore';

export interface SpatialExecutionApi {
  /** Start a run with the given goal/input text. Returns the task id. */
  run: (goal: string) => Promise<number>;
  /** Cancel the current run. */
  stop: () => Promise<void>;
}

export function useSpatialExecution(workflowId: number | null): SpatialExecutionApi {
  const taskId = useExecutionStore((s) => s.taskId);
  const replay = useExecutionStore((s) => s.replay);
  const replayTaskId = replay?.taskId ?? null;
  const replayLoaded = replay != null && replay.events.length > 0;

  const streamTaskId = replayTaskId ?? taskId;

  const { events, clearEvents, historicalLoaded } = useWorkflowStream(workflowId, {
    autoConnect: true,
    taskId: streamTaskId,
    loadHistorical: replayTaskId != null,
    maxEvents: 8000,
  });

  // Feed NEW events into the fold (live mode only).
  const lastIndexRef = useRef(0);
  useEffect(() => {
    if (replayTaskId != null) {
      // While replaying, the events array belongs to the historical task.
      lastIndexRef.current = events.length;
      return;
    }
    if (events.length < lastIndexRef.current) {
      // Stream was cleared/reset (task switch) — start over.
      lastIndexRef.current = 0;
    }
    if (events.length === lastIndexRef.current) return;
    const fresh = events.slice(lastIndexRef.current);
    lastIndexRef.current = events.length;
    useExecutionStore.getState().ingestEvents(fresh);
  }, [events, replayTaskId]);

  // Hand historical events to the replay scrubber once loaded.
  useEffect(() => {
    if (replayTaskId != null && historicalLoaded && !replayLoaded && events.length > 0) {
      useExecutionStore.getState().setReplayEvents(events);
    }
  }, [replayTaskId, historicalLoaded, replayLoaded, events]);

  // Keep the label->nodeId index in sync with the workflow graph.
  const nodes = useSpatialWorkflowStore((s) => s.nodes);
  const edges = useSpatialWorkflowStore((s) => s.edges);
  useEffect(() => {
    useExecutionStore.getState().rebuildIndex(nodes, edges);
  }, [nodes, edges]);

  // Leaving the workflow (or the view) resets execution state.
  useEffect(() => {
    return () => {
      const exec = useExecutionStore.getState();
      if (exec.replay) exec.exitReplay();
    };
  }, [workflowId]);

  const run = useCallback(
    async (goal: string): Promise<number> => {
      const wf = useSpatialWorkflowStore.getState();
      if (wf.workflowId == null) throw new Error('No workflow loaded');

      const exec = useExecutionStore.getState();
      if (exec.replay) exec.exitReplay();

      // ALWAYS flush pending saves before executing: the 3D path saves the
      // FULL persistence shape (position3d included) — never the lossy
      // {id,type,config} PUT the 2D execute path performs.
      if (wf.dirty) await wf.saveNow();

      clearEvents();
      lastIndexRef.current = 0;

      const response = await apiClient.executeWorkflow({
        workflow_id: wf.workflowId,
        project_id: 0, // standalone (parity with the 2D canvas default)
        input_data: {
          query: goal,
          task: goal,
          additional_context: '',
          max_events: 100000,
          timeout_seconds: 600,
        },
        context_documents: [],
      });

      const newTaskId: number = response.data.task_id;
      useExecutionStore.getState().beginRun(newTaskId);
      try {
        localStorage.setItem('langconfig-current-task-id', String(newTaskId));
      } catch {
        // localStorage unavailable — non-fatal
      }
      return newTaskId;
    },
    [clearEvents]
  );

  const stop = useCallback(async (): Promise<void> => {
    const currentTaskId = useExecutionStore.getState().taskId;
    if (currentTaskId == null) return;
    try {
      await apiClient.cancelTask(currentTaskId);
    } finally {
      useExecutionStore.getState().stopRun();
      try {
        localStorage.removeItem('langconfig-current-task-id');
      } catch {
        // non-fatal
      }
    }
  }, []);

  return { run, stop };
}
