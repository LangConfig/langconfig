/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import React from 'react';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md';
  icon?: React.ReactNode;
}

/**
 * Brutalist button: monospace uppercase label, hard border, press-in hover.
 * In dark themes the offset shadow becomes a glow via the shadow tokens.
 */
export function Button({
  variant = 'secondary',
  size = 'md',
  icon,
  className = '',
  children,
  ...rest
}: ButtonProps) {
  const base =
    variant === 'ghost'
      ? 'btn-ghost'
      : variant === 'primary'
        ? 'btn-brutal btn-brutal-primary'
        : 'btn-brutal';

  const danger =
    variant === 'danger'
      ? 'btn-brutal'
      : '';

  const sizeClass = size === 'sm' ? '!px-2.5 !py-1 !text-[0.62rem]' : '';

  return (
    <button
      className={[base, danger, sizeClass, 'inline-flex items-center gap-1.5', className]
        .filter(Boolean)
        .join(' ')}
      style={
        variant === 'danger'
          ? {
              color: 'var(--color-error)',
              background: 'var(--color-error-wash)',
              borderColor: 'var(--color-error-border)',
            }
          : undefined
      }
      {...rest}
    >
      {icon}
      {children}
    </button>
  );
}

export default Button;
