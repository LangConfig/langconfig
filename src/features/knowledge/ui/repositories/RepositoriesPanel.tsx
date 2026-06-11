/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  RefreshCw,
  Loader2,
  AlertCircle,
  Trash2,
  GitBranch,
  CheckCircle,
  Clock,
  FolderX,
} from 'lucide-react';
import apiClient from '@/lib/api-client';
import { useProject } from '../../../../contexts/ProjectContext';
import type { GitRepository, RepoSyncStatus } from '@/types/repository';
import RepoFileTree from './RepoFileTree';
import RepoFilePreview from './RepoFilePreview';

// =============================================================================
// Status Helpers
// =============================================================================

// In-progress states use the blush primary tint, terminal states use
// semantic green/red. Chips are square with 2px borders (Botanical Brutalism).
const STATUS_CONFIG: Record<
  RepoSyncStatus,
  { label: string; color: string; bg: string; icon: typeof Loader2 }
> = {
  pending: {
    label: 'Pending',
    color: 'var(--color-text-primary)',
    bg: 'color-mix(in srgb, var(--color-primary) 25%, white)',
    icon: Clock,
  },
  cloning: {
    label: 'Cloning',
    color: 'var(--color-text-primary)',
    bg: 'color-mix(in srgb, var(--color-primary) 25%, white)',
    icon: Loader2,
  },
  synced: {
    label: 'Synced',
    color: '#2F7D52',
    bg: '#DFF2E4',
    icon: CheckCircle,
  },
  syncing: {
    label: 'Syncing',
    color: 'var(--color-text-primary)',
    bg: 'color-mix(in srgb, var(--color-primary) 25%, white)',
    icon: Loader2,
  },
  indexing: {
    label: 'Indexing',
    color: '#1D5C8A',
    bg: '#DCECF7',
    icon: Loader2,
  },
  error: {
    label: 'Error',
    color: '#B3402F',
    bg: '#FAE3DC',
    icon: AlertCircle,
  },
};

function isInProgress(status: RepoSyncStatus): boolean {
  return status === 'pending' || status === 'cloning' || status === 'syncing' || status === 'indexing';
}

// =============================================================================
// RepositoriesPanel
// =============================================================================

