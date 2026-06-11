/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * Environment3D — lights, ground plane, grid, fog.
 *
 * Botanical Brutalism: light themes get a clean parchment plane with ink grid
 * and one hard-shadow directional light (the 3D analogue of the offset drop
 * shadow). Dark themes become the "nighttime garden": fog in the background
 * tone plus a faint primary-tinted grid. Bloom is added separately (PostFX).
 */

import type { ThemePalette } from '../lib/themePalette';

const GROUND_SIZE = 400;
const GRID_DIVISIONS = 100;

export default function Environment3D({ palette }: { palette: ThemePalette }) {
  return (
    <>
      <color attach="background" args={[palette.background]} />
      {palette.isDark && <fog attach="fog" args={[palette.background, 35, 160]} />}

      <ambientLight intensity={palette.isDark ? 0.35 : 0.65} />
      <directionalLight
        position={[18, 30, 12]}
        intensity={palette.isDark ? 0.9 : 1.4}
        castShadow
        shadow-mapSize-width={2048}
        shadow-mapSize-height={2048}
        shadow-camera-left={-60}
        shadow-camera-right={60}
        shadow-camera-top={60}
        shadow-camera-bottom={-60}
        shadow-camera-near={1}
        shadow-camera-far={120}
      />
      {palette.isDark && (
        <pointLight position={[0, 14, 0]} intensity={60} color={palette.primary} />
      )}

      {/* Parchment / soil ground plane (slightly below grid to avoid z-fighting) */}
      <mesh rotation-x={-Math.PI / 2} position-y={-0.02} receiveShadow>
        <planeGeometry args={[GROUND_SIZE, GROUND_SIZE]} />
        <meshStandardMaterial color={palette.ground} roughness={1} metalness={0} />
      </mesh>

      <gridHelper
        args={[GROUND_SIZE, GRID_DIVISIONS, palette.grid, palette.grid]}
        position-y={0}
      />
    </>
  );
}
