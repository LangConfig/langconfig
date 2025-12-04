/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useEffect } from 'react';
import { Database, HardDrive, RefreshCw, Info } from 'lucide-react';
import apiClient from '../../lib/api-client';

interface StorageMetricsProps {
  projectId: number;
  onRefresh?: () => void;
}

interface StorageStats {
  project_id: number;
  project_name: string;
  indexing_status: string;
  last_indexed_at: string | null;
  actual_storage: {
    exists: boolean;
    total_bytes: number;
    table_bytes: number;
    index_bytes: number;
    total_gb: number;
  };
  configuration: {
    chunk_size: number;
    chunk_overlap: number;
    embedding_dimensions: number;
    indexed_nodes_count: number;
  };
  storage_per_document_gb: number;
  message: string;
}

export default function StorageMetrics({ projectId, onRefresh }: StorageMetricsProps) {
  const [stats, setStats] = useState<StorageStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadStats = async (signal?: AbortSignal) => {
    try {
      setLoading(true);
      setError(null);
      const response = await apiClient.getProjectStorageStats(projectId);
      setStats(response.data);
    } catch (err: any) {
      // Ignore abort errors
      if (err instanceof Error && err.name === 'AbortError') {
        return;
      }
      console.error('Failed to load storage stats:', err);
      if (err.response?.status === 404) {
        setError('Storage metrics endpoint not available. Backend may need restart.');
      } else {
        setError(err.response?.data?.detail || 'Failed to load storage stats');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const abortController = new AbortController();

    if (projectId) {
      loadStats(abortController.signal);
    }

    return () => {
      abortController.abort();
    };
  }, [projectId]);

  const handleRefresh = () => {
    loadStats();
    onRefresh?.();
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'ready': return 'text-green-500';
      case 'indexing': return 'text-blue-500';
      case 'failed': return 'text-red-500';
      default: return 'text-gray-500';
    }
  };

  const getStatusLabel = (status: string) => {
    return status.replace('_', ' ').toUpperCase();
  };

  if (loading) {
    return (
      <div className="bg-white dark:bg-panel-dark rounded-lg border border-gray-200 dark:border-border-dark p-6">
        <div className="flex items-center justify-center">
          <RefreshCw className="w-6 h-6 animate-spin" style={{ color: 'var(--color-primary)' }} />
          <span className="ml-2" style={{ color: 'var(--color-text-muted)' }}>Loading storage stats...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-800 p-6">
        <div className="flex items-center">
          <Info className="w-5 h-5 text-red-500 mr-2" />
          <span className="text-red-700 dark:text-red-400" style={{ color: 'var(--color-text-primary)' }}>{error}</span>
        </div>
      </div>
    );
  }

  if (!stats || !stats.actual_storage.exists) {
    return (
      <div className="bg-white dark:bg-panel-dark rounded-lg border border-gray-200 dark:border-border-dark p-6">
        <div className="text-center">
          <Database className="w-12 h-12 mx-auto mb-3" style={{ color: 'var(--color-text-muted)' }} />
          <p style={{ color: 'var(--color-text-muted)' }}>No indexed data yet</p>
          <p className="text-sm mt-1" style={{ color: 'var(--color-text-muted)' }}>
            Upload and index documents to see storage metrics
          </p>
        </div>
      </div>
    );
  }

  const { actual_storage, configuration } = stats;
  const vectorStorePercent = actual_storage.total_bytes > 0 && actual_storage.index_bytes
    ? ((actual_storage.index_bytes / actual_storage.total_bytes) * 100)
    : 0;
  const dataPercent = actual_storage.total_bytes > 0 && actual_storage.table_bytes
    ? ((actual_storage.table_bytes / actual_storage.total_bytes) * 100)
    : 0;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <HardDrive className="w-5 h-5" style={{ color: 'var(--color-primary)' }} />
          <h3 className="text-lg font-semibold" style={{ color: 'var(--color-text-primary)' }}>Storage Metrics</h3>
        </div>
        <button
          onClick={handleRefresh}
          className="flex items-center gap-2 px-3 py-1.5 text-sm hover:opacity-70 transition-colors"
          style={{ color: 'var(--color-text-muted)' }}
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Main Stats Card */}
      <div className="bg-white dark:bg-panel-dark rounded-lg border border-gray-200 dark:border-border-dark p-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Total Storage */}
          <div>
            <p className="text-sm mb-1" style={{ color: 'var(--color-text-muted)' }}>Total Storage</p>
            <p className="text-2xl font-bold" style={{ color: 'var(--color-text-primary)' }}>
              {actual_storage.total_gb.toFixed(3)} GB
            </p>
            <p className="text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
              {formatBytes(actual_storage.total_bytes)}
            </p>
          </div>

          {/* Indexed Chunks */}
          <div>
            <p className="text-sm mb-1" style={{ color: 'var(--color-text-muted)' }}>Indexed Chunks</p>
            <p className="text-2xl font-bold" style={{ color: 'var(--color-text-primary)' }}>
              {configuration.indexed_nodes_count.toLocaleString()}
            </p>
            <p className="text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
              {stats.storage_per_document_gb.toFixed(3)} GB/doc
            </p>
          </div>

          {/* Status */}
          <div>
            <p className="text-sm mb-1" style={{ color: 'var(--color-text-muted)' }}>Status</p>
            <p className={`text-2xl font-bold ${getStatusColor(stats.indexing_status)}`}>
              {getStatusLabel(stats.indexing_status)}
            </p>
            {stats.last_indexed_at && (
              <p className="text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
                {new Date(stats.last_indexed_at).toLocaleDateString()}
              </p>
            )}
          </div>
        </div>

        {/* Storage Breakdown */}
        <div className="mt-6 pt-6 border-t border-gray-200 dark:border-border-dark">
          <p className="text-sm font-medium mb-3" style={{ color: 'var(--color-text-primary)' }}>Storage Breakdown</p>

          {/* Progress Bar */}
          <div className="w-full h-4 rounded-full overflow-hidden flex" style={{ backgroundColor: 'var(--color-background-dark)' }}>
            <div
              className="bg-blue-500 transition-all duration-300"
              style={{ width: `${dataPercent}%` }}
              title={`Data: ${formatBytes(actual_storage.table_bytes)}`}
            />
            <div
              className="bg-purple-500 transition-all duration-300"
              style={{ width: `${vectorStorePercent}%` }}
              title={`Indexes: ${formatBytes(actual_storage.index_bytes)}`}
            />
          </div>

          {/* Legend */}
          <div className="flex gap-4 mt-3 text-sm">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 bg-blue-500 rounded"></div>
              <span style={{ color: 'var(--color-text-muted)' }}>
                Data: {formatBytes(actual_storage.table_bytes)} ({dataPercent.toFixed(1)}%)
              </span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 bg-purple-500 rounded"></div>
              <span style={{ color: 'var(--color-text-muted)' }}>
                Indexes: {formatBytes(actual_storage.index_bytes)} ({vectorStorePercent.toFixed(1)}%)
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Configuration Card */}
      <div className="rounded-lg border border-gray-200 dark:border-border-dark p-4" style={{ backgroundColor: 'var(--color-background-dark)' }}>
        <p className="text-sm font-medium mb-3" style={{ color: 'var(--color-text-primary)' }}>Configuration</p>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
          <div>
            <p style={{ color: 'var(--color-text-muted)' }}>Chunk Size</p>
            <p className="font-medium" style={{ color: 'var(--color-text-primary)' }}>{configuration.chunk_size} tokens</p>
          </div>
          <div>
            <p style={{ color: 'var(--color-text-muted)' }}>Chunk Overlap</p>
            <p className="font-medium" style={{ color: 'var(--color-text-primary)' }}>{configuration.chunk_overlap} tokens</p>
          </div>
          <div>
            <p style={{ color: 'var(--color-text-muted)' }}>Embedding Dimensions</p>
            <p className="font-medium" style={{ color: 'var(--color-text-primary)' }}>{configuration.embedding_dimensions}D</p>
          </div>
        </div>
      </div>

      {/* Info Note */}
      <div className="flex items-start gap-2 text-xs" style={{ color: 'var(--color-text-muted)' }}>
        <Info className="w-4 h-4 flex-shrink-0 mt-0.5" />
        <p>{stats.message}</p>
      </div>
    </div>
  );
}
