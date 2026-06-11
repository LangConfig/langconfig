/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * NodeMesh — brutalist stepped column for a workflow node.
 *
 * Flat-shaded stacked boxes (no bevels) with an ink EdgesGeometry outline per
 * tier, echoing the app's 2px-border + offset-shadow language. Geometry
 * varies by node kind. Dark themes add emissive so Bloom catches the tops.
 *
 * Stage 2 interactions:
 * - click body  -> select (or complete a connection when connecting)
 * - hover       -> highlight + out-port indicator appears
 * - click port  -> start connecting (rubber band handled by GhostEdge)
 * - drag body   -> plane-constrained move (Shift = elevation) via useNodeDrag
 * - selected    -> primary slab + boosted glow (DOM config panel opens)
 */

import * as THREE from 'three';
import { useEffect, useMemo } from 'react';
import type { ThreeEvent } from '@react-three/fiber';
import type { WorkflowNode } from '@/types/workflow';
import type { NodeKind, Vec3 } from '../types';
import type { ThemePalette } from '../lib/themePalette';
import { useSceneStore } from '../state/sceneStore';
import { useSpatialWorkflowStore } from '../state/workflowStore';
import { useNodeDrag } from '../builder/useNodeDrag';
import NodeLabel from './NodeLabel';

interface TierSpec {
  size: [number, number, number];
  color: THREE.Color;
  rotateY?: number;
  /** Emissive boost in dark themes (top tiers glow more). */
  glow: number;
}

/** Coarse category from the node's agentType / type. */
export function nodeKind(node: WorkflowNode): NodeKind {
  const raw = String(node.data?.agentType ?? node.type ?? '').toLowerCase();
  if (raw.includes('start')) return 'start';
  if (raw.includes('end')) return 'end';
  if (raw.includes('conditional')) return 'conditional';
  if (raw.includes('loop')) return 'loop';
  if (raw.includes('approval')) return 'approval';
  if (raw.includes('checkpoint')) return 'checkpoint';
  if (raw.includes('output')) return 'output';
  if (raw.includes('tool')) return 'tool';
  return 'agent';
}

function nodeLabelText(node: WorkflowNode): string {
  const data = node.data;
  return (
    (typeof data?.label === 'string' && data.label) ||
    (typeof data?.name === 'string' && data.name) ||
    node.type ||
    node.id
  );
}

function tiersFor(kind: NodeKind, palette: ThemePalette): TierSpec[] {
  switch (kind) {
    case 'start':
      return [{ size: [3.4, 0.6, 3.4], color: palette.success, glow: 0.45 }];
    case 'end':
      return [{ size: [3.4, 0.6, 3.4], color: palette.error, glow: 0.45 }];
    case 'conditional':
      return [
        { size: [3, 0.5, 3], color: palette.node, glow: 0.12 },
        { size: [2, 1.2, 2], color: palette.warning, rotateY: Math.PI / 4, glow: 0.45 },
      ];
    case 'loop':
      return [
        { size: [3, 0.5, 3], color: palette.node, glow: 0.12 },
        { size: [2.2, 1, 2.2], color: palette.info, glow: 0.45 },
      ];
    case 'approval':
      return [
        { size: [3, 0.5, 3], color: palette.node, glow: 0.12 },
        { size: [2.2, 1, 2.2], color: palette.warning, glow: 0.45 },
      ];
    case 'checkpoint':
      return [
        { size: [3, 0.5, 3], color: palette.node, glow: 0.12 },
        { size: [1.6, 1.3, 1.6], color: palette.info, glow: 0.45 },
      ];
    case 'output':
      return [
        { size: [3, 0.5, 3], color: palette.node, glow: 0.12 },
        { size: [2.6, 0.7, 2.6], color: palette.success, glow: 0.4 },
      ];
    case 'tool':
      return [
        { size: [3, 0.5, 3], color: palette.node, glow: 0.12 },
        { size: [2.6, 0.8, 2.6], color: palette.nodeLight, glow: 0.35 },
      ];
    case 'agent':
    default:
      return [
        { size: [3.2, 0.6, 3.2], color: palette.node, glow: 0.12 },
        { size: [2.4, 1.1, 2.4], color: palette.nodeLight, glow: 0.2 },
        { size: [1.6, 0.9, 1.6], color: palette.primary, glow: 0.5 },
      ];
  }
}

/** One flat-shaded box with an ink wireframe outline. */
function Tier({
  spec,
  centerY,
  palette,
  highlight,
}: {
  spec: TierSpec;
  centerY: number;
  palette: ThemePalette;
  /** 0 = none, 1 = hovered, 2 = selected. */
  highlight: number;
}) {
  const [w, h, d] = spec.size;
  const edges = useMemo(() => new THREE.EdgesGeometry(new THREE.BoxGeometry(w, h, d)), [w, h, d]);
  useEffect(() => () => edges.dispose(), [edges]);

  // Light themes have no idle emissive; hover/selection borrow the tier color
  // so the highlight reads in both theme families.
  const baseIntensity = palette.isDark ? spec.glow : 0;
  const boost = highlight === 2 ? 0.45 : highlight === 1 ? 0.18 : 0;
  const emissiveColor = palette.isDark || highlight > 0 ? spec.color : '#000000';

  return (
    <group position-y={centerY} rotation-y={spec.rotateY ?? 0}>
      <mesh castShadow receiveShadow>
        <boxGeometry args={[w, h, d]} />
        <meshStandardMaterial
          color={spec.color}
          flatShading
          roughness={0.85}
          metalness={0}
          emissive={emissiveColor}
          emissiveIntensity={baseIntensity + boost}
        />
      </mesh>
      <lineSegments geometry={edges}>
        <lineBasicMaterial color={palette.ink} />
      </lineSegments>
    </group>
  );
}

