/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { memo } from 'react';

/**
 * Displayed when the workflow canvas has no nodes
 */
const EmptyCanvasState = memo(function EmptyCanvasState() {
  return (
    <div className="w-full h-full flex flex-col items-center justify-center gap-6 text-center p-12">
      <div className="w-24 h-24 rounded-full bg-primary/10 dark:bg-primary/20 flex items-center justify-center">
        <span className="material-symbols-outlined text-primary" style={{ fontSize: '48px' }}>
          account_tree
        </span>
      </div>
      <div>
        <h4 className="text-2xl font-bold text-gray-900 dark:text-white mb-3">
          Start Building Your Workflow
        </h4>
        <p className="text-gray-600 dark:text-gray-400 max-w-md text-base">
          Click on an agent from the left panel to add your first node, then connect them to create your workflow.
        </p>
      </div>
    </div>
  );
});

export default EmptyCanvasState;
