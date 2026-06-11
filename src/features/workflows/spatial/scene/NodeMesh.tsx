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
 *
 * Stage 3 (execution viz): materials react to the node's execution status
 * (executionStore.statuses, keyed by this node's LABEL):
 * - running:   primary emissive pulse + slow column bob
 * - thinking:  faster emissive shimmer
 * - completed: success flash that decays to a settled glow
 * - error:     error-tone strobe
 * All per-frame motion is done in useFrame against material refs (no React
 * state). A floating DOM chip above the column shows activeTool /
 * thinkingPreview (store-coalesced to <=10Hz) and is distance-culled.
 */

import * as THREE from 'three';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useFrame, type ThreeEvent } from '@react-three/fiber';
import { Html } from '@react-three/drei';
import type { WorkflowNode } from '@/types/workflow';
import type { NodeKind, Vec3 } from '../types';
import type { ThemePalette } from '../lib/themePalette';
import { useSceneStore } from '../state/sceneStore';
import { useSpatialWorkflowStore } from '../state/workflowStore';
import { useExecutionStore } from '../state/executionStore';
import { useNodeDrag } from '../builder/useNodeDrag';
import NodeLabel from './NodeLabel';

/** Beyond this camera distance the floating exec chip unmounts. */
const CHIP_CULL_DISTANCE = 55;

const BLACK = new THREE.Color('#000000');

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
  matRef,
}: {
  spec: TierSpec;
  centerY: number;
  palette: ThemePalette;
  /** 0 = none, 1 = hovered, 2 = selected. */
  highlight: number;
  /** Exposes the standard material for the exec-state animation loop. */
  matRef?: (mat: THREE.MeshStandardMaterial | null) => void;
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
          ref={matRef}
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
  const label = nodeLabelText(node);

  const selected = useSceneStore(
    (s) => s.selection?.kind === 'node' && s.selection.id === node.id
  );
  const hovered = useSceneStore((s) => s.hoveredNodeId === node.id);
  const mode = useSceneStore((s) => s.mode);
  const isConnectSource = useSceneStore((s) => s.connectSourceId === node.id);

  // Execution status (keyed by LABEL — eventMapping fold semantics). The
  // selected object identity only changes when this node's status changes
  // (<=10Hz for thinking text), so re-renders stay cheap.
  const execStatus = useExecutionStore((s) => s.statuses[label]);
  const execState = execStatus?.state ?? 'idle';

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

  // ---- Execution-state animation (per-frame, refs only) --------------------
  const matsRef = useRef<(THREE.MeshStandardMaterial | null)[]>([]);
  const bobRef = useRef<THREE.Group>(null);
  const restoredRef = useRef(true);
  const chipCheckRef = useRef(0);
  const chipNearRef = useRef(true);
  const [chipNear, setChipNear] = useState(true);

  // Baseline emissive values (what React would render with no execution) so
  // the animation loop can restore them exactly when the node returns idle.
  const baseRef = useRef<{ color: THREE.Color; intensity: number }[]>([]);
  baseRef.current = placed.map(({ spec }) => ({
    color: palette.isDark || highlight > 0 ? spec.color : BLACK,
    intensity:
      (palette.isDark ? spec.glow : 0) +
      (highlight === 2 ? 0.45 : highlight === 1 ? 0.18 : 0),
  }));

  useFrame((state) => {
    // Chip distance culling, checked at ~2.5Hz (no per-frame React state).
    const t = state.clock.elapsedTime;
    if (t - chipCheckRef.current > 0.4) {
      chipCheckRef.current = t;
      const dx = state.camera.position.x - position[0];
      const dy = state.camera.position.y - position[1];
      const dz = state.camera.position.z - position[2];
      const near = dx * dx + dy * dy + dz * dz < CHIP_CULL_DISTANCE * CHIP_CULL_DISTANCE;
      if (near !== chipNearRef.current) {
        chipNearRef.current = near;
        setChipNear(near);
      }
    }

    const status = useExecutionStore.getState().statuses[label];
    const st = status?.state ?? 'idle';
    const mats = matsRef.current;
    const bob = bobRef.current;

    if (st === 'idle') {
      if (!restoredRef.current) {
        const base = baseRef.current;
        for (let i = 0; i < mats.length; i++) {
          const mat = mats[i];
          if (mat && base[i]) {
            mat.emissive.copy(base[i].color);
            mat.emissiveIntensity = base[i].intensity;
          }
        }
        if (bob) bob.position.y = 0;
        restoredRef.current = true;
      }
      return;
    }
    restoredRef.current = false;

    let target: THREE.Color = palette.primary;
    let intensity = 0;
    let bobY = 0;
    if (st === 'running') {
      // Accent emissive pulse + slow column bob.
      intensity = 0.55 + 0.3 * Math.sin(t * 2.6);
      bobY = 0.12 * Math.sin(t * 2.2);
    } else if (st === 'thinking') {
      // Faster shimmer while tokens stream.
      intensity = 0.55 + 0.3 * Math.sin(t * 8.5);
      bobY = 0.07 * Math.sin(t * 4.2);
    } else if (st === 'completed') {
      // Success flash that decays into a settled glow.
      const since = Date.now() - (status?.stateChangedAt ?? 0);
      target = palette.success;
      intensity = 0.3 + Math.max(0, 1 - since / 1400) * 1.1;
    } else if (st === 'error') {
      target = palette.error;
      intensity = 0.45 + 0.45 * Math.abs(Math.sin(t * 6));
    }

    for (const mat of mats) {
      if (!mat) continue;
      mat.emissive.lerp(target, 0.18);
      mat.emissiveIntensity = THREE.MathUtils.lerp(mat.emissiveIntensity, intensity, 0.25);
    }
    if (bob) bob.position.y = THREE.MathUtils.lerp(bob.position.y, bobY, 0.18);
  });

  const chipText =
    execStatus && (execState === 'running' || execState === 'thinking')
      ? (execStatus.activeTool || execStatus.thinkingPreview || '').slice(0, 40)
      : '';
  const showChip = chipText.length > 0 && chipNear;

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
        ref={bobRef}
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
          <Tier
            key={i}
            spec={spec}
            centerY={centerY}
            palette={palette}
            highlight={highlight}
            matRef={(mat) => {
              matsRef.current[i] = mat;
            }}
          />
        ))}
      </group>

      {/* Floating exec chip: active tool / thinking preview (<=10Hz). */}
      {showChip && (
        <Html
          position={[0, totalHeight + 2.4, 0]}
          center
          distanceFactor={28}
          zIndexRange={[30, 0]}
          style={{ pointerEvents: 'none', userSelect: 'none' }}
        >
          <div
            style={{
              background: 'var(--surface-1)',
              border: 'var(--border-w) solid var(--color-primary)',
              borderRadius: 'var(--radius-control)',
              boxShadow: 'var(--shadow-card-sm)',
              padding: '3px 9px',
              whiteSpace: 'nowrap',
              fontFamily: 'var(--font-family-mono, monospace)',
              fontSize: '11px',
              fontWeight: 600,
              color: 'var(--color-text-primary)',
            }}
          >
            {execStatus?.activeTool ? (
              <span style={{ color: 'var(--color-primary)' }}>{chipText}</span>
            ) : (
              <span style={{ fontStyle: 'italic' }}>{chipText}…</span>
            )}
          </div>
        </Html>
      )}

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
