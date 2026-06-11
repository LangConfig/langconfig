/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import React from 'react';
import type { BadgeTone } from './Badge';

interface ProgressBarProps {
  /** 0..max */
  value: number;
  max?: number;
  tone?: Exclude<BadgeTone, 'neutral'>;
  /** Glowing leading edge while active. */
  animated?: boolean;
  /** Bar height in px. */
  height?: number;
  className?: string;
}

const TONE_VAR: Record<string, string> = {
  success: 'var(--color-success)',
  warning: 'var(--color-warning)',
  error: 'var(--color-error)',
  info: 'var(--color-info)',
  accent: 'var(--color-primary)',
};

/**
 * Energy-bar progress: hatched track, tone-colored fill with a glowing
 * leading edge while animated. Reads as an HP bar without breaking the
 * brutalist structure.
 */
export function ProgressBar({
  value,
  max = 100,
  tone = 'info',
  animated = false,
  height = 8,
  className = '',
}: ProgressBarProps) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  const color = TONE_VAR[tone] ?? TONE_VAR.info;

  return (
    <div className={`energy-bar-track w-full ${className}`} style={{ height }}>
      <div
        className={`energy-bar-fill ${animated && pct < 100 ? 'animated' : ''}`}
        style={{
          width: `${pct}%`,
          background: color,
          boxShadow: animated ? `var(--glow-${tone === 'accent' ? 'accent' : tone})` : undefined,
        }}
      />
    </div>
  );
}

export default ProgressBar;
