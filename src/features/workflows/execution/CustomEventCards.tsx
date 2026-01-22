/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * CustomEventCards - UI Components for LangGraph-style Custom Streaming Events
 *
 * Components for rendering progress bars, status badges, and file operations
 * emitted by tools during workflow execution.
 */

import {
  Activity,
  CheckCircle,
  XCircle,
  Loader2,
  Clock,
  AlertTriangle,
  FileText,
  FilePlus,
  FileEdit,
  FileX,
  FileSearch,
  Eye,
} from 'lucide-react';
import type {
  ProgressEvent,
  StatusEvent,
  FileStatusEvent,
  GenericCustomEvent,
} from '@/hooks/useCustomEvents';

// =============================================================================
// ProgressCard - Progress bar with label and percentage
// =============================================================================

interface ProgressCardProps {
  event: ProgressEvent;
  compact?: boolean;
}

/**
 * Displays a progress bar for long-running operations.
 * Supports persistent updates via event_id (same id updates in-place).
 */
export function ProgressCard({ event, compact = false }: ProgressCardProps) {
  const { data, toolName, agentLabel, timestamp } = event;
  const { label, value, total = 100, message } = data;

  const percentage = Math.min(100, Math.max(0, (value / total) * 100));
  const isComplete = percentage >= 100;

  const getProgressBarColor = () => {
    if (isComplete) return 'bg-green-500';
    if (percentage < 25) return 'bg-blue-500';
    if (percentage < 75) return 'bg-amber-500';
    return 'bg-emerald-500';
  };

  const getBorderColor = () => {
    if (isComplete) return 'border-green-400/50';
    return 'border-blue-400/50';
  };

  const getBackgroundColor = () => {
    if (isComplete) return 'bg-green-50 dark:bg-green-950/30';
    return 'bg-blue-50 dark:bg-blue-950/30';
  };

  if (compact) {
    return (
      <div className={`flex items-center gap-2 px-2 py-1 rounded border ${getBorderColor()} ${getBackgroundColor()}`}>
        {isComplete ? (
          <CheckCircle className="w-3.5 h-3.5 text-green-500 shrink-0" />
        ) : (
          <Loader2 className="w-3.5 h-3.5 animate-spin text-blue-500 shrink-0" />
        )}
        <span className="text-xs text-gray-600 dark:text-gray-400 truncate">
          {label}
        </span>
        <span className="text-xs text-gray-500 font-mono ml-auto shrink-0">
          {Math.round(percentage)}%
        </span>
      </div>
    );
  }

  return (
    <div className={`flex flex-col gap-1.5 p-2.5 rounded-lg border ${getBorderColor()} ${getBackgroundColor()}`}>
      <div className="flex items-center gap-2">
        {isComplete ? (
          <CheckCircle className="w-4 h-4 text-green-500 shrink-0" />
        ) : (
          <Loader2 className="w-4 h-4 animate-spin text-blue-500 shrink-0" />
        )}
        <div className="flex-1 min-w-0">
          <div className="text-xs font-medium text-gray-700 dark:text-gray-300 truncate">
            {label}
          </div>
          {message && (
            <div className="text-xs text-gray-500 dark:text-gray-400 truncate">
              {message}
            </div>
          )}
        </div>
        <span className="text-xs text-gray-500 font-mono shrink-0">
          {Math.round(percentage)}%
        </span>
      </div>

      {/* Progress bar */}
      <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5 overflow-hidden">
        <div
          className={`${getProgressBarColor()} h-1.5 rounded-full transition-all duration-300 ease-out`}
          style={{ width: `${percentage}%` }}
        />
      </div>

      {/* Metadata row */}
      {(toolName || agentLabel) && (
        <div className="flex items-center gap-2 text-[10px] text-gray-400 dark:text-gray-500">
          {agentLabel && <span>{agentLabel}</span>}
          {agentLabel && toolName && <span>·</span>}
          {toolName && <span>{toolName}</span>}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// StatusBadge - Status indicator (pending/running/success/error/warning)
// =============================================================================

interface StatusBadgeProps {
  event: StatusEvent;
  compact?: boolean;
}

/**
 * Displays a status badge for operation status.
 * Supports persistent updates via event_id (same id updates in-place).
 */
export function StatusBadge({ event, compact = false }: StatusBadgeProps) {
  const { data, toolName, agentLabel } = event;
  const { label, status, message } = data;

  const getIcon = () => {
    switch (status) {
      case 'pending':
        return <Clock className="w-3.5 h-3.5 text-gray-500" />;
      case 'running':
        return <Loader2 className="w-3.5 h-3.5 animate-spin text-blue-500" />;
      case 'success':
        return <CheckCircle className="w-3.5 h-3.5 text-green-500" />;
      case 'error':
        return <XCircle className="w-3.5 h-3.5 text-red-500" />;
      case 'warning':
        return <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />;
      default:
        return <Activity className="w-3.5 h-3.5 text-gray-500" />;
    }
  };

  const getBorderColor = () => {
    switch (status) {
      case 'pending':
        return 'border-gray-400/50';
      case 'running':
        return 'border-blue-400/50';
      case 'success':
        return 'border-green-400/50';
      case 'error':
        return 'border-red-400/50';
      case 'warning':
        return 'border-amber-400/50';
      default:
        return 'border-gray-400/50';
    }
  };

  const getBackgroundColor = () => {
    switch (status) {
      case 'pending':
        return 'bg-gray-50 dark:bg-gray-950/30';
      case 'running':
        return 'bg-blue-50 dark:bg-blue-950/30';
      case 'success':
        return 'bg-green-50 dark:bg-green-950/30';
      case 'error':
        return 'bg-red-50 dark:bg-red-950/30';
      case 'warning':
        return 'bg-amber-50 dark:bg-amber-950/30';
      default:
        return 'bg-gray-50 dark:bg-gray-950/30';
    }
  };

  const getStatusTextColor = () => {
    switch (status) {
      case 'pending':
        return 'text-gray-600 dark:text-gray-400';
      case 'running':
        return 'text-blue-600 dark:text-blue-400';
      case 'success':
        return 'text-green-600 dark:text-green-400';
      case 'error':
        return 'text-red-600 dark:text-red-400';
      case 'warning':
        return 'text-amber-600 dark:text-amber-400';
      default:
        return 'text-gray-600 dark:text-gray-400';
    }
  };

  if (compact) {
    return (
      <div className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full border ${getBorderColor()} ${getBackgroundColor()}`}>
        {getIcon()}
        <span className={`text-xs font-medium ${getStatusTextColor()}`}>
          {label}
        </span>
      </div>
    );
  }

  return (
    <div className={`flex flex-col gap-1 p-2 rounded-lg border ${getBorderColor()} ${getBackgroundColor()}`}>
      <div className="flex items-center gap-2">
        {getIcon()}
        <span className={`text-xs font-medium ${getStatusTextColor()}`}>
          {label}
        </span>
        <span className="text-[10px] text-gray-400 dark:text-gray-500 capitalize ml-auto">
          {status}
        </span>
      </div>
      {message && (
        <div className="text-xs text-gray-500 dark:text-gray-400 pl-5">
          {message}
        </div>
      )}
      {(toolName || agentLabel) && (
        <div className="flex items-center gap-2 text-[10px] text-gray-400 dark:text-gray-500 pl-5">
          {agentLabel && <span>{agentLabel}</span>}
          {agentLabel && toolName && <span>·</span>}
          {toolName && <span>{toolName}</span>}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// FileOperationCard - File operation display with icons
// =============================================================================

interface FileOperationCardProps {
  event: FileStatusEvent;
  compact?: boolean;
}

/**
 * Displays file operation status (reading, writing, created, modified, deleted, error).
 */
export function FileOperationCard({ event, compact = false }: FileOperationCardProps) {
  const { data, toolName, agentLabel } = event;
  const { filename, operation, size_bytes, line_count, message } = data;

  const getIcon = () => {
    switch (operation) {
      case 'reading':
        return <FileSearch className="w-3.5 h-3.5 text-blue-500" />;
      case 'writing':
        return <FileEdit className="w-3.5 h-3.5 text-amber-500" />;
      case 'created':
        return <FilePlus className="w-3.5 h-3.5 text-green-500" />;
      case 'modified':
        return <FileEdit className="w-3.5 h-3.5 text-emerald-500" />;
      case 'deleted':
        return <FileX className="w-3.5 h-3.5 text-red-500" />;
      case 'error':
        return <XCircle className="w-3.5 h-3.5 text-red-500" />;
      default:
        return <FileText className="w-3.5 h-3.5 text-gray-500" />;
    }
  };

  const getOperationColor = () => {
    switch (operation) {
      case 'reading':
        return 'text-blue-600 dark:text-blue-400';
      case 'writing':
        return 'text-amber-600 dark:text-amber-400';
      case 'created':
        return 'text-green-600 dark:text-green-400';
      case 'modified':
        return 'text-emerald-600 dark:text-emerald-400';
      case 'deleted':
        return 'text-red-600 dark:text-red-400';
      case 'error':
        return 'text-red-600 dark:text-red-400';
      default:
        return 'text-gray-600 dark:text-gray-400';
    }
  };

  const getBorderColor = () => {
    switch (operation) {
      case 'reading':
        return 'border-blue-400/50';
      case 'writing':
        return 'border-amber-400/50';
      case 'created':
        return 'border-green-400/50';
      case 'modified':
        return 'border-emerald-400/50';
      case 'deleted':
      case 'error':
        return 'border-red-400/50';
      default:
        return 'border-gray-400/50';
    }
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  if (compact) {
    return (
      <div className={`flex items-center gap-2 px-2 py-1 rounded border ${getBorderColor()} bg-gray-50 dark:bg-gray-950/30`}>
        {getIcon()}
        <span className="text-xs text-gray-600 dark:text-gray-400 truncate max-w-[150px]">
          {filename}
        </span>
        <span className={`text-[10px] capitalize ${getOperationColor()}`}>
          {operation}
        </span>
      </div>
    );
  }

  return (
    <div className={`flex flex-col gap-1 p-2 rounded-lg border ${getBorderColor()} bg-gray-50 dark:bg-gray-950/30`}>
      <div className="flex items-center gap-2">
        {getIcon()}
        <span className="text-xs font-medium text-gray-700 dark:text-gray-300 truncate flex-1">
          {filename}
        </span>
        <span className={`text-[10px] capitalize font-medium ${getOperationColor()}`}>
          {operation}
        </span>
      </div>

      {/* Metadata row */}
      <div className="flex items-center gap-3 text-[10px] text-gray-400 dark:text-gray-500 pl-5">
        {size_bytes !== undefined && (
          <span>{formatSize(size_bytes)}</span>
        )}
        {line_count !== undefined && (
          <span>{line_count} lines</span>
        )}
        {agentLabel && <span>{agentLabel}</span>}
        {toolName && <span>{toolName}</span>}
      </div>

      {message && (
        <div className="text-xs text-gray-500 dark:text-gray-400 pl-5">
          {message}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// GenericEventCard - Display for custom event types
// =============================================================================

interface GenericEventCardProps {
  event: GenericCustomEvent;
  compact?: boolean;
}

/**
 * Displays generic custom events with arbitrary data.
 */
export function GenericEventCard({ event, compact = false }: GenericEventCardProps) {
  const { eventType, data, toolName, agentLabel } = event;

  if (compact) {
    return (
      <div
        className="flex items-center gap-2 px-2 py-1 rounded border"
        style={{
          borderColor: 'var(--color-border-dark)',
          backgroundColor: 'var(--color-background-light)',
        }}
      >
        <Eye className="w-3.5 h-3.5" style={{ color: 'var(--color-primary)' }} />
        <span className="text-xs truncate" style={{ color: 'var(--color-text-muted)' }}>
          {eventType}
        </span>
      </div>
    );
  }

  return (
    <div
      className="flex flex-col gap-1 p-2 rounded-lg border"
      style={{
        borderColor: 'var(--color-border-dark)',
        backgroundColor: 'var(--color-background-light)',
      }}
    >
      <div className="flex items-center gap-2">
        <Eye className="w-4 h-4" style={{ color: 'var(--color-primary)' }} />
        <span className="text-xs font-medium" style={{ color: 'var(--color-text-primary)' }}>
          {eventType}
        </span>
      </div>
      <pre
        className="text-[10px] pl-5 overflow-hidden text-ellipsis max-h-16"
        style={{ color: 'var(--color-text-muted)' }}
      >
        {JSON.stringify(data, null, 2)}
      </pre>
      {(toolName || agentLabel) && (
        <div className="flex items-center gap-2 text-[10px] pl-5" style={{ color: 'var(--color-text-muted)' }}>
          {agentLabel && <span>{agentLabel}</span>}
          {agentLabel && toolName && <span>·</span>}
          {toolName && <span>{toolName}</span>}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// CustomEventRenderer - Auto-selects component based on event type
// =============================================================================

interface CustomEventRendererProps {
  event: ProgressEvent | StatusEvent | FileStatusEvent | GenericCustomEvent;
  compact?: boolean;
}

/**
 * Automatically renders the appropriate component based on event type.
 */
export function CustomEventRenderer({ event, compact = false }: CustomEventRendererProps) {
  // Type guard functions
  const isProgressEvent = (e: any): e is ProgressEvent => 'data' in e && 'value' in e.data;
  const isStatusEvent = (e: any): e is StatusEvent => 'data' in e && 'status' in e.data;
  const isFileStatusEvent = (e: any): e is FileStatusEvent => 'data' in e && 'operation' in e.data && 'filename' in e.data;
  const isGenericEvent = (e: any): e is GenericCustomEvent => 'eventType' in e;

  if (isProgressEvent(event)) {
    return <ProgressCard event={event} compact={compact} />;
  }

  if (isStatusEvent(event)) {
    return <StatusBadge event={event} compact={compact} />;
  }

  if (isFileStatusEvent(event)) {
    return <FileOperationCard event={event} compact={compact} />;
  }

  if (isGenericEvent(event)) {
    return <GenericEventCard event={event} compact={compact} />;
  }

  // Fallback - shouldn't happen with proper typing
  return null;
}

// =============================================================================
// CustomEventsSection - Container for displaying multiple custom events
// =============================================================================

interface CustomEventsSectionProps {
  progressEvents: ProgressEvent[];
  statusEvents: StatusEvent[];
  fileStatusEvents: FileStatusEvent[];
  recentEvents?: Array<ProgressEvent | StatusEvent | FileStatusEvent | GenericCustomEvent>;
  compact?: boolean;
  showRecent?: boolean;
  maxRecentItems?: number;
}

/**
 * Container component that displays all custom events organized by type.
 */
export function CustomEventsSection({
  progressEvents,
  statusEvents,
  fileStatusEvents,
  recentEvents = [],
  compact = false,
  showRecent = false,
  maxRecentItems = 5,
}: CustomEventsSectionProps) {
  const hasAnyEvents = progressEvents.length > 0 || statusEvents.length > 0 || fileStatusEvents.length > 0;

  if (!hasAnyEvents && (!showRecent || recentEvents.length === 0)) {
    return null;
  }

  return (
    <div className="flex flex-col gap-2">
      {/* Active progress events */}
      {progressEvents.length > 0 && (
        <div className="flex flex-col gap-1.5">
          {progressEvents.map((event) => (
            <ProgressCard key={event.id} event={event} compact={compact} />
          ))}
        </div>
      )}

      {/* Status badges */}
      {statusEvents.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {statusEvents.map((event) => (
            <StatusBadge key={event.id} event={event} compact={compact} />
          ))}
        </div>
      )}

      {/* File operations */}
      {fileStatusEvents.length > 0 && (
        <div className="flex flex-col gap-1">
          {fileStatusEvents.slice(-5).map((event) => (
            <FileOperationCard key={event.id} event={event} compact={compact} />
          ))}
        </div>
      )}

      {/* Recent events feed */}
      {showRecent && recentEvents.length > 0 && (
        <div className="flex flex-col gap-1 border-t border-gray-200 dark:border-gray-700 pt-2 mt-1">
          <div className="text-[10px] text-gray-400 dark:text-gray-500 uppercase tracking-wide mb-1">
            Recent Activity
          </div>
          {recentEvents.slice(0, maxRecentItems).map((event) => (
            <CustomEventRenderer key={event.id} event={event} compact />
          ))}
        </div>
      )}
    </div>
  );
}

export default CustomEventRenderer;
