/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * 2D <-> 3D position mapping and topological fallback layout.
 *
 * Priority per node:
 *   1. node.data.position3d ({x, y, z} world units) — authored in 3D
 *   2. node.position (ReactFlow px) -> (x/SCALE, 0, y/SCALE), centered on the
 *      centroid of all 2D positions so the graph sits around the world origin
 *   3. Topological BFS rows: depth from roots -> Z rows, siblings spread on X
 */

import type { WorkflowNode, WorkflowEdge } from '@/types/workflow';
import { SCALE, ROW_SPACING, COL_SPACING, type Vec3, type Position3D } from '../types';

function isFiniteNumber(v: unknown): v is number {
  return typeof v === 'number' && Number.isFinite(v);
}

function readPosition3D(node: WorkflowNode): Vec3 | null {
  const raw = (node.data as Record<string, unknown> | undefined)?.position3d;
  if (!raw || typeof raw !== 'object') return null;
  const p = raw as Partial<Position3D>;
  if (isFiniteNumber(p.x) && isFiniteNumber(p.y) && isFiniteNumber(p.z)) {
    return [p.x, p.y, p.z];
  }
  return null;
}

/** 2D pixel-space anchor used to map between ReactFlow px and world units. */
export interface Origin2D {
  x: number;
  y: number;
}

/** Default 2D origin when a workflow has no stored 2D positions at all. */
export const DEFAULT_ORIGIN_2D: Origin2D = { x: 500, y: 300 };

/**
 * Inverse of the 2D -> 3D mapping: derive a ReactFlow pixel position from a
 * world position, using the origin captured when the workflow was loaded.
 * Writing this alongside data.position3d keeps the 2D canvas in sync with
 * 3D edits (D1 in the architecture plan).
 */
export function to2DPosition(p: Vec3, origin: Origin2D): { x: number; y: number } {
  return {
    x: Math.round(origin.x + p[0] * SCALE),
    y: Math.round(origin.y + p[2] * SCALE),
  };
}

export interface LayoutResult {
  positions: Record<string, Vec3>;
  /** Centroid of the stored 2D positions (or DEFAULT_ORIGIN_2D). */
  origin: Origin2D;
}

/**
 * Compute a world-space position for every node in the workflow, plus the 2D
 * origin used for bidirectional 2D <-> 3D position sync.
 */
export function computePositions(
  nodes: WorkflowNode[],
  edges: WorkflowEdge[]
): LayoutResult {
  const out: Record<string, Vec3> = {};

  // Pass 1: explicit 3D positions and valid 2D positions. The origin is the
  // centroid of ALL valid 2D positions so the inverse mapping stays
  // consistent for every node in the session.
  const all2D: Array<{ x: number; y: number }> = [];
  const from2D: Array<{ id: string; x: number; y: number }> = [];
  const needAuto: string[] = [];

  for (const node of nodes) {
    const has2D =
      node.position && isFiniteNumber(node.position.x) && isFiniteNumber(node.position.y);
    if (has2D) all2D.push({ x: node.position!.x, y: node.position!.y });

    const p3 = readPosition3D(node);
    if (p3) {
      out[node.id] = p3;
    } else if (has2D) {
      from2D.push({ id: node.id, x: node.position!.x, y: node.position!.y });
    } else {
      needAuto.push(node.id);
    }
  }

  const origin: Origin2D =
    all2D.length > 0
      ? {
          x: all2D.reduce((s, p) => s + p.x, 0) / all2D.length,
          y: all2D.reduce((s, p) => s + p.y, 0) / all2D.length,
        }
      : { ...DEFAULT_ORIGIN_2D };

  // Pass 2: 2D -> 3D mapping, centered on the shared origin.
  for (const p of from2D) {
    out[p.id] = [(p.x - origin.x) / SCALE, 0, (p.y - origin.y) / SCALE];
  }

  // Pass 3: topological BFS rows for nodes with no stored position at all.
  if (needAuto.length > 0) {
    // Start the fallback grid past anything already placed so groups never overlap.
    let baseZ = 0;
    for (const id of Object.keys(out)) {
      baseZ = Math.max(baseZ, out[id][2] + ROW_SPACING);
    }
    layoutTopological(needAuto, edges, baseZ, out);
  }

  return { positions: out, origin };
}

/**
 * BFS depth layout over the subgraph of `ids`. Roots are nodes with no
 * incoming edge within the subgraph (or all nodes, if the subgraph is cyclic).
 */
function layoutTopological(
  ids: string[],
  edges: WorkflowEdge[],
  baseZ: number,
  out: Record<string, Vec3>
): void {
  const idSet = new Set(ids);
  const inDegree = new Map<string, number>();
  const adjacency = new Map<string, string[]>();
  for (const id of ids) {
    inDegree.set(id, 0);
    adjacency.set(id, []);
  }
  for (const edge of edges) {
    if (!idSet.has(edge.source) || !idSet.has(edge.target)) continue;
    if (edge.source === edge.target) continue;
    adjacency.get(edge.source)!.push(edge.target);
    inDegree.set(edge.target, (inDegree.get(edge.target) ?? 0) + 1);
  }

  const roots = ids.filter((id) => (inDegree.get(id) ?? 0) === 0);
  const queue: Array<{ id: string; depth: number }> = (roots.length > 0 ? roots : ids.slice(0, 1)).map(
    (id) => ({ id, depth: 0 })
  );

  const depthOf = new Map<string, number>();
  const visited = new Set<string>();
  while (queue.length > 0) {
    const { id, depth } = queue.shift()!;
    if (visited.has(id)) continue;
    visited.add(id);
    depthOf.set(id, depth);
    for (const next of adjacency.get(id) ?? []) {
      if (!visited.has(next)) queue.push({ id: next, depth: depth + 1 });
    }
  }

  // Anything unreached (disconnected or cycle remainder) goes on an extra row.
  let maxDepth = 0;
  for (const d of depthOf.values()) maxDepth = Math.max(maxDepth, d);
  for (const id of ids) {
    if (!depthOf.has(id)) depthOf.set(id, maxDepth + 1);
  }

  // Group by depth, spread siblings symmetrically on X.
  const rows = new Map<number, string[]>();
  for (const id of ids) {
    const d = depthOf.get(id)!;
    const row = rows.get(d);
    if (row) row.push(id);
    else rows.set(d, [id]);
  }
  for (const [depth, row] of rows) {
    row.forEach((id, i) => {
      const x = (i - (row.length - 1) / 2) * COL_SPACING;
      out[id] = [x, 0, baseZ + depth * ROW_SPACING];
    });
  }
}
