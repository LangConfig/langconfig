/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import type { FileContent } from '@/features/workflows/execution/InlineFilePreview';

// Module-level cache for file content - persists across component re-mounts
const fileContentCache = new Map<string, FileContent>();
const MAX_CACHE_SIZE = 30;

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
  /** Custom output path for workflows that have a custom destination configured */
  customOutputPath?: string | null;
  /** Workflow ID - used to fetch all files for a workflow when no task is selected */
  workflowId?: number | null;
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
  customOutputPath,
  workflowId,
}: UseFileHandlingOptions): UseFileHandlingReturn {
  // File state
  const [files, setFiles] = useState<TaskFile[]>([]);
  const [filesLoading, setFilesLoading] = useState(false);
  const [filesError, setFilesError] = useState<string | null>(null);

  // File preview state
  const [selectedPreviewFile, setSelectedPreviewFile] = useState<TaskFile | null>(null);
  const [filePreviewContent, setFilePreviewContent] = useState<FileContent | null>(null);
  const [filePreviewLoading, setFilePreviewLoading] = useState(false);

  // Fetch files for the current task (or from custom output path if configured)
  const fetchFiles = useCallback(async () => {
    // If customOutputPath is set, fetch from that directory instead
    if (customOutputPath) {
      setFilesLoading(true);
      setFilesError(null);

      try {
        const response = await fetch(`/api/workspace/files/from-path?directory=${encodeURIComponent(customOutputPath)}`);
        if (!response.ok) {
          throw new Error('Failed to fetch files from custom path');
        }

        const data = await response.json();
        if (!data.exists) {
          // Directory doesn't exist yet - that's okay, just show empty
          setFiles([]);
        } else {
          setFiles(data.files || []);
        }
      } catch (error) {
        console.error('Error fetching files from custom path:', error);
        setFilesError(error instanceof Error ? error.message : 'Failed to load files');
      } finally {
        setFilesLoading(false);
      }
      return;
    }

    // Fetch by task ID if available
    if (currentTaskId) {
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
      return;
    }

    // Fallback: fetch all files for the workflow if no task is selected
    if (workflowId) {
      setFilesLoading(true);
      setFilesError(null);

      try {
        const response = await fetch(`/api/workspace/workflows/${workflowId}/files`);
        if (!response.ok) {
          throw new Error('Failed to fetch workflow files');
        }

        const data = await response.json();
        setFiles(data.files || []);
      } catch (error) {
        console.error('Error fetching workflow files:', error);
        setFilesError(error instanceof Error ? error.message : 'Failed to load files');
      } finally {
        setFilesLoading(false);
      }
      return;
    }
  }, [currentTaskId, customOutputPath, workflowId]);

  // Download a file from the workspace
  // Uses path-based endpoint to support files in subdirectories
  const handleDownloadFile = useCallback((filenameOrPath: string) => {
    // Try to find the file in the files list to get the full path
    const file = files.find(f => f.filename === filenameOrPath || f.path === filenameOrPath);
    const filePath = file?.path || filenameOrPath;

    // Determine if path is absolute (custom output path) or relative (default outputs/)
    const isAbsolutePath = /^[A-Za-z]:/.test(filePath) || filePath.startsWith('/');

    // Use appropriate endpoint based on path type
    const url = isAbsolutePath
      ? `/api/workspace/files/from-path/download?file_path=${encodeURIComponent(filePath)}`
      : `/api/workspace/by-path/download?file_path=${encodeURIComponent(filePath)}`;

    window.open(url, '_blank');
  }, [files]);

  // Fetch file content for preview (with caching)
  const fetchFileContent = useCallback(async (file: TaskFile) => {
    const cacheKey = file.path;

    // Check cache first - instant return if cached
    if (fileContentCache.has(cacheKey)) {
      setFilePreviewContent(fileContentCache.get(cacheKey)!);
      setFilePreviewLoading(false);
      return;
    }

    setFilePreviewLoading(true);
    try {
      // Determine if path is absolute (custom output path) or relative (default outputs/)
      // Absolute paths start with drive letter (C:) on Windows or / on Unix
      const isAbsolutePath = /^[A-Za-z]:/.test(file.path) || file.path.startsWith('/');

      // Use appropriate endpoint based on path type
      const url = isAbsolutePath
        ? `/api/workspace/files/from-path/content?file_path=${encodeURIComponent(file.path)}`
        : `/api/workspace/by-path/content?file_path=${encodeURIComponent(file.path)}`;

      const response = await fetch(url);
      if (!response.ok) throw new Error('Failed to fetch content');
      const data = await response.json();

      // Add to cache (with size limit)
      if (fileContentCache.size >= MAX_CACHE_SIZE) {
        // Remove oldest entry (first key)
        const firstKey = fileContentCache.keys().next().value;
        if (firstKey) fileContentCache.delete(firstKey);
      }
      fileContentCache.set(cacheKey, data);

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

  // Fetch files when Files tab is active or when task/customOutputPath/workflowId changes
  // Also pre-fetch when task changes so file count is ready
  useEffect(() => {
    if (currentTaskId || customOutputPath || workflowId) {
      fetchFiles();
    }
  }, [currentTaskId, customOutputPath, workflowId, fetchFiles]);

  // Re-fetch when switching to files tab in case files were added
  useEffect(() => {
    if (activeTab === 'files' && (currentTaskId || customOutputPath || workflowId)) {
      fetchFiles();
    }
  }, [activeTab, currentTaskId, customOutputPath, workflowId, fetchFiles]);

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
