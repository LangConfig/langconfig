/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useRef } from 'react';
import { FolderPlus, FolderOpen } from 'lucide-react';
import { useProject } from '../contexts/ProjectContext';
import { useNavigate } from 'react-router-dom';
import apiClient from '../lib/api-client';

export default function HomePage() {
  const { projects, refreshProjects, setActiveProjectId } = useProject();
  const navigate = useNavigate();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showOpenModal, setShowOpenModal] = useState(false);
  const [createForm, setCreateForm] = useState({
    name: '',
    description: '',
    directory_path: ''
  });
  const [creating, setCreating] = useState(false);
  const directoryInputRef = useRef<HTMLInputElement>(null);

  const handleCreateProject = async () => {
    if (!createForm.name.trim()) {
      alert('Please enter a project name');
      return;
    }

    setCreating(true);
    try {
      const response = await apiClient.createProject({
        name: createForm.name,
        description: createForm.description || undefined,
        configuration: {
          directory_path: createForm.directory_path || undefined
        }
      });

      // Axios throws on error by default, so if we get here it's success
      const newProject = response.data;
      await refreshProjects();
      setActiveProjectId(newProject.id);
      setShowCreateModal(false);
      setCreateForm({ name: '', description: '', directory_path: '' });
      navigate('/studio');
    } catch (error) {
      console.error('Failed to create project:', error);
      alert('Failed to create project. Check console for details.');
    } finally {
      setCreating(false);
    }
  };

  const handleOpenProject = (projectId: number) => {
    setActiveProjectId(projectId);
    setShowOpenModal(false);
    navigate('/studio');
  };

  const handleDirectorySelect = () => {
    if (directoryInputRef.current) {
      directoryInputRef.current.click();
    }
  };

  const handleDirectoryChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      // Get the directory path from the first file
      const firstFile = files[0];
      // Extract directory path (remove filename)
      const fullPath = firstFile.webkitRelativePath || firstFile.name;
      const directoryPath = fullPath.split('/')[0];
      setCreateForm(prev => ({ ...prev, directory_path: directoryPath }));
    }
  };

  return (
    <div
      className="flex flex-col items-center justify-center h-full w-full relative overflow-hidden bg-gray-50 dark:bg-background-dark"
    >
      {/* Background decoration */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div
          className="absolute -top-1/2 -right-1/2 w-full h-full rounded-full opacity-5"
          style={{ backgroundColor: 'var(--color-primary)' }}
        />
        <div
          className="absolute -bottom-1/2 -left-1/2 w-full h-full rounded-full opacity-5"
          style={{ backgroundColor: 'var(--color-primary)' }}
        />
      </div>

      {/* Content */}
      <div className="relative z-10 flex flex-col items-center max-w-4xl px-8 w-full">
        {/* Welcome Text */}
        <h1
          className="text-5xl font-bold mb-4 text-center tracking-tight"
          style={{ color: 'var(--color-text-primary)' }}
        >
          LangConfig Studio
        </h1>
        <p
          className="text-base mb-16 text-center max-w-lg"
          style={{ color: 'var(--color-text-muted)' }}
        >
          Visual AI workflow builder with multi-agent orchestration
        </p>

        {/* Action Cards Grid */}
        <div className="grid grid-cols-2 gap-4 w-full max-w-2xl mb-8">
          {/* Create Project */}
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-4 p-6 rounded-xl border border-gray-200 dark:border-border-dark bg-white dark:bg-panel-dark transition-all hover:shadow-lg group text-left"
          >
            <div
              className="p-3 rounded-lg transition-all group-hover:scale-110"
              style={{ backgroundColor: 'var(--color-primary)', color: 'white' }}
            >
              <FolderPlus size={24} />
            </div>
            <div className="flex-1">
              <div
                className="text-base font-semibold mb-0.5"
                style={{ color: 'var(--color-text-primary)' }}
              >
                Create Project
              </div>
              <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                Start building a new workflow
              </div>
            </div>
          </button>

          {/* Open Project */}
          <button
            onClick={() => setShowOpenModal(true)}
            className="flex items-center gap-4 p-6 rounded-xl border border-gray-200 dark:border-border-dark bg-white dark:bg-panel-dark transition-all hover:shadow-lg group text-left"
          >
            <div
              className="p-3 rounded-lg transition-all group-hover:scale-110"
              style={{
                backgroundColor: 'var(--color-background-light)',
                border: '2px solid var(--color-border-dark)',
                color: 'var(--color-primary)'
              }}
            >
              <FolderOpen size={24} />
            </div>
            <div className="flex-1">
              <div
                className="text-base font-semibold mb-0.5"
                style={{ color: 'var(--color-text-primary)' }}
              >
                Open Project
              </div>
              <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                Browse existing projects
              </div>
            </div>
          </button>
        </div>

        {/* Recent Projects */}
        {projects.length > 0 && (
          <div className="w-full max-w-2xl">
            <div
              className="flex items-center justify-between mb-3 px-1"
            >
              <div className="flex items-center gap-2">
                <span
                  className="text-sm font-semibold"
                  style={{ color: 'var(--color-text-primary)' }}
                >
                  Recent Projects
                </span>
                <span
                  className="text-xs px-2 py-0.5 rounded-full"
                  style={{
                    backgroundColor: 'var(--color-primary)',
                    color: 'white',
                    opacity: 0.8
                  }}
                >
                  {projects.length}
                </span>
              </div>
            </div>
            <div className="grid gap-2">
              {projects.slice(0, 3).map(project => (
                <button
                  key={project.id}
                  onClick={() => handleOpenProject(project.id)}
                  className="flex items-center justify-between p-4 rounded-lg border border-gray-200 dark:border-border-dark bg-white dark:bg-panel-dark transition-all hover:shadow-md text-left group"
                >
                  <div className="flex-1 min-w-0 mr-4">
                    <div
                      className="font-medium text-sm mb-0.5 truncate"
                      style={{ color: 'var(--color-text-primary)' }}
                    >
                      {project.name}
                    </div>
                    {project.description && (
                      <div
                        className="text-xs truncate"
                        style={{ color: 'var(--color-text-muted)' }}
                      >
                        {project.description}
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-3 flex-shrink-0">
                    <span
                      className="text-xs"
                      style={{ color: 'var(--color-text-muted)' }}
                    >
                      {new Date(project.created_at).toLocaleDateString()}
                    </span>
                    <span
                      className="material-symbols-outlined text-lg opacity-0 group-hover:opacity-100 transition-opacity"
                      style={{ color: 'var(--color-primary)' }}
                    >
                      arrow_forward
                    </span>
                  </div>
                </button>
              ))}
            </div>
            {projects.length > 3 && (
              <button
                onClick={() => setShowOpenModal(true)}
                className="w-full mt-2 p-2 rounded-lg text-xs font-medium transition-all hover:bg-white/5"
                style={{ color: 'var(--color-text-muted)' }}
              >
                View all {projects.length} projects →
              </button>
            )}
          </div>
        )}
      </div>

      {/* Create Project Modal */}
      {showCreateModal && (
        <>
          <div
            className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40"
            onClick={() => setShowCreateModal(false)}
          />
          <div
            className="fixed top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 z-50 w-full max-w-md rounded-xl shadow-2xl border border-gray-200 dark:border-border-dark bg-white dark:bg-panel-dark"
          >
            <div className="p-6">
              <h2
                className="text-2xl font-bold mb-6"
                style={{ color: 'var(--color-text-primary)' }}
              >
                Create New Project
              </h2>

              <div className="space-y-4">
                {/* Name */}
                <div>
                  <label
                    className="block text-sm font-medium mb-2"
                    style={{ color: 'var(--color-text-primary)' }}
                  >
                    Project Name *
                  </label>
                  <input
                    type="text"
                    value={createForm.name}
                    onChange={(e) => setCreateForm(prev => ({ ...prev, name: e.target.value }))}
                    placeholder="My AI Workflow"
                    className="w-full px-4 py-2 rounded-lg border border-gray-200 dark:border-border-dark bg-white dark:bg-panel-dark transition-all focus:outline-none focus:ring-2"
                    style={{
                      color: 'var(--color-text-primary)'
                    }}
                  />
                </div>

                {/* Description */}
                <div>
                  <label
                    className="block text-sm font-medium mb-2"
                    style={{ color: 'var(--color-text-primary)' }}
                  >
                    Description
                  </label>
                  <textarea
                    value={createForm.description}
                    onChange={(e) => setCreateForm(prev => ({ ...prev, description: e.target.value }))}
                    placeholder="Optional project description..."
                    rows={3}
                    className="w-full px-4 py-2 rounded-lg border border-gray-200 dark:border-border-dark bg-white dark:bg-panel-dark transition-all focus:outline-none focus:ring-2"
                    style={{
                      color: 'var(--color-text-primary)'
                    }}
                  />
                </div>

                {/* Directory Path */}
                <div>
                  <label
                    className="block text-sm font-medium mb-2"
                    style={{ color: 'var(--color-text-primary)' }}
                  >
                    Link to Directory (Optional)
                  </label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={createForm.directory_path}
                      onChange={(e) => setCreateForm(prev => ({ ...prev, directory_path: e.target.value }))}
                      placeholder="No directory selected"
                      readOnly
                      className="flex-1 px-4 py-2 rounded-lg border border-gray-200 dark:border-border-dark bg-gray-100 dark:bg-background-dark"
                      style={{
                        color: 'var(--color-text-muted)'
                      }}
                    />
                    <button
                      onClick={handleDirectorySelect}
                      className="px-4 py-2 rounded-lg border transition-all hover:bg-white/5"
                      style={{
                        borderColor: 'var(--color-border-dark)',
                        color: 'var(--color-text-primary)'
                      }}
                    >
                      Browse
                    </button>
                  </div>
                  <input
                    ref={directoryInputRef}
                    type="file"
                    // @ts-ignore
                    webkitdirectory=""
                    directory=""
                    multiple
                    onChange={handleDirectoryChange}
                    className="hidden"
                  />
                </div>
              </div>

              {/* Actions */}
              <div className="flex gap-3 mt-6">
                <button
                  onClick={() => setShowCreateModal(false)}
                  className="flex-1 px-4 py-2 rounded-lg border transition-all hover:bg-white/5"
                  style={{
                    borderColor: 'var(--color-border-dark)',
                    color: 'var(--color-text-primary)'
                  }}
                >
                  Cancel
                </button>
                <button
                  onClick={handleCreateProject}
                  disabled={creating || !createForm.name.trim()}
                  className="flex-1 px-4 py-2 rounded-lg font-semibold transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                  style={{
                    backgroundColor: 'var(--color-primary)',
                    color: 'white'
                  }}
                >
                  {creating ? 'Creating...' : 'Create Project'}
                </button>
              </div>
            </div>
          </div>
        </>
      )}

      {/* Open Project Modal */}
      {showOpenModal && (
        <>
          <div
            className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40"
            onClick={() => setShowOpenModal(false)}
          />
          <div
            className="fixed top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 z-50 w-full max-w-2xl max-h-[80vh] rounded-xl shadow-2xl border border-gray-200 dark:border-border-dark bg-white dark:bg-panel-dark overflow-hidden flex flex-col"
          >
            <div className="p-6 border-b" style={{ borderColor: 'var(--color-border-dark)' }}>
              <h2
                className="text-2xl font-bold"
                style={{ color: 'var(--color-text-primary)' }}
              >
                Open Project
              </h2>
            </div>

            <div className="flex-1 overflow-y-auto p-6">
              {projects.length === 0 ? (
                <div
                  className="text-center py-12"
                  style={{ color: 'var(--color-text-muted)' }}
                >
                  <FolderOpen size={48} className="mx-auto mb-4 opacity-50" />
                  <p>No projects found. Create one to get started!</p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {projects.map(project => (
                    <button
                      key={project.id}
                      onClick={() => handleOpenProject(project.id)}
                      className="p-4 rounded-lg border-2 border-gray-200 dark:border-border-dark bg-white dark:bg-panel-dark transition-all hover:scale-105 hover:shadow-lg text-left"
                    >
                      <div
                        className="font-bold text-lg mb-2"
                        style={{ color: 'var(--color-text-primary)' }}
                      >
                        {project.name}
                      </div>
                      {project.description && (
                        <div
                          className="text-sm mb-2"
                          style={{ color: 'var(--color-text-muted)' }}
                        >
                          {project.description}
                        </div>
                      )}
                      <div
                        className="text-xs flex items-center gap-2"
                        style={{ color: 'var(--color-text-muted)' }}
                      >
                        <span className={`px-2 py-0.5 rounded ${project.status === 'active' ? 'bg-green-500/20 text-green-700 dark:text-green-400' :
                          project.status === 'archived' ? 'bg-gray-500/20 text-gray-700 dark:text-gray-400' :
                            'bg-blue-500/20 text-blue-700 dark:text-blue-400'
                          }`}>
                          {project.status}
                        </span>
                        <span>•</span>
                        <span>{new Date(project.created_at).toLocaleDateString()}</span>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className="p-4 border-t" style={{ borderColor: 'var(--color-border-dark)' }}>
              <button
                onClick={() => setShowOpenModal(false)}
                className="w-full px-4 py-2 rounded-lg border transition-all hover:bg-white/5"
                style={{
                  borderColor: 'var(--color-border-dark)',
                  color: 'var(--color-text-primary)'
                }}
              >
                Close
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
