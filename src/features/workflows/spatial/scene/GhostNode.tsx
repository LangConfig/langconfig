/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * GhostNode — translucent placement preview that follows the ground-plane
 * raycast while a palette kind is armed. Position/visibility are driven in
 * useFrame from the shared cursorTarget (refs only; GroundPlane invalidates
 * the demand frameloop on pointer move).
 */

import * as THREE from 'three';
import { useEffect, useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import { useSceneStore } from '../state/sceneStore';
import { cursorTarget } from '../builder/cursorTarget';
import type { ThemePalette } from '../lib/themePalette';

const GHOST_SIZE: [number, number, number] = [3.2, 1.5, 3.2];

export default function GhostNode({ palette }: { palette: ThemePalette }) {
  const mode = useSceneStore((s) => s.mode);
  const placingKind = useSceneStore((s) => s.placingKind);
  const groupRef = useRef<THREE.Group>(null);

  const placing = mode === 'placing' && placingKind != null;

  // Fresh interaction: hide the ghost until the pointer produces a hit.
  useEffect(() => {
    if (placing) cursorTarget.active = false;
  }, [placing]);

  const edges = useMemo(
    () => new THREE.EdgesGeometry(new THREE.BoxGeometry(...GHOST_SIZE)),
    []
  );
  useEffect(() => () => edges.dispose(), [edges]);

  useFrame(() => {
    const g = groupRef.current;
    if (!g) return;
    g.visible = cursorTarget.active;
    if (cursorTarget.active) g.position.copy(cursorTarget.point);
  });

  if (!placing) return null;

  return (
    <group ref={groupRef} visible={false}>
      <mesh position-y={GHOST_SIZE[1] / 2}>
        <boxGeometry args={GHOST_SIZE} />
        <meshStandardMaterial
          color={palette.primary}
          flatShading
          roughness={0.8}
          metalness={0}
          transparent
          opacity={0.35}
          emissive={palette.primary}
          emissiveIntensity={palette.isDark ? 0.5 : 0.1}
          depthWrite={false}
        />
      </mesh>
      <lineSegments geometry={edges} position-y={GHOST_SIZE[1] / 2}>
        <lineBasicMaterial color={palette.ink} />
      </lineSegments>
    </group>
  );
}
