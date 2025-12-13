/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { memo } from 'react';
import { Save, History as HistoryIcon, Settings, FolderOpen, Image, Camera } from 'lucide-react';

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

type Tab = 'studio' | 'results' | 'files' | 'artifacts';

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

  // Tabs (merged from TabNavigation)
  activeTab: Tab;
  onTabChange: (tab: Tab) => void;
  taskHistoryCount: number;
  filesCount: number;
  artifactsCount: number;
  hasUnsavedChanges: boolean;
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
  activeTab,
  onTabChange,
  taskHistoryCount,
  filesCount,
  artifactsCount,
  hasUnsavedChanges,
}: WorkflowToolbarProps) {
  const tabClass = (tab: Tab) =>
    `px-4 py-2 text-sm font-semibold border-b-2 transition-all ${
      activeTab === tab
        ? 'border-primary text-primary'
        : 'border-transparent text-gray-600 dark:text-text-muted hover:text-gray-900 dark:hover:text-white'
    }`;
  return (
    <div className="bg-white dark:bg-panel-dark border-b border-gray-200 dark:border-border-dark px-4 py-1.5">
      <div className="flex items-center">
        {/* LEFT SECTION: Workflow Switcher + Save + Versions + Settings */}
        <div className="flex items-center gap-2">
          {/* Workflow Name/Switcher */}
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
                className="px-2 py-1.5 text-sm font-semibold bg-white dark:bg-background-dark border border-primary rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                style={{ color: 'var(--color-text-primary, #1a1a1a)', minWidth: '180px' }}
              />
            ) : (
              <button
                onClick={handleToggleWorkflowDropdown}
                className="inline-flex items-center gap-1.5 px-2 py-1.5 text-sm font-semibold bg-white dark:bg-background-dark border border-gray-300 dark:border-border-dark rounded-lg hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
                style={{ color: 'var(--color-text-primary)' }}
                title="Click to switch workflow or double-click name to rename"
              >
                <span
                  onDoubleClick={handleStartEditingName}
                  className="max-w-[200px] truncate"
                >
                  {workflowName}
                </span>
                <span className="material-symbols-outlined text-base" style={{ color: 'var(--color-text-muted)' }}>
                  expand_more
                </span>
              </button>
            )}

            {/* Workflow Dropdown */}
            {showWorkflowDropdown && (
              <>
                <div className="fixed inset-0 z-40" onClick={handleCloseWorkflowDropdown} />
                <div
                  className="absolute top-full left-0 mt-1 w-80 rounded-lg shadow-xl z-50 max-h-96 overflow-hidden flex flex-col border"
                  style={{ backgroundColor: 'var(--color-panel-dark)', borderColor: 'var(--color-border-dark)' }}
                >
                  <div className="p-3 border-b" style={{ borderColor: 'var(--color-border-dark)' }}>
                    <input
                      type="text"
                      placeholder="Search workflows..."
                      value={workflowSearchQuery}
                      onChange={handleWorkflowSearchChange}
                      className="w-full px-3 py-2 text-sm rounded-lg border focus:outline-none focus:ring-2 transition-all"
                      style={{ backgroundColor: 'var(--color-background-light)', borderColor: 'var(--color-border-dark)', color: 'var(--color-text-primary)' }}
                    />
                  </div>
                  <div className="p-2 border-b" style={{ borderColor: 'var(--color-border-dark)' }}>
                    <button
                      onClick={onShowCreateWorkflowModal}
                      className="w-full px-3 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:opacity-90 transition-opacity flex items-center justify-center gap-2"
                    >
                      <span className="material-symbols-outlined text-sm">add</span>
                      Create New Workflow
                    </button>
                  </div>
                  <div className="overflow-y-auto">
                    {filteredWorkflows.length === 0 ? (
                      <div className="p-4 text-center text-sm" style={{ color: 'var(--color-text-muted)' }}>
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
                            onMouseEnter={(e) => { if (!isActive) e.currentTarget.style.backgroundColor = 'var(--color-background-light, rgba(255, 255, 255, 0.03))'; }}
                            onMouseLeave={(e) => { if (!isActive) e.currentTarget.style.backgroundColor = 'transparent'; }}
                          >
                            <div
                              className="font-semibold text-sm leading-tight"
                              style={{
                                color: isActive ? 'var(--color-primary)' : 'var(--color-text-primary)',
                                wordBreak: 'break-word', overflowWrap: 'break-word',
                                display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden'
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

          {/* Save Button */}
          <button
            onClick={() => handleSave(false)}
            className="px-3 py-1.5 rounded-lg transition-all hover:opacity-90 bg-primary text-white flex items-center gap-1.5 text-sm font-medium"
            title="Save workflow"
          >
            <Save className="w-4 h-4" />
            <span>Save</span>
          </button>

          {/* Versions Dropdown - Compact with integrated snapshot */}
          {currentWorkflowId && (
            <div className="relative">
              <button
                onClick={() => setShowVersionDropdown(!showVersionDropdown)}
                className="inline-flex items-center gap-1.5 px-2 py-1.5 text-sm font-medium bg-white dark:bg-background-dark border border-gray-300 dark:border-border-dark rounded-lg hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
                style={{ color: 'var(--color-text-primary)' }}
                title="Versions"
              >
                <HistoryIcon className="w-4 h-4" />
                <span>{currentVersion ? `v${currentVersion.version_number}` : 'v1'}</span>
                <span className="text-xs opacity-60">▼</span>
              </button>

              {showVersionDropdown && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setShowVersionDropdown(false)} />
                  <div className="absolute top-full mt-1 left-0 w-72 bg-white dark:bg-panel-dark border border-gray-200 dark:border-border-dark rounded-lg shadow-xl z-50 max-h-80 overflow-hidden flex flex-col">
                    {/* Create Snapshot at top */}
                    <div className="p-2 border-b border-gray-200 dark:border-border-dark">
                      <button
                        onClick={() => { handleSaveVersion(); setShowVersionDropdown(false); }}
                        className="w-full px-3 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:opacity-90 transition-opacity flex items-center justify-center gap-2"
                      >
                        <Camera className="w-4 h-4" />
                        Create Snapshot
                      </button>
                    </div>

                    {/* Version List */}
                    <div className="overflow-y-auto flex-1">
                      {loadingVersions ? (
                        <div className="p-4 text-center text-gray-500 dark:text-gray-400 text-sm">Loading...</div>
                      ) : versions.length === 0 ? (
                        <div className="p-4 text-center text-gray-500 dark:text-gray-400 text-sm">
                          No snapshots yet
                        </div>
                      ) : (
                        versions.map((version) => (
                          <button
                            key={version.id}
                            onClick={() => { handleLoadVersion(version.version_number); setShowVersionDropdown(false); }}
                            className={`w-full px-3 py-2.5 text-left hover:bg-gray-50 dark:hover:bg-white/5 transition-colors border-b last:border-0 border-l-4 ${
                              version.is_current ? 'border-l-green-500 bg-green-50/50 dark:bg-green-900/20' : 'border-l-transparent'
                            }`}
                            style={{ borderBottomColor: 'var(--color-border-dark)' }}
                          >
                            <div className="flex items-center justify-between">
                              <span className="text-sm font-semibold text-gray-900 dark:text-white">
                                v{version.version_number}
                                {version.is_current && (
                                  <span className="ml-2 px-1.5 py-0.5 text-xs bg-green-500 text-white rounded">Current</span>
                                )}
                              </span>
                              <span className="text-xs text-gray-500 dark:text-gray-400">
                                {new Date(version.created_at).toLocaleDateString()}
                              </span>
                            </div>
                            {version.notes && (
                              <p className="text-xs text-gray-600 dark:text-gray-400 mt-1 line-clamp-1">{version.notes}</p>
                            )}
                          </button>
                        ))
                      )}
                    </div>
                  </div>
                </>
              )}
            </div>
          )}

          {/* Settings Button - Icon only */}
          <button
            onClick={handleToggleSettingsModal}
            className="p-2 rounded-lg transition-colors hover:bg-gray-100 dark:hover:bg-white/5"
            style={{ color: 'var(--color-text-muted)' }}
            title="Workflow Settings"
          >
            <Settings className="w-4 h-4" />
          </button>

          {/* Divider */}
          <div className="w-px h-6 bg-gray-300 dark:bg-gray-600 mx-2" />

          {/* Tabs - After settings */}
          <div className="flex items-center">
            <button onClick={() => onTabChange('studio')} className={tabClass('studio')}>
              Studio
            </button>
            <button onClick={() => onTabChange('results')} className={tabClass('results')}>
              Results {taskHistoryCount > 0 && <span className="ml-1 text-xs opacity-70">({taskHistoryCount})</span>}
            </button>
            <button onClick={() => onTabChange('files')} className={`${tabClass('files')} flex items-center gap-1.5`}>
              <FolderOpen className="w-4 h-4" />
              Files {filesCount > 0 && <span className="text-xs opacity-70">({filesCount})</span>}
            </button>
            <button onClick={() => onTabChange('artifacts')} className={`${tabClass('artifacts')} flex items-center gap-1.5`}>
              <Image className="w-4 h-4" />
              Artifacts {artifactsCount > 0 && <span className="text-xs opacity-70">({artifactsCount})</span>}
            </button>
          </div>
        </div>

        {/* SPACER */}
        <div className="flex-1" />

        {/* RIGHT SECTION: Status indicators */}
        <div className="flex items-center gap-3">
          {/* Unsaved Changes Indicator */}
          {hasUnsavedChanges && (
            <div className="flex items-center gap-1.5 text-xs font-medium text-yellow-600 dark:text-yellow-500 animate-pulse">
              <span className="material-symbols-outlined" style={{ fontSize: '14px' }}>warning</span>
              <span>Unsaved</span>
            </div>
          )}

          {/* Workflow ID */}
          {currentWorkflowId && (
            <div className="text-xs font-mono text-text-muted dark:text-text-muted px-2 py-1 rounded bg-gray-100 dark:bg-white/5">
              #{currentWorkflowId}
            </div>
          )}
        </div>
      </div>
    </div>
  );
});

export default WorkflowToolbar;
