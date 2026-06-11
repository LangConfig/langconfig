/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * WorkflowPicker — DOM overlay (not 3D) for choosing which workflow to view
 * in the spatial scene. Styled with the Botanical Brutalism token classes so
 * it theme-switches with the rest of the app.
 */

import { useState } from 'react';
import type { Workflow } from '@/types/workflow';

interface WorkflowPickerProps {
  workflows: Workflow[];
  selectedId: number | null;
  loading: boolean;
  onSelect: (id: number) => void;
}

export default function WorkflowPicker({
  workflows,
  selectedId,
  loading,
  onSelect,
}: WorkflowPickerProps) {
  const [open, setOpen] = useState(false);
  const selected = workflows.find((w) => w.id === selectedId) ?? null;

  return (
    <div className="absolute left-4 top-4 z-50">
      <button
        onClick={() => setOpen((v) => !v)}
        className="surface-card-sm flex items-center gap-2 px-3 py-2"
        style={{ color: 'var(--color-text-primary)', minWidth: '240px' }}
        title="Choose workflow"
      >
        <span className="material-symbols-outlined text-base" style={{ color: 'var(--color-primary)' }}>
          deployed_code
        </span>
        <span className="truncate text-sm font-semibold">
          {loading ? 'Loading workflows…' : selected?.name || 'Select a workflow'}
        </span>
        <span className="material-symbols-outlined ml-auto text-base">
          {open ? 'expand_less' : 'expand_more'}
        </span>
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div
            className="surface-card absolute left-0 z-50 mt-2 max-h-96 w-80 overflow-auto"
          >
            {workflows.length === 0 ? (
              <div className="px-4 py-3 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                {loading ? 'Loading…' : 'No workflows found. Create one in Studio first.'}
              </div>
            ) : (
              workflows.map((workflow) => {
                const isActive = workflow.id === selectedId;
                return (
                  <button
                    key={workflow.id}
                    onClick={() => {
                      onSelect(workflow.id);
                      setOpen(false);
                    }}
                    className="flex w-full items-center justify-between px-4 py-2 text-left transition-all hover:bg-black/5 dark:hover:bg-white/5"
                  >
                    <div className="min-w-0 flex-1">
                      <div
                        className="truncate text-sm font-medium"
                        style={{
                          color: isActive ? 'var(--color-primary)' : 'var(--color-text-primary)',
                        }}
                      >
                        {workflow.name}
                      </div>
                      {workflow.description && (
                        <div className="truncate text-xs" style={{ color: 'var(--color-text-muted)' }}>
                          {workflow.description}
                        </div>
                      )}
                    </div>
                    {isActive && (
                      <span
                        className="material-symbols-outlined ml-2 text-base"
                        style={{ color: 'var(--color-primary)' }}
                      >
                        check
                      </span>
                    )}
                  </button>
                );
              })
            )}
          </div>
        </>
      )}
    </div>
  );
}
