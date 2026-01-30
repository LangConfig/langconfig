/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * FolderTree Component
 *
 * Hierarchical folder navigation for workspace files.
 * Shows files organized by workflow -> task structure.
 */

import { useState, useCallback, useMemo } from 'react';
import { ChevronRight, ChevronDown, Folder, FolderOpen, FileText, Bot, Hash } from 'lucide-react';
import { getFileIcon } from '../utils/fileHelpers';

export interface TreeNode {
  id: string;
  name: string;
  type: 'workflow' | 'task' | 'file';
  path?: string;
  children?: TreeNode[];
  metadata?: {
    id?: number;
    workflow_id?: number;
    task_id?: number;
    file_count?: number;
    task_count?: number;
    size_bytes?: number;
    extension?: string;
    agent_label?: string;
    created_at?: string;
  };
}

interface FolderTreeProps {
  tree: TreeNode[];
  loading?: boolean;
  selectedFileId?: number | null;
  onFileSelect: (node: TreeNode) => void;
  className?: string;
}

interface TreeItemProps {
  node: TreeNode;
  depth: number;
  selectedFileId?: number | null;
  expandedNodes: Set<string>;
  onToggle: (id: string) => void;
  onFileSelect: (node: TreeNode) => void;
}

function TreeItem({
  node,
  depth,
  selectedFileId,
  expandedNodes,
  onToggle,
  onFileSelect,
}: TreeItemProps) {
  const isExpanded = expandedNodes.has(node.id);
  const hasChildren = node.children && node.children.length > 0;
  const isSelected = node.type === 'file' && node.metadata?.id === selectedFileId;

  const handleClick = useCallback(() => {
    if (node.type === 'file') {
      onFileSelect(node);
    } else if (hasChildren) {
      onToggle(node.id);
    }
  }, [node, hasChildren, onToggle, onFileSelect]);

  const renderIcon = () => {
    if (node.type === 'file') {
      const extension = node.metadata?.extension || '';
      return <span className="text-base">{getFileIcon(extension)}</span>;
    }

    if (node.type === 'workflow') {
      return isExpanded ? (
        <FolderOpen className="w-4 h-4" style={{ color: 'var(--color-primary)' }} />
      ) : (
        <Folder className="w-4 h-4" style={{ color: 'var(--color-primary)' }} />
      );
    }

    // Task folder
    return isExpanded ? (
      <FolderOpen className="w-4 h-4" style={{ color: 'var(--color-text-muted)' }} />
    ) : (
      <Folder className="w-4 h-4" style={{ color: 'var(--color-text-muted)' }} />
    );
  };

  const renderBadge = () => {
    if (node.type === 'workflow' && node.metadata?.file_count) {
      return (
        <span
          className="ml-auto text-xs px-1.5 py-0.5 rounded-full"
          style={{ backgroundColor: 'var(--color-primary)', color: 'white', opacity: 0.9 }}
        >
          {node.metadata.file_count}
        </span>
      );
    }
    if (node.type === 'task' && node.metadata?.file_count) {
      return (
        <span
          className="ml-auto text-xs px-1.5 py-0.5 rounded-full"
          style={{ backgroundColor: 'var(--color-border-dark)', color: 'var(--color-text-muted)' }}
        >
          {node.metadata.file_count}
        </span>
      );
    }
    if (node.type === 'file' && node.metadata?.agent_label) {
      return (
        <span title={`Created by ${node.metadata.agent_label}`}>
          <Bot
            className="ml-auto w-3.5 h-3.5"
            style={{ color: 'var(--color-text-muted)' }}
          />
        </span>
      );
    }
    return null;
  };

  return (
    <>
      <div
        onClick={handleClick}
        className={`flex items-center gap-2 px-2 py-1.5 rounded-md cursor-pointer transition-colors ${
          isSelected
            ? 'bg-primary/10 ring-1 ring-primary/30'
            : 'hover:bg-white/5'
        }`}
        style={{ paddingLeft: `${8 + Math.min(depth, 5) * 16}px` }}
        title={depth > 5 ? `Depth: ${depth}` : undefined}
      >
        {/* Depth indicator for deeply nested items */}
        {depth > 5 && (
          <span
            className="flex-shrink-0 text-[10px] px-1 rounded"
            style={{ backgroundColor: 'var(--color-border-dark)', color: 'var(--color-text-muted)' }}
            title={`Nested ${depth} levels deep`}
          >
            +{depth - 5}
          </span>
        )}

        {/* Expand/Collapse chevron */}
        {hasChildren ? (
          <span className="flex-shrink-0 w-4 h-4 flex items-center justify-center">
            {isExpanded ? (
              <ChevronDown className="w-3.5 h-3.5" style={{ color: 'var(--color-text-muted)' }} />
            ) : (
              <ChevronRight className="w-3.5 h-3.5" style={{ color: 'var(--color-text-muted)' }} />
            )}
          </span>
        ) : (
          <span className="flex-shrink-0 w-4" />
        )}

        {/* Icon */}
        <span className="flex-shrink-0">{renderIcon()}</span>

        {/* Name */}
        <span
          className={`flex-1 truncate text-sm ${isSelected ? 'font-medium' : ''}`}
          style={{ color: isSelected ? 'var(--color-primary)' : 'var(--color-text-primary)' }}
          title={node.name}
        >
          {node.name}
        </span>

        {/* Badge */}
        {renderBadge()}
      </div>

      {/* Children */}
      {hasChildren && isExpanded && (
        <div>
          {node.children!.map((child) => (
            <TreeItem
              key={child.id}
              node={child}
              depth={depth + 1}
              selectedFileId={selectedFileId}
              expandedNodes={expandedNodes}
              onToggle={onToggle}
              onFileSelect={onFileSelect}
            />
          ))}
        </div>
      )}
    </>
  );
}

