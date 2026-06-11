/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * Shared mutable cursor target — the latest ground-plane raycast hit.
 *
 * Written by GroundPlane's onPointerMove and consumed by GhostNode/GhostEdge
 * inside useFrame. Deliberately NOT React state: per-frame data lives in
 * refs/mutables so pointer movement never causes React churn (the writer
 * calls invalidate() to wake the demand frameloop).
 */

import * as THREE from 'three';

export const cursorTarget = {
  point: new THREE.Vector3(),
  /** False until the pointer has produced at least one hit this interaction. */
  active: false,
};
