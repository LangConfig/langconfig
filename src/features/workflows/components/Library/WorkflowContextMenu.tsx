/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useEffect, useRef } from 'react';

interface WorkflowContextMenuProps {
  x: number;
  y: number;
  onClose: () => void;
  onRename: () => void;
  onDuplicate: () => void;
  onChangeProject: () => void;
  onDelete: () => void;
}

export default function WorkflowContextMenu({
  x,
  y,
  onClose,
  onRename,
  onDuplicate,
  onChangeProject,
  onDelete
}: WorkflowContextMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null);

  // Adjust position to prevent going off-screen
  useEffect(() => {
    if (menuRef.current) {
      const rect = menuRef.current.getBoundingClientRect();
      const viewportWidth = window.innerWidth;
      const viewportHeight = window.innerHeight;

      let adjustedX = x;
      let adjustedY = y;

      // Check if menu goes off right edge
      if (x + rect.width > viewportWidth) {
        adjustedX = viewportWidth - rect.width - 8;
      }

      // Check if menu goes off bottom edge
      if (y + rect.height > viewportHeight) {
        adjustedY = viewportHeight - rect.height - 8;
      }

      // Update position if needed
      if (adjustedX !== x || adjustedY !== y) {
        menuRef.current.style.left = `${adjustedX}px`;
        menuRef.current.style.top = `${adjustedY}px`;
      }
    }
  }, [x, y]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose();
      }
    };

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleEscape);

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [onClose]);

  const menuItems = [
    {
      label: 'Rename',
      icon: 'edit',
      onClick: () => {
        onRename();
        onClose();
      }
    },
    {
      label: 'Duplicate',
      icon: 'content_copy',
      onClick: () => {
        onDuplicate();
        onClose();
      }
    },
    {
      label: 'Change Project',
      icon: 'folder_open',
      onClick: () => {
        onChangeProject();
        onClose();
      }
    },
    {
      label: 'Delete',
      icon: 'delete',
      onClick: () => {
        onDelete();
        onClose();
      },
      danger: true
    }
  ];

  return (
    <div
      ref={menuRef}
      className="fixed z-50 w-56 rounded-lg shadow-xl border py-1"
      style={{
        left: `${x}px`,
        top: `${y}px`,
        backgroundColor: 'var(--color-background-light, #ffffff)',
        borderColor: 'var(--color-border-dark, #e5e7eb)',
        boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.3), 0 8px 10px -6px rgba(0, 0, 0, 0.2)'
      }}
    >
      {menuItems.map((item, index) => (
        <button
          key={index}
          onClick={item.onClick}
          className={`w-full flex items-center gap-3 px-4 py-2.5 text-sm transition-all duration-150 ${
            item.danger
              ? 'hover:bg-red-50 dark:hover:bg-red-500/20 text-red-600 dark:text-red-400 hover:pl-5'
              : 'hover:bg-primary/10 dark:hover:bg-primary/20 hover:pl-5'
          }`}
          style={!item.danger ? { color: 'var(--color-text-primary)' } : undefined}
        >
          <span className="material-symbols-outlined text-lg">
            {item.icon}
          </span>
          <span className="font-medium">{item.label}</span>
        </button>
      ))}
    </div>
  );
}
