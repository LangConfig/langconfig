/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useEffect, useRef } from 'react';

interface UseWorkflowCompletionOptions {
  workflowEvents: any[];
  setExecutionStatus: (updater: (prev: any) => any) => void;
  fetchTaskHistory: () => void;
  onComplete?: () => void;
  /** Clear any selected task so the latest task is shown after completion */
  clearSelectedTask?: () => void;
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

          // Refresh task history to get the new result - wait for it to complete
          await fetchTaskHistory();

          // Trigger completion callback (e.g., switch to results tab)
          // Now we can call immediately since history is loaded
          if (onComplete) {
            onComplete();
          }
        }
        // Note: Error handling is disabled to let workflow complete naturally
        // Error events don't stop the stream
      }
    };

    handleCompletion();
  }, [workflowEvents, setExecutionStatus, fetchTaskHistory, onComplete, clearSelectedTask]);
}
