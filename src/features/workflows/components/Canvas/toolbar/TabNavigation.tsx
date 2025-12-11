/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { memo } from 'react';

type Tab = 'studio' | 'results';

interface TabNavigationProps {
  activeTab: Tab;
  onTabChange: (tab: Tab) => void;
  taskHistoryCount: number;
  hasUnsavedChanges: boolean;
  currentWorkflowId: number | null;
  onResultsTabClick?: () => void;
}

/**
 * Tab navigation bar for switching between Studio and Results views
 */
const TabNavigation = memo(function TabNavigation({
  activeTab,
  onTabChange,
  taskHistoryCount,
  hasUnsavedChanges,
  currentWorkflowId,
  onResultsTabClick,
}: TabNavigationProps) {
  const tabClass = (tab: Tab) =>
    `px-4 py-3 text-sm font-semibold border-b-2 transition-all ${
      activeTab === tab
        ? 'border-primary text-primary'
        : 'border-transparent text-gray-600 dark:text-text-muted hover:text-gray-900 dark:hover:text-white'
    }`;

  return (
    <div className="bg-white dark:bg-panel-dark border-b border-gray-200 dark:border-border-dark">
      <div className="flex items-center px-4">
        <button
          onClick={() => onTabChange('studio')}
          className={tabClass('studio')}
        >
          Studio
        </button>
        <button
          onClick={() => {
            onTabChange('results');
            onResultsTabClick?.();
          }}
          className={tabClass('results')}
        >
          Results {taskHistoryCount > 0 && `(${taskHistoryCount})`}
        </button>

        {/* Spacer to push workflow ID to the right */}
        <div className="flex-1" />

        {/* Unsaved Changes Indicator */}
        {hasUnsavedChanges && (
          <div className="flex items-center gap-2 text-xs font-medium text-yellow-600 dark:text-yellow-500 py-3 animate-pulse mr-4">
            <span className="material-symbols-outlined" style={{ fontSize: '16px' }}>
              warning
            </span>
            Unsaved Changes
          </div>
        )}

        {/* Workflow ID - Plain text on the right */}
        {currentWorkflowId && (
          <div className="text-xs font-mono text-text-muted dark:text-text-muted py-3">
            ID: {currentWorkflowId}
          </div>
        )}
      </div>
    </div>
  );
});

export default TabNavigation;
