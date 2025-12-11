/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { memo } from 'react';
import { Save, Play, Trash2, History as HistoryIcon, StopCircle, Settings } from 'lucide-react';

interface WorkflowVersion {
  id: number;
  version_number: number;
  created_at: string;
  notes?: string;
  is_current?: boolean;
  created_by?: string;
}

interface AvailableWorkflow {
  id: number;
  name: string;
}

interface ExecutionStatus {
  state: 'idle' | 'running' | 'completed' | 'failed';
  currentNode?: string;
  progress?: number;
  startTime?: string;
  duration?: string;
}

interface WorkflowToolbarProps {
  // Workflow name editing
  workflowName: string;
  editedName: string;
  setEditedName: (name: string) => void;
  isEditingName: boolean;
  setIsEditingName: (editing: boolean) => void;
  handleWorkflowNameSave: () => void;
  handleStartEditingName: (e: React.MouseEvent) => void;

  // Workflow dropdown
  showWorkflowDropdown: boolean;
  handleToggleWorkflowDropdown: () => void;
  handleCloseWorkflowDropdown: () => void;
  workflowSearchQuery: string;
  handleWorkflowSearchChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  filteredWorkflows: AvailableWorkflow[];
  currentWorkflowId: number | null;
  handleWorkflowSwitch: (id: number) => void;
  onShowCreateWorkflowModal: () => void;

  // Save/Version actions
  handleSave: (silent?: boolean) => void;
  handleSaveVersion: () => void;

  // Version dropdown
  showVersionDropdown: boolean;
  setShowVersionDropdown: (show: boolean) => void;
  currentVersion: WorkflowVersion | null;
  versions: WorkflowVersion[];
  loadingVersions: boolean;
  handleLoadVersion: (versionNumber: number) => void;

  // Settings
  handleToggleSettingsModal: () => void;

  // Execution
  executionStatus: ExecutionStatus;
  currentTaskId: number | string | null;
  handleRun: () => void;
  handleStop: () => void;

  // Clear
  handleClear: () => void;
}

/**
 * Main toolbar component for the workflow canvas
 */
