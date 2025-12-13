/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * Workflow Run History Panel
 *
 * Displays all past executions for a workflow with ability to view results.
 * Slides in from the right side of the screen.
 *
 * Features:
 * - List of all past workflow runs
 * - Status indicators (completed, failed, running)
 * - Duration and timestamp for each run
 * - Click to view full results in modal
 * - Filter by status
 * - Refresh to get latest runs
 */

import React, { useState, useEffect } from 'react';
import { X, Clock, CheckCircle, XCircle, AlertCircle, ChevronRight, RefreshCw, Calendar } from 'lucide-react';
import apiClient from '@/lib/api-client';

interface TaskExecution {
  id: number;
  status: string;
  created_at: string;
  completed_at: string | null;
  duration_seconds?: number;
  error_message?: string;
  result?: any;
  description?: string;
}

interface WorkflowRunHistoryProps {
  isOpen: boolean;
  onClose: () => void;
  workflowId: number | null;
  workflowName?: string;
  onViewResult: (task: TaskExecution) => void;
}

export default function WorkflowRunHistory({
  isOpen,
  onClose,
  workflowId,
  workflowName,
  onViewResult
}: WorkflowRunHistoryProps) {
  const [tasks, setTasks] = useState<TaskExecution[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<'all' | 'completed' | 'failed'>('all');
  const [totalCount, setTotalCount] = useState(0);

  // Fetch task history
  const fetchHistory = async () => {
    if (!workflowId) return;

    setLoading(true);
    setError(null);

    try {
      const response = await apiClient.getWorkflowHistory(workflowId, 50, 0);
      setTasks(response.data.tasks || []);
      setTotalCount(response.data.total_count || 0);
    } catch (err: any) {
      console.error('Failed to fetch workflow history:', err);
      setError(err.response?.data?.detail || 'Failed to load workflow history');
    } finally {
      setLoading(false);
    }
  };

  // Fetch on open or workflow change
  useEffect(() => {
    if (isOpen && workflowId) {
      fetchHistory();
    }
  }, [isOpen, workflowId]);

  // Filter tasks
  const filteredTasks = tasks.filter(task => {
    if (filter === 'all') return true;
    if (filter === 'completed') return task.status === 'COMPLETED';
    if (filter === 'failed') return task.status === 'FAILED';
    return true;
  });

  // Format duration
  const formatDuration = (seconds?: number) => {
    if (!seconds) return 'N/A';
    if (seconds < 60) return `${Math.round(seconds)}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.round(seconds % 60);
    return `${minutes}m ${remainingSeconds}s`;
  };

  // Format date
  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffHours = diffMs / (1000 * 60 * 60);

    if (diffHours < 1) {
      const diffMinutes = Math.floor(diffMs / (1000 * 60));
      return `${diffMinutes} min ago`;
    } else if (diffHours < 24) {
      return `${Math.floor(diffHours)} hours ago`;
    } else {
      return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
    }
  };

  // Get status icon and color
  const getStatusDisplay = (status: string) => {
    switch (status) {
      case 'COMPLETED':
        return {
          icon: <CheckCircle className="w-5 h-5" />,
          color: 'text-green-600 dark:text-green-400',
          bg: 'bg-green-50 dark:bg-green-900/20',
          border: 'border-green-200 dark:border-green-800/30',
          label: 'Completed'
        };
      case 'FAILED':
        return {
          icon: <XCircle className="w-5 h-5" />,
          color: 'text-red-600 dark:text-red-400',
          bg: 'bg-red-50 dark:bg-red-900/20',
          border: 'border-red-200 dark:border-red-800/30',
          label: 'Failed'
        };
      case 'IN_PROGRESS':
        return {
          icon: <AlertCircle className="w-5 h-5 animate-pulse" />,
          color: 'text-blue-600 dark:text-blue-400',
          bg: 'bg-blue-50 dark:bg-blue-900/20',
          border: 'border-blue-200 dark:border-blue-800/30',
          label: 'Running'
        };
      default:
        return {
          icon: <AlertCircle className="w-5 h-5" />,
          color: 'text-gray-600 dark:text-gray-400',
          bg: 'bg-gray-50 dark:bg-gray-900/20',
          border: 'border-gray-200 dark:border-gray-800/30',
          label: status
        };
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className={`fixed right-0 top-0 bottom-0 w-full md:w-[500px] bg-background-light dark:bg-background-dark border-l border-gray-200 dark:border-border-dark shadow-2xl z-40 transform transition-transform duration-300 ${
        isOpen ? 'translate-x-0' : 'translate-x-full'
      }`}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-border-dark bg-background-light dark:bg-panel-dark">
        <div>
          <h2 className="text-lg font-bold text-gray-900 dark:text-white">
            Run History
          </h2>
          <p className="text-sm text-gray-600 dark:text-text-muted">
            {workflowName || 'Workflow'} - {totalCount} total runs
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={fetchHistory}
            disabled={loading}
            className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-white/5 transition-colors disabled:opacity-50"
            title="Refresh"
          >
            <RefreshCw className={`w-5 h-5 text-gray-600 dark:text-text-muted ${loading ? 'animate-spin' : ''}`} />
          </button>

          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-white/5 transition-colors"
            title="Close"
          >
            <X className="w-5 h-5 text-gray-600 dark:text-text-muted" />
          </button>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex border-b border-gray-200 dark:border-border-dark px-6 bg-background-light dark:bg-panel-dark">
        <button
          onClick={() => setFilter('all')}
          className={`px-4 py-3 text-sm font-semibold border-b-2 transition-all ${
            filter === 'all'
              ? 'border-primary text-primary'
              : 'border-transparent text-gray-600 dark:text-text-muted hover:text-gray-900 dark:hover:text-white'
          }`}
        >
          All ({tasks.length})
        </button>
        <button
          onClick={() => setFilter('completed')}
          className={`px-4 py-3 text-sm font-semibold border-b-2 transition-all ${
            filter === 'completed'
              ? 'border-primary text-primary'
              : 'border-transparent text-gray-600 dark:text-text-muted hover:text-gray-900 dark:hover:text-white'
          }`}
        >
          Completed ({tasks.filter(t => t.status === 'COMPLETED').length})
        </button>
        <button
          onClick={() => setFilter('failed')}
          className={`px-4 py-3 text-sm font-semibold border-b-2 transition-all ${
            filter === 'failed'
              ? 'border-primary text-primary'
              : 'border-transparent text-gray-600 dark:text-text-muted hover:text-gray-900 dark:hover:text-white'
          }`}
        >
          Failed ({tasks.filter(t => t.status === 'FAILED').length})
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {loading && tasks.length === 0 && (
          <div className="flex items-center justify-center py-16">
            <RefreshCw className="w-8 h-8 text-gray-400 dark:text-text-muted animate-spin" />
          </div>
        )}

        {error && (
          <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
            <p className="text-sm font-medium text-red-800 dark:text-red-200">
              {error}
            </p>
          </div>
        )}

        {!loading && !error && filteredTasks.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <Calendar className="w-16 h-16 text-gray-300 dark:text-text-muted/30 mb-4" />
            <p className="text-lg font-medium text-gray-600 dark:text-text-muted">
              No runs found
            </p>
            <p className="text-sm text-gray-500 dark:text-text-muted/70 mt-2">
              {filter === 'all'
                ? 'Execute this workflow to see its history here.'
                : `No ${filter} runs found. Try a different filter.`}
            </p>
          </div>
        )}

        {/* Task List */}
        <div className="space-y-3">
          {filteredTasks.map((task) => {
            const statusDisplay = getStatusDisplay(task.status);
            return (
              <button
                key={task.id}
                onClick={() => onViewResult(task)}
                className={`w-full text-left p-4 rounded-lg border ${statusDisplay.border} ${statusDisplay.bg} hover:shadow-md transition-all group`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-3 flex-1 min-w-0">
                    <div className={statusDisplay.color}>
                      {statusDisplay.icon}
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className={`text-sm font-semibold ${statusDisplay.color}`}>
                          {statusDisplay.label}
                        </span>
                        <span className="text-xs font-mono text-gray-500 dark:text-text-muted/70">
                          Task #{task.id}
                        </span>
                      </div>

                      <div className="flex items-center gap-3 mt-2 text-xs text-gray-600 dark:text-text-muted flex-wrap">
                        <div className="flex items-center gap-1">
                          <Clock className="w-3.5 h-3.5" />
                          {formatDate(task.created_at)}
                        </div>
                        {task.duration_seconds !== undefined && (
                          <div className="flex items-center gap-1">
                            <span>Duration: {formatDuration(task.duration_seconds)}</span>
                          </div>
                        )}
                      </div>

                      {task.error_message && (
                        <p className="text-xs text-red-600 dark:text-red-400 mt-2 line-clamp-2">
                          {task.error_message}
                        </p>
                      )}
                    </div>
                  </div>

                  <ChevronRight className="w-5 h-5 text-gray-400 dark:text-text-muted/50 group-hover:text-gray-600 dark:group-hover:text-text-muted transition-colors flex-shrink-0" />
                </div>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
