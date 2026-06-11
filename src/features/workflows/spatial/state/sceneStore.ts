/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * Scene store (zustand) — ephemeral 3D builder UI state.
 *
 * Kept separate from workflowStore (persistent truth) so interaction churn
 * (hover, mode, selection) never invalidates persistence logic, and so the
 * execution stage can later add its own store without touching this one.
 *
 * - selection: selected node OR edge ({kind, id} | null)
 * - mode: 'idle' | 'placing' | 'connecting'
 * - placingKind: agentType armed in the palette while placing
 * - connectSourceId: source node of the in-progress connection (null while
 *   "connect" was armed from the toolbar and no source is picked yet)
 * - fitRequestId: bump to ask CameraRig to re-frame the graph
 * - dragging: true while a node is being plane-dragged (CameraRig disables
 *   OrbitControls in response — the controls.enabled pattern)
 * - notice/noticeSeq: one-shot messages surfaced as toasts by the DOM view
 *   (scene components run in the R3F reconciler and cannot reach the Toast
 *   React context directly)
 */

import { create } from 'zustand';
import type { SpatialMode, SpatialSelection } from '../types';

export interface SceneState {
  selection: SpatialSelection;
  mode: SpatialMode;
  placingKind: string | null;
  connectSourceId: string | null;
  hoveredNodeId: string | null;
  dragging: boolean;
  fitRequestId: number;
  notice: string | null;
  noticeSeq: number;
  /**
   * Follow-cam: CameraRig pans smoothly to the currently running node while
   * true. Any manual orbit/pan/zoom input cancels it (CameraRig listens for
   * the OrbitControls 'start' event, which only fires on user interaction).
   */
  followCam: boolean;

  selectNode: (id: string) => void;
  selectEdge: (id: string) => void;
  clearSelection: () => void;
  startPlacing: (kind: string) => void;
  /** Arm connecting mode; sourceId may be picked later by clicking a node. */
  startConnecting: (sourceId?: string | null) => void;
  setConnectSource: (sourceId: string) => void;
  endConnecting: () => void;
  /** Cancel any in-progress placing/connecting and return to idle. */
  resetInteraction: () => void;
  setHovered: (id: string | null) => void;
  setDragging: (dragging: boolean) => void;
  requestFit: () => void;
  setNotice: (message: string) => void;
  setFollowCam: (follow: boolean) => void;
}

export const useSceneStore = create<SceneState>((set) => ({
  selection: null,
  mode: 'idle',
  placingKind: null,
  connectSourceId: null,
  hoveredNodeId: null,
  dragging: false,
  fitRequestId: 0,
  notice: null,
  noticeSeq: 0,
  followCam: false,

  selectNode: (id) =>
    set({ selection: { kind: 'node', id }, mode: 'idle', placingKind: null, connectSourceId: null }),

  selectEdge: (id) =>
    set({ selection: { kind: 'edge', id }, mode: 'idle', placingKind: null, connectSourceId: null }),

  clearSelection: () => set({ selection: null }),

  startPlacing: (kind) =>
    set({ mode: 'placing', placingKind: kind, connectSourceId: null, selection: null }),

  startConnecting: (sourceId = null) =>
    set({ mode: 'connecting', connectSourceId: sourceId, placingKind: null, selection: null }),

  setConnectSource: (sourceId) => set({ connectSourceId: sourceId }),

  endConnecting: () => set({ mode: 'idle', connectSourceId: null }),

  resetInteraction: () => set({ mode: 'idle', placingKind: null, connectSourceId: null }),

  setHovered: (id) => set({ hoveredNodeId: id }),

  setDragging: (dragging) => set({ dragging }),

  requestFit: () => set((s) => ({ fitRequestId: s.fitRequestId + 1 })),

  setNotice: (message) => set((s) => ({ notice: message, noticeSeq: s.noticeSeq + 1 })),

  setFollowCam: (follow) => set({ followCam: follow }),
}));
