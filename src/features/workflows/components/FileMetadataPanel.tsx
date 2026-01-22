/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * FileMetadataPanel Component
 *
 * Displays detailed metadata about a selected file including:
 * - Agent that created the file
 * - Workflow/task context
 * - File info (size, type, timestamps)
 * - Version history summary
 * - Tags
 */

import { useState, useCallback } from 'react';
import {
  Bot,
  Calendar,
  FileText,
  GitBranch,
  Hash,
  Info,
  Tag,
  Clock,
  ChevronDown,
  ChevronUp,
  Workflow,
} from 'lucide-react';
import { getFileIcon } from '../utils/fileHelpers';

export interface FileMetadata {
  id: number;
  filename: string;
  file_path: string;
  agent_label: string | null;
  agent_type: string | null;
  node_id: string | null;
  workflow_id: number | null;
  workflow_name: string | null;
  task_id: number | null;
  project_id: number | null;
  execution_id: string | null;
  original_query: string | null;
  description: string | null;
  content_type: string | null;
  tags: string[];
  size_bytes: number | null;
  mime_type: string | null;
  extension: string | null;
  created_at: string | null;
  updated_at: string | null;
  version_count?: number;
  latest_version?: {
    version_number: number;
    operation: string;
    change_summary: string | null;
    created_at: string | null;
  } | null;
}

interface FileMetadataPanelProps {
  metadata: FileMetadata | null;
  loading?: boolean;
  onViewVersions?: () => void;
  onCompareVersions?: () => void;
  className?: string;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
}