const RepositoriesPanel = () => {
  const { activeProjectId } = useProject();

  const [repos, setRepos] = useState<GitRepository[]>([]);
  const [loading, setLoading] = useState(true);
  const [cloneUrl, setCloneUrl] = useState('');
  const [branch, setBranch] = useState('main');
  const [cloning, setCloning] = useState(false);
  const [syncingId, setSyncingId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [selectedRepoId, setSelectedRepoId] = useState<number | null>(null);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ---------------------------------------------------------------------------
  // Data Fetching
  // ---------------------------------------------------------------------------

  const fetchRepos = useCallback(
    async (signal?: AbortSignal) => {
      if (!activeProjectId) return;
      try {
        const res = await apiClient.listRepositories(activeProjectId, { signal });
        setRepos(res.data);
        setError(null);
      } catch (err: any) {
        if (err?.name === 'AbortError' || err?.name === 'CanceledError') return;
        console.error('Failed to load repositories:', err);
        setError('Failed to load repositories.');
      } finally {
        setLoading(false);
      }
    },
    [activeProjectId],
  );

  useEffect(() => {
    setLoading(true);
    const ac = new AbortController();
    fetchRepos(ac.signal);
    return () => ac.abort();
  }, [fetchRepos]);

  // Poll every 3s while any repo is in a transitional state.
  useEffect(() => {
    const anyInProgress = repos.some((r) => isInProgress(r.sync_status));
    if (anyInProgress && !pollRef.current) {
      pollRef.current = setInterval(() => fetchRepos(), 3000);
    } else if (!anyInProgress && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [repos, fetchRepos]);

  // Auto-select first synced repo
  useEffect(() => {
    if (selectedRepoId !== null) return;
    const firstSynced = repos.find((r) => r.sync_status === 'synced');
    if (firstSynced) setSelectedRepoId(firstSynced.id);
  }, [repos, selectedRepoId]);

  // Clear preview when switching repos
  useEffect(() => {
    setSelectedPath(null);
  }, [selectedRepoId]);

  // ---------------------------------------------------------------------------
  // Actions
  // ---------------------------------------------------------------------------

  const handleClone = async () => {
    if (!cloneUrl.trim() || !activeProjectId) return;
    setCloning(true);
    setError(null);
    try {
      await apiClient.createRepository({
        project_id: activeProjectId,
        clone_url: cloneUrl.trim(),
        branch: branch.trim() || 'main',
      });
      setCloneUrl('');
      setBranch('main');
      await fetchRepos();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to add repository.');
    } finally {
      setCloning(false);
    }
  };

  const handleSync = async (repoId: number) => {
    setSyncingId(repoId);
    try {
      await apiClient.syncRepository(repoId);
      await fetchRepos();
    } catch (err: any) {
      // 409 (already syncing) surfaces as ConflictError from the api-client interceptor.
      if (err?.name === 'ConflictError') {
        setError('Repository is busy. Try again once the current operation finishes.');
      } else {
        const detail = err?.response?.data?.detail;
        setError(typeof detail === 'string' ? detail : 'Sync failed.');
      }
      await fetchRepos();
    } finally {
      setSyncingId(null);
    }
  };

  const handleDelete = async (repoId: number) => {
    const repo = repos.find((r) => r.id === repoId);
    const name = repo?.repo_name ?? 'this repository';
    if (!window.confirm(`Remove "${name}"? This deletes the local clone and all indexed content.`)) {
      return;
    }
    setDeletingId(repoId);
    try {
      await apiClient.deleteRepository(repoId);
      setRepos((prev) => prev.filter((r) => r.id !== repoId));
      if (selectedRepoId === repoId) {
        setSelectedRepoId(null);
        setSelectedPath(null);
      }
    } catch {
      setError('Failed to delete repository.');
    } finally {
      setDeletingId(null);
    }
  };

  // ---------------------------------------------------------------------------
  // No project selected
  // ---------------------------------------------------------------------------

  if (!activeProjectId) {
    return (
      <div className="h-full flex items-center justify-center bg-background-light">
        <div className="text-center border-2 border-border-dark bg-panel-dark px-8 py-6 shadow-[4px_4px_0_var(--color-border-dark)]">
          <FolderX size={40} className="mx-auto mb-3 text-text-muted" />
          <p className="text-sm font-semibold uppercase tracking-wide text-text-primary">
            No project selected
          </p>
          <p className="text-xs mt-1 text-text-muted">
            Select a project to manage its repositories.
          </p>
        </div>
      </div>
    );
  }

  const selectedRepo = repos.find((r) => r.id === selectedRepoId) || null;

  // ---------------------------------------------------------------------------
  // Render (two-pane)
  // ---------------------------------------------------------------------------

  return (
    <div className="h-full flex overflow-hidden bg-background-light">
      {/* Left pane — clone form + repo list + file tree */}
      <aside className="w-96 flex flex-col border-r-2 border-border-dark bg-panel-dark">
        {/* Clone form */}
        <div className="px-4 pt-4 pb-3 border-b-2 border-border-dark">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-xs font-mono font-bold uppercase tracking-wide flex items-center gap-1.5 text-text-primary">
              <GitBranch size={14} />
              Repositories
            </h2>
            <button
              onClick={() => fetchRepos()}
              disabled={loading}
              className="p-1 rounded-[3px] border-2 border-transparent transition-colors hover:border-border-dark hover:bg-background-light/60"
              title="Refresh"
            >
              <RefreshCw size={14} className={`text-text-muted ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>

          <div className="flex gap-1.5">
            <input
              type="text"
              placeholder="https://github.com/org/repo.git"
              value={cloneUrl}
              onChange={(e) => setCloneUrl(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleClone()}
              className="flex-1 min-w-0 px-2.5 py-1.5 rounded-[3px] border-2 border-border-dark bg-background-light text-xs text-text-primary outline-none placeholder:text-text-muted"
            />
            <input
              type="text"
              placeholder="main"
              value={branch}
              onChange={(e) => setBranch(e.target.value)}
              className="w-16 px-2 py-1.5 rounded-[3px] border-2 border-border-dark bg-background-light text-xs text-text-primary outline-none placeholder:text-text-muted"
            />
            <button
              onClick={handleClone}
              disabled={cloning || !cloneUrl.trim()}
              className="px-3 py-1.5 rounded-[3px] border-2 border-border-dark bg-background-light text-[11px] font-mono font-bold uppercase tracking-wide text-text-primary transition-all disabled:opacity-50 flex items-center shadow-[2px_2px_0_var(--color-border-dark)] hover:translate-x-[1px] hover:translate-y-[1px] hover:shadow-[1px_1px_0_var(--color-border-dark)] disabled:hover:translate-x-0 disabled:hover:translate-y-0 disabled:hover:shadow-[2px_2px_0_var(--color-border-dark)]"
            >
              {cloning ? <Loader2 size={12} className="animate-spin" /> : 'Clone'}
            </button>
          </div>

          {error && (
            <div
              className="mt-2 rounded-[3px] border-2 border-border-dark px-2.5 py-1.5 flex items-center gap-2 text-xs"
              style={{ backgroundColor: '#FAE3DC', color: '#B3402F' }}
            >
              <AlertCircle size={12} className="shrink-0" />
              <span className="flex-1">{error}</span>
              <button onClick={() => setError(null)} className="underline font-semibold">
                Dismiss
              </button>
            </div>
          )}
        </div>

        {/* Repo list */}
        <div className="shrink-0 max-h-64 overflow-y-auto">
          {loading && repos.length === 0 && (
            <div className="px-4 py-6 flex items-center gap-2 text-xs text-text-muted">
              <Loader2 size={14} className="animate-spin" />
              Loading repositories...
            </div>
          )}
          {!loading && repos.length === 0 && (
            <div className="px-4 py-6 text-xs text-center text-text-muted">
              No repositories yet. Clone one above.
            </div>
          )}
          {repos.map((repo) => {
            const cfg = STATUS_CONFIG[repo.sync_status];
            const StatusIcon = cfg.icon;
            const isBusy = isInProgress(repo.sync_status);
            const isSelected = repo.id === selectedRepoId;
            return (
              <div
                key={repo.id}
                onClick={() => setSelectedRepoId(repo.id)}
                className={`group px-3 py-2 border-b-2 border-border-dark cursor-pointer transition-colors ${
                  isSelected ? 'bg-background-light' : 'bg-transparent hover:bg-background-light/50'
                }`}
                style={{
                  borderLeft: isSelected
                    ? '4px solid var(--color-border-dark)'
                    : '4px solid transparent',
                }}
              >
                <div className="flex items-center gap-2">
                  <GitBranch size={12} className="shrink-0 text-text-primary" />
                  <span className="font-semibold text-xs truncate flex-1 text-text-primary">
                    {repo.repo_name}
                  </span>
                  <span
                    className="inline-flex items-center gap-1 text-[9px] font-mono font-bold uppercase tracking-wide shrink-0 px-1.5 py-0.5 border-2 border-border-dark"
                    style={{ backgroundColor: cfg.bg, color: cfg.color }}
                  >
                    <StatusIcon size={10} className={isBusy ? 'animate-spin' : ''} />
                    {cfg.label}
                  </span>
                </div>
                <div className="flex items-center gap-2 mt-1 ml-4 text-[10px] text-text-muted">
                  <span className="font-mono">{repo.branch}</span>
                  <span>·</span>
                  <span>{repo.indexed_files_count} files</span>
                  <div className="ml-auto flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleSync(repo.id);
                      }}
                      disabled={isBusy || syncingId === repo.id}
                      className="p-1 rounded-[3px] border border-transparent hover:border-border-dark hover:bg-background-light disabled:opacity-30 text-text-primary"
                      title="Sync"
                    >
                      {syncingId === repo.id ? (
                        <Loader2 size={10} className="animate-spin" />
                      ) : (
                        <RefreshCw size={10} />
                      )}
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(repo.id);
                      }}
                      disabled={isBusy || deletingId === repo.id}
                      className="p-1 rounded-[3px] border border-transparent hover:border-border-dark hover:bg-background-light disabled:opacity-30 text-text-primary"
                      title="Remove"
                    >
                      {deletingId === repo.id ? (
                        <Loader2 size={10} className="animate-spin" />
                      ) : (
                        <Trash2 size={10} />
                      )}
                    </button>
                  </div>
                </div>
                {repo.sync_status === 'error' && repo.last_error && (
                  <p
                    className="mt-1 ml-4 text-[10px] truncate"
                    style={{ color: '#B3402F' }}
                    title={repo.last_error}
                  >
                    {repo.last_error}
                  </p>
                )}
              </div>
            );
          })}
        </div>

        {/* File tree (only when a synced repo is selected) */}
        {selectedRepo && selectedRepo.sync_status === 'synced' && (
          <div className="flex-1 flex flex-col overflow-hidden border-t-2 border-border-dark bg-background-light">
            <div className="px-3 py-1.5 text-[10px] font-mono font-bold uppercase tracking-wide text-text-muted border-b-2 border-border-dark bg-panel-dark">
              Files
            </div>
            <RepoFileTree
              repoId={selectedRepo.id}
              selectedPath={selectedPath}
              onSelectFile={setSelectedPath}
            />
          </div>
        )}
        {selectedRepo && selectedRepo.sync_status !== 'synced' && (
          <div className="flex-1 flex items-center justify-center px-4 text-xs text-center text-text-muted border-t-2 border-border-dark">
            {isInProgress(selectedRepo.sync_status)
              ? 'Waiting for repo to finish syncing...'
              : 'Repo must be synced to browse files.'}
          </div>
        )}
      </aside>

      {/* Right pane — preview */}
      <main className="flex-1 overflow-hidden bg-background-light">
        <RepoFilePreview repoId={selectedRepo?.id ?? null} path={selectedPath} />
      </main>
    </div>
  );
};

export default RepositoriesPanel;
