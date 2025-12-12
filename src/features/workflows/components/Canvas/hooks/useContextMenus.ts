/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useEffect, useCallback } from 'react';

interface TaskContextMenu {
  taskId: number;
  x: number;
  y: number;
}

interface NodeContextMenu {
  nodeId: string;
  nodeData: any;
  x: number;
  y: number;
}

interface UseContextMenusReturn {
  taskContextMenu: TaskContextMenu | null;
  setTaskContextMenu: React.Dispatch<React.SetStateAction<TaskContextMenu | null>>;
  nodeContextMenu: NodeContextMenu | null;
  setNodeContextMenu: React.Dispatch<React.SetStateAction<NodeContextMenu | null>>;
  openNodeContextMenu: (nodeId: string, nodeData: any, x: number, y: number) => void;
}

/**
 * Hook for managing context menu state and auto-close behavior
 */
export function useContextMenus(): UseContextMenusReturn {
  const [taskContextMenu, setTaskContextMenu] = useState<TaskContextMenu | null>(null);
  const [nodeContextMenu, setNodeContextMenu] = useState<NodeContextMenu | null>(null);

  // Handler to open node context menu
  const openNodeContextMenu = useCallback((nodeId: string, nodeData: any, x: number, y: number) => {
    setNodeContextMenu({ nodeId, nodeData, x, y });
  }, []);

  // Close context menus when clicking outside
  useEffect(() => {
    const handleClickOutside = () => {
      if (taskContextMenu) {
        setTaskContextMenu(null);
      }
      if (nodeContextMenu) {
        setNodeContextMenu(null);
      }
    };

    if (taskContextMenu || nodeContextMenu) {
      document.addEventListener('click', handleClickOutside);
      return () => document.removeEventListener('click', handleClickOutside);
    }
  }, [taskContextMenu, nodeContextMenu]);

  return {
    taskContextMenu,
    setTaskContextMenu,
    nodeContextMenu,
    setNodeContextMenu,
    openNodeContextMenu,
  };
}
