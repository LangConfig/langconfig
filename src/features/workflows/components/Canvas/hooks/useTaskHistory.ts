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
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  created_at: string;
  completed_at?: string;
  input_data?: any;
  output_data?: any;
  error_message?: string;
}

interface UseTaskHistoryOptions {
  currentWorkflowId: number | null;
  onRunningTaskFound?: (task: TaskHistoryEntry) => void;
}

export function useTaskHistory({
  currentWorkflowId,
  onRunningTaskFound,
}: UseTaskHistoryOptions) {
  const [taskHistory, setTaskHistory] = useState<TaskHistoryEntry[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [selectedHistoryTask, setSelectedHistoryTask] = useState<TaskHistoryEntry | null>(null);

  // Fetch task history for the workflow
  const fetchTaskHistory = useCallback(async () => {
    if (!currentWorkflowId) return;

    setLoadingHistory(true);
    try {
      const response = await apiClient.getWorkflowHistory(currentWorkflowId, 50, 0);
      const tasks = response.data.tasks || [];
      setTaskHistory(tasks);

      // Check if there's a running task and notify parent
      const runningTask = tasks.find((task: TaskHistoryEntry) =>
        task.status === 'running' || task.status === 'pending'
      );

      if (runningTask && onRunningTaskFound) {
        onRunningTaskFound(runningTask);
      }
    } catch (err) {
      console.error('Failed to fetch task history:', err);
    } finally {
      setLoadingHistory(false);
    }
  }, [currentWorkflowId, onRunningTaskFound]);

  // Fetch history when workflow changes
  useEffect(() => {
    if (currentWorkflowId) {
      fetchTaskHistory();
    }
  }, [currentWorkflowId, fetchTaskHistory]);

  // Select a task from history
  const handleSelectHistoryTask = useCallback((task: TaskHistoryEntry | null) => {
    setSelectedHistoryTask(task);
  }, []);

  // Delete a task from history
  const handleDeleteTask = useCallback(async (taskId: number) => {
    if (!currentWorkflowId) return;

    try {
      await apiClient.deleteTask(taskId);
      await fetchTaskHistory();

      // Clear selection if deleted task was selected
      if (selectedHistoryTask?.id === taskId) {
        setSelectedHistoryTask(null);
      }
    } catch (error) {
      console.error('Failed to delete task:', error);
      throw error;
    }
  }, [currentWorkflowId, selectedHistoryTask, fetchTaskHistory]);

  // Get the display task (selected or latest)
  const getDisplayTask = useCallback(() => {
    return selectedHistoryTask || taskHistory[0] || null;
  }, [selectedHistoryTask, taskHistory]);

  return {
    // State
    taskHistory,
    loadingHistory,
    selectedHistoryTask,

    // Handlers
    fetchTaskHistory,
    handleSelectHistoryTask,
    handleDeleteTask,
    getDisplayTask,

    // Setters (for external updates)
    setTaskHistory,
    setSelectedHistoryTask,
  };
}
