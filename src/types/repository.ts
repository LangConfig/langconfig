export type RepoSyncStatus =
  | 'pending'
  | 'cloning'
  | 'synced'
  | 'syncing'
  | 'indexing'
  | 'error';

export interface GitRepository {
  id: number;
  project_id: number;
  clone_url: string;
  repo_name: string;
  branch: string;
  sync_status: RepoSyncStatus;
  local_path: string | null;
  last_commit_hash: string | null;
  last_synced_at: string | null;
  last_error: string | null;
  indexed_files_count: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface RepoFile {
  path: string;
  size: number;
  extension: string;
}