export default function FolderTree({
  tree,
  loading,
  selectedFileId,
  onFileSelect,
  className = '',
}: FolderTreeProps) {
  // Start with all workflow/task nodes expanded
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(() => {
    const expanded = new Set<string>();
    const expandAll = (nodes: TreeNode[]) => {
      nodes.forEach((node) => {
        if (node.type !== 'file') {
          expanded.add(node.id);
          if (node.children) {
            expandAll(node.children);
          }
        }
      });
    };
    expandAll(tree);
    return expanded;
  });

  const handleToggle = useCallback((id: string) => {
    setExpandedNodes((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  // Count total files
  const totalFiles = useMemo(() => {
    let count = 0;
    const countFiles = (nodes: TreeNode[]) => {
      nodes.forEach((node) => {
        if (node.type === 'file') {
          count++;
        } else if (node.children) {
          countFiles(node.children);
        }
      });
    };
    countFiles(tree);
    return count;
  }, [tree]);

  if (loading) {
    return (
      <div className={`flex flex-col ${className}`}>
        <div className="p-4 flex items-center justify-center">
          <div
            className="animate-spin rounded-full h-6 w-6 border-b-2"
            style={{ borderColor: 'var(--color-primary)' }}
          />
        </div>
      </div>
    );
  }

  if (tree.length === 0) {
    return (
      <div className={`flex flex-col items-center justify-center py-8 ${className}`}>
        <Folder className="w-8 h-8 mb-2" style={{ color: 'var(--color-text-muted)', opacity: 0.5 }} />
        <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
          No files found
        </p>
      </div>
    );
  }

  return (
    <div className={`flex flex-col ${className}`}>
      {/* Header */}
      <div
        className="px-4 py-2 border-b flex items-center justify-between"
        style={{ borderColor: 'var(--color-border-dark)' }}
      >
        <span className="text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>
          Files
        </span>
        <span
          className="text-xs px-2 py-0.5 rounded-full"
          style={{ backgroundColor: 'var(--color-border-dark)', color: 'var(--color-text-muted)' }}
        >
          {totalFiles}
        </span>
      </div>

      {/* Tree */}
      <div className="flex-1 overflow-y-auto overflow-x-auto py-2">
        {tree.map((node) => (
          <TreeItem
            key={node.id}
            node={node}
            depth={0}
            selectedFileId={selectedFileId}
            expandedNodes={expandedNodes}
            onToggle={handleToggle}
            onFileSelect={onFileSelect}
          />
        ))}
      </div>
    </div>
  );
}
