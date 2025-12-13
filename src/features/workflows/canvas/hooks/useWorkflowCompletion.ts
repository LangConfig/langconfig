/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useEffect } from 'react';

interface UseWorkflowCompletionOptions {
  workflowEvents: any[];
  setExecutionStatus: (updater: (prev: any) => any) => void;
  fetchTaskHistory: () => void;
  onComplete?: () => void;
}

/**
 * Hook for detecting workflow completion from events and triggering side effects
 */
export function useWorkflowCompletion({
  workflowEvents,
  setExecutionStatus,
  fetchTaskHistory,
  onComplete,
}: UseWorkflowCompletionOptions): void {
  useEffect(() => {
    if (workflowEvents.length > 0) {
      const lastEvent = workflowEvents[workflowEvents.length - 1];

      // Check for completion
      if (lastEvent.type === 'complete') {
        setExecutionStatus(prev => ({
          ...prev,
          state: 'completed',
          progress: 100,
        }));

        // Refresh task history to get the new result
        fetchTaskHistory();

        // Trigger completion callback (e.g., switch to results tab)
        if (onComplete) {
          setTimeout(() => {
            onComplete();
          }, 500); // Small delay to ensure history is fetched
        }
      }
      // Note: Error handling is disabled to let workflow complete naturally
      // Error events don't stop the stream
    }
  }, [workflowEvents, setExecutionStatus, fetchTaskHistory, onComplete]);
}
