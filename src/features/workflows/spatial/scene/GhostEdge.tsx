/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * GhostEdge — rubber-band line from the connect-source node to the cursor
 * while a connection is in progress. A unit cylinder is positioned/oriented/
 * scaled per frame in useFrame from refs (cursorTarget + store snapshot), so
 * pointer movement causes zero React churn.
 */

import * as THREE from 'three';
import { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import { useSceneStore } from '../state/sceneStore';
import { useSpatialWorkflowStore } from '../state/workflowStore';
import { cursorTarget } from '../builder/cursorTarget';
import type { ThemePalette } from '../lib/themePalette';

const ANCHOR_Y = 0.8;
const UP = new THREE.Vector3(0, 1, 0);

const a = new THREE.Vector3();
const b = new THREE.Vector3();
const dir = new THREE.Vector3();

export default function GhostEdge({ palette }: { palette: ThemePalette }) {
  const mode = useSceneStore((s) => s.mode);
  const sourceId = useSceneStore((s) => s.connectSourceId);
  const meshRef = useRef<THREE.Mesh>(null);

  useFrame(() => {
    const m = meshRef.current;
    if (!m) return;
    const src = sourceId
      ? useSpatialWorkflowStore.getState().positions[sourceId]
      : undefined;
    if (!src || !cursorTarget.active) {
      m.visible = false;
      return;
    }
    a.set(src[0], src[1] + ANCHOR_Y, src[2]);
    b.copy(cursorTarget.point);
    b.y += 0.4;
    const length = a.distanceTo(b);
    if (length < 0.05) {
      m.visible = false;
      return;
    }
    m.visible = true;
    m.position.copy(a).add(b).multiplyScalar(0.5);
    dir.copy(b).sub(a).normalize();
    m.quaternion.setFromUnitVectors(UP, dir);
    m.scale.set(1, length, 1);
  });

  if (mode !== 'connecting' || !sourceId) return null;

  return (
    <mesh ref={meshRef} visible={false}>
      <cylinderGeometry args={[0.06, 0.06, 1, 6]} />
      <meshStandardMaterial
        color={palette.warning}
        flatShading
        roughness={0.5}
        metalness={0}
        transparent
        opacity={0.9}
        emissive={palette.warning}
        emissiveIntensity={0.6}
        depthWrite={false}
      />
    </mesh>
  );
}
