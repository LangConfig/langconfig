/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { createContext, useContext } from 'react';
import type { WorkflowCanvasContextValue } from './types';

/**
 * Context for sharing functions with nested components like CustomNode
 */
export const WorkflowCanvasContext = createContext<WorkflowCanvasContextValue | null>(null);

/**
 * Hook to access the workflow canvas context
 * Must be used within WorkflowCanvasContext.Provider
 */
export const useWorkflowCanvasContext = () => {
  const context = useContext(WorkflowCanvasContext);
  if (!context) {
    throw new Error('useWorkflowCanvasContext must be used within WorkflowCanvasContext.Provider');
  }
  return context;
};
