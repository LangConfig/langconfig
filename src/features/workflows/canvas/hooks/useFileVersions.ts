/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * useFileVersions Hook
 *
 * Manages file version history, fetching versions, and comparing diffs.
 */

import { useState, useCallback } from 'react';
import type { FileVersion } from '../../components/VersionTimeline';
import type { DiffStats, SideBySideLine } from '../../components/DiffViewer';
import type { FileMetadata } from '../../components/FileMetadataPanel';

interface DiffResult {
  fileId: number;
  filename: string;
  v1: number;
  v2: number;
  unifiedDiff: string;
  sideBySide: SideBySideLine[];
  stats: DiffStats;
}

interface VersionContent {
  fileId: number;
  versionNumber: number;
  hasContent: boolean;
  content: string | null;
  operation?: string;
  agentLabel?: string;
}

interface UseFileVersionsReturn {
  // State
  versions: FileVersion[];
  versionsLoading: boolean;
  versionsError: string | null;
  diffResult: DiffResult | null;
  diffLoading: boolean;
  versionContent: VersionContent | null;
  versionContentLoading: boolean;
  fileMetadata: FileMetadata | null;
  metadataLoading: boolean;

  // Actions
  fetchVersions: (fileId: number) => Promise<void>;
  fetchDiff: (fileId: number, v1: number, v2: number) => Promise<void>;
  fetchVersionContent: (fileId: number, versionNumber: number) => Promise<void>;
  fetchFullMetadata: (fileId: number) => Promise<void>;
  clearDiff: () => void;
  clearVersionContent: () => void;
}

export function useFileVersions(): UseFileVersionsReturn {
  // Versions state
  const [versions, setVersions] = useState<FileVersion[]>([]);
  const [versionsLoading, setVersionsLoading] = useState(false);
  const [versionsError, setVersionsError] = useState<string | null>(null);

  // Diff state
  const [diffResult, setDiffResult] = useState<DiffResult | null>(null);
  const [diffLoading, setDiffLoading] = useState(false);

  // Version content state
  const [versionContent, setVersionContent] = useState<VersionContent | null>(null);
  const [versionContentLoading, setVersionContentLoading] = useState(false);

  // Metadata state
  const [fileMetadata, setFileMetadata] = useState<FileMetadata | null>(null);
  const [metadataLoading, setMetadataLoading] = useState(false);

  // Fetch versions for a file
  const fetchVersions = useCallback(async (fileId: number) => {
    setVersionsLoading(true);
    setVersionsError(null);

    try {
      const response = await fetch(`/api/workspace/files/${fileId}/versions`);
      if (!response.ok) {
        throw new Error('Failed to fetch versions');
      }

      const data = await response.json();
      setVersions(data.versions || []);
    } catch (err) {
      console.error('Error fetching versions:', err);
      setVersionsError(err instanceof Error ? err.message : 'Failed to load versions');
      setVersions([]);
    } finally {
      setVersionsLoading(false);
    }
  }, []);

  // Fetch diff between two versions
  const fetchDiff = useCallback(async (fileId: number, v1: number, v2: number) => {
    setDiffLoading(true);

    try {
      const response = await fetch(
        `/api/workspace/files/${fileId}/diff?v1=${v1}&v2=${v2}`
      );
      if (!response.ok) {
        throw new Error('Failed to fetch diff');
      }

      const data = await response.json();
      setDiffResult({
        fileId: data.file_id,
        filename: data.filename,
        v1: data.v1,
        v2: data.v2,
        unifiedDiff: data.unified_diff,
        sideBySide: data.side_by_side,
        stats: data.stats,
      });
    } catch (err) {
      console.error('Error fetching diff:', err);
      setDiffResult(null);
    } finally {
      setDiffLoading(false);
    }
  }, []);

  // Fetch content of a specific version
  const fetchVersionContent = useCallback(async (fileId: number, versionNumber: number) => {
    setVersionContentLoading(true);

    try {
      const response = await fetch(
        `/api/workspace/files/${fileId}/version/${versionNumber}/content`
      );
      if (!response.ok) {
        throw new Error('Failed to fetch version content');
      }

      const data = await response.json();
      setVersionContent({
        fileId: data.file_id,
        versionNumber: data.version_number,
        hasContent: data.has_content,
        content: data.content,
        operation: data.operation,
        agentLabel: data.agent_label,
      });
    } catch (err) {
      console.error('Error fetching version content:', err);
      setVersionContent(null);
    } finally {
      setVersionContentLoading(false);
    }
  }, []);

  // Fetch full metadata with version info
  const fetchFullMetadata = useCallback(async (fileId: number) => {
    setMetadataLoading(true);

    try {
      const response = await fetch(`/api/workspace/files/${fileId}/metadata/full`);
      if (!response.ok) {
        throw new Error('Failed to fetch metadata');
      }

      const data = await response.json();
      setFileMetadata(data);
    } catch (err) {
      console.error('Error fetching metadata:', err);
      setFileMetadata(null);
    } finally {
      setMetadataLoading(false);
    }
  }, []);

  // Clear diff result
  const clearDiff = useCallback(() => {
    setDiffResult(null);
  }, []);

  // Clear version content
  const clearVersionContent = useCallback(() => {
    setVersionContent(null);
  }, []);

  return {
    // State
    versions,
    versionsLoading,
    versionsError,
    diffResult,
    diffLoading,
    versionContent,
    versionContentLoading,
    fileMetadata,
    metadataLoading,

    // Actions
    fetchVersions,
    fetchDiff,
    fetchVersionContent,
    fetchFullMetadata,
    clearDiff,
    clearVersionContent,
  };
}
