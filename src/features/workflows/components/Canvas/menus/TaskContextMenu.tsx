/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { memo } from 'react';
import { Trash2 } from 'lucide-react';

interface TaskContextMenuProps {
  x: number;
  y: number;
  taskId: number;
  onDeleteTask: (taskId: number) => void;
}

/**
 * Context menu that appears when right-clicking a task in the history sidebar
 */
const TaskContextMenu = memo(function TaskContextMenu({
  x,
  y,
  taskId,
  onDeleteTask,
}: TaskContextMenuProps) {
  return (
    <div
      className="fixed z-[9999] bg-white dark:bg-panel-dark border border-gray-200 dark:border-border-dark rounded-lg shadow-lg py-1 min-w-[160px]"
      style={{
        left: `${x}px`,
        top: `${y}px`,
      }}
      onClick={(e) => e.stopPropagation()}
    >
      <button
        onClick={() => onDeleteTask(taskId)}
        className="w-full text-left px-4 py-2 text-sm hover:bg-gray-100 dark:hover:bg-white/10 transition-colors flex items-center gap-2 text-red-600 dark:text-red-400"
      >
        <Trash2 className="w-4 h-4" />
        Delete Task
      </button>
    </div>
  );
});

export default TaskContextMenu;
