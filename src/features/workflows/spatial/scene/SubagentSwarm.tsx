/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * SubagentSwarm — instanced orbs orbiting their parent node while a
 * subagent runs (subagent_start/end events; parent resolved via
 * parent_agent_label -> labelToNodeId in the fold).
 *
 * React only re-renders when the subagents map changes (spawn / despawn /
 * state flip); per-frame orbit motion writes instance matrices in useFrame.
 * Spawn scales in from the parent top; ended orbs flash to success/error and
 * shrink away over SUBAGENT_FADE_MS, after which pruneSubagents drops them.
 * Hovering an orb shows its name in a DOM chip.
 */

import * as THREE from 'three';
import { useMemo, useRef, useState } from 'react';
import { useFrame, type ThreeEvent } from '@react-three/fiber';
import { Html } from '@react-three/drei';
import type { ThemePalette } from '../lib/themePalette';
import { useSpatialWorkflowStore } from '../state/workflowStore';
import {
  useExecutionStore,
  MAX_SUBAGENTS,
  SUBAGENT_FADE_MS,
} from '../state/executionStore';

const ORBIT_RADIUS = 2.9;
const ORBIT_HEIGHT = 3.2;
const ORBIT_SPEED = 1.4; // rad/s
const SPAWN_MS = 350;
const ORB_RADIUS = 0.34;

/** Stable per-runId orbit phase so orbs do not stack. */
function phaseOf(runId: string): number {
  let hash = 0;
  for (let i = 0; i < runId.length; i++) hash = (hash * 31 + runId.charCodeAt(i)) | 0;
  return (Math.abs(hash) % 360) * (Math.PI / 180);
}

export default function SubagentSwarm({ palette }: { palette: ThemePalette }) {
  const subagents = useExecutionStore((s) => s.subagents);
  const entries = useMemo(
    () => Object.values(subagents).slice(0, MAX_SUBAGENTS),
    [subagents]
  );

  const meshRef = useRef<THREE.InstancedMesh>(null);
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const colors = useMemo(
    () => ({
      running: palette.info.clone(),
      done: palette.success.clone(),
      error: palette.error.clone(),
    }),
    [palette]
  );

  const [hover, setHover] = useState<{ name: string; point: THREE.Vector3 } | null>(null);
  const lastPruneRef = useRef(0);

  useFrame((state) => {
    const mesh = meshRef.current;
    if (!mesh) return;

    const positions = useSpatialWorkflowStore.getState().positions;
    const now = Date.now();
    const t = state.clock.elapsedTime;
    let count = 0;

    for (let i = 0; i < entries.length; i++) {
      const sub = entries[i];
      const parentPos = sub.parentNodeId ? positions[sub.parentNodeId] : undefined;
      if (!parentPos) continue;

      // Spawn scale-in, despawn scale-out (absorb).
      let scale = Math.min(1, (now - sub.startedAt) / SPAWN_MS);
      if (sub.endedAt !== undefined) {
        scale *= Math.max(0, 1 - (now - sub.endedAt) / SUBAGENT_FADE_MS);
      }
      if (scale <= 0) continue;

      const angle = t * ORBIT_SPEED + phaseOf(sub.runId) + i * 0.9;
      // Ended orbs spiral inward toward the parent (absorb feel).
      const radius = ORBIT_RADIUS * (sub.endedAt !== undefined ? scale : 1);
      dummy.position.set(
        parentPos[0] + Math.cos(angle) * radius,
        parentPos[1] + ORBIT_HEIGHT + Math.sin(t * 2.3 + phaseOf(sub.runId)) * 0.35,
        parentPos[2] + Math.sin(angle) * radius
      );
      dummy.scale.setScalar(ORB_RADIUS * scale);
      dummy.updateMatrix();
      mesh.setMatrixAt(count, dummy.matrix);
      mesh.setColorAt(count, colors[sub.state]);
      count += 1;
    }

    mesh.count = count;
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;

    // Occasionally drop fully-faded orbs from the store (cheap; <=2Hz).
    if (now - lastPruneRef.current > 500) {
      lastPruneRef.current = now;
      if (entries.some((s) => s.endedAt !== undefined && now - s.endedAt > SUBAGENT_FADE_MS)) {
        useExecutionStore.getState().pruneSubagents(now);
      }
    }
  });

  if (entries.length === 0) return null;

  const handleMove = (e: ThreeEvent<PointerEvent>) => {
    e.stopPropagation();
    // Instance order in useFrame matches entries order (skips only trailing
    // unresolved parents); good enough for a hover name chip.
    const sub = e.instanceId !== undefined ? entries[e.instanceId] : undefined;
    if (sub) setHover({ name: sub.name, point: e.point.clone() });
  };

  return (
    <group>
      <instancedMesh
        ref={meshRef}
        args={[undefined, undefined, MAX_SUBAGENTS]}
        count={0}
        frustumCulled={false}
        onPointerMove={handleMove}
        onPointerOut={() => setHover(null)}
      >
        <sphereGeometry args={[1, 12, 12]} />
        <meshBasicMaterial color="#ffffff" toneMapped={false} />
      </instancedMesh>

      {hover && (
        <Html
          position={[hover.point.x, hover.point.y + 0.8, hover.point.z]}
          center
          distanceFactor={24}
          zIndexRange={[30, 0]}
          style={{ pointerEvents: 'none', userSelect: 'none' }}
        >
          <div
            style={{
              background: 'var(--surface-1)',
              border: 'var(--border-w) solid var(--border-strong)',
              borderRadius: 'var(--radius-control)',
              boxShadow: 'var(--shadow-card-sm)',
              padding: '3px 8px',
              whiteSpace: 'nowrap',
              fontFamily: 'var(--font-family-mono, monospace)',
              fontSize: '11px',
              fontWeight: 700,
              color: 'var(--color-text-primary)',
            }}
          >
            {hover.name}
          </div>
        </Html>
      )}
    </group>
  );
}
