/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * SpatialWorkflowView — top-level lazy view for the 3D workflow scene.
 *
 * Stage 2 (builder): hosts the R3F canvas plus DOM overlays — workflow
 * picker, node palette, toolbar (modes / fit / open-in-2D / save chip) and
 * the reused NodeConfigPanel. Owns the keyboard shortcuts (Esc cancels
 * interactions, Delete removes the selection) and surfaces store notices /
 * save conflicts as toasts.
 */

import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '@/lib/api-client';
import { useToast } from '@/hooks/useToast';
import type { Workflow, WorkflowNode } from '@/types/workflow';
import SpatialCanvas from './SpatialCanvas';
import WorkflowPicker from './hud/WorkflowPicker';
import NodePalette from './builder/NodePalette';
import SpatialToolbar from './builder/SpatialToolbar';
import SpatialNodeConfig from './builder/SpatialNodeConfig';
import { useSpatialWorkflowStore, getLastSpatialWorkflowId } from './state/workflowStore';
import { useSceneStore } from './state/sceneStore';
import { to2DPosition } from './lib/layout3d';

/** Counter seed for the 2D canvas, derived the same way it derives it. */
function nodeCounterFrom(nodes: WorkflowNode[]): number {
  let max = 0;
  for (const n of nodes) {
    const match = n.id.match(/node-(\d+)/);
    if (match) max = Math.max(max, parseInt(match[1], 10));
  }
  return max + 1;
}

