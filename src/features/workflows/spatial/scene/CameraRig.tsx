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
 */

import * as THREE from 'three';
import { useEffect, useRef, type ComponentRef } from 'react';
import { useThree } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import { useSpatialWorkflowStore } from '../state/workflowStore';
import { useSceneStore } from '../state/sceneStore';

const VIEW_DIRECTION = new THREE.Vector3(0.85, 0.95, 1).normalize();

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
