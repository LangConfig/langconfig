/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * GroundPlane — invisible y=0 raycast target for builder interactions.
 *
 * - pointer move (while placing/connecting): updates the shared cursorTarget
 *   that GhostNode / GhostEdge consume in useFrame (no React churn), then
 *   invalidates the demand frameloop.
 * - click while placing: creates the armed node kind at the hit point.
 * - click while connecting: cancels the connection.
 * - click while idle: clears the selection.
 *
 * Click events with e.delta > 5px are ignored — those are OrbitControls
 * drags that happened to end over the ground.
 */

import type { ThreeEvent } from '@react-three/fiber';
import { useThree } from '@react-three/fiber';
import { useSceneStore } from '../state/sceneStore';
import { useSpatialWorkflowStore } from '../state/workflowStore';
import { getSpatialKind } from '../builder/nodeKinds';
import { cursorTarget } from '../builder/cursorTarget';

export default function GroundPlane() {
  const invalidate = useThree((s) => s.invalidate);

  const handlePointerMove = (e: ThreeEvent<PointerEvent>) => {
    if (useSceneStore.getState().mode === 'idle') return;
    cursorTarget.point.set(e.point.x, 0, e.point.z);
    cursorTarget.active = true;
    invalidate();
  };

  const handleClick = (e: ThreeEvent<MouseEvent>) => {
    if (e.delta > 5) return;
    const scene = useSceneStore.getState();

    if (scene.mode === 'placing' && scene.placingKind) {
      const kind = getSpatialKind(scene.placingKind);
      if (kind) {
        const id = useSpatialWorkflowStore
          .getState()
          .addNode(kind, [e.point.x, 0, e.point.z]);
        scene.resetInteraction();
        scene.selectNode(id);
      }
      return;
    }
    if (scene.mode === 'connecting') {
      scene.endConnecting();
      return;
    }
    if (scene.selection) scene.clearSelection();
  };

  return (
    <mesh
      rotation-x={-Math.PI / 2}
      position-y={0}
      onPointerMove={handlePointerMove}
      onClick={handleClick}
    >
      <planeGeometry args={[1000, 1000]} />
      <meshBasicMaterial transparent opacity={0} depthWrite={false} />
    </mesh>
  );
}
