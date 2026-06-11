/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * RunDialog — small centered HUD card asking for the run's goal text.
 * Submits via useSpatialExecution.run (which flushes pending saves first,
 * then POSTs the same /api/orchestration/execute payload the 2D canvas uses).
 */

import { useEffect, useRef, useState } from 'react';

export default function RunDialog({
  workflowName,
  onRun,
  onClose,
}: {
  workflowName: string;
  /** Kick off the run; the dialog closes itself once accepted. */
  onRun: (goal: string) => Promise<void>;
  onClose: () => void;
}) {
  const [goal, setGoal] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  const submit = async () => {
    const trimmed = goal.trim();
    if (!trimmed || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await onRun(trimmed);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start the run');
      setSubmitting(false);
    }
  };

  return (
    <div
      className="absolute inset-0 z-50 flex items-center justify-center"
      style={{ background: 'color-mix(in srgb, var(--color-background-dark) 35%, transparent)' }}
      onClick={onClose}
    >
      <div
        className="surface-card w-[min(440px,90vw)] px-5 py-4"
        onClick={(e) => e.stopPropagation()}
      >
        <p
          className="text-sm font-bold uppercase tracking-wide"
          style={{ color: 'var(--color-text-primary)' }}
        >
          Run workflow
        </p>
        <p className="mt-0.5 truncate text-xs" style={{ color: 'var(--color-text-muted)' }}>
          {workflowName}
        </p>

        <textarea
          ref={textareaRef}
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) void submit();
            if (e.key === 'Escape') onClose();
          }}
          rows={3}
          placeholder="What should this workflow do? (Ctrl+Enter to run)"
          className="mt-3 w-full resize-none border px-2.5 py-2 text-sm outline-none"
          style={{
            background: 'var(--surface-2)',
            borderColor: 'var(--border-strong)',
            borderRadius: 'var(--radius-control)',
            color: 'var(--color-text-primary)',
            fontFamily: 'var(--font-family-mono)',
          }}
        />

        {error && (
          <p className="mt-2 text-xs font-semibold" style={{ color: 'var(--color-error)' }}>
            {error}
          </p>
        )}

        <div className="mt-3 flex items-center justify-end gap-2">
          <button onClick={onClose} className="btn-brutal px-3 py-1.5 text-xs" disabled={submitting}>
            Cancel
          </button>
          <button
            onClick={() => void submit()}
            disabled={!goal.trim() || submitting}
            className="flex items-center gap-1 px-3 py-1.5 text-xs font-bold uppercase tracking-wider transition-opacity disabled:opacity-50"
            style={{
              background: 'var(--color-primary)',
              color: 'var(--color-on-accent)',
              border: 'var(--border-w) solid var(--border-strong)',
              borderRadius: 'var(--radius-control)',
              boxShadow: 'var(--shadow-card-sm)',
            }}
          >
            <span className="material-symbols-outlined text-sm">play_arrow</span>
            {submitting ? 'Starting…' : 'Run'}
          </button>
        </div>
      </div>
    </div>
  );
}
