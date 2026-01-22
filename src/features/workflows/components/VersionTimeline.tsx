/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * VersionTimeline Component
 *
 * Shows version history for a file in a timeline format.
 * Allows viewing individual versions and comparing between versions.
 */

import { useState, useCallback } from 'react';
import {
  GitCommit,
  Plus,
  Minus,
  Edit3,
  FilePlus,
  Replace,
  Bot,
  Clock,
  Eye,
  GitCompare,
  Check,
} from 'lucide-react';

export interface FileVersion {
  id: number;
  version_number: number;
  operation: 'create' | 'edit' | 'replace';
  change_summary: string | null;
  agent_label: string | null;
  node_id: string | null;
  lines_added: number | null;
  lines_removed: number | null;
  created_at: string | null;
  has_content_snapshot: boolean;
}

interface VersionTimelineProps {
  versions: FileVersion[];
  filename: string;
  loading?: boolean;
  onViewVersion: (version: FileVersion) => void;
  onCompareVersions: (v1: FileVersion, v2: FileVersion) => void;
  className?: string;
}

function getOperationIcon(operation: string) {
  switch (operation) {
    case 'create':
      return <FilePlus className="w-4 h-4" style={{ color: '#22c55e' }} />;
    case 'edit':
      return <Edit3 className="w-4 h-4" style={{ color: '#f59e0b' }} />;
    case 'replace':
      return <Replace className="w-4 h-4" style={{ color: '#3b82f6' }} />;
    default:
      return <GitCommit className="w-4 h-4" style={{ color: 'var(--color-text-muted)' }} />;
  }
}

function getOperationLabel(operation: string) {
  switch (operation) {
    case 'create':
      return 'Created';
    case 'edit':
      return 'Edited';
    case 'replace':
      return 'Replaced';
    default:
      return 'Modified';
  }
}

