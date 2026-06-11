/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * CameraRig — OrbitControls plus fit-to-graph framing.
 *
 * The camera is re-framed along a fixed isometric-ish direction when:
 * - a (different) workflow is loaded, or
 * - the toolbar requests a fit (sceneStore.fitRequestId bump).
 *
 * It deliberately does NOT refit on every position change — drags and
 * placements would otherwise yank the camera.
 *
 * OrbitControls are disabled while a node is being dragged
 * (sceneStore.dragging — the controls.enabled pattern, no TransformControls).
 *
 * Follow-cam (stage 3): while sceneStore.followCam is on and a node is
 * running, the rig pans smoothly (lerped target + preserved orbit offset)
 * toward the current node. Any user input on the controls ('start' event,
 * which OrbitControls only fires for real interaction) cancels follow mode.
 */

import * as THREE from 'three';
import { useEffect, useMemo, useRef, type ComponentRef } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import { useSpatialWorkflowStore } from '../state/workflowStore';
import { useSceneStore } from '../state/sceneStore';
import { useExecutionStore } from '../state/executionStore';

const VIEW_DIRECTION = new THREE.Vector3(0.85, 0.95, 1).normalize();

/** Per-frame lerp factor for the follow pan. */
const FOLLOW_LERP = 0.045;

export default function CameraRig() {
  const controlsRef = useRef<ComponentRef<typeof OrbitControls>>(null);
  const camera = useThree((s) => s.camera);
  const invalidate = useThree((s) => s.invalidate);

  const workflowId = useSpatialWorkflowStore((s) => s.workflowId);
  const fitRequestId = useSceneStore((s) => s.fitRequestId);
  const dragging = useSceneStore((s) => s.dragging);

  // Disable orbit while plane-dragging a node.
  useEffect(() => {
    const controls = controlsRef.current;
    if (controls) controls.enabled = !dragging;
  }, [dragging]);

  // Manual control input cancels follow-cam ('start' only fires on user
  // interaction, never on programmatic target/position writes).
  useEffect(() => {
    const controls = controlsRef.current;
    if (!controls) return;
    const cancelFollow = () => {
      const scene = useSceneStore.getState();
      if (scene.followCam) scene.setFollowCam(false);
    };
    controls.addEventListener('start', cancelFollow);
    return () => controls.removeEventListener('start', cancelFollow);
  }, []);

  // Follow-cam: pan target+camera toward the currently running node.
  const followCam = useSceneStore((s) => s.followCam);
  const followTarget = useMemo(() => new THREE.Vector3(), []);
  const followOffset = useMemo(() => new THREE.Vector3(), []);
  useFrame(() => {
    if (!followCam) return;
    const controls = controlsRef.current;
    if (!controls || dragging) return;

    const exec = useExecutionStore.getState();
    const labelNow = exec.currentLabel;
    if (!labelNow) return;
    const nodeId = exec.index.labelToNodeId[labelNow];
    const pos = nodeId ? useSpatialWorkflowStore.getState().positions[nodeId] : undefined;
    if (!pos) return;

    followTarget.set(pos[0], pos[1] + 1.2, pos[2]);
    if (followTarget.distanceToSquared(controls.target) < 0.0004) return;

    // Preserve the current orbit offset so following pans without re-angling.
    followOffset.copy(camera.position).sub(controls.target);
    controls.target.lerp(followTarget, FOLLOW_LERP);
    camera.position.copy(controls.target).add(followOffset);
    controls.update();
  });

  useEffect(() => {
    const points = Object.values(useSpatialWorkflowStore.getState().positions);
    if (points.length === 0) return;

    const box = new THREE.Box3();
    const v = new THREE.Vector3();
    for (const p of points) box.expandByPoint(v.set(p[0], p[1], p[2]));
    // Margin for node footprints + labels.
    box.expandByScalar(3.5);

    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    const radius = Math.max(size.length() / 2, 8);
    const fov = camera instanceof THREE.PerspectiveCamera ? camera.fov : 45;
    const distance = Math.max(radius / Math.tan(THREE.MathUtils.degToRad(fov / 2)), 14) * 1.25;

    camera.position.copy(center).addScaledVector(VIEW_DIRECTION, distance);
    if (camera instanceof THREE.PerspectiveCamera) {
      camera.near = 0.1;
      camera.far = Math.max(600, distance * 10);
      camera.updateProjectionMatrix();
    }

    const controls = controlsRef.current;
    if (controls) {
      controls.target.copy(center);
      controls.update();
    }
    invalidate();
  }, [workflowId, fitRequestId, camera, invalidate]);

  return (
    <OrbitControls
      ref={controlsRef}
      makeDefault
      enableDamping
      dampingFactor={0.12}
      maxPolarAngle={Math.PI / 2.05}
      minDistance={4}
      maxDistance={300}
    />
  );
}
