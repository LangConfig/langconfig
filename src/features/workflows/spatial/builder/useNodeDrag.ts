/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * useNodeDrag — plane-constrained pointer drag for NodeMesh.
 *
 * - Default: raycast the event ray onto a horizontal plane at the node's
 *   current elevation -> move on XZ (the ground plane).
 * - Shift held: raycast onto a camera-facing vertical plane through the node
 *   -> adjust elevation (Y), clamped to >= 0. Toggling Shift mid-drag
 *   re-bases the plane so the node never jumps.
 * - OrbitControls are disabled for the duration via sceneStore.dragging
 *   (CameraRig applies controls.enabled = !dragging). NO TransformControls.
 * - Move events only touch the ephemeral positions map (cheap); the final
 *   position3d + derived 2D position are committed on pointer-up, which
 *   also schedules the debounced save.
 * - A drag suppresses the click that fires after pointer-up so releasing a
 *   drag does not also select the node.
 */

import * as THREE from 'three';
import { useMemo, useRef } from 'react';
import { useThree, type ThreeEvent } from '@react-three/fiber';
import { useSpatialWorkflowStore } from '../state/workflowStore';
import { useSceneStore } from '../state/sceneStore';
import type { Vec3 } from '../types';

/** World-units of accumulated travel before a press counts as a drag. */
const DRAG_THRESHOLD = 0.12;

const UP = new THREE.Vector3(0, 1, 0);

interface DragState {
  active: boolean;
  pointerId: number;
  vertical: boolean;
  plane: THREE.Plane;
  offset: THREE.Vector3;
  moved: number;
  suppressClick: boolean;
}

export interface NodeDragHandlers {
  onPointerDown: (e: ThreeEvent<PointerEvent>) => void;
  onPointerMove: (e: ThreeEvent<PointerEvent>) => void;
  onPointerUp: (e: ThreeEvent<PointerEvent>) => void;
  /** Returns true (once) if the click following a drag should be swallowed. */
  consumeClickSuppression: () => boolean;
}

export function useNodeDrag(nodeId: string): NodeDragHandlers {
  const camera = useThree((s) => s.camera);
  const invalidate = useThree((s) => s.invalidate);

  const state = useRef<DragState>({
    active: false,
    pointerId: -1,
    vertical: false,
    plane: new THREE.Plane(),
    offset: new THREE.Vector3(),
    moved: 0,
    suppressClick: false,
  });

  return useMemo<NodeDragHandlers>(() => {
    const scratch = new THREE.Vector3();
    const nodeVec = new THREE.Vector3();

    const rebasePlane = (pos: Vec3, vertical: boolean) => {
      const s = state.current;
      nodeVec.set(pos[0], pos[1], pos[2]);
      if (vertical) {
        // Camera-facing vertical plane through the node (horizontal normal).
        const normal = camera.getWorldDirection(new THREE.Vector3());
        normal.y = 0;
        if (normal.lengthSq() < 1e-6) normal.set(0, 0, 1);
        else normal.normalize();
        s.plane.setFromNormalAndCoplanarPoint(normal, nodeVec);
      } else {
        // Horizontal plane at the node's current elevation.
        s.plane.setFromNormalAndCoplanarPoint(UP, nodeVec);
      }
      s.vertical = vertical;
    };

    const rebaseOffset = (e: ThreeEvent<PointerEvent>, pos: Vec3) => {
      const s = state.current;
      if (e.ray.intersectPlane(s.plane, scratch)) {
        s.offset.copy(scratch).sub(nodeVec.set(pos[0], pos[1], pos[2]));
      } else {
        s.offset.set(0, 0, 0);
      }
    };

    const onPointerDown = (e: ThreeEvent<PointerEvent>) => {
      if (e.button !== 0) return;
      if (useSceneStore.getState().mode !== 'idle') return; // placing/connecting handled elsewhere
      const pos = useSpatialWorkflowStore.getState().positions[nodeId];
      if (!pos) return;

      e.stopPropagation();
      (e.target as Element).setPointerCapture(e.pointerId);

      const s = state.current;
      s.active = true;
      s.pointerId = e.pointerId;
      s.moved = 0;
      rebasePlane(pos, e.shiftKey);
      rebaseOffset(e, pos);
      // Disable OrbitControls while dragging (controls.enabled pattern).
      useSceneStore.getState().setDragging(true);
    };

    const onPointerMove = (e: ThreeEvent<PointerEvent>) => {
      const s = state.current;
      if (!s.active || e.pointerId !== s.pointerId) return;
      e.stopPropagation();

      const store = useSpatialWorkflowStore.getState();
      const pos = store.positions[nodeId];
      if (!pos) return;

      // Shift toggled mid-drag: re-base the constraint plane at the current
      // position so the node does not jump.
      if (e.shiftKey !== s.vertical) {
        rebasePlane(pos, e.shiftKey);
        rebaseOffset(e, pos);
      }

      if (!e.ray.intersectPlane(s.plane, scratch)) return;

      const next: Vec3 = s.vertical
        ? [pos[0], Math.max(0, scratch.y - s.offset.y), pos[2]]
        : [scratch.x - s.offset.x, pos[1], scratch.z - s.offset.z];

      s.moved +=
        Math.abs(next[0] - pos[0]) + Math.abs(next[1] - pos[1]) + Math.abs(next[2] - pos[2]);
      store.moveNode(nodeId, next);
      invalidate();
    };

    const onPointerUp = (e: ThreeEvent<PointerEvent>) => {
      const s = state.current;
      if (!s.active || e.pointerId !== s.pointerId) return;
      e.stopPropagation();
      try {
        (e.target as Element).releasePointerCapture(s.pointerId);
      } catch {
        // capture may already be released
      }
      s.active = false;
      useSceneStore.getState().setDragging(false);

      if (s.moved > DRAG_THRESHOLD) {
        s.suppressClick = true;
        // Writes data.position3d + derived 2D position, schedules the save.
        useSpatialWorkflowStore.getState().commitNodePosition(nodeId);
      }
    };

    const consumeClickSuppression = () => {
      const v = state.current.suppressClick;
      state.current.suppressClick = false;
      return v;
    };

    return { onPointerDown, onPointerMove, onPointerUp, consumeClickSuppression };
  }, [nodeId, camera, invalidate]);
}
