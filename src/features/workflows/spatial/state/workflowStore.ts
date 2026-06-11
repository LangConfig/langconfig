/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * Spatial workflow store (zustand) — persistent workflow truth for the 3D view.
 *
 * Stage 2: mutations (place, drag, connect, config edit, delete) plus a
 * debounced PUT that mirrors the FULL persistence shape used by the 2D
 * canvas (useWorkflowPersistence.ts:148-190 — per node {id, type, data,
 * position, config} with data saved verbatim so data.position3d round-trips),
 * with lock_version optimistic locking. On a 409 the latest version is
 * reloaded and conflictSeq is bumped so the view can toast.
 *
 * Conventions copied from the 2D canvas:
 * - node ids:  `node-${Date.now()}` (WorkflowCanvas.tsx:804 duplicate path;
 *   matches the `node-(\d+)` counter-restore regex)
 * - edge ids:  `e-${source}-${target}-${Date.now()}` (WorkflowCanvas.tsx:1244)
 * - persisted type: `n.data.agentType || label.toLowerCase().replace(/\s+/g,'_')`
 * - config normalization (native_tools/enable_memory/enable_rag flags)
 */

import { create } from 'zustand';
import apiClient, { ConflictErrorClass } from '@/lib/api-client';
import type { AgentConfig, Workflow, WorkflowNode, WorkflowEdge, NodeData } from '@/types/workflow';
import { computePositions, to2DPosition, DEFAULT_ORIGIN_2D, type Origin2D } from '../lib/layout3d';
import type { SpatialNodeKind } from '../builder/nodeKinds';
import { LAST_SPATIAL_WORKFLOW_KEY, SAVE_DEBOUNCE_MS, type SaveStatus, type Vec3 } from '../types';

export interface SpatialWorkflowState {
  workflowId: number | null;
  workflowName: string;
  /** Optimistic-locking version; sent with every PUT, updated from responses. */
  lockVersion: number;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  /** Derived world positions keyed by node id (see lib/layout3d.ts). */
  positions: Record<string, Vec3>;
  /** 2D px origin captured at load — used to derive node.position from 3D moves. */
  origin2d: Origin2D;
  loading: boolean;
  error: string | null;

  dirty: boolean;
  saveStatus: SaveStatus;
  /** Monotonic counter bumped on every mutation (guards stale save results). */
  mutationSeq: number;
  /** Bumped whenever a 409 conflict forced a reload (view shows a toast). */
  conflictSeq: number;

  loadWorkflow: (id: number) => Promise<void>;
  clear: () => void;

  /** Place a new node at a world position; returns the new node id. */
  addNode: (kind: SpatialNodeKind, pos: Vec3) => string;
  /** Ephemeral position update during drag (positions map only, no save). */
  moveNode: (id: string, pos: Vec3) => void;
  /** Persist the dragged position into data.position3d + derived 2D position. */
  commitNodePosition: (id: string) => void;
  /** Merge a NodeConfigPanel fullConfig into the node (2D updateNodeConfig parity). */
  updateNodeConfig: (id: string, newConfig: Record<string, unknown>) => void;
  /** Create an edge; rejects self-loops and duplicates. */
  addEdgeBetween: (source: string, target: string) => { ok: boolean; reason?: string };
  removeNode: (id: string) => void;
  removeEdge: (id: string) => void;

  /** Debounced save (800ms after the last mutation). */
  scheduleSave: () => void;
  /** Immediate save (flushes any pending debounce). */
  saveNow: () => Promise<void>;
}

let saveTimer: ReturnType<typeof setTimeout> | null = null;

function clearSaveTimer() {
  if (saveTimer !== null) {
    clearTimeout(saveTimer);
    saveTimer = null;
  }
}

function normalizeEdges(raw: unknown): WorkflowEdge[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((e): e is WorkflowEdge => Boolean(e && typeof e === 'object' && (e as WorkflowEdge).source && (e as WorkflowEdge).target))
    .map((e, i) => ({
      ...e,
      id: e.id || `e-${e.source}-${e.target}-${i}`,
    }));
}

