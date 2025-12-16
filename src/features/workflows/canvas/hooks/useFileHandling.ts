/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useCallback, useEffect } from 'react';
import type { FileContent } from '@/features/workflows/execution/InlineFilePreview';

/**
 * File entry from workspace
 */
export interface TaskFile {
  filename: string;
  path: string;
  size_bytes: number;
  size_human: string;
  modified_at: string;
  extension: string;
}

interface UseFileHandlingOptions {
  currentTaskId: number | null;
  activeTab: 'studio' | 'results' | 'files' | 'artifacts';
}

interface UseFileHandlingReturn {
  // State
  files: TaskFile[];
  filesLoading: boolean;
  filesError: string | null;
  selectedPreviewFile: TaskFile | null;
  filePreviewContent: FileContent | null;
  filePreviewLoading: boolean;

  // Handlers
  fetchFiles: () => Promise<void>;
  handleDownloadFile: (filename: string) => void;
  handleFileSelect: (file: TaskFile) => void;
  closeFilePreview: () => void;
}

/**
 * Hook for managing workspace file operations
 */
export function useFileHandling({
  currentTaskId,
  activeTab,
}: UseFileHandlingOptions): UseFileHandlingReturn {
  // File state
  const [files, setFiles] = useState<TaskFile[]>([]);
  const [filesLoading, setFilesLoading] = useState(false);
  const [filesError, setFilesError] = useState<string | null>(null);

  // File preview state
  const [selectedPreviewFile, setSelectedPreviewFile] = useState<TaskFile | null>(null);
  const [filePreviewContent, setFilePreviewContent] = useState<FileContent | null>(null);
  const [filePreviewLoading, setFilePreviewLoading] = useState(false);

  // Fetch files for the current task
  const fetchFiles = useCallback(async () => {
    if (!currentTaskId) return;

    setFilesLoading(true);
    setFilesError(null);

    try {
      const response = await fetch(`/api/workspace/tasks/${currentTaskId}/files`);
      if (!response.ok) {
        throw new Error('Failed to fetch files');
      }

      const data = await response.json();
      setFiles(data.files || []);
    } catch (error) {
      console.error('Error fetching files:', error);
      setFilesError(error instanceof Error ? error.message : 'Failed to load files');
    } finally {
      setFilesLoading(false);
    }
  }, [currentTaskId]);

  // Download a file from the workspace
  // Uses path-based endpoint to support files in subdirectories
  const handleDownloadFile = useCallback((filenameOrPath: string) => {
    // Try to find the file in the files list to get the full path
    const file = files.find(f => f.filename === filenameOrPath || f.path === filenameOrPath);
    const filePath = file?.path || filenameOrPath;

    // Use path-based download endpoint
    const url = `/api/workspace/by-path/download?file_path=${encodeURIComponent(filePath)}`;
    window.open(url, '_blank');
  }, [files]);

  // Fetch file content for preview
  const fetchFileContent = useCallback(async (file: TaskFile) => {
    setFilePreviewLoading(true);
    try {
      const url = `/api/workspace/by-path/content?file_path=${encodeURIComponent(file.path)}`;
      const response = await fetch(url);
      if (!response.ok) throw new Error('Failed to fetch content');
      const data = await response.json();
      setFilePreviewContent(data);
    } catch (error) {
      console.error('Error fetching file content:', error);
      setFilePreviewContent(null);
    } finally {
      setFilePreviewLoading(false);
    }
  }, []);

  // Handle file selection for preview
  const handleFileSelect = useCallback((file: TaskFile) => {
    setSelectedPreviewFile(file);
    fetchFileContent(file);
  }, [fetchFileContent]);

  // Close file preview
  const closeFilePreview = useCallback(() => {
    setSelectedPreviewFile(null);
    setFilePreviewContent(null);
  }, []);

  // Fetch files when Files tab is active or when task changes
  // Also pre-fetch when task changes so file count is ready
  useEffect(() => {
    if (currentTaskId) {
      fetchFiles();
    }
  }, [currentTaskId, fetchFiles]);

  // Re-fetch when switching to files tab in case files were added
  useEffect(() => {
    if (activeTab === 'files' && currentTaskId) {
      fetchFiles();
    }
  }, [activeTab, currentTaskId, fetchFiles]);

  return {
    // State
    files,
    filesLoading,
    filesError,
    selectedPreviewFile,
    filePreviewContent,
    filePreviewLoading,

    // Handlers
    fetchFiles,
    handleDownloadFile,
    handleFileSelect,
    closeFilePreview,
  };
}
