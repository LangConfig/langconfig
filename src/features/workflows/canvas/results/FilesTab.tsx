/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * Enhanced Files Tab
 *
 * Comprehensive file viewer with:
 * - Folder tree navigation (grouped by task)
 * - File preview with syntax highlighting
 * - Diff viewer for comparing file versions
 * - File metadata panel with agent context
 * - Version timeline for edit history
 */

import { useState, useCallback, useMemo, useEffect } from 'react';
import { CheckSquare, Square, X, Presentation, GitBranch, ChevronLeft, FolderTree as FolderTreeIcon, Clock, List, PanelLeftClose, PanelLeft, FolderOpen, RefreshCw, Search } from 'lucide-react';
import InlineFilePreview, { FileContent } from '@/features/workflows/execution/InlineFilePreview';
import { getFileIcon } from '../../utils/fileHelpers';
import { useSelection, createFileSelectionItem } from '../context/SelectionContext';
import type { TaskFile } from '../hooks/useFileHandling';

// New components
import FolderTree, { TreeNode } from '../../components/FolderTree';
import DiffViewer from '../../components/DiffViewer';
import FileMetadataPanel, { FileMetadata } from '../../components/FileMetadataPanel';
import VersionTimeline, { FileVersion } from '../../components/VersionTimeline';
import FolderBrowserDialog from '../dialogs/FolderBrowserDialog';

// Hooks
import { useFileTree } from '../hooks/useFileTree';
import { useFileVersions } from '../hooks/useFileVersions';

// Normalize path separators for cross-platform comparison
function normalizePath(path: string): string {
  return path.replace(/\\/g, '/').toLowerCase();
}

interface FilesTabProps {
  files: TaskFile[];
  filesLoading: boolean;
  filesError: string | null;
  selectedPreviewFile: TaskFile | null;
  filePreviewContent: FileContent | null;
  filePreviewLoading: boolean;
  currentTaskId: number | null;
  workflowId?: number | null;
  fetchFiles: () => Promise<void>;
  handleDownloadFile: (filename: string) => void;
  handleFileSelect: (file: TaskFile) => void;
  closeFilePreview: () => void;
  onCreatePresentation?: () => void;
  /** Current folder path being browsed */
  browsePath?: string | null;
  /** Callback when user changes the browse path */
  onBrowsePathChange?: (path: string | null) => void;
}

type ViewMode = 'list' | 'tree' | 'diff' | 'versions';

