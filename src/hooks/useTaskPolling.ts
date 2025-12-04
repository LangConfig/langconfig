/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { apiClient } from '@/lib/api-client';
import type { BackgroundTask } from '@/types/api';

/**
 * Hook for polling background task status
 *
 *
 * Usage:
 * ```typescript
 * const { status, progress, error, result } = useTaskPolling({
 *   taskId: exportResponse.task_id,
 *   onComplete: (result) => {
 *     toast.success('Export completed!');
 *     downloadFile(result.download_url);
 *   },
 *   onError: (error) => {
 *     toast.error(`Export failed: ${error}`);
 *   }
 * });
 * ```
 */

interface UseTaskPollingOptions {
  taskId: number;
  enabled?: boolean;  // Whether to start polling immediately
  onComplete?: (result: any) => void;
  onError?: (error: string) => void;
  pollInterval?: number;  // milliseconds (default: 2000)
}

interface UseTaskPollingResult {
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'IDLE';
  progress: number;  // 0-100
  error: string | null;
  result: any | null;
  task: BackgroundTask | null;
  retry: () => void;
  cancel: () => void;
}

export function useTaskPolling({
  taskId,
  enabled = true,
  onComplete,
  onError,
  pollInterval = 2000
}: UseTaskPollingOptions): UseTaskPollingResult {
  const [status, setStatus] = useState<UseTaskPollingResult['status']>('IDLE');
  const [progress, setProgress] = useState<number>(0);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<any | null>(null);
  const [task, setTask] = useState<BackgroundTask | null>(null);

  const intervalRef = useRef<number | null>(null);
  const hasCompletedRef = useRef(false);

  const checkStatus = useCallback(async () => {
    if (!taskId || !enabled) return true;  // Stop polling

    try {
      const response = await apiClient.getBackgroundTask(taskId);
      const taskData: BackgroundTask = response.data;

      setTask(taskData);
      setStatus(taskData.status);

      if (taskData.status === 'COMPLETED') {
        setProgress(100);
        setResult(taskData.result);

        // Only call onComplete once
        if (!hasCompletedRef.current) {
          hasCompletedRef.current = true;
          onComplete?.(taskData.result);
        }

        return true;  // Stop polling
      } else if (taskData.status === 'FAILED') {
        const errorMsg = taskData.error || 'Task failed with unknown error';
        setError(errorMsg);

        // Only call onError once
        if (!hasCompletedRef.current) {
          hasCompletedRef.current = true;
          onError?.(errorMsg);
        }

        return true;  // Stop polling
      } else if (taskData.status === 'RUNNING') {
        // Estimate progress (backend doesn't provide real progress yet)
        // Could be enhanced with task-specific progress in the future
        setProgress(50);
      } else if (taskData.status === 'PENDING') {
        setProgress(10);
      }

      return false;  // Continue polling
    } catch (err) {
      console.error('Failed to check task status:', err);
      const errorMsg = err instanceof Error ? err.message : 'Failed to check task status';
      setError(errorMsg);

      // Don't stop polling on network errors - they might be temporary
      // Only stop if it's a 404 (task not found)
      if (err instanceof Error && err.message.includes('404')) {
        hasCompletedRef.current = true;
        onError?.(errorMsg);
        return true;
      }

      return false;  // Continue polling
    }
  }, [taskId, enabled, onComplete, onError]);

  const retry = useCallback(async () => {
    if (!taskId) return;

    try {
      await apiClient.retryBackgroundTask(taskId);

      // Reset state
      hasCompletedRef.current = false;
      setStatus('PENDING');
      setProgress(0);
      setError(null);
      setResult(null);

      // Resume polling
      if (!intervalRef.current) {
        startPolling();
      }
    } catch (err) {
      console.error('Failed to retry task:', err);
      setError(err instanceof Error ? err.message : 'Failed to retry task');
    }
  }, [taskId]);

  const cancel = useCallback(async () => {
    if (!taskId) return;

    try {
      await apiClient.cancelBackgroundTask(taskId);

      // Stop polling
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }

      setStatus('FAILED');
      setError('Task cancelled by user');
    } catch (err) {
      console.error('Failed to cancel task:', err);
      setError(err instanceof Error ? err.message : 'Failed to cancel task');
    }
  }, [taskId]);

  const startPolling = useCallback(() => {
    // Check immediately
    checkStatus().then((shouldStop) => {
      if (shouldStop) return;

      // Then poll at intervals
      intervalRef.current = setInterval(async () => {
        const shouldStop = await checkStatus();
        if (shouldStop && intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
      }, pollInterval);
    });
  }, [checkStatus, pollInterval]);

  useEffect(() => {
    if (!enabled || !taskId) {
      setStatus('IDLE');
      return;
    }

    // Reset completion flag when taskId changes
    hasCompletedRef.current = false;

    startPolling();

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [enabled, taskId, startPolling]);

  return {
    status,
    progress,
    error,
    result,
    task,
    retry,
    cancel
  };
}
