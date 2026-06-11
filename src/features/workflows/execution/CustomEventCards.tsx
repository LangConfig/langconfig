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
import { Surface } from '@/components/ui/Surface';
import { Badge } from '@/components/ui/Badge';
import type { BadgeTone } from '@/components/ui/Badge';
import { ProgressBar } from '@/components/ui/ProgressBar';

// =============================================================================
// Tone maps - status/operation -> theme tone (replaces per-component switches)
// =============================================================================

const STATUS_TONE: Record<string, BadgeTone> = {
  pending: 'neutral',
  running: 'info',
  success: 'success',
  error: 'error',
  warning: 'warning',
};

const OPERATION_TONE: Record<string, BadgeTone> = {
  reading: 'info',
  writing: 'warning',
  created: 'success',
  modified: 'success',
  deleted: 'error',
  error: 'error',
};

const TONE_COLOR: Record<BadgeTone, string> = {
  neutral: 'var(--color-text-muted)',
  info: 'var(--color-info)',
  success: 'var(--color-success)',
  warning: 'var(--color-warning)',
  error: 'var(--color-error)',
  accent: 'var(--color-primary)',
};

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
  const { data, toolName, agentLabel } = event;
  const { label, value, total = 100, message } = data;

  const percentage = Math.min(100, Math.max(0, (value / total) * 100));
  const isComplete = percentage >= 100;
  const tone = isComplete ? ('success' as const) : ('info' as const);

  const icon = isComplete ? (
    <CheckCircle
      className={`${compact ? 'w-3.5 h-3.5' : 'w-4 h-4'} shrink-0`}
      style={{ color: TONE_COLOR.success }}
    />
  ) : (
    <Loader2
      className={`${compact ? 'w-3.5 h-3.5' : 'w-4 h-4'} animate-spin shrink-0`}
      style={{ color: TONE_COLOR.info }}
    />
  );

  if (compact) {
    return (
      <Surface variant="inset" tone={tone} className="flex items-center gap-2 px-2 py-1">
        {icon}
        <span className="text-xs truncate" style={{ color: 'var(--color-text-muted)' }}>
          {label}
        </span>
        <span
          className="text-xs font-mono ml-auto shrink-0"
          style={{ color: 'var(--color-text-muted)' }}
        >
          {Math.round(percentage)}%
        </span>
      </Surface>
    );
  }

  return (
    <Surface variant="card-sm" tone={tone} className="flex flex-col gap-1.5 p-2.5">
      <div className="flex items-center gap-2">
        {icon}
        <div className="flex-1 min-w-0">
          <div
            className="text-xs font-medium truncate"
            style={{ color: 'var(--color-text-primary)' }}
          >
            {label}
          </div>
          {message && (
            <div className="text-xs truncate" style={{ color: 'var(--color-text-muted)' }}>
              {message}
            </div>
          )}
        </div>
        <span className="text-xs font-mono shrink-0" style={{ color: 'var(--color-text-muted)' }}>
          {Math.round(percentage)}%
        </span>
      </div>

      {/* Progress bar */}
      <ProgressBar value={percentage} tone={tone} animated={!isComplete} height={6} />

      {/* Metadata row */}
      {(toolName || agentLabel) && (
        <div
          className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.1em]"
          style={{ color: 'var(--color-text-muted)' }}
        >
          {agentLabel && <span>{agentLabel}</span>}
          {agentLabel && toolName && <span>·</span>}
          {toolName && <span>{toolName}</span>}
        </div>
      )}
    </Surface>
  );
}

// =============================================================================
// StatusBadge - Status indicator (pending/running/success/error/warning)
// =============================================================================

interface StatusBadgeProps {
  event: StatusEvent;
  compact?: boolean;
}

function statusIcon(status: string, tone: BadgeTone) {
  const style = { color: TONE_COLOR[tone] };
  switch (status) {
    case 'pending':
      return <Clock className="w-3.5 h-3.5 shrink-0" style={style} />;
    case 'running':
      return <Loader2 className="w-3.5 h-3.5 animate-spin shrink-0" style={style} />;
    case 'success':
      return <CheckCircle className="w-3.5 h-3.5 shrink-0" style={style} />;
    case 'error':
      return <XCircle className="w-3.5 h-3.5 shrink-0" style={style} />;
    case 'warning':
      return <AlertTriangle className="w-3.5 h-3.5 shrink-0" style={style} />;
    default:
      return <Activity className="w-3.5 h-3.5 shrink-0" style={style} />;
  }
}

/**
 * Displays a status badge for operation status.
 * Supports persistent updates via event_id (same id updates in-place).
 */
export function StatusBadge({ event, compact = false }: StatusBadgeProps) {
  const { data, toolName, agentLabel } = event;
  const { label, status, message } = data;
  const tone = STATUS_TONE[status] ?? 'neutral';

  if (compact) {
    return (
      <Badge tone={tone} className="gap-1.5">
        {statusIcon(status, tone)}
        {label}
      </Badge>
    );
  }

  return (
    <Surface variant="inset" tone={tone} className="flex flex-col gap-1 p-2">
      <div className="flex items-center gap-2">
        {statusIcon(status, tone)}
        <span className="text-xs font-medium" style={{ color: 'var(--color-text-primary)' }}>
          {label}
        </span>
        <span
          className="ml-auto font-mono text-[10px] uppercase tracking-[0.1em]"
          style={{ color: TONE_COLOR[tone] }}
        >
          {status}
        </span>
      </div>
      {message && (
        <div className="text-xs pl-5" style={{ color: 'var(--color-text-muted)' }}>
          {message}
        </div>
      )}
      {(toolName || agentLabel) && (
        <div
          className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.1em] pl-5"
          style={{ color: 'var(--color-text-muted)' }}
        >
          {agentLabel && <span>{agentLabel}</span>}
          {agentLabel && toolName && <span>·</span>}
          {toolName && <span>{toolName}</span>}
        </div>
      )}
    </Surface>
  );
}

