/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import React from 'react';

type SurfaceVariant = 'card' | 'card-sm' | 'panel' | 'inset' | 'terminal';

interface SurfaceProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: SurfaceVariant;
  /** Adds press-in hover behavior (translate + shadow/glow reduction). */
  interactive?: boolean;
  /** Status tone wash applied over the surface. */
  tone?: 'success' | 'warning' | 'error' | 'info' | 'accent' | 'neutral';
  as?: React.ElementType;
}

const VARIANT_CLASS: Record<SurfaceVariant, string> = {
  card: 'surface-card',
  'card-sm': 'surface-card-sm',
  panel: 'surface-card-sm',
  inset: 'surface-inset',
  terminal: 'terminal-block',
};

/**
 * Botanical Brutalist surface: hard border + offset shadow in light themes,
 * subtle border + glow in dark themes. All theming flows from CSS tokens.
 */
export function Surface({
  variant = 'card',
  interactive = false,
  tone,
  as: Tag = 'div',
  className = '',
  children,
  ...rest
}: SurfaceProps) {
  const classes = [
    VARIANT_CLASS[variant],
    interactive ? 'surface-card-interactive' : '',
    tone ? `tone-${tone}` : '',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <Tag className={classes} {...rest}>
      {children}
    </Tag>
  );
}

export default Surface;
