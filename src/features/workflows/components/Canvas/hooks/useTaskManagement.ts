/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useCallback, useEffect } from 'react';
import apiClient from '../../../../../lib/api-client';

interface TaskHistoryEntry {
  id: number;
  task_id: number;
  status: string;
  created_at: string;
  completed_at?: string;
  input_data?: any;
  result?: any;
  error?: string;
}

interface RunningTaskInfo {
  id: number;
  created_at: string;
}

interface UseTaskManagementOptions {
  currentWorkflowId: number | null;
  showSuccess: (message: string) => void;
  logError: (title: string, detail?: string) => void;
  onRunningTaskFound?: (taskInfo: RunningTaskInfo) => void;
}

export function useTaskManagement({
  currentWorkflowId,
  showSuccess,
  logError,
  onRunningTaskFound,
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

  // Task context menu state
  const [taskContextMenu, setTaskContextMenu] = useState<{
    x: number;
    y: number;
    taskId: number;
  } | null>(null);

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

    setLoadingHistory(true);
    try {
      const response = await apiClient.getWorkflowHistory(currentWorkflowId, 50, 0);
      const tasks = response.data.tasks || [];
      setTaskHistory(tasks);

      // Check if there's a running task and notify parent
      const runningTask = tasks.find((task: any) =>
        task.status === 'running' || task.status === 'pending'
      );

      if (runningTask && onRunningTaskFound) {
        onRunningTaskFound({
          id: runningTask.id,
          created_at: runningTask.created_at,
        });
      }
    } catch (error) {
      console.error('Failed to fetch task history:', error);
      setTaskHistory([]);
    } finally {
      setLoadingHistory(false);
    }
  }, [currentWorkflowId, onRunningTaskFound]);

  // Load task history when workflow changes
  useEffect(() => {
    fetchTaskHistory();
  }, [fetchTaskHistory]);

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

      // Close context menu
      setTaskContextMenu(null);

      showSuccess('Task deleted successfully');
    } catch (error: any) {
      console.error('Failed to delete task:', error);
      logError('Failed to delete task', error.response?.data?.detail || error.message);
    }
  }, [selectedHistoryTask, showSuccess, logError]);

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
    setIsHistoryCollapsed(prev => !prev);
  }, []);

  // Open task context menu
  const openTaskContextMenu = useCallback((x: number, y: number, taskId: number) => {
    setTaskContextMenu({ x, y, taskId });
  }, []);

  // Close task context menu
  const closeTaskContextMenu = useCallback(() => {
    setTaskContextMenu(null);
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

    // Replay panel
    showReplayPanel,
    setShowReplayPanel,
    replayTaskId,
    setReplayTaskId,
    handleOpenReplay,
    handleCloseReplay,

    // Context menu
    taskContextMenu,
    setTaskContextMenu,
    openTaskContextMenu,
    closeTaskContextMenu,
  };
}
