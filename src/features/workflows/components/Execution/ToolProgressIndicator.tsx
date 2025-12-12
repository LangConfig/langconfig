/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { Activity, CheckCircle, XCircle, Loader2, Clock } from 'lucide-react';
import type { ToolProgressEvent } from '@/types/events';

interface ToolProgressIndicatorProps {
  event: ToolProgressEvent;
  compact?: boolean;
}

/**
 * Displays progress updates for long-running tool operations.
 * Shows a progress bar, step counter, and status icon based on progress_type.
 */
export function ToolProgressIndicator({ event, compact = false }: ToolProgressIndicatorProps) {
  const { data } = event;
  const {
    tool_name,
    message,
    progress_type,
    percent_complete,
    current_step,
    total_steps,
  } = data;

  const getIcon = () => {
    switch (progress_type) {
      case 'started':
        return <Loader2 className="w-4 h-4 animate-spin text-blue-500" />;
      case 'update':
        return <Activity className="w-4 h-4 animate-pulse text-amber-500" />;
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'error':
        return <XCircle className="w-4 h-4 text-red-500" />;
      default:
        return <Clock className="w-4 h-4 text-gray-500" />;
    }
  };

  const getBorderColor = () => {
    switch (progress_type) {
      case 'started':
        return 'border-blue-400/50';
      case 'update':
        return 'border-amber-400/50';
      case 'completed':
        return 'border-green-400/50';
      case 'error':
        return 'border-red-400/50';
      default:
        return 'border-gray-400/50';
    }
  };

  const getBackgroundColor = () => {
    switch (progress_type) {
      case 'started':
        return 'bg-blue-50 dark:bg-blue-950/30';
      case 'update':
        return 'bg-amber-50 dark:bg-amber-950/30';
      case 'completed':
        return 'bg-green-50 dark:bg-green-950/30';
      case 'error':
        return 'bg-red-50 dark:bg-red-950/30';
      default:
        return 'bg-gray-50 dark:bg-gray-950/30';
    }
  };

  const getProgressBarColor = () => {
    switch (progress_type) {
      case 'started':
        return 'bg-blue-500';
      case 'update':
        return 'bg-amber-500';
      case 'completed':
        return 'bg-green-500';
      case 'error':
        return 'bg-red-500';
      default:
        return 'bg-gray-500';
    }
  };

  if (compact) {
    return (
      <div className={`flex items-center gap-2 px-2 py-1 rounded border ${getBorderColor()} ${getBackgroundColor()}`}>
        {getIcon()}
        <span className="text-xs text-gray-600 dark:text-gray-400 truncate max-w-[200px]">
          {message}
        </span>
        {percent_complete !== undefined && (
          <span className="text-xs text-gray-500 font-mono">{percent_complete}%</span>
        )}
      </div>
    );
  }

  return (
    <div className={`flex flex-col gap-1.5 p-2.5 rounded-lg border ${getBorderColor()} ${getBackgroundColor()}`}>
      <div className="flex items-center gap-2">
        {getIcon()}
        <div className="flex-1 min-w-0">
          <div className="text-xs font-medium text-gray-700 dark:text-gray-300 truncate">
            {tool_name}
          </div>
          <div className="text-xs text-gray-500 dark:text-gray-400">
            {message}
          </div>
        </div>
        {progress_type === 'update' && percent_complete !== undefined && (
          <span className="text-xs text-gray-500 font-mono shrink-0">
            {percent_complete}%
          </span>
        )}
      </div>

      {/* Progress bar */}
      {(percent_complete !== undefined || (current_step !== undefined && total_steps !== undefined)) && (
        <div className="mt-1">
          <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5 overflow-hidden">
            <div
              className={`${getProgressBarColor()} h-1.5 rounded-full transition-all duration-300 ease-out`}
              style={{
                width: `${percent_complete ?? ((current_step ?? 0) / (total_steps ?? 1) * 100)}%`
              }}
            />
          </div>
          {current_step !== undefined && total_steps !== undefined && (
            <div className="text-[10px] text-gray-400 dark:text-gray-500 mt-0.5 text-right">
              Step {current_step} of {total_steps}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default ToolProgressIndicator;
