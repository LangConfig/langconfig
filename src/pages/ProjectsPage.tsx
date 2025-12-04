/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useEffect } from 'react';
import apiClient from '../lib/api-client';

interface ProjectsViewProps {
  onProjectSelect: (projectId: number) => void;
}

interface Project {
  id: number;
  name: string;
  description?: string;
  status: string;
  created_at: string;
  indexed_nodes_count?: number;
}

export default function ProjectsView({ onProjectSelect }: ProjectsViewProps) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newProject, setNewProject] = useState({ name: '', description: '' });

  useEffect(() => {
    const abortController = new AbortController();

    fetchProjects(abortController.signal);

    return () => {
      abortController.abort();
    };
  }, []);

  const fetchProjects = async (signal?: AbortSignal) => {
    try {
      const response = await apiClient.listProjects({ signal } as any);
      setProjects(response.data || []);
    } catch (error) {
      // Ignore abort errors
      if (error instanceof Error && error.name === 'AbortError') {
        return;
      }
      console.error('Failed to fetch projects:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateProject = async () => {
    if (!newProject.name.trim()) return;

    try {
      await apiClient.createProject({
        name: newProject.name,
        description: newProject.description || undefined
      });
      setShowCreateModal(false);
      setNewProject({ name: '', description: '' });
      fetchProjects();
    } catch (error) {
      console.error('Failed to create project:', error);
      alert('Failed to create project. Check console for details.');
    }
  };

  return (
    <section className="flex-1 flex flex-col rounded-xl frosted-glass overflow-hidden p-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-[var(--text-light-primary)] dark:text-[var(--text-dark-primary)]">
          Projects
        </h2>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--primary)] text-white hover:opacity-90 transition-all button-90s"
        >
          <span className="material-symbols-outlined">add</span>
          New Project
        </button>
      </div>

      {loading ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-[var(--text-light-secondary)] dark:text-[var(--text-dark-secondary)]">
            Loading projects...
          </div>
        </div>
      ) : projects.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center gap-4">
          <span className="material-symbols-outlined text-6xl text-[var(--text-light-secondary)] dark:text-[var(--text-dark-secondary)] opacity-50">
            folder_off
          </span>
          <p className="text-[var(--text-light-secondary)] dark:text-[var(--text-dark-secondary)] text-center">
            No projects yet. Create your first project to get started!
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 overflow-y-auto">
          {projects.map((project) => (
            <div
              key={project.id}
              onClick={() => onProjectSelect(project.id)}
              className="p-4 rounded-lg bg-[var(--background-light)] dark:bg-[var(--background-dark)]/50 hover:border-[var(--primary)] border border-transparent cursor-pointer transition-all"
            >
              <div className="flex items-start gap-3">
                <span className="material-symbols-outlined text-[var(--primary)] text-3xl">folder</span>
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-[var(--text-light-primary)] dark:text-[var(--text-dark-primary)] truncate">
                    {project.name}
                  </h3>
                  {project.description && (
                    <p className="text-sm text-[var(--text-light-secondary)] dark:text-[var(--text-dark-secondary)] mt-1 line-clamp-2">
                      {project.description}
                    </p>
                  )}
                  <div className="flex items-center gap-4 mt-3 text-xs text-[var(--text-light-secondary)] dark:text-[var(--text-dark-secondary)]">
                    <span className={`px-2 py-1 rounded ${
                      project.status === 'active' ? 'bg-green-500/20 text-green-700 dark:text-green-300' : 'bg-gray-500/20'
                    }`}>
                      {project.status}
                    </span>
                    {project.indexed_nodes_count !== undefined && (
                      <span>{project.indexed_nodes_count} indexed</span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create Project Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 cursor-pointer" onClick={() => setShowCreateModal(false)}>
          <div className="bg-[var(--background-light)] dark:bg-[var(--background-dark)] rounded-xl p-6 w-full max-w-md frosted-glass" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-xl font-bold text-[var(--text-light-primary)] dark:text-[var(--text-dark-primary)] mb-4">
              Create New Project
            </h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-[var(--text-light-secondary)] dark:text-[var(--text-dark-secondary)] mb-2">
                  Project Name
                </label>
                <input
                  type="text"
                  value={newProject.name}
                  onChange={(e) => setNewProject({ ...newProject, name: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg shadow-inner-90s bg-[var(--background-light)] dark:bg-[var(--background-dark)] text-[var(--text-light-primary)] dark:text-[var(--text-dark-primary)] border-none focus:outline-none focus:ring-2 focus:ring-[var(--primary)]"
                  placeholder="My Awesome Project"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-[var(--text-light-secondary)] dark:text-[var(--text-dark-secondary)] mb-2">
                  Description (Optional)
                </label>
                <textarea
                  value={newProject.description}
                  onChange={(e) => setNewProject({ ...newProject, description: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg shadow-inner-90s bg-[var(--background-light)] dark:bg-[var(--background-dark)] text-[var(--text-light-primary)] dark:text-[var(--text-dark-primary)] border-none focus:outline-none focus:ring-2 focus:ring-[var(--primary)] min-h-[80px]"
                  placeholder="Describe what this project is about..."
                />
              </div>
            </div>
            <div className="flex gap-3 mt-6">
              <button
                onClick={() => setShowCreateModal(false)}
                className="flex-1 px-4 py-2 rounded-lg bg-gray-500/20 text-[var(--text-light-primary)] dark:text-[var(--text-dark-primary)] hover:bg-gray-500/30 transition-all"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateProject}
                className="flex-1 px-4 py-2 rounded-lg bg-[var(--primary)] text-white hover:opacity-90 transition-all button-90s"
                disabled={!newProject.name.trim()}
              >
                Create
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
