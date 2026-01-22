/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { memo, useState, useEffect, useCallback } from 'react';
import { X, Folder, ChevronUp, Loader2 } from 'lucide-react';
import apiClient from '@/lib/api-client';

interface DirectoryEntry {
  name: string;
  path: string;
  is_directory: boolean;
}

interface FolderBrowserDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onSelect: (path: string) => void;
  initialPath?: string;
}

/**
 * Dialog for browsing and selecting directories
 */
const FolderBrowserDialog = memo(function FolderBrowserDialog({
  isOpen,
  onClose,
  onSelect,
  initialPath,
}: FolderBrowserDialogProps) {
  const [currentPath, setCurrentPath] = useState<string>('');
  const [parentPath, setParentPath] = useState<string | null>(null);
  const [entries, setEntries] = useState<DirectoryEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadDirectory = useCallback(async (path?: string) => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.browseDirectories(path);
      const data = response.data;
      setCurrentPath(data.current_path);
      setParentPath(data.parent_path);
      setEntries(data.entries || []);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to load directory');
      setEntries([]);
    } finally {
      setLoading(false);
    }
  }, []);

  // Load initial directory when dialog opens
  useEffect(() => {
    if (isOpen) {
      loadDirectory(initialPath);
    }
  }, [isOpen, initialPath, loadDirectory]);

  const handleNavigate = (path: string) => {
    loadDirectory(path);
  };

  const handleGoUp = () => {
    if (parentPath) {
      loadDirectory(parentPath);
    }
  };

  const handleSelectCurrent = () => {
    onSelect(currentPath);
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[110] flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div
        className="w-full max-w-lg rounded-xl shadow-2xl overflow-hidden"
        style={{
          backgroundColor: 'var(--color-panel-dark)',
          border: '1px solid var(--color-border-dark)'
        }}
      >
        {/* Header */}
        <div className="px-6 py-4 border-b flex justify-between items-center" style={{ borderColor: 'var(--color-border-dark)' }}>
          <h3 className="text-lg font-semibold" style={{ color: 'var(--color-text-primary)' }}>
            Select Folder
          </h3>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-white/10 transition-colors"
            style={{ color: 'var(--color-text-muted)' }}
          >
            <X size={20} />
          </button>
        </div>

        {/* Current Path */}
        <div className="px-6 py-3 border-b" style={{ borderColor: 'var(--color-border-dark)', backgroundColor: 'var(--color-background-dark)' }}>
          <div className="flex items-center gap-2">
            <button
              onClick={handleGoUp}
              disabled={!parentPath || loading}
              className="p-1.5 rounded hover:bg-white/10 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
              style={{ color: 'var(--color-text-muted)' }}
              title="Go to parent folder"
            >
              <ChevronUp size={18} />
            </button>
            <div className="flex-1 text-sm font-mono truncate" style={{ color: 'var(--color-text-primary)' }}>
              {currentPath || 'Loading...'}
            </div>
          </div>
        </div>

        {/* Directory List */}
        <div className="h-72 overflow-y-auto" style={{ backgroundColor: 'var(--color-panel-dark)' }}>
          {loading ? (
            <div className="flex items-center justify-center h-full">
              <Loader2 className="w-6 h-6 animate-spin" style={{ color: 'var(--color-text-muted)' }} />
            </div>
          ) : error ? (
            <div className="flex items-center justify-center h-full">
              <p className="text-sm" style={{ color: '#ef4444' }}>{error}</p>
            </div>
          ) : entries.length === 0 ? (
            <div className="flex items-center justify-center h-full">
              <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>No subdirectories</p>
            </div>
          ) : (
            <div className="p-2">
              {entries.map((entry) => (
                <button
                  key={entry.path}
                  onClick={() => handleNavigate(entry.path)}
                  className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-white/5 transition-colors text-left"
                >
                  <Folder size={18} style={{ color: 'var(--color-primary)' }} />
                  <span className="text-sm truncate" style={{ color: 'var(--color-text-primary)' }}>
                    {entry.name}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t flex justify-between" style={{ borderColor: 'var(--color-border-dark)', backgroundColor: 'var(--color-background-dark)' }}>
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-sm font-medium transition-colors hover:bg-white/10"
            style={{ color: 'var(--color-text-muted)' }}
          >
            Cancel
          </button>
          <button
            onClick={handleSelectCurrent}
            disabled={!currentPath || loading}
            className="px-4 py-2 rounded-lg text-sm font-medium transition-colors bg-primary text-white hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Select This Folder
          </button>
        </div>
      </div>
    </div>
  );
});

export default FolderBrowserDialog;
