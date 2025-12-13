/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState } from 'react';

interface Project {
  id: number;
  name: string;
  description?: string;
  status: string;
}

interface ChangeProjectModalProps {
  currentProjectId: number | null;
  projects: Project[];
  onChangeProject: (projectId: number | null) => void;
  onClose: () => void;
}

export default function ChangeProjectModal({
  currentProjectId,
  projects,
  onChangeProject,
  onClose
}: ChangeProjectModalProps) {
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(currentProjectId);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedProjectId !== currentProjectId) {
      onChangeProject(selectedProjectId);
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-panel-dark rounded-lg max-w-md w-full p-6 shadow-2xl">
        <h3 className="text-lg font-bold mb-4" style={{ color: 'var(--color-text-primary)' }}>
          Change Project
        </h3>

        <form onSubmit={handleSubmit}>
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {/* Uncategorized option */}
            <label
              className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-colors border ${
                selectedProjectId === null
                  ? 'bg-primary/10 border-primary/50'
                  : 'hover:bg-gray-50 dark:hover:bg-white/5 border-gray-200 dark:border-border-dark'
              }`}
            >
              <input
                type="radio"
                name="project"
                checked={selectedProjectId === null}
                onChange={() => setSelectedProjectId(null)}
                className="w-4 h-4 text-primary"
              />
              <div className="flex-1">
                <p className="text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>
                  Uncategorized
                </p>
                <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                  No project assigned
                </p>
              </div>
            </label>

            {/* Project options */}
            {projects.map((project) => (
              <label
                key={project.id}
                className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-colors border ${
                  selectedProjectId === project.id
                    ? 'bg-primary/10 border-primary/50'
                    : 'hover:bg-gray-50 dark:hover:bg-white/5 border-gray-200 dark:border-border-dark'
                }`}
              >
                <input
                  type="radio"
                  name="project"
                  checked={selectedProjectId === project.id}
                  onChange={() => setSelectedProjectId(project.id)}
                  className="w-4 h-4 text-primary"
                />
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>
                      {project.name}
                    </p>
                    {project.status === 'active' && (
                      <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-green-100 dark:bg-green-500/20 text-green-700 dark:text-green-400">
                        Active
                      </span>
                    )}
                  </div>
                  {project.description && (
                    <p className="text-xs mt-0.5 line-clamp-1" style={{ color: 'var(--color-text-muted)' }}>
                      {project.description}
                    </p>
                  )}
                </div>
              </label>
            ))}
          </div>

          <div className="flex items-center justify-end gap-3 mt-6">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium border border-gray-300 dark:border-border-dark rounded-lg hover:bg-gray-100 dark:hover:bg-white/10 hover:border-gray-400 dark:hover:border-border-light transition-all"
              style={{ color: 'var(--color-text-primary)' }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={selectedProjectId === currentProjectId}
              className="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:brightness-110 hover:shadow-lg transition-all disabled:opacity-50"
            >
              Change Project
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
