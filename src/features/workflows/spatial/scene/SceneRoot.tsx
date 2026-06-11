/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * SceneRoot — composition root inside the R3F <Canvas>.
 *
 * Subscribes to the spatial workflow store (zustand is framework-global, so
 * no context bridging is needed across the Canvas boundary) and to the
 * theme palette. Stage 2 adds the builder layers: ground raycast target,
 * placement ghost, and the connect rubber band. Stage 3 adds the execution
 * layers: edge pulses and the subagent swarm (both instanced, both fed
 * transiently from executionStore inside useFrame).
 */

import Environment3D from './Environment3D';
import CameraRig from './CameraRig';
import NodeMesh from './NodeMesh';
import EdgeCurve from './EdgeCurve';
import EdgePulses from './EdgePulses';
import SubagentSwarm from './SubagentSwarm';
import GroundPlane from './GroundPlane';
import GhostNode from './GhostNode';
import GhostEdge from './GhostEdge';
import PostFX from './effects/PostFX';
import { useSpatialWorkflowStore } from '../state/workflowStore';
import { useThemePalette } from '../lib/themePalette';

export default function SceneRoot() {
  const nodes = useSpatialWorkflowStore((s) => s.nodes);
  const edges = useSpatialWorkflowStore((s) => s.edges);
  const positions = useSpatialWorkflowStore((s) => s.positions);
  const palette = useThemePalette();

  return (
    <>
      <Environment3D palette={palette} />
      <CameraRig />
      <GroundPlane />

      {nodes.map((node) => {
        const position = positions[node.id];
        if (!position) return null;
        return <NodeMesh key={node.id} node={node} position={position} palette={palette} />;
      })}

      {edges.map((edge) => {
        const from = positions[edge.source];
        const to = positions[edge.target];
        if (!from || !to) return null;
        return <EdgeCurve key={edge.id} edge={edge} from={from} to={to} palette={palette} />;
      })}

      <GhostNode palette={palette} />
      <GhostEdge palette={palette} />

      {/* Execution visualization layers */}
      <EdgePulses palette={palette} />
      <SubagentSwarm palette={palette} />

      {palette.isDark && <PostFX />}
    </>
  );
}
