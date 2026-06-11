/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * NodePalette — DOM HUD overlay listing the node kinds the builder can place.
 *
 * Clicking a kind arms 'placing' mode (ghost preview follows the ground
 * raycast; clicking the ground places the node). Clicking the armed kind
 * again — or pressing Escape — cancels. Botanical Brutalism styling via the
 * shared token utilities.
 */

import { useSceneStore } from '../state/sceneStore';
import { SPATIAL_NODE_KINDS } from './nodeKinds';

export default function NodePalette() {
  const mode = useSceneStore((s) => s.mode);
  const placingKind = useSceneStore((s) => s.placingKind);
  const startPlacing = useSceneStore((s) => s.startPlacing);
  const resetInteraction = useSceneStore((s) => s.resetInteraction);

  return (
    <div className="surface-card absolute left-4 top-20 z-40 w-44 overflow-hidden">
      <div
        className="border-b px-3 py-2 text-[0.62rem] font-semibold uppercase tracking-widest"
        style={{
          borderColor: 'var(--border-strong)',
          color: 'var(--color-text-muted)',
          fontFamily: 'var(--font-family-mono)',
        }}
      >
        Add node
      </div>
      <div className="flex flex-col">
        {SPATIAL_NODE_KINDS.map((kind) => {
          const active = mode === 'placing' && placingKind === kind.agentType;
          return (
            <button
              key={kind.agentType}
              onClick={() => (active ? resetInteraction() : startPlacing(kind.agentType))}
              title={kind.description}
              className="flex w-full items-center gap-2 px-3 py-1.5 text-left transition-colors hover:bg-black/5 dark:hover:bg-white/5"
              style={{
                background: active ? 'var(--color-primary)' : 'transparent',
                color: active ? 'var(--color-on-accent)' : 'var(--color-text-primary)',
              }}
            >
              <span
                className="material-symbols-outlined text-base"
                style={{ color: active ? 'var(--color-on-accent)' : 'var(--color-primary)' }}
              >
                {kind.icon}
              </span>
              <span className="truncate text-xs font-semibold">{kind.label}</span>
            </button>
          );
        })}
      </div>
      {mode === 'placing' && (
        <div
          className="border-t px-3 py-2 text-[0.6rem] uppercase tracking-wide"
          style={{
            borderColor: 'var(--border-strong)',
            color: 'var(--color-text-muted)',
            fontFamily: 'var(--font-family-mono)',
          }}
        >
          Click the ground to place · Esc cancels
        </div>
      )}
    </div>
  );
}
