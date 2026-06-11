/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * Spatial (3D) workflow view — shared types and constants.
 *
 * Stage 2: building/editing interactions + persistence.
 */

/** World-units position stored on node.data.position3d ({x, y, z}). */
export interface Position3D {
  x: number;
  y: number;
  z: number;
}

/** Tuple form used internally for scene math. */
export type Vec3 = [number, number, number];

/**
 * ReactFlow pixels -> world units. 2D (x, y) maps to 3D (x/SCALE, 0, y/SCALE),
 * centered on the graph centroid (ground plane = XZ, Y = elevation).
 */
export const SCALE = 40;

/** Z spacing between BFS depth rows in the topological fallback layout. */
export const ROW_SPACING = 8;

/** X spacing between siblings within a BFS row. */
export const COL_SPACING = 7;

/** localStorage key remembering the last workflow viewed in 3D. */
export const LAST_SPATIAL_WORKFLOW_KEY = 'langconfig-spatial-workflow-id';

/** Window event dispatched by applyTheme() in src/lib/themes.ts. */
export const THEME_CHANGED_EVENT = 'langconfig:theme-changed';

/** Coarse node category used to pick geometry + color in the scene. */
export type NodeKind =
  | 'start'
  | 'end'
  | 'conditional'
  | 'loop'
  | 'tool'
  | 'approval'
  | 'checkpoint'
  | 'output'
  | 'agent';

/** Persistence status surfaced in the toolbar save chip. */
export type SaveStatus = 'idle' | 'saving' | 'saved' | 'error' | 'conflict';

/** Builder interaction mode (sceneStore). */
export type SpatialMode = 'idle' | 'placing' | 'connecting';

/** Current selection in the 3D scene (node or edge). */
export type SpatialSelection = { kind: 'node' | 'edge'; id: string } | null;

/** Debounce window for the autosave PUT (matches App.tsx's 2D debounce). */
export const SAVE_DEBOUNCE_MS = 800;
