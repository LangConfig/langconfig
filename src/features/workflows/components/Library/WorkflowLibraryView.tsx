/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useEffect, useMemo, useRef } from 'react';
import apiClient from "../../../../lib/api-client";
import { useProject } from "../../../../contexts/ProjectContext";
import ProjectSection from './ProjectSection';
import LibraryContentPanel from './LibraryContentPanel';
import RenameModal from './RenameModal';
import ChangeProjectModal from './ChangeProjectModal';
import type { Workflow, Project } from '../types/workflow';

interface WorkflowLibraryViewProps {
  onWorkflowSelect: (workflowId: number) => void;
  onWorkflowOpen: (workflowId: number) => void;
}

export default function WorkflowLibraryView({
  onWorkflowSelect,
  onWorkflowOpen,
}: WorkflowLibraryViewProps) {
  const { activeProject } = useProject();
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<number | null>(null);
  const [expandedProjects, setExpandedProjects] = useState<Set<number>>(new Set());
  const [showCodeModal, setShowCodeModal] = useState(false);
  const [generatedCode, setGeneratedCode] = useState<string>('');
  const [loadingCode, setLoadingCode] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [workflowToDelete, setWorkflowToDelete] = useState<number | null>(null);
  const [showRenameModal, setShowRenameModal] = useState(false);
  const [workflowToRename, setWorkflowToRename] = useState<Workflow | null>(null);
  const [showChangeProjectModal, setShowChangeProjectModal] = useState(false);
  const [workflowToChangeProject, setWorkflowToChangeProject] = useState<Workflow | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newWorkflowName, setNewWorkflowName] = useState('');
  const [showExportMenu, setShowExportMenu] = useState(false);
  const [exportLoading, setExportLoading] = useState(false);
  const [showImportModal, setShowImportModal] = useState(false);
  const [importLoading, setImportLoading] = useState(false);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importPreview, setImportPreview] = useState<any>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const abortController = new AbortController();

    loadData(abortController.signal);

    return () => {
      abortController.abort();
    };
  }, []);

  // Auto-expand active project on load (run once after projects load)
  useEffect(() => {
    if (activeProject && projects.length > 0 && !expandedProjects.has(activeProject.id)) {
      setExpandedProjects(prev => new Set([...prev, activeProject.id]));
    }
  }, [activeProject?.id, projects.length]); // Only depend on project ID, not the whole object

  const loadData = async (signal?: AbortSignal) => {
    try {
      setLoading(true);

      // Load projects and workflows in parallel
      const [projectsResponse, workflowsResponse] = await Promise.all([
        apiClient.listProjects({ signal } as any),
        apiClient.listWorkflows({ signal } as any)
      ]);

      const loadedProjects = projectsResponse.data.projects || projectsResponse.data || [];
      const loadedWorkflows = workflowsResponse.data || [];


      setProjects(loadedProjects);
      setWorkflows(loadedWorkflows);

      // Auto-expand active project
      if (activeProject) {
        setExpandedProjects(new Set([activeProject.id]));
      }

      // Auto-expand uncategorized section if there are workflows without projects
      const hasUncategorized = loadedWorkflows.some((w: Workflow) => !w.project_id);
      if (hasUncategorized) {
        setExpandedProjects(prev => new Set([...prev, -1]));
      }
    } catch (error) {
      // Ignore abort errors
      if (error instanceof Error && error.name === 'AbortError') {
        return;
      }
      console.error('Failed to load data:', error);
      setProjects([]);
      setWorkflows([]);
    } finally {
      setLoading(false);
    }
  };

  // Group workflows by project
  const workflowsByProject = useMemo(() => {
    const grouped = new Map<number | null, Workflow[]>();

    workflows.forEach(workflow => {
      const projectId = workflow.project_id || null;
      if (!grouped.has(projectId)) {
        grouped.set(projectId, []);
      }
      grouped.get(projectId)!.push(workflow);
    });

    return grouped;
  }, [workflows]);

  // Filter workflows based on search query
  const filteredWorkflowsByProject = useMemo(() => {
    if (!searchQuery.trim()) {
      return workflowsByProject;
    }

    const filtered = new Map<number | null, Workflow[]>();
    const lowerQuery = searchQuery.toLowerCase();

    workflowsByProject.forEach((projectWorkflows, projectId) => {
      const matchingWorkflows = projectWorkflows.filter(workflow =>
        workflow.name.toLowerCase().includes(lowerQuery)
      );
      if (matchingWorkflows.length > 0) {
        filtered.set(projectId, matchingWorkflows);
      }
    });

    return filtered;
  }, [workflowsByProject, searchQuery]);

  const selectedWorkflow = useMemo(() => {
    return workflows.find(w => w.id === selectedWorkflowId) || null;
  }, [workflows, selectedWorkflowId]);

  const toggleProject = (projectId: number) => {
    setExpandedProjects(prev => {
      const next = new Set(prev);
      if (next.has(projectId)) {
        next.delete(projectId);
      } else {
        next.add(projectId);
      }
      return next;
    });
  };

  const handleSelectWorkflow = (workflow: Workflow) => {
    // Toggle selection - clicking the same workflow deselects it
    if (selectedWorkflowId === workflow.id) {
      setSelectedWorkflowId(null);
    } else {
      setSelectedWorkflowId(workflow.id);
      onWorkflowSelect(workflow.id);
    }
  };

  const handleCreateWorkflow = () => {
    // Show modal to name the new workflow
    setNewWorkflowName('');
    setShowCreateModal(true);
  };

  const confirmCreateWorkflow = async () => {
    if (!newWorkflowName.trim()) {
      alert('Please enter a workflow name');
      return;
    }

    try {
      // Create new workflow in database
      const response = await apiClient.createWorkflow({
        name: newWorkflowName.trim(),
        project_id: activeProject?.id || undefined,
        configuration: {},
        blueprint: { nodes: [], edges: [] }
      });

      // Add to list
      setWorkflows([response.data, ...workflows]);

      // Close modal
      setShowCreateModal(false);
      setNewWorkflowName('');

      // Open the new workflow in studio
      onWorkflowOpen(response.data.id);
    } catch (error: any) {
      console.error('Failed to create workflow:', error);
      alert(`Failed to create workflow: ${error.response?.data?.detail || error.message || 'Unknown error'}`);
    }
  };

  const handleOpenStudio = () => {
    if (selectedWorkflowId) {
      onWorkflowOpen(selectedWorkflowId);
    }
  };

  const handleDuplicate = async () => {
    if (!selectedWorkflow) return;
    await handleDuplicateWorkflow(selectedWorkflow);
  };

  const handleDuplicateWorkflow = async (workflow: Workflow) => {
    try {
      // Find the next available number for this workflow name
      const baseName = workflow.name.replace(/ \(\d+\)$/, '');
      const existingCopies = workflows.filter(w =>
        w.name === baseName || w.name.match(new RegExp(`^${baseName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')} \\(\\d+\\)$`))
      );
      const nextNumber = existingCopies.length > 0 ? existingCopies.length + 1 : 1;

      const duplicateData = {
        name: `${baseName} (${nextNumber})`,
        project_id: workflow.project_id,
        strategy_type: workflow.strategy_type,
        configuration: workflow.configuration,
        blueprint: workflow.blueprint,
      };

      const response = await apiClient.createWorkflow(duplicateData);
      setWorkflows([response.data, ...workflows]);
    } catch (error) {
      console.error('Failed to duplicate workflow:', error);
      alert('Failed to duplicate workflow');
    }
  };

  const handleDelete = async () => {
    if (!selectedWorkflowId) return;
    setWorkflowToDelete(selectedWorkflowId);
    setShowDeleteConfirm(true);
  };

  const handleDeleteWorkflow = (workflow: Workflow) => {
    setWorkflowToDelete(workflow.id);
    setShowDeleteConfirm(true);
  };

  const handleRenameWorkflow = (workflow: Workflow) => {
    setWorkflowToRename(workflow);
    setShowRenameModal(true);
  };

  const handleChangeProjectWorkflow = (workflow: Workflow) => {
    setWorkflowToChangeProject(workflow);
    setShowChangeProjectModal(true);
  };

  const confirmRename = async (newName: string) => {
    if (!workflowToRename) return;

    try {
      await apiClient.updateWorkflow(workflowToRename.id, { name: newName });
      setWorkflows(workflows.map(w =>
        w.id === workflowToRename.id ? { ...w, name: newName } : w
      ));
      setShowRenameModal(false);
      setWorkflowToRename(null);
    } catch (error: any) {
      console.error('Failed to rename workflow:', error);
      alert(`Failed to rename workflow: ${error.response?.data?.detail || error.message || 'Unknown error'}`);
    }
  };

  const confirmChangeProject = async (projectId: number | null) => {
    if (!workflowToChangeProject) return;

    try {
      await apiClient.updateWorkflow(workflowToChangeProject.id, { project_id: projectId });
      setWorkflows(workflows.map(w =>
        w.id === workflowToChangeProject.id ? { ...w, project_id: projectId ?? undefined } : w
      ));
      setShowChangeProjectModal(false);
      setWorkflowToChangeProject(null);
    } catch (error: any) {
      console.error('Failed to change project:', error);
      alert(`Failed to change project: ${error.response?.data?.detail || error.message || 'Unknown error'}`);
    }
  };

  const confirmDelete = async () => {
    if (!workflowToDelete) return;

    try {
      await apiClient.deleteWorkflow(workflowToDelete);
      setWorkflows(workflows.filter(w => w.id !== workflowToDelete));
      setSelectedWorkflowId(null);
      setShowDeleteConfirm(false);
      setWorkflowToDelete(null);
    } catch (error: any) {
      console.error('Failed to delete workflow:', error);
      alert(`Failed to delete workflow: ${error.response?.data?.detail || error.message || 'Unknown error'}`);
    }
  };

  const handleExportCode = async () => {
    if (!selectedWorkflowId) return;

    try {
      setLoadingCode(true);
      setShowCodeModal(true);
      const response = await apiClient.getWorkflowCode(selectedWorkflowId);
      setGeneratedCode(response.data);
    } catch (error) {
      console.error('Failed to generate code:', error);
      setGeneratedCode('// Error generating code\n// Please try again');
    } finally {
      setLoadingCode(false);
    }
  };

  const handleExportPackage = async () => {
    if (!selectedWorkflowId) return;

    try {
      setExportLoading(true);
      setShowExportMenu(false);

      // Call the export package endpoint
      const response = await fetch(`/api/workflows/${selectedWorkflowId}/export/package`, {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error('Failed to export package');
      }

      // Get the blob and download
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `workflow_${selectedWorkflow?.name?.replace(/\s+/g, '_') || selectedWorkflowId}.zip`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      alert('Workflow exported as Python package!');
    } catch (error) {
      console.error('Failed to export package:', error);
      alert('Failed to export workflow package. Please try again.');
    } finally {
      setExportLoading(false);
    }
  };

  const handleExportLangConfig = async () => {
    if (!selectedWorkflowId) return;

    try {
      setExportLoading(true);
      setShowExportMenu(false);

      // Call the export config endpoint
      const response = await fetch(`/api/workflows/${selectedWorkflowId}/export/config`);

      if (!response.ok) {
        throw new Error('Failed to export config');
      }

      // Get the JSON and download
      const config = await response.json();
      const blob = new Blob([JSON.stringify(config, null, 2)], { type: 'application/json' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${selectedWorkflow?.name?.replace(/\s+/g, '_') || 'workflow'}.langconfig`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      alert('Workflow exported as .langconfig file!');
    } catch (error) {
      console.error('Failed to export config:', error);
      alert('Failed to export workflow config. Please try again.');
    } finally {
      setExportLoading(false);
    }
  };

  const handleImportClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // Validate file extension
    if (!file.name.endsWith('.langconfig')) {
      alert('Please select a .langconfig file');
      return;
    }

    try {
      const content = await file.text();
      const config = JSON.parse(content);

      setImportFile(file);
      setImportPreview(config);
      setShowImportModal(true);
    } catch (error) {
      console.error('Failed to parse file:', error);
      alert('Invalid .langconfig file. Please check the file format.');
    }

    // Reset file input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const confirmImport = async () => {
    if (!importPreview) return;

    try {
      setImportLoading(true);

      const response = await fetch('/api/workflows/import', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          config: importPreview,
          project_id: activeProject?.id || 0,
          create_custom_tools: true,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to import workflow');
      }

      const result = await response.json();

      // Reload workflows
      await loadData();

      setShowImportModal(false);
      setImportFile(null);
      setImportPreview(null);

      alert(`Workflow "${result.workflow_name}" imported successfully!`);

      // Select the new workflow
      setSelectedWorkflowId(result.workflow_id);
    } catch (error: any) {
      console.error('Failed to import workflow:', error);
      alert(`Failed to import workflow: ${error.message || 'Unknown error'}`);
    } finally {
      setImportLoading(false);
    }
  };

  const copyToClipboard = () => {
    navigator.clipboard.writeText(generatedCode);
    alert('Code copied to clipboard!');
  };

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center bg-background-light dark:bg-background-dark">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary mb-4"></div>
          <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>Loading workflows...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex overflow-hidden bg-background-light dark:bg-background-dark">
      {/* Left Panel - Project-Grouped Workflows */}
      <div className="w-96 flex flex-col border-r border-gray-200 dark:border-border-dark bg-white dark:bg-panel-dark">
        {/* Header */}
        <div className="p-4 border-b border-gray-200 dark:border-border-dark">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold" style={{ color: 'var(--color-text-primary)' }}>
              Workflow Library
            </h2>
            <div className="flex items-center gap-2">
              <button
                onClick={handleImportClick}
                className="px-3 py-1.5 text-sm font-medium border border-gray-300 dark:border-border-dark rounded-lg hover:bg-gray-50 dark:hover:bg-white/5 transition-colors flex items-center gap-1"
                style={{ color: 'var(--color-text-primary)' }}
              >
                <span className="material-symbols-outlined text-sm">upload</span>
                Import
              </button>
              <button
                onClick={handleCreateWorkflow}
                className="px-3 py-1.5 text-sm font-medium text-white bg-primary rounded-lg hover:opacity-90 transition-opacity flex items-center gap-1"
              >
                <span className="material-symbols-outlined text-sm">add</span>
                New
              </button>
            </div>
            {/* Hidden file input for import */}
            <input
              ref={fileInputRef}
              type="file"
              accept=".langconfig"
              onChange={handleFileSelect}
              className="hidden"
            />
          </div>

          {/* Search Bar */}
          <div className="relative">
            <span
              className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-base"
              style={{ color: 'var(--color-text-muted)' }}
            >
              search
            </span>
            <input
              type="text"
              placeholder="Search workflows..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 text-sm border border-gray-300 dark:border-border-dark rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
              style={{
                backgroundColor: 'var(--color-input-background)',
                color: 'var(--color-text-primary)'
              }}
            />
          </div>
        </div>

        {/* Project Sections */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {/* Display all projects (even if they don't have workflows) */}
          {projects.map(project => {
            const projectWorkflows = filteredWorkflowsByProject.get(project.id) || [];
            return (
              <ProjectSection
                key={project.id}
                project={project}
                workflows={projectWorkflows}
                isExpanded={expandedProjects.has(project.id)}
                isActive={activeProject?.id === project.id}
                selectedWorkflowId={selectedWorkflowId}
                onToggle={() => toggleProject(project.id)}
                onSelectWorkflow={handleSelectWorkflow}
                onRenameWorkflow={handleRenameWorkflow}
                onDuplicateWorkflow={handleDuplicateWorkflow}
                onChangeProjectWorkflow={handleChangeProjectWorkflow}
                onDeleteWorkflow={handleDeleteWorkflow}
              />
            );
          })}

          {/* Uncategorized workflows (no project) */}
          {filteredWorkflowsByProject.has(null) && (
            <ProjectSection
              project={{
                id: -1,
                name: 'Uncategorized',
                description: 'Workflows not assigned to any project',
                status: 'idle'
              }}
              workflows={filteredWorkflowsByProject.get(null) || []}
              isExpanded={expandedProjects.has(-1)}
              selectedWorkflowId={selectedWorkflowId}
              onToggle={() => toggleProject(-1)}
              onSelectWorkflow={handleSelectWorkflow}
              onRenameWorkflow={handleRenameWorkflow}
              onDuplicateWorkflow={handleDuplicateWorkflow}
              onChangeProjectWorkflow={handleChangeProjectWorkflow}
              onDeleteWorkflow={handleDeleteWorkflow}
            />
          )}

          {/* No workflows found */}
          {projects.length === 0 && workflows.length === 0 && (
            <div className="text-center py-12">
              <span
                className="material-symbols-outlined text-5xl mb-3"
                style={{ color: 'var(--color-text-muted)' }}
              >
                account_tree
              </span>
              <p className="text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                No workflows yet
              </p>
              <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                Create your first workflow to get started
              </p>
            </div>
          )}
          {searchQuery && workflows.length > 0 && filteredWorkflowsByProject.size === 0 && (
            <div className="text-center py-12">
              <span
                className="material-symbols-outlined text-5xl mb-3"
                style={{ color: 'var(--color-text-muted)' }}
              >
                search_off
              </span>
              <p className="text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                No workflows found
              </p>
              <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                Try a different search term
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Right Panel - Context-Aware Content */}
      <div className="flex-1 overflow-hidden">
        <LibraryContentPanel
          activeProject={activeProject}
          onCreateWorkflow={handleCreateWorkflow}
          selectedWorkflow={selectedWorkflow}
          onOpenStudio={handleOpenStudio}
          onDuplicate={handleDuplicate}
          onDelete={handleDelete}
          onExportCode={handleExportCode}
        />
      </div>

      {/* Code Export Modal */}
      {showCodeModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-panel-dark rounded-lg max-w-4xl w-full max-h-[80vh] flex flex-col shadow-2xl">
            {/* Modal Header */}
            <div className="p-6 border-b border-gray-200 dark:border-border-dark flex items-center justify-between">
              <h3 className="text-xl font-bold" style={{ color: 'var(--color-text-primary)' }}>
                Generated LangGraph Code
              </h3>
              <button
                onClick={() => setShowCodeModal(false)}
                className="p-2 hover:bg-gray-100 dark:hover:bg-white/10 rounded-lg transition-all"
              >
                <span className="material-symbols-outlined" style={{ color: 'var(--color-text-muted)' }}>
                  close
                </span>
              </button>
            </div>

            {/* Modal Content */}
            <div className="flex-1 overflow-y-auto p-6">
              {loadingCode ? (
                <div className="text-center py-12">
                  <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary mb-4"></div>
                  <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>Generating code...</p>
                </div>
              ) : (
                <pre className="text-xs p-4 rounded-lg bg-gray-50 dark:bg-black/20 overflow-x-auto" style={{ color: 'var(--color-text-primary)' }}>
                  {generatedCode}
                </pre>
              )}
            </div>

            {/* Modal Footer */}
            <div className="p-6 border-t border-gray-200 dark:border-border-dark flex items-center justify-end gap-3">
              <button
                onClick={() => setShowCodeModal(false)}
                className="px-4 py-2 text-sm font-medium border border-gray-300 dark:border-border-dark rounded-lg hover:bg-gray-100 dark:hover:bg-white/10 hover:border-gray-400 dark:hover:border-border-light transition-all"
                style={{ color: 'var(--color-text-primary)' }}
              >
                Close
              </button>
              <button
                onClick={copyToClipboard}
                disabled={loadingCode}
                className="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:brightness-110 hover:shadow-lg transition-all disabled:opacity-50 flex items-center gap-2"
              >
                <span className="material-symbols-outlined text-sm">content_copy</span>
                Copy to Clipboard
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-panel-dark rounded-lg max-w-md w-full p-6 shadow-2xl">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 rounded-lg bg-red-100 dark:bg-red-500/20 flex items-center justify-center">
                <span className="material-symbols-outlined text-red-600 dark:text-red-400 text-2xl">
                  warning
                </span>
              </div>
              <h3 className="text-lg font-bold" style={{ color: 'var(--color-text-primary)' }}>
                Delete Workflow?
              </h3>
            </div>

            <div className="mb-6">
              <p className="text-sm mb-3 font-medium text-red-600 dark:text-red-400">
                ⚠️ This will permanently delete:
              </p>
              <ul className="text-sm space-y-1.5 ml-4" style={{ color: 'var(--color-text-muted)' }}>
                <li className="flex items-start gap-2">
                  <span className="text-red-500 mt-0.5">•</span>
                  <span>The workflow configuration and design</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-red-500 mt-0.5">•</span>
                  <span>All execution history and task records</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-red-500 mt-0.5">•</span>
                  <span>All execution events and logs</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-red-500 mt-0.5">•</span>
                  <span>All generated files in the workspace</span>
                </li>
              </ul>
              <p className="text-sm mt-3 font-semibold text-red-600 dark:text-red-400">
                This action cannot be undone.
              </p>
            </div>

            <div className="flex items-center justify-end gap-3">
              <button
                onClick={() => {
                  setShowDeleteConfirm(false);
                  setWorkflowToDelete(null);
                }}
                className="px-4 py-2 text-sm font-medium border border-gray-300 dark:border-border-dark rounded-lg hover:bg-gray-100 dark:hover:bg-white/10 hover:border-gray-400 dark:hover:border-border-light transition-all"
                style={{ color: 'var(--color-text-primary)' }}
              >
                Cancel
              </button>
              <button
                onClick={confirmDelete}
                className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:brightness-110 hover:shadow-lg transition-all"
              >
                Delete Workflow
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Rename Modal */}
      {showRenameModal && workflowToRename && (
        <RenameModal
          currentName={workflowToRename.name}
          onRename={confirmRename}
          onClose={() => {
            setShowRenameModal(false);
            setWorkflowToRename(null);
          }}
        />
      )}

      {/* Change Project Modal */}
      {showChangeProjectModal && workflowToChangeProject && (
        <ChangeProjectModal
          currentProjectId={workflowToChangeProject.project_id || null}
          projects={projects}
          onChangeProject={confirmChangeProject}
          onClose={() => {
            setShowChangeProjectModal(false);
            setWorkflowToChangeProject(null);
          }}
        />
      )}

      {/* Create Workflow Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-panel-dark rounded-lg max-w-md w-full p-6 shadow-2xl">
            <h3 className="text-lg font-bold mb-4" style={{ color: 'var(--color-text-primary)' }}>
              Create New Workflow
            </h3>

            <form onSubmit={(e) => {
              e.preventDefault();
              confirmCreateWorkflow();
            }}>
              <div className="mb-4">
                <label className="block text-sm font-medium mb-2" style={{ color: 'var(--color-text-primary)' }}>
                  Workflow Name
                </label>
                <input
                  type="text"
                  value={newWorkflowName}
                  onChange={(e) => setNewWorkflowName(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-border-dark rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                  style={{
                    backgroundColor: 'var(--color-input-background)',
                    color: 'var(--color-text-primary)'
                  }}
                  placeholder="Enter workflow name..."
                  autoFocus
                />
              </div>

              {activeProject && (
                <div className="mb-4 p-3 rounded-lg bg-gray-50 dark:bg-white/5">
                  <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                    Will be created in: <span className="font-medium" style={{ color: 'var(--color-text-primary)' }}>{activeProject.name}</span>
                  </p>
                </div>
              )}

              <div className="flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={() => {
                    setShowCreateModal(false);
                    setNewWorkflowName('');
                  }}
                  className="px-4 py-2 text-sm font-medium border border-gray-300 dark:border-border-dark rounded-lg hover:bg-gray-100 dark:hover:bg-white/10 hover:border-gray-400 dark:hover:border-border-light transition-all"
                  style={{ color: 'var(--color-text-primary)' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!newWorkflowName.trim()}
                  className="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:brightness-110 hover:shadow-lg transition-all disabled:opacity-50"
                >
                  Create Workflow
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Import Workflow Modal */}
      {showImportModal && importPreview && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-panel-dark rounded-lg max-w-lg w-full p-6 shadow-2xl">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center">
                <span className="material-symbols-outlined text-primary text-2xl">
                  upload_file
                </span>
              </div>
              <h3 className="text-lg font-bold" style={{ color: 'var(--color-text-primary)' }}>
                Import Workflow
              </h3>
            </div>

            {/* Import Preview */}
            <div className="mb-4 p-4 rounded-lg bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-border-dark">
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm" style={{ color: 'var(--color-text-muted)' }}>Workflow Name:</span>
                  <span className="text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>
                    {importPreview.workflow?.name || 'Unknown'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm" style={{ color: 'var(--color-text-muted)' }}>Version:</span>
                  <span className="text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>
                    {importPreview.version || 'Unknown'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm" style={{ color: 'var(--color-text-muted)' }}>Nodes:</span>
                  <span className="text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>
                    {importPreview.workflow?.configuration?.nodes?.length ||
                     importPreview.workflow?.blueprint?.nodes?.length || 0}
                  </span>
                </div>
                {importPreview.custom_tools?.length > 0 && (
                  <div className="flex items-center justify-between">
                    <span className="text-sm" style={{ color: 'var(--color-text-muted)' }}>Custom Tools:</span>
                    <span className="text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>
                      {importPreview.custom_tools.length}
                    </span>
                  </div>
                )}
                {importPreview.metadata?.exported_at && (
                  <div className="flex items-center justify-between">
                    <span className="text-sm" style={{ color: 'var(--color-text-muted)' }}>Exported:</span>
                    <span className="text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>
                      {new Date(importPreview.metadata.exported_at).toLocaleDateString()}
                    </span>
                  </div>
                )}
              </div>
            </div>

            {importPreview.workflow?.description && (
              <div className="mb-4">
                <p className="text-xs font-medium mb-1" style={{ color: 'var(--color-text-muted)' }}>
                  Description:
                </p>
                <p className="text-sm" style={{ color: 'var(--color-text-primary)' }}>
                  {importPreview.workflow.description}
                </p>
              </div>
            )}

            {activeProject && (
              <div className="mb-4 p-3 rounded-lg bg-blue-50 dark:bg-blue-500/10 border border-blue-200 dark:border-blue-500/30">
                <p className="text-xs text-blue-700 dark:text-blue-400">
                  Will be imported to: <span className="font-medium">{activeProject.name}</span>
                </p>
              </div>
            )}

            <div className="flex items-center justify-end gap-3">
              <button
                onClick={() => {
                  setShowImportModal(false);
                  setImportFile(null);
                  setImportPreview(null);
                }}
                className="px-4 py-2 text-sm font-medium border border-gray-300 dark:border-border-dark rounded-lg hover:bg-gray-100 dark:hover:bg-white/10 hover:border-gray-400 dark:hover:border-border-light transition-all"
                style={{ color: 'var(--color-text-primary)' }}
                disabled={importLoading}
              >
                Cancel
              </button>
              <button
                onClick={confirmImport}
                disabled={importLoading}
                className="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:brightness-110 hover:shadow-lg transition-all disabled:opacity-50 flex items-center gap-2"
              >
                {importLoading ? (
                  <>
                    <span className="inline-block animate-spin rounded-full h-4 w-4 border-b-2 border-white"></span>
                    Importing...
                  </>
                ) : (
                  <>
                    <span className="material-symbols-outlined text-sm">download</span>
                    Import Workflow
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
