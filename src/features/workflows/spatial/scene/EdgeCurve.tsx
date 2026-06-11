/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * EdgeCurve — arched tube between two node columns with a cone arrowhead at
 * the target end. Quadratic bezier lifted at the midpoint so edges read as
 * garden arches rather than floor wires.
 *
 * Stage 2: edges are selectable (click) — a fat invisible picking tube makes
 * the thin visual tube clickable; selected edges recolor to the warning tone
 * and thicken. Delete removes the selected edge (handled by the view).
 */

import * as THREE from 'three';
import { useEffect, useMemo } from 'react';
import type { ThreeEvent } from '@react-three/fiber';
import type { WorkflowEdge } from '@/types/workflow';
import type { Vec3 } from '../types';
import type { ThemePalette } from '../lib/themePalette';
import { useSceneStore } from '../state/sceneStore';

/** Edge anchor height on the column (roughly mid-tier). */
const ANCHOR_Y = 0.8;

/**
 * The shared edge arc: quadratic bezier lifted at the midpoint. EdgePulses
 * animates along the exact same curve, so keep all tuning here.
 */
export function buildEdgeArc(from: Vec3, to: Vec3): THREE.QuadraticBezierCurve3 {
  const a = new THREE.Vector3(from[0], from[1] + ANCHOR_Y, from[2]);
  const b = new THREE.Vector3(to[0], to[1] + ANCHOR_Y, to[2]);
  const mid = a.clone().lerp(b, 0.5);
  mid.y += Math.max(1.2, a.distanceTo(b) * 0.18);
  return new THREE.QuadraticBezierCurve3(a, mid, b);
}

export default function EdgeCurve({
  edge,
  from,
  to,
  palette,
}: {
  edge: WorkflowEdge;
  from: Vec3;
  to: Vec3;
  palette: ThemePalette;
}) {
  const selected = useSceneStore(
    (s) => s.selection?.kind === 'edge' && s.selection.id === edge.id
  );

  const radius = selected ? 0.11 : 0.07;

  const { tube, pickTube, tip, tipQuaternion } = useMemo(() => {
    const curve = buildEdgeArc(from, to);
    const tube = new THREE.TubeGeometry(curve, 24, radius, 6, false);
    // Fat invisible tube so the thin edge is easy to click.
    const pickTube = new THREE.TubeGeometry(curve, 16, 0.4, 6, false);

    const tip = curve.getPoint(0.95);
    const tangent = curve.getTangent(0.95).normalize();
    const tipQuaternion = new THREE.Quaternion().setFromUnitVectors(
      new THREE.Vector3(0, 1, 0),
      tangent
    );
    return { tube, pickTube, tip, tipQuaternion };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [from[0], from[1], from[2], to[0], to[1], to[2], radius]);

  useEffect(
    () => () => {
      tube.dispose();
      pickTube.dispose();
    },
    [tube, pickTube]
  );

  const color = selected ? palette.warning : palette.primary;
  const emissiveIntensity = selected ? 0.7 : palette.isDark ? 0.55 : 0;
  const emissive = selected || palette.isDark ? color : new THREE.Color('#000000');

  const handleClick = (e: ThreeEvent<MouseEvent>) => {
    if (e.delta > 5) return; // ignore orbit drags ending on the edge
    e.stopPropagation();
    useSceneStore.getState().selectEdge(edge.id);
  };

  return (
    <group>
      {/* Invisible picking volume */}
      <mesh geometry={pickTube} onClick={handleClick}>
        <meshBasicMaterial transparent opacity={0} depthWrite={false} />
      </mesh>
      <mesh geometry={tube} castShadow>
        <meshStandardMaterial
          color={color}
          flatShading
          roughness={0.6}
          metalness={0}
          emissive={emissive}
          emissiveIntensity={emissiveIntensity}
        />
      </mesh>
      <mesh position={tip} quaternion={tipQuaternion} castShadow>
        <coneGeometry args={[selected ? 0.28 : 0.22, 0.6, 6]} />
        <meshStandardMaterial
          color={color}
          flatShading
          roughness={0.6}
          metalness={0}
          emissive={emissive}
          emissiveIntensity={emissiveIntensity}
        />
      </mesh>
    </group>
  );
}