export default function NodeMesh({
  node,
  position,
  palette,
}: {
  node: WorkflowNode;
  position: Vec3;
  palette: ThemePalette;
}) {
  const kind = nodeKind(node);
  const tiers = useMemo(() => tiersFor(kind, palette), [kind, palette]);
  const drag = useNodeDrag(node.id);

  const selected = useSceneStore(
    (s) => s.selection?.kind === 'node' && s.selection.id === node.id
  );
  const hovered = useSceneStore((s) => s.hoveredNodeId === node.id);
  const mode = useSceneStore((s) => s.mode);
  const isConnectSource = useSceneStore((s) => s.connectSourceId === node.id);

  // Stack tiers from the ground up; remember footprint + height for ports.
  let acc = 0;
  let maxW = 0;
  let maxD = 0;
  const placed = tiers.map((spec) => {
    const centerY = acc + spec.size[1] / 2;
    acc += spec.size[1];
    maxW = Math.max(maxW, spec.size[0]);
    maxD = Math.max(maxD, spec.size[2]);
    return { spec, centerY };
  });
  const totalHeight = acc;
  const highlight = selected ? 2 : hovered ? 1 : 0;
  const showPort =
    (hovered || selected || isConnectSource) && mode !== 'placing';

  const handleClick = (e: ThreeEvent<MouseEvent>) => {
    if (drag.consumeClickSuppression()) {
      e.stopPropagation();
      return;
    }
    if (e.delta > 5) return; // orbit drag that happened to end on this node
    e.stopPropagation();

    const scene = useSceneStore.getState();
    if (scene.mode === 'connecting') {
      if (!scene.connectSourceId) {
        // Connect was armed from the toolbar: first node click picks the source.
        scene.setConnectSource(node.id);
        return;
      }
      if (scene.connectSourceId === node.id) {
        scene.endConnecting();
        return;
      }
      const result = useSpatialWorkflowStore
        .getState()
        .addEdgeBetween(scene.connectSourceId, node.id);
      if (result.ok) {
        scene.endConnecting();
      } else if (result.reason) {
        scene.setNotice(result.reason);
      }
      return;
    }
    if (scene.mode === 'placing') return; // GroundPlane owns placement clicks
    scene.selectNode(node.id);
  };

  const handlePortClick = (e: ThreeEvent<MouseEvent>) => {
    if (e.delta > 5) return;
    e.stopPropagation();
    const scene = useSceneStore.getState();
    if (scene.mode === 'connecting' && scene.connectSourceId === node.id) {
      scene.endConnecting();
      return;
    }
    scene.startConnecting(node.id);
  };

  return (
    <group position={position}>
      {/* Selection slab — primary pad under the column (brutalist outline). */}
      {selected && (
        <mesh position-y={0.035}>
          <boxGeometry args={[maxW + 1.1, 0.07, maxD + 1.1]} />
          <meshStandardMaterial
            color={palette.primary}
            flatShading
            roughness={0.7}
            metalness={0}
            emissive={palette.primary}
            emissiveIntensity={palette.isDark ? 0.6 : 0.15}
          />
        </mesh>
      )}

      <group
        onClick={handleClick}
        onPointerDown={drag.onPointerDown}
        onPointerMove={drag.onPointerMove}
        onPointerUp={drag.onPointerUp}
        onPointerOver={(e) => {
          e.stopPropagation();
          useSceneStore.getState().setHovered(node.id);
        }}
        onPointerOut={() => {
          const scene = useSceneStore.getState();
          if (scene.hoveredNodeId === node.id) scene.setHovered(null);
        }}
      >
        {placed.map(({ spec, centerY }, i) => (
          <Tier key={i} spec={spec} centerY={centerY} palette={palette} highlight={highlight} />
        ))}
      </group>

      {/* Out-port indicator: visible on hover/selection; click starts a connection. */}
      {showPort && (
        <mesh
          position={[maxW / 2 + 0.5, Math.max(totalHeight * 0.55, 0.5), 0]}
          onClick={handlePortClick}
          onPointerOver={(e) => e.stopPropagation()}
        >
          <sphereGeometry args={[0.3, 12, 12]} />
          <meshStandardMaterial
            color={isConnectSource ? palette.warning : palette.primary}
            flatShading
            roughness={0.4}
            metalness={0}
            emissive={isConnectSource ? palette.warning : palette.primary}
            emissiveIntensity={isConnectSource ? 0.9 : 0.45}
          />
        </mesh>
      )}

      <NodeLabel label={nodeLabelText(node)} kind={kind} height={totalHeight} />
    </group>
  );
}