function formatRelativeTime(dateStr: string | null): string {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;

  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

export default function VersionTimeline({
  versions,
  filename,
  loading,
  onViewVersion,
  onCompareVersions,
  className = '',
}: VersionTimelineProps) {
  const [compareMode, setCompareMode] = useState(false);
  const [selectedVersions, setSelectedVersions] = useState<FileVersion[]>([]);

  const handleVersionClick = useCallback((version: FileVersion) => {
    if (compareMode) {
      setSelectedVersions((prev) => {
        const isSelected = prev.some((v) => v.id === version.id);
        if (isSelected) {
          return prev.filter((v) => v.id !== version.id);
        }
        if (prev.length >= 2) {
          return [prev[1], version];
        }
        return [...prev, version];
      });
    } else {
      onViewVersion(version);
    }
  }, [compareMode, onViewVersion]);

  const handleCompare = useCallback(() => {
    if (selectedVersions.length === 2) {
      // Sort by version number to ensure v1 < v2
      const sorted = [...selectedVersions].sort((a, b) => a.version_number - b.version_number);
      onCompareVersions(sorted[0], sorted[1]);
    }
  }, [selectedVersions, onCompareVersions]);

  const isSelected = (version: FileVersion) =>
    selectedVersions.some((v) => v.id === version.id);

  if (loading) {
    return (
      <div className={`p-4 ${className}`}>
        <div className="animate-pulse space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="flex gap-3">
              <div className="w-8 h-8 bg-white/10 rounded-full"></div>
              <div className="flex-1 space-y-2">
                <div className="h-4 bg-white/10 rounded w-1/2"></div>
                <div className="h-3 bg-white/10 rounded w-3/4"></div>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (versions.length === 0) {
    return (
      <div className={`p-4 text-center ${className}`}>
        <GitCommit className="w-8 h-8 mx-auto mb-2" style={{ color: 'var(--color-text-muted)', opacity: 0.5 }} />
        <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
          No version history available
        </p>
      </div>
    );
  }

  return (
    <div className={`flex flex-col ${className}`}>
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-3 border-b"
        style={{ borderColor: 'var(--color-border-dark)' }}
      >
        <div>
          <h3 className="text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>
            Version History
          </h3>
          <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
            {versions.length} version{versions.length > 1 ? 's' : ''} • {filename}
          </p>
        </div>

        {/* Compare Mode Toggle */}
        {versions.length > 1 && (
          <button
            onClick={() => {
              setCompareMode(!compareMode);
              setSelectedVersions([]);
            }}
            className={`px-3 py-1.5 text-sm rounded-lg flex items-center gap-1.5 transition-colors ${
              compareMode ? 'bg-primary/20 ring-1 ring-primary/30' : 'hover:bg-white/5'
            }`}
            style={{ color: compareMode ? 'var(--color-primary)' : 'var(--color-text-muted)' }}
          >
            <GitCompare className="w-4 h-4" />
            Compare
          </button>
        )}
      </div>

      {/* Compare Action Bar */}
      {compareMode && (
        <div
          className="flex items-center justify-between px-4 py-2 border-b"
          style={{ borderColor: 'var(--color-border-dark)', backgroundColor: 'var(--color-primary)', opacity: 0.1 }}
        >
          <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
            Select two versions to compare ({selectedVersions.length}/2 selected)
          </span>
          <button
            onClick={handleCompare}
            disabled={selectedVersions.length !== 2}
            className="px-3 py-1 text-xs rounded-lg transition-colors disabled:opacity-50"
            style={{
              backgroundColor: selectedVersions.length === 2 ? 'var(--color-primary)' : 'transparent',
              color: selectedVersions.length === 2 ? 'white' : 'var(--color-text-muted)',
            }}
          >
            View Diff
          </button>
        </div>
      )}

      {/* Timeline */}
      <div className="flex-1 overflow-y-auto">
        <div className="relative py-4">
          {/* Timeline line */}
          <div
            className="absolute left-7 top-0 bottom-0 w-0.5"
            style={{ backgroundColor: 'var(--color-border-dark)' }}
          />

          {/* Version Items */}
          {versions.map((version, index) => (
            <div
              key={version.id}
              onClick={() => handleVersionClick(version)}
              className={`relative flex items-start gap-3 px-4 py-3 cursor-pointer transition-colors ${
                compareMode && isSelected(version)
                  ? 'bg-primary/10'
                  : 'hover:bg-white/5'
              }`}
            >
              {/* Timeline dot */}
              <div
                className={`relative z-10 w-6 h-6 rounded-full flex items-center justify-center ${
                  compareMode && isSelected(version)
                    ? 'bg-primary'
                    : 'bg-gray-800 dark:bg-gray-700'
                }`}
                style={{
                  border: `2px solid ${
                    compareMode && isSelected(version)
                      ? 'var(--color-primary)'
                      : 'var(--color-border-dark)'
                  }`,
                }}
              >
                {compareMode && isSelected(version) ? (
                  <Check className="w-3 h-3 text-white" />
                ) : (
                  getOperationIcon(version.operation)
                )}
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>
                    v{version.version_number}
                  </span>
                  <span
                    className="text-xs px-1.5 py-0.5 rounded"
                    style={{
                      backgroundColor:
                        version.operation === 'create'
                          ? 'rgba(34, 197, 94, 0.2)'
                          : version.operation === 'edit'
                          ? 'rgba(245, 158, 11, 0.2)'
                          : 'rgba(59, 130, 246, 0.2)',
                      color:
                        version.operation === 'create'
                          ? '#22c55e'
                          : version.operation === 'edit'
                          ? '#f59e0b'
                          : '#3b82f6',
                    }}
                  >
                    {getOperationLabel(version.operation)}
                  </span>
                  {version.created_at && (
                    <span className="text-xs flex items-center gap-1" style={{ color: 'var(--color-text-muted)' }}>
                      <Clock className="w-3 h-3" />
                      {formatRelativeTime(version.created_at)}
                    </span>
                  )}
                </div>

                {/* Change summary */}
                {version.change_summary && (
                  <p className="text-xs mt-1 truncate" style={{ color: 'var(--color-text-muted)' }}>
                    {version.change_summary}
                  </p>
                )}

                {/* Line changes */}
                {(version.lines_added !== null || version.lines_removed !== null) && (
                  <div className="flex items-center gap-3 mt-1">
                    {version.lines_added !== null && version.lines_added > 0 && (
                      <span className="text-xs flex items-center gap-0.5" style={{ color: '#22c55e' }}>
                        <Plus className="w-3 h-3" />
                        {version.lines_added}
                      </span>
                    )}
                    {version.lines_removed !== null && version.lines_removed > 0 && (
                      <span className="text-xs flex items-center gap-0.5" style={{ color: '#ef4444' }}>
                        <Minus className="w-3 h-3" />
                        {version.lines_removed}
                      </span>
                    )}
                  </div>
                )}

                {/* Agent info */}
                {version.agent_label && (
                  <div className="flex items-center gap-1.5 mt-1">
                    <Bot className="w-3 h-3" style={{ color: 'var(--color-text-muted)' }} />
                    <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                      {version.agent_label}
                    </span>
                  </div>
                )}
              </div>

              {/* View button (when not in compare mode) */}
              {!compareMode && version.has_content_snapshot && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onViewVersion(version);
                  }}
                  className="p-1.5 rounded hover:bg-white/10 transition-colors"
                  title="View this version"
                >
                  <Eye className="w-4 h-4" style={{ color: 'var(--color-text-muted)' }} />
                </button>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