export default function SpatialWorkflowView() {
  const navigate = useNavigate();
  const { showToast } = useToast();
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [listLoading, setListLoading] = useState(true);

  const workflowId = useSpatialWorkflowStore((s) => s.workflowId);
  const loading = useSpatialWorkflowStore((s) => s.loading);
  const error = useSpatialWorkflowStore((s) => s.error);
  const nodeCount = useSpatialWorkflowStore((s) => s.nodes.length);
  const loadWorkflow = useSpatialWorkflowStore((s) => s.loadWorkflow);
  const conflictSeq = useSpatialWorkflowStore((s) => s.conflictSeq);

  const mode = useSceneStore((s) => s.mode);
  const hoveredNodeId = useSceneStore((s) => s.hoveredNodeId);
  const notice = useSceneStore((s) => s.notice);
  const noticeSeq = useSceneStore((s) => s.noticeSeq);

  // Fetch the workflow list once; auto-load the remembered (or first)
  // workflow if nothing is loaded yet. The store is global, so revisiting
  // the view keeps the previously loaded workflow.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const response = await apiClient.listWorkflows();
        if (cancelled) return;
        const list: Workflow[] = Array.isArray(response.data) ? response.data : [];
        setWorkflows(list);

        const current = useSpatialWorkflowStore.getState().workflowId;
        if (current == null && list.length > 0) {
          const last = getLastSpatialWorkflowId();
          const target =
            last != null && list.some((w) => w.id === last) ? last : list[0].id;
          void loadWorkflow(target);
        }
      } catch (err) {
        console.error('Failed to fetch workflows for spatial view:', err);
      } finally {
        if (!cancelled) setListLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [loadWorkflow]);

  // Keyboard shortcuts: Esc cancels interactions / selection, Delete removes
  // the selected node (plus attached edges) or edge.
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.tagName === 'SELECT' ||
          target.isContentEditable)
      ) {
        return;
      }

      if (e.key === 'Escape') {
        const scene = useSceneStore.getState();
        if (scene.mode !== 'idle') scene.resetInteraction();
        else if (scene.selection) scene.clearSelection();
      } else if (e.key === 'Delete' || e.key === 'Backspace') {
        const scene = useSceneStore.getState();
        const sel = scene.selection;
        if (!sel) return;
        e.preventDefault();
        const wf = useSpatialWorkflowStore.getState();
        if (sel.kind === 'node') wf.removeNode(sel.id);
        else wf.removeEdge(sel.id);
        scene.clearSelection();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  // Scene notices (rejected connections, etc.) -> toasts.
  const lastNoticeSeq = useRef(0);
  useEffect(() => {
    if (noticeSeq > lastNoticeSeq.current) {
      lastNoticeSeq.current = noticeSeq;
      if (notice) showToast(notice, 'warning');
    }
  }, [notice, noticeSeq, showToast]);

  // Optimistic-lock conflicts -> reload happened in the store; explain it.
  const lastConflictSeq = useRef(conflictSeq);
  useEffect(() => {
    if (conflictSeq > lastConflictSeq.current) {
      lastConflictSeq.current = conflictSeq;
      showToast(
        'Workflow was modified elsewhere — reloaded the latest version',
        'warning'
      );
    }
  }, [conflictSeq, showToast]);

  // Open the same workflow in the 2D Studio canvas. Flush any pending save,
  // then hand the canvas its restore payload via the same localStorage shape
  // it persists itself ('langconfig-workflow', see WorkflowCanvas.tsx:1054).
  const handleOpenIn2D = async () => {
    const store = useSpatialWorkflowStore.getState();
    if (store.workflowId == null) return;
    if (store.dirty) await store.saveNow();

    const { nodes, edges, positions, origin2d, workflowId: id, workflowName } =
      useSpatialWorkflowStore.getState();
    try {
      const rfNodes = nodes.map((n) => ({
        id: n.id,
        type: 'custom',
        position:
          n.position ??
          (positions[n.id] ? to2DPosition(positions[n.id], origin2d) : { x: 250, y: 250 }),
        data: n.data,
      }));
      const rfEdges = edges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        label: e.label,
        data: e.data,
        type: 'smoothstep',
      }));
      localStorage.setItem(
        'langconfig-workflow',
        JSON.stringify({
          nodes: rfNodes,
          edges: rfEdges,
          counter: nodeCounterFrom(nodes),
          name: workflowName,
          workflowId: id,
        })
      );
      localStorage.setItem('langconfig-workflow-id', String(id));
    } catch (err) {
      console.error('Failed to hand off workflow to the 2D canvas:', err);
    }
    navigate('/studio');
  };

  const cursor =
    mode !== 'idle' ? 'crosshair' : hoveredNodeId ? 'pointer' : 'default';

  return (
    <div className="relative h-full w-full overflow-hidden" style={{ cursor }}>
      <SpatialCanvas />

      {/* DOM overlays (HUD) */}
      <WorkflowPicker
        workflows={workflows}
        selectedId={workflowId}
        loading={listLoading}
        onSelect={(id) => void loadWorkflow(id)}
      />

      {workflowId != null && !loading && !error && (
        <>
          <NodePalette />
          <SpatialToolbar onOpenIn2D={() => void handleOpenIn2D()} />
          <SpatialNodeConfig />
        </>
      )}

      {/* Loading overlay */}
      {loading && (
        <div className="pointer-events-none absolute inset-0 z-40 flex items-center justify-center">
          <div className="surface-card px-5 py-4">
            <div
              className="mb-2 h-1.5 w-28 overflow-hidden border"
              style={{ borderColor: 'var(--border-strong)', background: 'var(--surface-2)' }}
            >
              <div className="h-full w-1/2 animate-pulse" style={{ background: 'var(--color-primary)' }} />
            </div>
            <p
              className="text-sm font-semibold uppercase tracking-wide"
              style={{ color: 'var(--color-text-primary)' }}
            >
              Loading workflow
            </p>
          </div>
        </div>
      )}

      {/* Error state */}
      {error && !loading && (
        <div className="absolute inset-0 z-40 flex items-center justify-center">
          <div className="surface-card max-w-md px-6 py-5">
            <p
              className="text-sm font-semibold uppercase tracking-wide"
              style={{ color: 'var(--color-error)' }}
            >
              Failed to load workflow
            </p>
            <p className="mt-2 text-sm" style={{ color: 'var(--color-text-muted)' }}>
              {error}
            </p>
          </div>
        </div>
      )}

      {/* Empty workflow state */}
      {!loading && !error && workflowId != null && nodeCount === 0 && (
        <div className="pointer-events-none absolute inset-0 z-30 flex items-center justify-center">
          <div className="surface-card max-w-md px-6 py-5 text-center">
            <p
              className="text-sm font-semibold uppercase tracking-wide"
              style={{ color: 'var(--color-text-primary)' }}
            >
              Empty workflow
            </p>
            <p className="mt-2 text-sm" style={{ color: 'var(--color-text-muted)' }}>
              Pick a node kind from the palette on the left, then click the
              ground to place it.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
