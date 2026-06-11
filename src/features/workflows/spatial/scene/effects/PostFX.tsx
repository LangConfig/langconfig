/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * PostFX — subtle Bloom for dark themes only ("nighttime garden" glow on the
 * emissive column tops and edges). Light themes render without a composer:
 * clean cream/ink, no atmospherics. The caller is responsible for mounting
 * this component only when the active theme is dark.
 */

import { EffectComposer, Bloom } from '@react-three/postprocessing';

export default function PostFX() {
  return (
    <EffectComposer>
      <Bloom
        intensity={0.55}
        luminanceThreshold={0.25}
        luminanceSmoothing={0.85}
        mipmapBlur
      />
    </EffectComposer>
  );
}