/**
 * Ensure every node carries a usable data object (label/agentType/config) so
 * selection + the reused NodeConfigPanel work. Mirrors the restore
 * normalization in WorkflowCanvas.tsx handleWorkflowSwitch (~1788-1808).
 */
function normalizeNodes(raw: WorkflowNode[]): WorkflowNode[] {
  return raw.map((n) => {
    let agentType = String(n.data?.agentType || n.type || 'agent');
    const lower = agentType.toLowerCase();
    if (lower === 'conditional') agentType = 'CONDITIONAL_NODE';
    if (lower === 'loop') agentType = 'LOOP_NODE';
    if (lower === 'start') agentType = 'START_NODE';
    if (lower === 'end') agentType = 'END_NODE';
    if (lower === 'approval') agentType = 'APPROVAL_NODE';
    if (lower === 'tool') agentType = 'TOOL_NODE';

    const data: NodeData = n.data
      ? { ...n.data, agentType: n.data.agentType || agentType }
      : {
          label: n.type
            ? n.type.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())
            : `Node ${n.id}`,
          agentType,
          model: n.config?.model,
          config: (n.config || {}) as AgentConfig,
        };

    return { ...n, data };
  });
}

/** Unique node id following the 2D `node-${number}` convention. */
function uniqueNodeId(nodes: WorkflowNode[]): string {
  let stamp = Date.now();
  const taken = new Set(nodes.map((n) => n.id));
  while (taken.has(`node-${stamp}`)) stamp += 1;
  return `node-${stamp}`;
}

/**
 * Build the FULL persistence shape — exact mirror of
 * useWorkflowPersistence.ts:148-190 (data saved verbatim, including
 * data.position3d, plus position and a normalized config).
 */
function buildConfiguration(nodes: WorkflowNode[], edges: WorkflowEdge[]) {
  return {
    nodes: nodes.map((n) => {
      const dataConfig = (n.data?.config ?? {}) as Record<string, unknown>;
      const nativeTools = (dataConfig.native_tools || dataConfig.nativeTools || []) as string[];

      const nodeConfig = {
        ...dataConfig, // Preserve all existing config fields (CONDITIONAL_NODE, etc.)
        model: (dataConfig.model as string) || 'gpt-5.4-mini',
        temperature: (dataConfig.temperature as number) ?? 0.7,
        system_prompt: (dataConfig.system_prompt as string) || '',
        tools: dataConfig.tools || [],
        native_tools: nativeTools,
        custom_tools: dataConfig.custom_tools || [],
        enable_memory:
          ((dataConfig.enable_memory as boolean) ?? nativeTools.includes('enable_memory')) || false,
        enable_rag:
          ((dataConfig.enable_rag as boolean) ?? nativeTools.includes('enable_rag')) || false,
      };

      return {
        id: n.id,
        type:
          n.data?.agentType ||
          String(n.data?.label || n.type || 'node').toLowerCase().replace(/\s+/g, '_'),
        data: n.data, // Full data object (includes position3d) so 2D restores it verbatim
        position: n.position,
        config: nodeConfig,
      };
    }),
    edges: edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      label: e.label,
      data: e.data,
    })),
  };
}

