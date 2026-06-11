/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useEffect, useMemo, useState } from 'react';
import { ChevronDown, ChevronRight, File, Folder, FolderOpen, Loader2 } from 'lucide-react';
import apiClient from '@/lib/api-client';
import type { RepoFile } from '@/types/repository';
import { AddToKnowledgeButton } from './RepoFilePreview';

interface RepoFileTreeProps {
  repoId: number;
  selectedPath: string | null;
  onSelectFile: (path: string) => void;
}

type TreeNode = {
  name: string;
  path: string;
  type: 'dir' | 'file';
  size?: number;
  children?: TreeNode[];
};

function buildTree(files: RepoFile[]): TreeNode[] {
  const root: TreeNode = { name: '', path: '', type: 'dir', children: [] };

  for (const file of files) {
    const parts = file.path.split('/');
    let cursor = root;
    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];
      const isLeaf = i === parts.length - 1;
      const path = parts.slice(0, i + 1).join('/');
      cursor.children = cursor.children || [];
      let next = cursor.children.find((c) => c.name === part);
      if (!next) {
        next = isLeaf
          ? { name: part, path, type: 'file', size: file.size }
          : { name: part, path, type: 'dir', children: [] };
        cursor.children.push(next);
      }
      cursor = next;
    }
  }

  const sortChildren = (node: TreeNode) => {
    if (!node.children) return;
    node.children.sort((a, b) => {
      if (a.type !== b.type) return a.type === 'dir' ? -1 : 1;
      return a.name.localeCompare(b.name);
    });
    for (const child of node.children) sortChildren(child);
  };
  sortChildren(root);

  return root.children || [];
}

export default function RepoFileTree({ repoId, selectedPath, onSelectFile }: RepoFileTreeProps) {
  const [files, setFiles] = useState<RepoFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  useEffect(() => {
    const ac = new AbortController();
    setLoading(true);
    setError(null);
    apiClient
      .listRepositoryFiles(repoId, { signal: ac.signal })
      .then((res) => {
        setFiles(res.data.files || []);
        // Start fully collapsed — user expands the folders they care about.
        setExpanded(new Set());
      })
      .catch((err: any) => {
        if (err?.name === 'AbortError' || err?.name === 'CanceledError') return;
        setError('Failed to load files');
      })
      .finally(() => setLoading(false));
    return () => ac.abort();
  }, [repoId]);

  const tree = useMemo(() => buildTree(files), [files]);

  const toggle = (path: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 px-4 py-6 text-xs text-text-muted">
        <Loader2 size={14} className="animate-spin" />
        Loading files...
      </div>
    );
  }
  if (error) {
    return (
      <div className="px-4 py-6 text-xs" style={{ color: '#B3402F' }}>
        {error}
      </div>
    );
  }
  if (tree.length === 0) {
    return (
      <div className="px-4 py-6 text-xs text-text-muted">
        No indexable files in this repository.
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto py-2">
      {tree.map((node) => (
        <TreeRow
          key={node.path}
          node={node}
          depth={0}
          expanded={expanded}
          toggle={toggle}
          selectedPath={selectedPath}
          onSelectFile={onSelectFile}
          repoId={repoId}
        />
      ))}
    </div>
  );
}

function TreeRow({
  node,
  depth,
  expanded,
  toggle,
  selectedPath,
  onSelectFile,
  repoId,
}: {
  node: TreeNode;
  depth: number;
  expanded: Set<string>;
  toggle: (path: string) => void;
  selectedPath: string | null;
  onSelectFile: (path: string) => void;
  repoId: number;
}) {
  const isOpen = expanded.has(node.path);
  const isSelected = node.path === selectedPath;

  if (node.type === 'dir') {
    return (
      <>
        <div className="group w-full flex items-center gap-1 pr-2 text-xs text-text-primary transition-colors hover:bg-black/[0.04]">
          <button
            onClick={() => toggle(node.path)}
            className="flex items-center gap-1 py-1 text-left flex-1 min-w-0"
            style={{ paddingLeft: 8 + depth * 14 }}
          >
            {isOpen ? <ChevronDown size={12} className="shrink-0" /> : <ChevronRight size={12} className="shrink-0" />}
            {isOpen ? (
              <FolderOpen size={13} className="shrink-0 text-primary" />
            ) : (
              <Folder size={13} className="shrink-0 text-primary" />
            )}
            <span className="truncate">{node.name}</span>
          </button>
          <div className="opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
            <AddToKnowledgeButton repoId={repoId} path={node.path} kind="folder" compact />
          </div>
        </div>
        {isOpen &&
          node.children?.map((child) => (
            <TreeRow
              key={child.path}
              node={child}
              depth={depth + 1}
              expanded={expanded}
              toggle={toggle}
              selectedPath={selectedPath}
              onSelectFile={onSelectFile}
              repoId={repoId}
            />
          ))}
      </>
    );
  }

  return (
    <button
      onClick={() => onSelectFile(node.path)}
      className={`w-full flex items-center gap-1.5 px-2 py-1 text-left text-xs transition-colors ${
        isSelected
          ? 'bg-border-dark text-background-light font-semibold'
          : 'text-text-primary hover:bg-black/[0.04]'
      }`}
      style={{ paddingLeft: 8 + depth * 14 + 16 }}
    >
      <File size={13} className={`shrink-0 ${isSelected ? 'text-background-light' : 'text-text-muted'}`} />
      <span className="truncate">{node.name}</span>
    </button>
  );
}