function formatBytes(bytes: number | null): string {
  if (bytes === null || bytes === undefined) return 'Unknown';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return 'Unknown';
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function MetadataRow({
  icon: Icon,
  label,
  value,
  valueStyle,
}: {
  icon: React.ElementType;
  label: string;
  value: React.ReactNode;
  valueStyle?: React.CSSProperties;
}) {
  return (
    <div className="flex items-start gap-3 py-2">
      <Icon className="w-4 h-4 mt-0.5 flex-shrink-0" style={{ color: 'var(--color-text-muted)' }} />
      <div className="flex-1 min-w-0">
        <p className="text-xs mb-0.5" style={{ color: 'var(--color-text-muted)' }}>
          {label}
        </p>
        <p
          className="text-sm truncate"
          style={{ color: 'var(--color-text-primary)', ...valueStyle }}
          title={typeof value === 'string' ? value : undefined}
        >
          {value || <span style={{ color: 'var(--color-text-muted)', opacity: 0.5 }}>—</span>}
        </p>
      </div>
    </div>
  );
}

// Expandable text component for long content
function ExpandableText({
  label,
  text,
  maxLines = 3,
}: {
  label: string;
  text: string;
  maxLines?: number;
}) {
  const [isExpanded, setIsExpanded] = useState(false);
  const isLong = text.split('\n').length > maxLines || text.length > 200;

  return (
    <div className="pt-2 mt-2 border-t" style={{ borderColor: 'var(--color-border-dark)' }}>
      <div className="flex items-center justify-between mb-1">
        <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
          {label}
        </p>
        {isLong && (
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="text-xs hover:underline"
            style={{ color: 'var(--color-primary)' }}
          >
            {isExpanded ? 'Show less' : 'Show more'}
          </button>
        )}
      </div>
      <p
        className={`text-sm whitespace-pre-wrap break-words ${!isExpanded && isLong ? 'line-clamp-3' : ''}`}
        style={{ color: 'var(--color-text-primary)' }}
      >
        {text}
      </p>
    </div>
  );
}

export default function FileMetadataPanel({
  metadata,
  loading,
  onViewVersions,
  onCompareVersions,
  className = '',
  collapsed = false,
  onToggleCollapse,
}: FileMetadataPanelProps) {
  if (loading) {
    return (
      <div className={`p-4 ${className}`}>
        <div className="animate-pulse space-y-3">
          <div className="h-4 bg-white/10 rounded w-2/3"></div>
          <div className="h-4 bg-white/10 rounded w-1/2"></div>
          <div className="h-4 bg-white/10 rounded w-3/4"></div>
        </div>
      </div>
    );
  }

  if (!metadata) {
    return (
      <div className={`p-4 ${className}`}>
        <div className="text-center py-8">
          <Info className="w-8 h-8 mx-auto mb-2" style={{ color: 'var(--color-text-muted)', opacity: 0.5 }} />
          <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
            Select a file to view details
          </p>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`border-t ${className}`}
      style={{ borderColor: 'var(--color-border-dark)', backgroundColor: 'var(--color-bg-surface)' }}
    >
      {/* Collapsible Header */}
      {onToggleCollapse && (
        <button
          onClick={onToggleCollapse}
          className="w-full flex items-center justify-between px-4 py-2 hover:bg-white/5 transition-colors"
        >
          <span className="text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>
            File Details
          </span>
          {collapsed ? (
            <ChevronUp className="w-4 h-4" style={{ color: 'var(--color-text-muted)' }} />
          ) : (
            <ChevronDown className="w-4 h-4" style={{ color: 'var(--color-text-muted)' }} />
          )}
        </button>
      )}

      {/* Content */}
      {!collapsed && (
        <div className="px-4 pb-4 space-y-1">
          {/* File Header */}
          <div className="flex items-center gap-3 py-3 border-b mb-2" style={{ borderColor: 'var(--color-border-dark)' }}>
            <span className="text-2xl">{getFileIcon(metadata.extension || '')}</span>
            <div className="flex-1 min-w-0">
              <p
                className="font-medium truncate"
                style={{ color: 'var(--color-text-primary)' }}
                title={metadata.filename}
              >
                {metadata.filename}
              </p>
              <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                {formatBytes(metadata.size_bytes)} • {metadata.extension?.replace('.', '').toUpperCase() || 'FILE'}
              </p>
            </div>
          </div>

          {/* Agent Info */}
          {metadata.agent_label && (
            <MetadataRow
              icon={Bot}
              label="Created by"
              value={
                <span className="flex items-center gap-1.5">
                  {metadata.agent_label}
                  {metadata.agent_type && (
                    <span
                      className="text-xs px-1.5 py-0.5 rounded"
                      style={{ backgroundColor: 'var(--color-primary)', color: 'white', opacity: 0.9 }}
                    >
                      {metadata.agent_type}
                    </span>
                  )}
                </span>
              }
            />
          )}

          {/* Workflow Context */}
          {metadata.workflow_name && (
            <MetadataRow icon={Workflow} label="Workflow" value={metadata.workflow_name} />
          )}

          {/* Node ID */}
          {metadata.node_id && (
            <MetadataRow icon={Hash} label="Node ID" value={metadata.node_id} />
          )}

          {/* Timestamps */}
          <MetadataRow icon={Calendar} label="Created" value={formatDate(metadata.created_at)} />
          {metadata.updated_at && metadata.updated_at !== metadata.created_at && (
            <MetadataRow icon={Clock} label="Modified" value={formatDate(metadata.updated_at)} />
          )}

          {/* Version Info */}
          {metadata.version_count !== undefined && metadata.version_count > 0 && (
            <div className="pt-2 mt-2 border-t" style={{ borderColor: 'var(--color-border-dark)' }}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <GitBranch className="w-4 h-4" style={{ color: 'var(--color-text-muted)' }} />
                  <span className="text-sm" style={{ color: 'var(--color-text-primary)' }}>
                    {metadata.version_count} version{metadata.version_count > 1 ? 's' : ''}
                  </span>
                </div>
                <div className="flex gap-2">
                  {onViewVersions && (
                    <button
                      onClick={onViewVersions}
                      className="text-xs px-2 py-1 rounded hover:bg-white/10 transition-colors"
                      style={{ color: 'var(--color-primary)' }}
                    >
                      View History
                    </button>
                  )}
                  {onCompareVersions && metadata.version_count > 1 && (
                    <button
                      onClick={onCompareVersions}
                      className="text-xs px-2 py-1 rounded hover:bg-white/10 transition-colors"
                      style={{ color: 'var(--color-primary)' }}
                    >
                      Compare
                    </button>
                  )}
                </div>
              </div>
              {metadata.latest_version && (
                <p className="text-xs mt-1 ml-6" style={{ color: 'var(--color-text-muted)' }}>
                  Latest: {metadata.latest_version.change_summary || metadata.latest_version.operation}
                </p>
              )}
            </div>
          )}

          {/* Tags */}
          {metadata.tags && metadata.tags.length > 0 && (
            <div className="pt-2 mt-2 border-t" style={{ borderColor: 'var(--color-border-dark)' }}>
              <div className="flex items-start gap-2">
                <Tag className="w-4 h-4 mt-1" style={{ color: 'var(--color-text-muted)' }} />
                <div className="flex flex-wrap gap-1.5">
                  {metadata.tags.map((tag, i) => (
                    <span
                      key={i}
                      className="text-xs px-2 py-0.5 rounded-full"
                      style={{ backgroundColor: 'var(--color-border-dark)', color: 'var(--color-text-muted)' }}
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Description */}
          {metadata.description && (
            <ExpandableText label="Description" text={metadata.description} maxLines={3} />
          )}

          {/* Original Query */}
          {metadata.original_query && typeof metadata.original_query === 'string' && (
            <ExpandableText label="Original Prompt" text={metadata.original_query} maxLines={3} />
          )}
        </div>
      )}
    </div>
  );
}
