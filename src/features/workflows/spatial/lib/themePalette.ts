/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * Theme palette bridge: CSS custom properties -> THREE.Color.
 *
 * Reads the Botanical Brutalism tokens applied by applyTheme()
 * (src/lib/themes.ts) and re-reads them whenever the
 * 'langconfig:theme-changed' window event fires, so 3D materials track theme
 * switches live. DOM/Html overlays should keep using var(--token) directly —
 * this hook is only for colors that must live inside WebGL materials.
 */

import * as THREE from 'three';
import { useEffect, useMemo, useState } from 'react';
import { THEME_CHANGED_EVENT } from '../types';

export interface ThemePalette {
  isDark: boolean;
  /** Scene clear color / fog color. */
  background: THREE.Color;
  /** Ground plane (parchment in light themes, soil in dark). */
  ground: THREE.Color;
  /** Grid line color, pre-blended toward the background. */
  grid: THREE.Color;
  /** Outline ink for EdgesGeometry overlays. */
  ink: THREE.Color;
  primary: THREE.Color;
  node: THREE.Color;
  nodeLight: THREE.Color;
  success: THREE.Color;
  warning: THREE.Color;
  error: THREE.Color;
  info: THREE.Color;
}

/**
 * Parse a CSS color string into a THREE.Color. Handles #hex, rgb()/rgba()
 * (alpha discarded), and falls back for anything exotic (e.g. color-mix()).
 */
function cssToColor(raw: string, fallback: string): THREE.Color {
  const value = raw.trim();
  const color = new THREE.Color();
  if (!value) return color.set(fallback);

  const rgba = value.match(/^rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)/);
  if (rgba) {
    return color.setRGB(
      Number(rgba[1]) / 255,
      Number(rgba[2]) / 255,
      Number(rgba[3]) / 255,
      THREE.SRGBColorSpace
    );
  }

  try {
    color.set(value);
    return color;
  } catch {
    return color.set(fallback);
  }
}

/** Read the current palette from the document root. */
export function readPalette(): ThemePalette {
  const root = document.documentElement;
  const style = getComputedStyle(root);
  const isDark = root.classList.contains('dark');
  const get = (name: string, fallback: string) =>
    cssToColor(style.getPropertyValue(name), fallback);

  const background = get(
    isDark ? '--color-background-dark' : '--color-background-light',
    isDark ? '#101622' : '#FFF8ED'
  );
  const ground = get(
    isDark ? '--color-panel-dark' : '--color-background-dark',
    isDark ? '#181e29' : '#F8E7DC'
  );
  // Light themes outline in ink (border token); dark themes use the light
  // text tone so outlines stay visible against dark column faces.
  const ink = isDark
    ? get('--color-text-primary', '#e5e9f0')
    : get('--color-border-dark', '#102D43');
  const primary = get('--color-primary', '#D98984');

  const grid = (isDark ? primary : ink).clone().lerp(background, isDark ? 0.55 : 0.72);

  return {
    isDark,
    background,
    ground,
    grid,
    ink,
    primary,
    node: get('--color-node-background', '#E8B2AD'),
    nodeLight: get('--color-node-background-light', '#F5D5D0'),
    success: get('--color-success', '#3E7C4F'),
    warning: get('--color-warning', '#B07D2B'),
    error: get('--color-error', '#B6463F'),
    info: get('--color-info', '#3A6B8A'),
  };
}

/**
 * Reactive palette hook. Re-reads CSS vars on mount and on every
 * 'langconfig:theme-changed' event.
 */
export function useThemePalette(): ThemePalette {
  const [version, setVersion] = useState(0);

  useEffect(() => {
    const bump = () => setVersion((v) => v + 1);
    window.addEventListener(THEME_CHANGED_EVENT, bump);
    return () => window.removeEventListener(THEME_CHANGED_EVENT, bump);
  }, []);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  return useMemo(() => readPalette(), [version]);
}