// =============================================================================
// FileOperationCard - File operation display with icons
// =============================================================================

interface FileOperationCardProps {
  event: FileStatusEvent;
  compact?: boolean;
}

function fileOperationIcon(operation: string, tone: BadgeTone) {
  const style = { color: TONE_COLOR[tone] };
  switch (operation) {
    case 'reading':
      return <FileSearch className="w-3.5 h-3.5 shrink-0" style={style} />;
    case 'writing':
      return <FileEdit className="w-3.5 h-3.5 shrink-0" style={style} />;
    case 'created':
      return <FilePlus className="w-3.5 h-3.5 shrink-0" style={style} />;
    case 'modified':
      return <FileEdit className="w-3.5 h-3.5 shrink-0" style={style} />;
    case 'deleted':
      return <FileX className="w-3.5 h-3.5 shrink-0" style={style} />;
    case 'error':
      return <XCircle className="w-3.5 h-3.5 shrink-0" style={style} />;
    default:
      return <FileText className="w-3.5 h-3.5 shrink-0" style={style} />;
  }
}

/**
 * Displays file operation status (reading, writing, created, modified, deleted, error).
 */
export function FileOperationCard({ event, compact = false }: FileOperationCardProps) {
  const { data, toolName, agentLabel } = event;
  const { filename, operation, size_bytes, line_count, message } = data;
  const tone = OPERATION_TONE[operation] ?? 'neutral';

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  if (compact) {
    return (
      <Surface variant="inset" className="flex items-center gap-2 px-2 py-1">
        {fileOperationIcon(operation, tone)}
        <span
          className="text-xs truncate max-w-[150px]"
          style={{ color: 'var(--color-text-muted)' }}
        >
          {filename}
        </span>
        <span
          className="font-mono text-[10px] uppercase tracking-[0.1em]"
          style={{ color: TONE_COLOR[tone] }}
        >
          {operation}
        </span>
      </Surface>
    );
  }

  return (
    <Surface variant="inset" tone={tone} className="flex flex-col gap-1 p-2">
      <div className="flex items-center gap-2">
        {fileOperationIcon(operation, tone)}
        <span
          className="text-xs font-medium truncate flex-1"
          style={{ color: 'var(--color-text-primary)' }}
        >
          {filename}
        </span>
        <span
          className="font-mono text-[10px] uppercase tracking-[0.1em] font-medium"
          style={{ color: TONE_COLOR[tone] }}
        >
          {operation}
        </span>
      </div>

      {/* Metadata row */}
      <div
        className="flex items-center gap-3 font-mono text-[10px] uppercase tracking-[0.1em] pl-5"
        style={{ color: 'var(--color-text-muted)' }}
      >
        {size_bytes !== undefined && <span>{formatSize(size_bytes)}</span>}
        {line_count !== undefined && <span>{line_count} lines</span>}
        {agentLabel && <span>{agentLabel}</span>}
        {toolName && <span>{toolName}</span>}
      </div>

      {message && (
        <div className="text-xs pl-5" style={{ color: 'var(--color-text-muted)' }}>
          {message}
        </div>
      )}
    </Surface>
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
      <Surface variant="inset" className="flex items-center gap-2 px-2 py-1">
        <Eye className="w-3.5 h-3.5 shrink-0" style={{ color: 'var(--color-primary)' }} />
        <span className="text-xs truncate" style={{ color: 'var(--color-text-muted)' }}>
          {eventType}
        </span>
      </Surface>
    );
  }

  return (
    <Surface variant="inset" className="flex flex-col gap-1 p-2">
      <div className="flex items-center gap-2">
        <Eye className="w-4 h-4 shrink-0" style={{ color: 'var(--color-primary)' }} />
        <span className="text-xs font-medium" style={{ color: 'var(--color-text-primary)' }}>
          {eventType}
        </span>
      </div>
      <pre
        className="text-[10px] font-mono pl-5 overflow-hidden text-ellipsis max-h-16"
        style={{ color: 'var(--color-text-muted)' }}
      >
        {JSON.stringify(data, null, 2)}
      </pre>
      {(toolName || agentLabel) && (
        <div
          className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.1em] pl-5"
          style={{ color: 'var(--color-text-muted)' }}
        >
          {agentLabel && <span>{agentLabel}</span>}
          {agentLabel && toolName && <span>·</span>}
          {toolName && <span>{toolName}</span>}
        </div>
      )}
    </Surface>
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
        <div
          className="flex flex-col gap-1 border-t pt-2 mt-1"
          style={{ borderColor: 'var(--border-subtle)' }}
        >
          <div
            className="font-mono text-[10px] uppercase tracking-[0.12em] mb-1"
            style={{ color: 'var(--color-text-muted)' }}
          >
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
