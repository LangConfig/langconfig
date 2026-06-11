/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * NodeLabel — drei <Html> billboard above each node column.
 *
 * Plain DOM (NOT drei Text): the Tauri CSP has no worker-src, which blocks
 * troika's blob workers. DOM labels also inherit the CSS token cascade, so
 * they restyle on theme switch for free.
 */

import { Html } from '@react-three/drei';

interface NodeLabelProps {
  label: string;
  kind: string;
  /** World-space height of the column top (label floats above it). */
  height: number;
}

export default function NodeLabel({ label, kind, height }: NodeLabelProps) {
  return (
    <Html
      position={[0, height + 1.2, 0]}
      center
      distanceFactor={28}
      zIndexRange={[30, 0]}
      style={{ pointerEvents: 'none', userSelect: 'none' }}
    >
      <div
        style={{
          background: 'var(--surface-1)',
          border: 'var(--border-w) solid var(--border-strong)',
          borderRadius: 'var(--radius-control)',
          boxShadow: 'var(--shadow-card-sm)',
          padding: '4px 10px',
          whiteSpace: 'nowrap',
          textAlign: 'center',
          fontFamily: 'var(--font-family-mono, monospace)',
        }}
      >
        <div
          style={{
            color: 'var(--color-text-primary)',
            fontSize: '12px',
            fontWeight: 700,
            lineHeight: 1.25,
          }}
        >
          {label}
        </div>
        <div
          style={{
            color: 'var(--color-text-muted)',
            fontSize: '9px',
            fontWeight: 600,
            letterSpacing: '0.12em',
            textTransform: 'uppercase',
            lineHeight: 1.3,
          }}
        >
          {kind}
        </div>
      </div>
    </Html>
  );
}
