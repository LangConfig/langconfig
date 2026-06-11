/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import React from 'react';
import { Bot, User, AlertTriangle } from 'lucide-react';

export type OrbState = 'idle' | 'thinking' | 'streaming' | 'error';

interface AvatarOrbProps {
  kind: 'user' | 'agent';
  state?: OrbState;
  /** Optional avatar image. */
  src?: string;
  size?: number;
  className?: string;
}

const AURA_CLASS: Record<OrbState, string> = {
  idle: '',
  thinking: 'orb-aura-thinking',
  streaming: 'orb-aura-streaming',
  error: 'orb-aura-error',
};

/**
 * Agent/user avatar orb with state auras: breathing while thinking, glow ring
 * while streaming, error glow on failure. Aura expression adapts per theme
 * via the glow tokens (offset-ring echo in light, blur glow in dark).
 */
export function AvatarOrb({ kind, state = 'idle', src, size = 30, className = '' }: AvatarOrbProps) {
  const iconSize = Math.round(size * 0.55);

  return (
    <div
      className={`flex-shrink-0 flex items-center justify-center rounded-full overflow-hidden transition-shadow ${AURA_CLASS[state]} ${className}`}
      style={{
        width: size,
        height: size,
        border: 'var(--border-w) solid var(--border-strong)',
        background:
          kind === 'agent'
            ? state === 'error'
              ? 'var(--color-error-wash)'
              : 'var(--color-accent-wash)'
            : 'var(--surface-2)',
        color: state === 'error' ? 'var(--color-error)' : kind === 'agent' ? 'var(--color-primary)' : 'var(--color-text-muted)',
      }}
    >
      {src ? (
        <img src={src} alt="" className="w-full h-full object-cover" />
      ) : state === 'error' ? (
        <AlertTriangle size={iconSize} />
      ) : kind === 'agent' ? (
        <Bot size={iconSize} />
      ) : (
        <User size={iconSize} />
      )}
    </div>
  );
}

export default AvatarOrb;
