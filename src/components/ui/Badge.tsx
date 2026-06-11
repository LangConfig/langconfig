/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import React from 'react';

export type BadgeTone = 'neutral' | 'success' | 'warning' | 'error' | 'info' | 'accent';

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone;
  /** Leading status dot. */
  dot?: boolean;
  /** Pulse the dot (running/active states). */
  pulse?: boolean;
}

/**
 * Monospace uppercase tag. Reserved for functional state per the design
 * system — never decorative lists.
 */
export function Badge({
  tone = 'neutral',
  dot = false,
  pulse = false,
  className = '',
  children,
  ...rest
}: BadgeProps) {
  return (
    <span className={`badge-mono tone-${tone} ${className}`} {...rest}>
      {dot && (
        <span
          className={`inline-block w-1.5 h-1.5 rounded-full ${pulse ? 'animate-pulse' : ''}`}
          style={{ background: 'currentColor' }}
        />
      )}
      {children}
    </span>
  );
}

export default Badge;