export default function FilesTab({
  files,
  filesLoading,
  filesError,
  selectedPreviewFile,
  filePreviewContent,
  filePreviewLoading,
  currentTaskId,
  workflowId,
  fetchFiles,
  handleDownloadFile,
  handleFileSelect,
  closeFilePreview,
  onCreatePresentation,
  browsePath,
  onBrowsePathChange,
}: FilesTabProps) {
  const {
    isSelecting,
    setIsSelecting,
    toggleSelection,
    selectAll,
    clearSelection,
    isSelected,
    selectedCount,
    getSelectedByType,
  } = useSelection();

  // View state - default to tree view
  const [viewMode, setViewMode] = useState<ViewMode>('tree');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [metadataCollapsed, setMetadataCollapsed] = useState(true); // Start collapsed to give more preview space
  const [selectedFileId, setSelectedFileId] = useState<number | null>(null);
  const [viewingVersionNumber, setViewingVersionNumber] = useState<number | null>(null);

  // Track if we're in preview mode (full-width file preview)
  const isPreviewMode = selectedPreviewFile !== null;

  // Local selection mode state for files
  const [localIsSelecting, setLocalIsSelecting] = useState(false);
  const effectiveIsSelecting = isSelecting || localIsSelecting;

  // File tree hook
  const { tree, loading: treeLoading, refresh: refreshTree } = useFileTree({
    workflowId: workflowId || undefined,
    autoFetch: viewMode === 'tree',
  });

  // File versions hook
  const {
    versions,
    versionsLoading,
    fetchVersions,
    diffResult,
    diffLoading,
    fetchDiff,
    clearDiff,
    fileMetadata,
    metadataLoading,
    fetchFullMetadata,
    versionContent,
    versionContentLoading,
    fetchVersionContent,
    clearVersionContent,
  } = useFileVersions();

  // Enhanced close handler that resets all file-related state
  const handleCloseFilePreview = useCallback(() => {
    closeFilePreview();
    setSelectedFileId(null);
    setViewingVersionNumber(null);
    clearVersionContent();
  }, [closeFilePreview, clearVersionContent]);

  // Count of selected files
  const selectedFileCount = useMemo(() => {
    return getSelectedByType('file').length;
  }, [getSelectedByType]);

  // Check if a file is selected (for multi-select)
  const isFileSelected = useCallback((file: TaskFile) => {
    const key = `file-${currentTaskId}-${file.path}`;
    return isSelected(key);
  }, [currentTaskId, isSelected]);

  // Toggle file selection
  const handleToggleFileSelection = useCallback((file: TaskFile, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!currentTaskId) return;

    const selectionItem = createFileSelectionItem(
      currentTaskId,
      file.filename,
      file.path,
      file.size_bytes,
      file.extension
    );
    toggleSelection(selectionItem);
  }, [currentTaskId, toggleSelection]);

  // Select all files
  const handleSelectAll = useCallback(() => {
    if (!currentTaskId) return;

    const selectionItems = files.map(file =>
      createFileSelectionItem(
        currentTaskId,
        file.filename,
        file.path,
        file.size_bytes,
        file.extension
      )
    );
    selectAll(selectionItems);
  }, [currentTaskId, files, selectAll]);

  // Cancel selection
  const handleCancelSelection = useCallback(() => {
    clearSelection();
    setLocalIsSelecting(false);
  }, [clearSelection]);

  // Enter selection mode
  const handleEnterSelection = useCallback(() => {
    setIsSelecting(true);
    setLocalIsSelecting(true);
  }, [setIsSelecting]);

  // Handle file selection from tree
  const handleTreeFileSelect = useCallback((node: TreeNode) => {
    if (node.type === 'file' && node.metadata?.id) {
      setSelectedFileId(node.metadata.id);
      fetchFullMetadata(node.metadata.id);
      fetchVersions(node.metadata.id);

      // Also trigger the existing file select if we can map it (normalize paths for Windows compatibility)
      const nodePath = node.path;
      if (nodePath) {
        const file = files.find(f => normalizePath(f.path) === normalizePath(nodePath));
        if (file) {
          handleFileSelect(file);
        }
      }
    }
  }, [files, handleFileSelect, fetchFullMetadata, fetchVersions]);

  // Handle viewing a specific version
  const handleViewVersion = useCallback((version: FileVersion) => {
    if (selectedFileId && version.has_content_snapshot) {
      fetchVersionContent(selectedFileId, version.version_number);
      setViewingVersionNumber(version.version_number);
    }
  }, [selectedFileId, fetchVersionContent]);

  // Handle comparing versions
  const handleCompareVersions = useCallback((v1: FileVersion, v2: FileVersion) => {
    if (selectedFileId) {
      fetchDiff(selectedFileId, v1.version_number, v2.version_number);
      setViewMode('diff');
    }
  }, [selectedFileId, fetchDiff]);

  // Close diff view
  const handleCloseDiff = useCallback(() => {
    clearDiff();
    setViewMode('list');
  }, [clearDiff]);

  // Effect to load metadata when a file is selected via tree (when selectedFileId is available)
  useEffect(() => {
    if (selectedPreviewFile && selectedFileId) {
      // Fetch metadata and versions when we have a file ID from tree selection
      fetchFullMetadata(selectedFileId);
      fetchVersions(selectedFileId);
    }
  }, [selectedPreviewFile, selectedFileId, fetchFullMetadata, fetchVersions]);

  // Local state for path input - MUST be before early returns
  const [pathInput, setPathInput] = useState(browsePath || '');

  // State for folder browser dialog
  const [showFolderBrowser, setShowFolderBrowser] = useState(false);

  // Update local input when browsePath changes from parent
  useEffect(() => {
    setPathInput(browsePath || '');
  }, [browsePath]);

  // Handle path input change
  const handlePathInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setPathInput(e.target.value);
  };

  // Handle path submission (Enter key or button click)
  const handleBrowseToPath = () => {
    if (onBrowsePathChange) {
      onBrowsePathChange(pathInput.trim() || null);
    }
  };

  // Handle Enter key in input
  const handlePathKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleBrowseToPath();
    }
  };

  // Clear path and go back to default
  const handleClearPath = () => {
    setPathInput('');
    if (onBrowsePathChange) {
      onBrowsePathChange(null);
    }
  };

  // Handle folder selection from browser dialog
  const handleFolderSelect = (folderPath: string) => {
    setPathInput(folderPath);
    if (onBrowsePathChange) {
      onBrowsePathChange(folderPath);
    }
    setShowFolderBrowser(false);
  };

  // Inline folder browser bar JSX (not a component to avoid re-mount on state change)
  const folderBrowserBar = (
    <div
      className="flex items-center gap-3 px-4 py-2 border-b flex-shrink-0"
      style={{ borderColor: 'var(--color-border-dark)', backgroundColor: 'var(--color-panel-dark)' }}
    >
      <FolderOpen className="w-4 h-4 flex-shrink-0" style={{ color: 'var(--color-text-muted)' }} />
      <input
        type="text"
        value={pathInput}
        onChange={handlePathInputChange}
        onKeyDown={handlePathKeyDown}
        placeholder="Enter folder path (e.g., C:\Users\Projects\output)"
        className="flex-1 px-3 py-1.5 text-sm rounded border focus:outline-none focus:ring-2 focus:ring-primary/50"
        style={{
          backgroundColor: 'var(--color-background-light)',
          borderColor: 'var(--color-border-dark)',
          color: 'var(--color-text-primary)',
        }}
      />
      <button
        onClick={() => setShowFolderBrowser(true)}
        className="px-3 py-1.5 text-sm rounded border transition-colors hover:bg-white/5 flex items-center gap-1.5"
        style={{ borderColor: 'var(--color-border-dark)', color: 'var(--color-text-muted)' }}
        title="Browse for folder"
      >
        <Search className="w-3.5 h-3.5" />
        Browse
      </button>
      <button
        onClick={handleBrowseToPath}
        className="px-3 py-1.5 text-sm rounded transition-colors hover:opacity-80"
        style={{ backgroundColor: 'var(--color-primary)', color: 'white' }}
        title="Browse to folder"
      >
        Go
      </button>
      {browsePath && (
        <button
          onClick={handleClearPath}
          className="px-3 py-1.5 text-sm rounded border transition-colors hover:bg-white/5"
          style={{ borderColor: 'var(--color-border-dark)', color: 'var(--color-text-muted)' }}
          title="Clear and show default files"
        >
          Reset
        </button>
      )}
      <button
        onClick={fetchFiles}
        className="p-1.5 rounded transition-colors hover:bg-white/10"
        title="Refresh files"
      >
        <RefreshCw className="w-4 h-4" style={{ color: 'var(--color-text-muted)' }} />
      </button>
    </div>
  );

  if (filesLoading) {
    return (
      <div className="flex-1 flex flex-col overflow-hidden">
        {folderBrowserBar}
        <div className="flex items-center justify-center py-16 flex-1">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4" style={{ borderColor: 'var(--color-primary)' }}></div>
            <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>Loading files...</p>
          </div>
        </div>
        {/* Folder Browser Dialog - must be included in all return paths */}
        {showFolderBrowser && (
          <FolderBrowserDialog
            isOpen={showFolderBrowser}
            onClose={() => setShowFolderBrowser(false)}
            onSelect={handleFolderSelect}
            initialPath={pathInput || undefined}
          />
        )}
      </div>
    );
  }

  if (filesError) {
    return (
      <div className="flex-1 flex flex-col overflow-hidden">
        {folderBrowserBar}
        <div className="flex flex-col items-center justify-center py-16 text-center flex-1">
          <span className="material-symbols-outlined text-6xl text-red-300 dark:text-red-900/30 mb-4">
            error
          </span>
          <p className="text-lg font-medium text-red-600 dark:text-red-400">
            Failed to load files
          </p>
          <p className="text-sm mt-2" style={{ color: 'var(--color-text-muted)' }}>
            {filesError}
          </p>
          <button
            onClick={fetchFiles}
            className="mt-4 px-4 py-2 rounded-lg bg-primary/10 hover:bg-primary/20 transition-colors text-sm font-medium"
            style={{ color: 'var(--color-primary)' }}
          >
            Retry
          </button>
        </div>
        {/* Folder Browser Dialog - must be included in all return paths */}
        {showFolderBrowser && (
          <FolderBrowserDialog
            isOpen={showFolderBrowser}
            onClose={() => setShowFolderBrowser(false)}
            onSelect={handleFolderSelect}
            initialPath={pathInput || undefined}
          />
        )}
      </div>
    );
  }

  if (files.length === 0) {
    return (
      <div className="flex-1 flex flex-col overflow-hidden">
        {folderBrowserBar}
        {browsePath && (
          <div
            className="px-4 py-1.5 text-xs border-b flex items-center gap-2 flex-shrink-0"
            style={{ borderColor: 'var(--color-border-dark)', backgroundColor: 'var(--color-primary)', color: 'white', opacity: 0.9 }}
          >
            <FolderOpen className="w-3 h-3" />
            <span className="truncate">{browsePath}</span>
          </div>
        )}
        <div className="flex flex-col items-center justify-center py-16 text-center flex-1">
          <span className="material-symbols-outlined text-6xl mb-4" style={{ color: 'var(--color-text-muted)', opacity: 0.3 }}>
            folder_open
          </span>
          <p className="text-lg font-medium" style={{ color: 'var(--color-text-muted)' }}>
            {browsePath ? 'No files in this folder' : 'No files generated'}
          </p>
          <p className="text-sm mt-2 max-w-md" style={{ color: 'var(--color-text-muted)', opacity: 0.7 }}>
            {browsePath
              ? 'The folder is empty or does not exist. Try entering a different path.'
              : 'Enter a folder path above to browse files, or run a workflow to generate output files.'
            }
          </p>
        </div>
        {/* Folder Browser Dialog - must be included in all return paths */}
        {showFolderBrowser && (
          <FolderBrowserDialog
            isOpen={showFolderBrowser}
            onClose={() => setShowFolderBrowser(false)}
            onSelect={handleFolderSelect}
            initialPath={pathInput || undefined}
          />
        )}
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-hidden flex flex-col">
      {/* Folder Browser Bar */}
      {folderBrowserBar}

      {/* Current Path Indicator */}
      {browsePath && (
        <div
          className="px-4 py-1.5 text-xs border-b flex items-center gap-2 flex-shrink-0"
          style={{ borderColor: 'var(--color-border-dark)', backgroundColor: 'var(--color-primary)', color: 'white', opacity: 0.9 }}
        >
          <FolderOpen className="w-3 h-3" />
          <span className="truncate">{browsePath}</span>
        </div>
      )}

      {/* Selection Toolbar */}
      {files.length > 0 && (
        <div className="flex items-center justify-between px-6 py-3 border-b" style={{ borderColor: 'var(--color-border-dark)' }}>
          <div className="flex items-center gap-4">
            {/* View Mode Tabs */}
            <div className="flex rounded-lg overflow-hidden border" style={{ borderColor: 'var(--color-border-dark)' }}>
              <button
                onClick={() => setViewMode('list')}
                className={`px-3 py-1.5 text-sm transition-colors ${
                  viewMode === 'list' ? 'bg-primary/20' : 'hover:bg-white/5'
                }`}
                style={{ color: viewMode === 'list' ? 'var(--color-primary)' : 'var(--color-text-muted)' }}
              >
                List
              </button>
              <button
                onClick={() => { setViewMode('tree'); refreshTree(); }}
                className={`px-3 py-1.5 text-sm transition-colors border-l ${
                  viewMode === 'tree' ? 'bg-primary/20' : 'hover:bg-white/5'
                }`}
                style={{
                  color: viewMode === 'tree' ? 'var(--color-primary)' : 'var(--color-text-muted)',
                  borderColor: 'var(--color-border-dark)'
                }}
              >
                Tree
              </button>
              {(diffResult || versions.length > 1) && (
                <button
                  onClick={() => setViewMode('diff')}
                  className={`px-3 py-1.5 text-sm transition-colors border-l flex items-center gap-1.5 ${
                    viewMode === 'diff' ? 'bg-primary/20' : 'hover:bg-white/5'
                  }`}
                  style={{
                    color: viewMode === 'diff' ? 'var(--color-primary)' : 'var(--color-text-muted)',
                    borderColor: 'var(--color-border-dark)'
                  }}
                  title={diffResult ? 'View file diff' : 'Compare file versions'}
                >
                  <GitBranch className="w-3.5 h-3.5" />
                  Diff
                  {diffResult && (
                    <span className="w-2 h-2 rounded-full bg-primary" />
                  )}
                </button>
              )}
            </div>

            <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
              {effectiveIsSelecting
                ? `${selectedFileCount} file${selectedFileCount !== 1 ? 's' : ''} selected`
                : `${files.length} file${files.length !== 1 ? 's' : ''} generated`
              }
            </p>
          </div>

          <div className="flex items-center gap-2">
            {effectiveIsSelecting ? (
              <>
                {/* Select All */}
                <button
                  onClick={handleSelectAll}
                  className="px-3 py-1.5 text-sm flex items-center gap-1.5 rounded-lg border transition-colors hover:bg-white/5"
                  style={{ borderColor: 'var(--color-border-dark)', color: 'var(--color-text-muted)' }}
                  title={selectedFileCount === files.length ? "Deselect All" : "Select All"}
                >
                  {selectedFileCount === files.length ? (
                    <CheckSquare className="w-4 h-4" style={{ color: 'var(--color-primary)' }} />
                  ) : (
                    <Square className="w-4 h-4" />
                  )}
                  {selectedFileCount === files.length ? 'Deselect All' : 'Select All'}
                </button>

                {/* Create Presentation */}
                {selectedCount > 0 && onCreatePresentation && (
                  <button
                    onClick={onCreatePresentation}
                    className="px-3 py-1.5 text-sm flex items-center gap-1.5 rounded-lg transition-colors bg-primary hover:bg-primary/90"
                    style={{ color: 'white' }}
                    title="Create presentation from selected items"
                  >
                    <Presentation className="w-4 h-4" />
                    Create Presentation
                  </button>
                )}

                {/* Cancel */}
                <button
                  onClick={handleCancelSelection}
                  className="px-3 py-1.5 text-sm flex items-center gap-1.5 rounded-lg border transition-colors hover:bg-white/5"
                  style={{ borderColor: 'var(--color-border-dark)', color: 'var(--color-text-muted)' }}
                  title="Cancel selection"
                >
                  <X className="w-4 h-4" />
                  Cancel
                </button>
              </>
            ) : (
              <>
                {/* Enter Selection Mode */}
                <button
                  onClick={handleEnterSelection}
                  className="px-3 py-1.5 text-sm flex items-center gap-1.5 rounded-lg border transition-colors hover:bg-white/5"
                  style={{ borderColor: 'var(--color-border-dark)', color: 'var(--color-text-muted)' }}
                  title="Select files for presentation"
                >
                  <CheckSquare className="w-4 h-4" />
                  Select
                </button>
              </>
            )}
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <div className="flex-1 overflow-hidden flex">
        {/* Icon Strip Sidebar - Shows when in preview mode */}
        {isPreviewMode && (
          <div
            className="w-12 flex-shrink-0 border-r flex flex-col items-center py-2 gap-1"
            style={{ borderColor: 'var(--color-border-dark)', backgroundColor: 'var(--color-bg-surface)' }}
          >
            <button
              onClick={handleCloseFilePreview}
              className="w-10 h-10 rounded-lg flex items-center justify-center hover:bg-white/10 transition-colors"
              title="Back to files"
            >
              <ChevronLeft className="w-5 h-5" style={{ color: 'var(--color-primary)' }} />
            </button>
            <div className="w-6 border-t my-1" style={{ borderColor: 'var(--color-border-dark)' }} />
            <button
              onClick={() => {
                if (viewMode === 'tree') {
                  setSidebarCollapsed(!sidebarCollapsed);
                } else {
                  setViewMode('tree');
                  setSidebarCollapsed(false);
                }
              }}
              className={`w-10 h-10 rounded-lg flex items-center justify-center transition-colors ${
                !sidebarCollapsed && viewMode === 'tree' ? 'bg-primary/20' : 'hover:bg-white/10'
              }`}
              title="Folder tree"
            >
              <FolderTreeIcon className="w-5 h-5" style={{ color: !sidebarCollapsed && viewMode === 'tree' ? 'var(--color-primary)' : 'var(--color-text-muted)' }} />
            </button>
            {versions.length > 0 && (
              <button
                onClick={() => {
                  if (viewMode === 'versions') {
                    setSidebarCollapsed(!sidebarCollapsed);
                  } else {
                    setViewMode('versions');
                    setSidebarCollapsed(false);
                  }
                }}
                className={`w-10 h-10 rounded-lg flex items-center justify-center transition-colors ${
                  !sidebarCollapsed && viewMode === 'versions' ? 'bg-primary/20' : 'hover:bg-white/10'
                }`}
                title="Version history"
              >
                <Clock className="w-5 h-5" style={{ color: !sidebarCollapsed && viewMode === 'versions' ? 'var(--color-primary)' : 'var(--color-text-muted)' }} />
              </button>
            )}
            <button
              onClick={() => { setSidebarCollapsed(true); setViewMode('list'); }}
              className={`w-10 h-10 rounded-lg flex items-center justify-center transition-colors ${
                viewMode === 'list' ? 'bg-primary/20' : 'hover:bg-white/10'
              }`}
              title="List view"
            >
              <List className="w-5 h-5" style={{ color: viewMode === 'list' ? 'var(--color-primary)' : 'var(--color-text-muted)' }} />
            </button>
          </div>
        )}

        {/* Sidebar - Folder Tree (expanded when not in preview, or when toggled in preview) */}
        {((!isPreviewMode && viewMode === 'tree') || (isPreviewMode && !sidebarCollapsed && viewMode === 'tree')) && (
          <div
            className={`${isPreviewMode ? 'w-64' : 'w-64 lg:w-80'} flex-shrink-0 border-r overflow-hidden flex flex-col ${isPreviewMode ? 'animate-in slide-in-from-left duration-200' : ''}`}
            style={{ borderColor: 'var(--color-border-dark)' }}
          >
            <FolderTree
              tree={tree}
              loading={treeLoading}
              selectedFileId={selectedFileId}
              onFileSelect={handleTreeFileSelect}
              className="flex-1"
            />
          </div>
        )}

        {/* Version Timeline Sidebar */}
        {((!isPreviewMode && (viewMode === 'versions' || (versions.length > 0 && viewMode === 'tree'))) ||
          (isPreviewMode && !sidebarCollapsed && viewMode === 'versions')) && (
          <div
            className={`w-72 flex-shrink-0 border-r overflow-hidden flex flex-col ${isPreviewMode ? 'animate-in slide-in-from-left duration-200' : ''}`}
            style={{ borderColor: 'var(--color-border-dark)' }}
          >
            <VersionTimeline
              versions={versions}
              filename={fileMetadata?.filename || 'File'}
              loading={versionsLoading}
              onViewVersion={handleViewVersion}
              onCompareVersions={handleCompareVersions}
              className="flex-1"
            />
          </div>
        )}

        {/* Main Content - List View, Tree View, or Diff View */}
        {viewMode === 'diff' ? (
          /* Diff View */
          <div className="flex-1 overflow-hidden flex flex-col">
            {diffResult ? (
              <>
                <div className="flex items-center justify-between px-4 py-2 border-b" style={{ borderColor: 'var(--color-border-dark)' }}>
                  <span className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
                    Comparing v{diffResult.v1} → v{diffResult.v2}
                  </span>
                  <button
                    onClick={handleCloseDiff}
                    className="p-1.5 rounded hover:bg-white/10 transition-colors"
                    title="Close diff"
                  >
                    <X className="w-4 h-4" style={{ color: 'var(--color-text-muted)' }} />
                  </button>
                </div>
                <DiffViewer
                  filename={diffResult.filename}
                  unifiedDiff={diffResult.unifiedDiff}
                  sideBySide={diffResult.sideBySide}
                  stats={diffResult.stats}
                  v1Label={`Version ${diffResult.v1}`}
                  v2Label={`Version ${diffResult.v2}`}
                  className="flex-1"
                />
              </>
            ) : (
              /* No diff selected - show empty state */
              <div className="flex-1 flex flex-col items-center justify-center text-center p-8">
                <GitBranch className="w-12 h-12 mb-4" style={{ color: 'var(--color-text-muted)', opacity: 0.3 }} />
                <p className="text-lg font-medium" style={{ color: 'var(--color-text-muted)' }}>
                  No comparison selected
                </p>
                <p className="text-sm mt-2 max-w-md" style={{ color: 'var(--color-text-muted)', opacity: 0.7 }}>
                  Select a file with multiple versions from the Tree view, then use the Version Timeline to compare different versions.
                </p>
                <button
                  onClick={() => setViewMode('tree')}
                  className="mt-6 px-4 py-2 rounded-lg bg-primary/10 hover:bg-primary/20 transition-colors text-sm font-medium"
                  style={{ color: 'var(--color-primary)' }}
                >
                  Browse Files in Tree View
                </button>
              </div>
            )}
          </div>
        ) : isPreviewMode ? (
          /* Full-width Preview Mode */
          <div className="flex-1 overflow-hidden flex flex-col">
            {/* Version viewing indicator */}
            {viewingVersionNumber && (
              <div
                className="px-4 py-2 flex items-center justify-between border-b flex-shrink-0"
                style={{ backgroundColor: 'rgba(245, 158, 11, 0.1)', borderColor: 'rgba(245, 158, 11, 0.3)' }}
              >
                <span className="text-sm" style={{ color: '#f59e0b' }}>
                  Viewing version {viewingVersionNumber} (historical)
                </span>
                <button
                  onClick={() => { setViewingVersionNumber(null); clearVersionContent(); }}
                  className="text-xs px-2 py-1 rounded hover:bg-white/10 transition-colors"
                  style={{ color: '#f59e0b' }}
                >
                  View Current
                </button>
              </div>
            )}
            {/* Preview Content Area */}
            <div className="flex-1 min-h-0 overflow-hidden flex">
              <div className="flex-1 overflow-hidden">
                <InlineFilePreview
                  file={selectedPreviewFile!}
                  content={viewingVersionNumber && versionContent?.content
                    ? {
                        filename: selectedPreviewFile!.filename,
                        content: versionContent.content,
                        mime_type: filePreviewContent?.mime_type || 'text/plain',
                        is_binary: false,
                        truncated: false,
                        size_bytes: versionContent.content.length
                      }
                    : filePreviewContent
                  }
                  loading={versionContentLoading || filePreviewLoading}
                  onClose={handleCloseFilePreview}
                  onDownload={handleDownloadFile}
                />
              </div>
              {/* Collapsible Metadata Panel on the right */}
              {!metadataCollapsed && (
                <div
                  className="w-80 flex-shrink-0 border-l overflow-y-auto animate-in slide-in-from-right duration-200"
                  style={{ borderColor: 'var(--color-border-dark)' }}
                >
                  <FileMetadataPanel
                    metadata={fileMetadata}
                    loading={metadataLoading}
                    collapsed={metadataCollapsed}
                    onToggleCollapse={() => setMetadataCollapsed(!metadataCollapsed)}
                    onViewVersions={() => { setViewMode('versions'); setSidebarCollapsed(false); }}
                    onCompareVersions={() => {
                      if (versions.length >= 2) {
                        handleCompareVersions(versions[versions.length - 1], versions[0]);
                      }
                    }}
                  />
                </div>
              )}
            </div>
            {/* Metadata toggle bar at the bottom */}
            <div
              className="flex-shrink-0 px-4 py-2 border-t flex items-center justify-between"
              style={{ borderColor: 'var(--color-border-dark)', backgroundColor: 'var(--color-bg-surface)' }}
            >
              <span className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
                {selectedPreviewFile?.size_human} • {selectedPreviewFile?.extension?.replace('.', '').toUpperCase() || 'FILE'}
              </span>
              <button
                onClick={() => setMetadataCollapsed(!metadataCollapsed)}
                className="px-3 py-1 text-xs rounded-md transition-colors hover:bg-white/10"
                style={{ color: 'var(--color-primary)' }}
              >
                {metadataCollapsed ? 'Show Details' : 'Hide Details'}
              </button>
            </div>
          </div>
        ) : (
          /* Browse Mode - File List Only */
          <div className="flex-1 overflow-y-auto p-6">
            <div className="space-y-2">
              {files.map((file, index) => (
                <div
                  key={index}
                  onClick={() => effectiveIsSelecting ? handleToggleFileSelection(file, { stopPropagation: () => {} } as React.MouseEvent) : handleFileSelect(file)}
                  className={`flex items-center justify-between p-4 rounded-lg border cursor-pointer transition-all ${
                    isFileSelected(file)
                      ? 'border-primary/50 bg-primary/5 ring-2 ring-primary/20'
                      : 'hover:bg-gray-50 dark:hover:bg-white/5'
                  }`}
                  style={{ borderColor: isFileSelected(file) ? undefined : 'var(--color-border-dark)' }}
                >
                  {/* Selection Checkbox */}
                  {effectiveIsSelecting && (
                    <div
                      className="mr-3 flex-shrink-0"
                      onClick={(e) => handleToggleFileSelection(file, e)}
                    >
                      <div className={`w-6 h-6 rounded-md flex items-center justify-center transition-colors ${
                        isFileSelected(file)
                          ? 'bg-primary'
                          : 'bg-gray-200 dark:bg-white/10 hover:bg-gray-300 dark:hover:bg-white/20'
                      }`}>
                        {isFileSelected(file) ? (
                          <CheckSquare className="w-4 h-4 text-white" />
                        ) : (
                          <Square className="w-4 h-4" style={{ color: 'var(--color-text-muted)' }} />
                        )}
                      </div>
                    </div>
                  )}

                  <div className="flex items-center gap-3 flex-1 min-w-0">
                    <span className="text-2xl flex-shrink-0">{getFileIcon(file.extension)}</span>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium truncate" style={{ color: 'var(--color-text-primary)' }}>
                        {file.filename}
                      </p>
                      <div className="flex items-center gap-3 text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
                        <span>{file.size_human}</span>
                        <span>•</span>
                        <span>{new Date(file.modified_at).toLocaleDateString()}</span>
                        {file.extension && (
                          <>
                            <span>•</span>
                            <span className="uppercase">{file.extension.replace('.', '')}</span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>

                  {!effectiveIsSelecting && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDownloadFile(file.filename);
                      }}
                      className="ml-4 px-3 py-2 rounded-lg bg-gray-100 dark:bg-white/5 hover:bg-gray-200 dark:hover:bg-white/10 transition-colors flex items-center gap-2 text-sm font-medium"
                      style={{ color: 'var(--color-text-muted)' }}
                      title="Download file"
                    >
                      <span className="material-symbols-outlined text-base">download</span>
                      Download
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Folder Browser Dialog */}
      {showFolderBrowser && (
        <FolderBrowserDialog
          isOpen={showFolderBrowser}
          onClose={() => setShowFolderBrowser(false)}
          onSelect={handleFolderSelect}
          initialPath={pathInput || undefined}
        />
      )}
    </div>
  );
}
