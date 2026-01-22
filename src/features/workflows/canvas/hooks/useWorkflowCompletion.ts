/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useEffect, useRef } from 'react';
import { TaskHistoryEntry } from '../types';

interface UseWorkflowCompletionOptions {
  workflowEvents: any[];
  setExecutionStatus: (updater: (prev: any) => any) => void;
  fetchTaskHistory: (force?: boolean) => Promise<TaskHistoryEntry[]>;
  /** Callback when workflow completes, receives the new task directly */
  onComplete?: (newTask?: TaskHistoryEntry) => void;
  /** Clear any selected task so the latest task is shown after completion */
  clearSelectedTask?: () => void;
  /** Expand the history panel to show the new task */
  expandHistory?: () => void;
}

/**
 * Hook for detecting workflow completion from events and triggering side effects
 */
export function useWorkflowCompletion({
  workflowEvents,
  setExecutionStatus,
  fetchTaskHistory,
  onComplete,
  clearSelectedTask,
  expandHistory,
}: UseWorkflowCompletionOptions): void {
  // Track if we've already handled completion to prevent duplicate calls
  const hasHandledCompleteRef = useRef(false);

  // Reset the completion tracking when events are cleared (new workflow starts)
  useEffect(() => {
    if (workflowEvents.length === 0) {
      hasHandledCompleteRef.current = false;
    }
  }, [workflowEvents.length]);

  useEffect(() => {
    const handleCompletion = async () => {
      if (workflowEvents.length > 0) {
        const lastEvent = workflowEvents[workflowEvents.length - 1];

        // Check for completion - only handle once
        if (lastEvent.type === 'complete' && !hasHandledCompleteRef.current) {
          hasHandledCompleteRef.current = true;

          setExecutionStatus(prev => ({
            ...prev,
            state: 'completed',
            progress: 100,
          }));

          // Clear any previous task selection so the new task is shown
          clearSelectedTask?.();

          // Refresh task history to get the new result - force fetch to bypass guard
          // This now returns the fetched tasks directly, avoiding stale closure issues
          const newTasks = await fetchTaskHistory(true);

          // Expand history panel to show the new task
          expandHistory?.();

          // Trigger completion callback with the new task directly
          // No delay needed - we pass the task from the fetch result, not from closure
          if (onComplete) {
            const newTask = newTasks.length > 0 ? newTasks[0] : undefined;
            onComplete(newTask);
          }
        }
        // Note: Error handling is disabled to let workflow complete naturally
        // Error events don't stop the stream
      }
    };

    handleCompletion();
  }, [workflowEvents, setExecutionStatus, fetchTaskHistory, onComplete, clearSelectedTask]);
}
