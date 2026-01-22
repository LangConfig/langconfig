/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * useFileTree Hook
 *
 * Fetches and manages the hierarchical file tree for folder navigation.
 */

import { useState, useCallback, useEffect } from 'react';
import type { TreeNode } from '../../components/FolderTree';

interface UseFileTreeOptions {
  workflowId?: number | null;
  autoFetch?: boolean;
}

interface UseFileTreeReturn {
  tree: TreeNode[];
  loading: boolean;
  error: string | null;
  totalFiles: number;
  refresh: () => Promise<void>;
}

export function useFileTree({
  workflowId,
  autoFetch = true,
}: UseFileTreeOptions = {}): UseFileTreeReturn {
  const [tree, setTree] = useState<TreeNode[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [totalFiles, setTotalFiles] = useState(0);

  const fetchTree = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      if (workflowId) {
        params.set('workflow_id', workflowId.toString());
      }

      const url = `/api/workspace/files/tree${params.toString() ? '?' + params.toString() : ''}`;
      const response = await fetch(url);

      if (!response.ok) {
        throw new Error('Failed to fetch file tree');
      }

      const data = await response.json();
      setTree(data.tree || []);
      setTotalFiles(data.total_files || 0);
    } catch (err) {
      console.error('Error fetching file tree:', err);
      setError(err instanceof Error ? err.message : 'Failed to load file tree');
      setTree([]);
      setTotalFiles(0);
    } finally {
      setLoading(false);
    }
  }, [workflowId]);

  // Auto-fetch on mount and when workflowId changes
  useEffect(() => {
    if (autoFetch) {
      fetchTree();
    }
  }, [autoFetch, fetchTree]);

  return {
    tree,
    loading,
    error,
    totalFiles,
    refresh: fetchTree,
  };
}