const WorkflowToolbar = memo(function WorkflowToolbar({
  workflowName,
  editedName,
  setEditedName,
  isEditingName,
  setIsEditingName,
  handleWorkflowNameSave,
  handleStartEditingName,
  showWorkflowDropdown,
  handleToggleWorkflowDropdown,
  handleCloseWorkflowDropdown,
  workflowSearchQuery,
  handleWorkflowSearchChange,
  filteredWorkflows,
  currentWorkflowId,
  handleWorkflowSwitch,
  onShowCreateWorkflowModal,
  handleSave,
  handleSaveVersion,
  showVersionDropdown,
  setShowVersionDropdown,
  currentVersion,
  versions,
  loadingVersions,
  handleLoadVersion,
  handleToggleSettingsModal,
  executionStatus,
  currentTaskId,
  handleRun,
  handleStop,
  handleClear,
}: WorkflowToolbarProps) {
  return (
    <div className="bg-white dark:bg-panel-dark border-b border-gray-200 dark:border-border-dark px-4 py-2.5">
      <div className="flex items-center gap-4">
        {/* LEFT SECTION: Workflow Switcher with integrated name */}
        <div className="relative flex items-center">
          {isEditingName ? (
            <input
              type="text"
              value={editedName}
              onChange={(e) => setEditedName(e.target.value)}
              onBlur={handleWorkflowNameSave}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleWorkflowNameSave();
                if (e.key === 'Escape') {
                  setEditedName(workflowName);
                  setIsEditingName(false);
                }
              }}
              autoFocus
              className="px-3 py-2 text-sm font-semibold bg-white dark:bg-background-dark border border-primary rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
              style={{ color: 'var(--color-text-primary, #1a1a1a)', minWidth: '250px' }}
            />
          ) : (
            <button
              onClick={handleToggleWorkflowDropdown}
              className="inline-flex items-center gap-2 px-3 py-2 text-sm font-semibold bg-white dark:bg-background-dark border border-gray-300 dark:border-border-dark rounded-lg hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
              style={{ color: 'var(--color-text-primary)' }}
              title="Click to switch workflow or double-click name to rename"
            >
              <span
                onDoubleClick={handleStartEditingName}
                className="max-w-[200px] truncate"
              >
                {workflowName}
              </span>
              <span className="material-symbols-outlined text-lg" style={{ color: 'var(--color-text-muted)' }}>
                expand_more
              </span>
            </button>
          )}

          {/* Workflow Dropdown */}
          {showWorkflowDropdown && (
            <>
              {/* Backdrop */}
              <div
                className="fixed inset-0 z-40"
                onClick={handleCloseWorkflowDropdown}
              />
              <div
                className="absolute top-full left-0 mt-1 w-80 rounded-lg shadow-xl z-50 max-h-96 overflow-hidden flex flex-col border"
                style={{
                  backgroundColor: 'var(--color-panel-dark)',
                  borderColor: 'var(--color-border-dark)'
                }}
              >
                {/* Search Bar */}
                <div
                  className="p-3 border-b"
                  style={{ borderColor: 'var(--color-border-dark)' }}
                >
                  <input
                    type="text"
                    placeholder="Search workflows..."
                    value={workflowSearchQuery}
                    onChange={handleWorkflowSearchChange}
                    className="w-full px-3 py-2 text-sm rounded-lg border focus:outline-none focus:ring-2 transition-all"
                    style={{
                      backgroundColor: 'var(--color-background-light)',
                      borderColor: 'var(--color-border-dark)',
                      color: 'var(--color-text-primary)'
                    }}
                  />
                </div>

                {/* Create New Workflow Button */}
                <div
                  className="p-2 border-b"
                  style={{ borderColor: 'var(--color-border-dark)' }}
                >
                  <button
                    onClick={onShowCreateWorkflowModal}
                    className="w-full px-3 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:opacity-90 transition-opacity flex items-center justify-center gap-2"
                  >
                    <span className="material-symbols-outlined text-sm">add</span>
                    Create New Workflow
                  </button>
                </div>

                {/* Workflow List */}
                <div className="overflow-y-auto">
                  {filteredWorkflows.length === 0 ? (
                    <div
                      className="p-4 text-center text-sm"
                      style={{ color: 'var(--color-text-muted)' }}
                    >
                      No workflows found
                    </div>
                  ) : (
                    filteredWorkflows.map((workflow) => {
                      const isActive = currentWorkflowId === workflow.id;
                      return (
                        <button
                          key={workflow.id}
                          onClick={() => handleWorkflowSwitch(workflow.id)}
                          className="w-full px-3 py-2.5 text-left transition-colors border-b last:border-0"
                          style={{
                            borderColor: 'var(--color-border-dark)',
                            backgroundColor: isActive ? 'var(--color-primary-alpha, rgba(139, 92, 246, 0.1))' : 'transparent',
                            borderLeftWidth: isActive ? '3px' : '0px',
                            borderLeftColor: isActive ? 'var(--color-primary)' : 'transparent'
                          }}
                          onMouseEnter={(e) => {
                            if (!isActive) {
                              e.currentTarget.style.backgroundColor = 'var(--color-background-light, rgba(255, 255, 255, 0.03))';
                            }
                          }}
                          onMouseLeave={(e) => {
                            if (!isActive) {
                              e.currentTarget.style.backgroundColor = 'transparent';
                            }
                          }}
                        >
                          <div
                            className="font-semibold text-sm leading-tight"
                            style={{
                              color: isActive ? 'var(--color-primary)' : 'var(--color-text-primary)',
                              wordBreak: 'break-word',
                              overflowWrap: 'break-word',
                              display: '-webkit-box',
                              WebkitLineClamp: 2,
                              WebkitBoxOrient: 'vertical',
                              overflow: 'hidden'
                            }}
                          >
                            {workflow.name}
                          </div>
                        </button>
                      );
                    })
                  )}
                </div>
              </div>
            </>
          )}
        </div>

        {/* DIVIDER */}
        <div className="w-px h-6 bg-gray-300 dark:bg-border-dark" />

        {/* CENTER-LEFT SECTION: Action Buttons */}
        <div className="flex items-center gap-2.5">
          <button
            onClick={() => handleSave(false)}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-lg transition-all hover:opacity-90 bg-primary text-white shadow-sm"
            title="Save workflow"
          >
            <Save className="w-4 h-4" />
            <span>Save</span>
          </button>

          {/* Version Management Buttons */}
          {currentWorkflowId && (
            <>
              <button
                onClick={handleSaveVersion}
                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-lg transition-all hover:opacity-90 bg-white dark:bg-background-dark border border-gray-300 dark:border-border-dark text-primary"
                title="Save as new version"
              >
                <HistoryIcon className="w-4 h-4" />
                <span>Save Version</span>
              </button>

              <div className="relative">
                <button
                  onClick={() => setShowVersionDropdown(!showVersionDropdown)}
                  className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium bg-white dark:bg-background-dark border border-gray-300 dark:border-border-dark rounded-lg hover:bg-gray-50 dark:hover:bg-white/5 transition-colors text-text-primary dark:text-text-primary"
                  title="Switch version"
                >
                  <HistoryIcon className="w-4 h-4" />
                  <span>{currentVersion ? `v${currentVersion.version_number}` : 'Versions'}</span>
                  <span className="text-xs opacity-60">▼</span>
                </button>

                {/* Version Dropdown */}
                {showVersionDropdown && (
                  <div className="absolute top-full mt-2 right-0 w-80 bg-white dark:bg-panel-dark border border-gray-200 dark:border-border-dark rounded-lg shadow-xl z-50 max-h-96 overflow-y-auto">
                    <div className="p-3 border-b border-gray-200 dark:border-border-dark">
                      <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
                        Workflow Versions
                      </h3>
                    </div>

                    {loadingVersions ? (
                      <div className="p-4 text-center text-gray-500 dark:text-gray-400">
                        Loading versions...
                      </div>
                    ) : versions.length === 0 ? (
                      <div className="p-4 text-center text-gray-500 dark:text-gray-400 text-sm">
                        No versions yet. Click "Save Version" to create one.
                      </div>
                    ) : (
                      <div className="py-2">
                        {versions.map((version) => (
                          <button
                            key={version.id}
                            onClick={() => handleLoadVersion(version.version_number)}
                            className={`w-full px-4 py-3 text-left hover:bg-gray-50 dark:hover:bg-white/5 transition-colors border-l-4 ${version.is_current
                              ? 'border-green-500 bg-green-50 dark:bg-green-900/20'
                              : 'border-transparent'
                              }`}
                          >
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-sm font-semibold text-gray-900 dark:text-white">
                                Version {version.version_number}
                                {version.is_current && (
                                  <span className="ml-2 px-2 py-0.5 text-xs bg-green-500 text-white rounded">
                                    Current
                                  </span>
                                )}
                              </span>
                              <span className="text-xs text-gray-500 dark:text-gray-400">
                                {new Date(version.created_at).toLocaleDateString()}
                              </span>
                            </div>
                            {version.notes && (
                              <p className="text-xs text-gray-600 dark:text-gray-400 line-clamp-2">
                                {version.notes}
                              </p>
                            )}
                            {version.created_by && (
                              <p className="text-xs text-gray-500 dark:text-gray-500 mt-1">
                                by {version.created_by}
                              </p>
                            )}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </>
          )}

          <button
            onClick={handleToggleSettingsModal}
            className="p-2 rounded-lg transition-colors flex items-center gap-2"
            style={{
              backgroundColor: 'var(--color-background-light)',
              color: 'var(--color-text-primary)',
              border: `1px solid var(--color-border-dark)`
            }}
            title="Workflow Settings"
          >
            <Settings size={18} />
            <span className="text-sm font-medium">Settings</span>
          </button>

          <button
            onClick={handleRun}
            className={`inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-lg transition-all hover:opacity-90 text-white shadow-sm ${executionStatus.state === 'running'
              ? 'bg-amber-500 dark:bg-amber-600'
              : 'bg-primary'
              }`}
            title={executionStatus.state === 'running' ? 'Workflow running - click to cancel and restart' : 'Execute workflow'}
          >
            {executionStatus.state === 'running' ? (
              <>
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                <span>Running...</span>
              </>
            ) : (
              <>
                <Play className="w-4 h-4" />
                <span>Run</span>
              </>
            )}
          </button>

          <button
            onClick={handleStop}
            disabled={!currentTaskId || executionStatus?.state !== 'running'}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-lg transition-all hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed bg-red-600 dark:bg-red-500 text-white shadow-sm"
            title="Stop running workflow"
          >
            <StopCircle className="w-4 h-4" />
            <span>Stop</span>
          </button>

        </div>

        {/* DIVIDER */}
        <div className="w-px h-6 bg-gray-300 dark:bg-border-dark" />

        {/* CENTER SECTION: Secondary Actions */}
        <div className="flex items-center gap-2">
          <button
            onClick={handleClear}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-red-600 dark:text-red-400 bg-white dark:bg-background-dark border border-red-300 dark:border-red-500/30 rounded-lg hover:bg-red-50 dark:hover:bg-red-500/10 transition-colors"
            title="Clear all nodes"
          >
            <Trash2 className="w-4 h-4" />
            <span>Clear</span>
          </button>
        </div>

      </div>
    </div>
  );
});

export default WorkflowToolbar;
