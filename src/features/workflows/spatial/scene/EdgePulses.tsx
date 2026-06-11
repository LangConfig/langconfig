/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * EdgePulses — one InstancedMesh of glowing spheres traveling along edge
 * arcs during execution.
 *
 * Pulses are spawned by executionStore.ingestEvents (tool starts pulse the
 * edges into the active node; node handoffs pulse the completed->started
 * edge) and consumed here ENTIRELY inside useFrame via getState() — this
 * component never re-renders on pulse churn (the plan's no-per-frame-React
 * rule). Expired pulses are pruned back into the store at most once per
 * frame. Curves are rebuilt only when the graph changes and exactly mirror
 * EdgeCurve via buildEdgeArc.
 */

import * as THREE from 'three';
import { useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import type { ThemePalette } from '../lib/themePalette';
import { useSpatialWorkflowStore } from '../state/workflowStore';
import { useExecutionStore, MAX_PULSES, PULSE_DURATION_MS } from '../state/executionStore';
import { buildEdgeArc } from './EdgeCurve';

/** Ease so pulses accelerate out of the source and settle into the target. */
function easeInOut(t: number): number {
  return t * t * (3 - 2 * t);
}

export default function EdgePulses({ palette }: { palette: ThemePalette }) {
  const edges = useSpatialWorkflowStore((s) => s.edges);
  const positions = useSpatialWorkflowStore((s) => s.positions);

  const curves = useMemo(() => {
    const map = new Map<string, THREE.QuadraticBezierCurve3>();
    for (const edge of edges) {
      const from = positions[edge.source];
      const to = positions[edge.target];
      if (from && to) map.set(edge.id, buildEdgeArc(from, to));
    }
    return map;
  }, [edges, positions]);

  const meshRef = useRef<THREE.InstancedMesh>(null);
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const point = useMemo(() => new THREE.Vector3(), []);
  const toolColor = useMemo(() => palette.primary.clone(), [palette]);
  const handoffColor = useMemo(() => palette.success.clone(), [palette]);

  useFrame(() => {
    const mesh = meshRef.current;
    if (!mesh) return;

    const { pulses, prunePulses } = useExecutionStore.getState();
    const now = Date.now();
    let count = 0;
    let anyExpired = false;

    for (const pulse of pulses) {
      const t = (now - pulse.bornAt) / PULSE_DURATION_MS;
      if (t >= 1) {
        anyExpired = true;
        continue;
      }
      const curve = curves.get(pulse.edgeId);
      if (!curve || count >= MAX_PULSES) continue;

      curve.getPoint(easeInOut(t), point);
      dummy.position.copy(point);
      // Swell mid-flight, shrink at both ends.
      dummy.scale.setScalar(0.18 + 0.2 * Math.sin(t * Math.PI));
      dummy.updateMatrix();
      mesh.setMatrixAt(count, dummy.matrix);
      mesh.setColorAt(count, pulse.kind === 'tool' ? toolColor : handoffColor);
      count += 1;
    }

    mesh.count = count;
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    if (anyExpired) prunePulses(now);
  });

  return (
    <instancedMesh
      ref={meshRef}
      args={[undefined, undefined, MAX_PULSES]}
      count={0}
      frustumCulled={false}
    >
      <sphereGeometry args={[1, 10, 10]} />
      {/* Basic material: instance colors render at full brightness so Bloom
          (dark themes) catches them; light themes read as solid ink dots. */}
      <meshBasicMaterial color="#ffffff" toneMapped={false} />
    </instancedMesh>
  );
}