export const useSpatialWorkflowStore = create<SpatialWorkflowState>((set, get) => {
  /** Common post-mutation bookkeeping: bump seq, mark dirty, debounce save. */
  const touch = () => {
    set((s) => ({ dirty: true, mutationSeq: s.mutationSeq + 1 }));
    get().scheduleSave();
  };

  return {
    workflowId: null,
    workflowName: '',
    lockVersion: 1,
    nodes: [],
    edges: [],
    positions: {},
    origin2d: { ...DEFAULT_ORIGIN_2D },
    loading: false,
    error: null,

    dirty: false,
    saveStatus: 'idle',
    mutationSeq: 0,
    conflictSeq: 0,

    loadWorkflow: async (id: number) => {
      // Flush pending edits before switching to a different workflow so the
      // debounced save is not silently discarded.
      const prev = get();
      if (prev.workflowId != null && prev.workflowId !== id && prev.dirty) {
        await get().saveNow();
      }
      clearSaveTimer();
      set({ loading: true, error: null });
      try {
        const response = await apiClient.getWorkflow(id);
        const workflow = response.data as Workflow & { lock_version?: number };

        // Studio saves canvas state under `configuration`; some older workflows
        // store it under `blueprint` instead (see WorkflowDetailedView.tsx).
        const nodes = normalizeNodes(
          workflow.configuration?.nodes ?? workflow.blueprint?.nodes ?? []
        );
        const edges = normalizeEdges(
          workflow.configuration?.edges ?? workflow.blueprint?.edges ?? []
        );
        const { positions, origin } = computePositions(nodes, edges);

        try {
          localStorage.setItem(LAST_SPATIAL_WORKFLOW_KEY, String(id));
        } catch {
          // localStorage unavailable — non-fatal
        }

        set({
          workflowId: id,
          workflowName: workflow.name ?? `Workflow ${id}`,
          lockVersion: workflow.lock_version ?? 1,
          nodes,
          edges,
          positions,
          origin2d: origin,
          loading: false,
          error: null,
          dirty: false,
          saveStatus: 'idle',
        });
      } catch (err) {
        set({
          loading: false,
          error: err instanceof Error ? err.message : 'Failed to load workflow',
        });
      }
    },

    clear: () => {
      clearSaveTimer();
      set({
        workflowId: null,
        workflowName: '',
        lockVersion: 1,
        nodes: [],
        edges: [],
        positions: {},
        origin2d: { ...DEFAULT_ORIGIN_2D },
        loading: false,
        error: null,
        dirty: false,
        saveStatus: 'idle',
      });
    },

    addNode: (kind, pos) => {
      const { nodes, positions, origin2d } = get();
      const id = uniqueNodeId(nodes);
      const config = kind.buildConfig();
      const node: WorkflowNode = {
        id,
        type: 'custom',
        position: to2DPosition(pos, origin2d),
        data: {
          label: kind.label,
          agentType: kind.agentType,
          model: kind.model,
          config: config as unknown as AgentConfig,
          position3d: { x: pos[0], y: pos[1], z: pos[2] },
        },
      };
      set({
        nodes: [...nodes, node],
        positions: { ...positions, [id]: pos },
      });
      touch();
      return id;
    },

    moveNode: (id, pos) => {
      const { positions } = get();
      if (!positions[id]) return;
      set({ positions: { ...positions, [id]: pos } });
    },

    commitNodePosition: (id) => {
      const { nodes, positions, origin2d } = get();
      const pos = positions[id];
      if (!pos) return;
      set({
        nodes: nodes.map((n) =>
          n.id === id
            ? {
                ...n,
                position: to2DPosition(pos, origin2d),
                data: {
                  ...n.data,
                  position3d: { x: pos[0], y: pos[1], z: pos[2] },
                },
              }
            : n
        ),
      });
      touch();
    },

    updateNodeConfig: (id, newConfig) => {
      // Mirrors useNodeManagement.ts updateNodeConfig (2D parity): label/
      // agentType/model lift + config merge with explicit field precedence.
      const { nodes } = get();
      set({
        nodes: nodes.map((node) => {
          if (node.id !== id) return node;
          const data = node.data ?? {};
          const dataConfig = (data.config ?? {}) as Record<string, unknown>;
          const newLabel =
            (newConfig.label as string) || (newConfig.name as string) || data.label;
          return {
            ...node,
            data: {
              ...data,
              label: newLabel,
              agentType: (newConfig.agentType as string) || data.agentType,
              model: (newConfig.model as string) || data.model,
              config: {
                ...dataConfig,
                ...newConfig,
                model: (newConfig.model as string) || (dataConfig.model as string),
                temperature:
                  newConfig.temperature !== undefined ? newConfig.temperature : dataConfig.temperature,
                max_tokens:
                  newConfig.max_tokens !== undefined ? newConfig.max_tokens : dataConfig.max_tokens,
                max_retries:
                  newConfig.max_retries !== undefined ? newConfig.max_retries : dataConfig.max_retries,
                recursion_limit:
                  newConfig.recursion_limit !== undefined
                    ? newConfig.recursion_limit
                    : dataConfig.recursion_limit,
                system_prompt:
                  newConfig.system_prompt !== undefined
                    ? newConfig.system_prompt
                    : dataConfig.system_prompt,
                native_tools:
                  newConfig.native_tools !== undefined
                    ? newConfig.native_tools
                    : dataConfig.native_tools,
                tools: newConfig.tools !== undefined ? newConfig.tools : dataConfig.tools,
                custom_tools:
                  newConfig.custom_tools !== undefined
                    ? newConfig.custom_tools
                    : dataConfig.custom_tools,
                enable_memory:
                  newConfig.enable_memory !== undefined
                    ? newConfig.enable_memory
                    : dataConfig.enable_memory,
                enable_rag:
                  newConfig.enable_rag !== undefined ? newConfig.enable_rag : dataConfig.enable_rag,
              } as AgentConfig,
              _lastUpdated: Date.now(),
            },
          };
        }),
      });
      touch();
    },

    addEdgeBetween: (source, target) => {
      if (source === target) {
        return { ok: false, reason: 'Cannot connect a node to itself' };
      }
      const { nodes, edges } = get();
      const sourceExists = nodes.some((n) => n.id === source);
      const targetExists = nodes.some((n) => n.id === target);
      if (!sourceExists || !targetExists) {
        return { ok: false, reason: 'Connection endpoints no longer exist' };
      }
      if (edges.some((e) => e.source === source && e.target === target)) {
        return { ok: false, reason: 'These nodes are already connected' };
      }
      const edge: WorkflowEdge = {
        id: `e-${source}-${target}-${Date.now()}`,
        source,
        target,
      };
      set({ edges: [...edges, edge] });
      touch();
      return { ok: true };
    },

    removeNode: (id) => {
      const { nodes, edges, positions } = get();
      const nextPositions = { ...positions };
      delete nextPositions[id];
      set({
        nodes: nodes.filter((n) => n.id !== id),
        edges: edges.filter((e) => e.source !== id && e.target !== id),
        positions: nextPositions,
      });
      touch();
    },

    removeEdge: (id) => {
      const { edges } = get();
      set({ edges: edges.filter((e) => e.id !== id) });
      touch();
    },

    scheduleSave: () => {
      if (get().workflowId == null) return;
      clearSaveTimer();
      saveTimer = setTimeout(() => {
        saveTimer = null;
        void get().saveNow();
      }, SAVE_DEBOUNCE_MS);
    },

    saveNow: async () => {
      const { workflowId, nodes, edges, lockVersion, mutationSeq } = get();
      if (workflowId == null) return;
      clearSaveTimer();
      set({ saveStatus: 'saving' });

      try {
        const response = await apiClient.updateWorkflow(workflowId, {
          configuration: buildConfiguration(nodes, edges),
          lock_version: lockVersion,
        });
        const nextVersion =
          (response.data as { lock_version?: number })?.lock_version ?? lockVersion + 1;

        // Only clear dirty if nothing mutated while the PUT was in flight
        // (a newer debounce is already scheduled in that case).
        if (get().mutationSeq === mutationSeq) {
          set({ saveStatus: 'saved', dirty: false, lockVersion: nextVersion });
        } else {
          set({ lockVersion: nextVersion });
        }
      } catch (err) {
        if (err instanceof ConflictErrorClass) {
          // Someone else (likely the 2D canvas) saved first: reload the
          // latest version and let the view toast about it.
          set((s) => ({ saveStatus: 'conflict', conflictSeq: s.conflictSeq + 1 }));
          await get().loadWorkflow(workflowId);
          return;
        }
        console.error('Spatial save failed:', err);
        set({ saveStatus: 'error' });
      }
    },
  };
});

/** Last workflow viewed in the spatial view, if any. */
export function getLastSpatialWorkflowId(): number | null {
  try {
    const raw = localStorage.getItem(LAST_SPATIAL_WORKFLOW_KEY);
    if (!raw) return null;
    const id = Number(raw);
    return Number.isFinite(id) ? id : null;
  } catch {
    return null;
  }
}
