/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * SpatialCanvas — R3F <Canvas> configuration with a graceful WebGL fallback
 * (WebView2 normally supports WebGL2, but context creation can still fail on
 * exotic GPU/driver combos).
 *
 * frameloop="demand" while idle: the scene is static, so frames render only
 * on camera input / store changes. While a run is animating (start ->
 * post-completion linger) or a replay session is open, the loop flips to
 * "always" so pulses/orbits/shimmers advance every frame.
 */

import { useMemo } from 'react';
import { Canvas } from '@react-three/fiber';
import SceneRoot from './scene/SceneRoot';
import { useExecutionStore } from './state/executionStore';

function webglAvailable(): boolean {
  try {
    const canvas = document.createElement('canvas');
    return Boolean(canvas.getContext('webgl2') || canvas.getContext('webgl'));
  } catch {
    return false;
  }
}

export default function SpatialCanvas() {
  const supported = useMemo(webglAvailable, []);
  const animating = useExecutionStore((s) => s.animating || s.replay != null);

  if (!supported) {
    return (
      <div className="flex h-full w-full items-center justify-center px-6">
        <div className="surface-card max-w-md px-6 py-5">
          <p
            className="text-sm font-semibold uppercase tracking-wide"
            style={{ color: 'var(--color-text-primary)' }}
          >
            3D view unavailable
          </p>
          <p className="mt-2 text-sm" style={{ color: 'var(--color-text-muted)' }}>
            WebGL could not be initialized in this environment. The Studio (2D)
            view remains fully functional.
          </p>
        </div>
      </div>
    );
  }

  return (
    <Canvas
      frameloop={animating ? 'always' : 'demand'}
      dpr={[1, 2]}
      shadows="basic"
      camera={{ position: [18, 18, 18], fov: 45 }}
      gl={{ antialias: true }}
    >
      <SceneRoot />
    </Canvas>
  );
}
