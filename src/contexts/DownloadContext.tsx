/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * DownloadContext - Provides workflow context for artifact downloads
 */

import React, { createContext, useContext, useMemo } from 'react';

interface DownloadContextValue {
  /** Workflow name for file naming */
  workflowName: string;
  /** Counter for unique file numbering */
  getNextNumber: () => number;
}

const DownloadContext = createContext<DownloadContextValue | null>(null);

interface DownloadProviderProps {
  workflowName: string;
  children: React.ReactNode;
}

/**
 * Provider that makes workflow name available for download file naming
 */
export function DownloadProvider({ workflowName, children }: DownloadProviderProps) {
  // Use a ref-like counter that persists across renders
  const counterRef = React.useRef(0);

  const value = useMemo(() => ({
    workflowName: workflowName || 'Workflow',
    getNextNumber: () => {
      counterRef.current += 1;
      return counterRef.current;
    },
  }), [workflowName]);

  return (
    <DownloadContext.Provider value={value}>
      {children}
    </DownloadContext.Provider>
  );
}

/**
 * Hook to access download context
 */
export function useDownloadContext(): DownloadContextValue {
  const context = useContext(DownloadContext);

  // Return default values if not in a provider
  if (!context) {
    let counter = 0;
    return {
      workflowName: 'Generated',
      getNextNumber: () => {
        counter += 1;
        return counter;
      },
    };
  }

  return context;
}

/**
 * Generate a safe filename from workflow name
 */
export function sanitizeFilename(name: string): string {
  return name
    .replace(/[^a-zA-Z0-9\s-_]/g, '') // Remove special chars
    .replace(/\s+/g, '_') // Replace spaces with underscores
    .substring(0, 50); // Limit length
}
