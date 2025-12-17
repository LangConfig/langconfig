/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import apiClient from '@/lib/api-client';
import { TaskHistoryEntry } from '../types';

interface RunningTaskInfo {
  id: number;
  created_at: string;
}

interface UseTaskManagementOptions {
  currentWorkflowId: number | null;
  showSuccess: (message: string) => void;
  logError: (title: string, detail?: string) => void;
  onRunningTaskFound?: (taskInfo: RunningTaskInfo) => void;
  onTaskDeleted?: () => void;
}

export function useTaskManagement({
  currentWorkflowId,
  showSuccess,
  logError,
  onRunningTaskFound,
  onTaskDeleted,
}: UseTaskManagementOptions) {
  // Task history state
  const [taskHistory, setTaskHistory] = useState<TaskHistoryEntry[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [selectedHistoryTask, setSelectedHistoryTask] = useState<TaskHistoryEntry | null>(null);
  const [isHistoryCollapsed, setIsHistoryCollapsed] = useState(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('workflow-history-collapsed');
      return saved ? JSON.parse(saved) : false;
    }
    return false;
  });

  // Replay panel state
  const [showReplayPanel, setShowReplayPanel] = useState(false);
  const [replayTaskId, setReplayTaskId] = useState<number | null>(null);

  // Ref to prevent duplicate fetches
  const isFetchingRef = useRef(false);
  const onRunningTaskFoundRef = useRef(onRunningTaskFound);

  // Keep ref updated
  useEffect(() => {
    onRunningTaskFoundRef.current = onRunningTaskFound;
  }, [onRunningTaskFound]);

  // Persist collapsed state
  useEffect(() => {
    localStorage.setItem('workflow-history-collapsed', JSON.stringify(isHistoryCollapsed));
  }, [isHistoryCollapsed]);

  // Fetch task history for current workflow
  const fetchTaskHistory = useCallback(async () => {
    if (!currentWorkflowId) {
      setTaskHistory([]);
      return;
    }

    // Prevent duplicate/loop fetches
    if (isFetchingRef.current) {
      return;
    }

    isFetchingRef.current = true;
    setLoadingHistory(true);
    try {
      const response = await apiClient.getWorkflowHistory(currentWorkflowId, 50, 0);
      const tasks = response.data.tasks || [];
      setTaskHistory(tasks);

      // Check if there's a running task and notify parent
      const runningTask = tasks.find((task: any) =>
        task.status === 'running' || task.status === 'pending'
      );

      if (runningTask && onRunningTaskFoundRef.current) {
        onRunningTaskFoundRef.current({
          id: runningTask.id,
          created_at: runningTask.created_at,
        });
      }
    } catch (error) {
      console.error('Failed to fetch task history:', error);
      setTaskHistory([]);
    } finally {
      isFetchingRef.current = false;
      setLoadingHistory(false);
    }
  }, [currentWorkflowId]); // Only depend on workflowId, not callbacks

  // Load task history when workflow changes
  useEffect(() => {
    fetchTaskHistory();
  }, [currentWorkflowId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Delete a task from history
  const handleDeleteTask = useCallback(async (taskId: number) => {
    try {
      await apiClient.deleteTask(taskId);

      // Remove from local state
      setTaskHistory(prev => prev.filter(t => t.task_id !== taskId));

      // Clear selection if deleted task was selected
      if (selectedHistoryTask?.task_id === taskId) {
        setSelectedHistoryTask(null);
      }

      showSuccess('Task deleted successfully');

      // Notify parent about deletion for any cleanup
      onTaskDeleted?.();
    } catch (error: any) {
      console.error('Failed to delete task:', error);
      logError('Failed to delete task', error.response?.data?.detail || error.message);
    }
  }, [selectedHistoryTask, showSuccess, logError, onTaskDeleted]);

  // Select a task from history
  const handleSelectTask = useCallback((task: TaskHistoryEntry | null) => {
    setSelectedHistoryTask(task);

    // If selecting a task, set it for replay
    if (task) {
      setReplayTaskId(task.task_id);
    }
  }, []);

  // Open replay panel for a task
  const handleOpenReplay = useCallback((taskId: number) => {
    setReplayTaskId(taskId);
    setShowReplayPanel(true);
  }, []);

  // Close replay panel
  const handleCloseReplay = useCallback(() => {
    setShowReplayPanel(false);
    setReplayTaskId(null);
  }, []);

  // Toggle history sidebar collapsed state
  const toggleHistoryCollapsed = useCallback(() => {
    setIsHistoryCollapsed((prev: boolean) => !prev);
  }, []);

  // Reset task history (e.g., when creating a new workflow)
  const resetTaskHistory = useCallback(() => {
    setTaskHistory([]);
    setSelectedHistoryTask(null);
    setShowReplayPanel(false);
    setReplayTaskId(null);
  }, []);

  return {
    // Task history
    taskHistory,
    loadingHistory,
    selectedHistoryTask,
    setSelectedHistoryTask: handleSelectTask,
    isHistoryCollapsed,
    setIsHistoryCollapsed,
    toggleHistoryCollapsed,
    fetchTaskHistory,
    handleDeleteTask,
    resetTaskHistory,

    // Replay panel
    showReplayPanel,
    setShowReplayPanel,
    replayTaskId,
    setReplayTaskId,
    handleOpenReplay,
    handleCloseReplay,
  };
}
