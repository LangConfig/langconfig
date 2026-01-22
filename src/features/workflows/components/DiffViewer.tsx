/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * DiffViewer Component
 *
 * Displays file diffs in unified or split (side-by-side) view.
 * Supports syntax highlighting for diff lines.
 */

import { useState, useMemo, useRef, useCallback } from 'react';
import { SplitSquareVertical, AlignJustify, Plus, Minus, FileText } from 'lucide-react';

export interface DiffStats {
  lines_added: number;
  lines_removed: number;
  lines_changed: number;
  total_changes: number;
  similarity_ratio: number;
}

export interface SideBySideLine {
  left_num: number | null;
  left_content: string | null;
  left_type: 'normal' | 'removed' | 'empty';
  right_num: number | null;
  right_content: string | null;
  right_type: 'normal' | 'added' | 'empty';
}

interface DiffViewerProps {
  filename: string;
  unifiedDiff: string;
  sideBySide: SideBySideLine[];
  stats: DiffStats;
  v1Label?: string;
  v2Label?: string;
  defaultViewMode?: 'unified' | 'split';
  className?: string;
}

// Split view component with synchronized scrolling
function SplitDiffView({
  sideBySide,
  v1Label,
  v2Label,
  getSideBySideStyle,
}: {
  sideBySide: SideBySideLine[];
  v1Label: string;
  v2Label: string;
  getSideBySideStyle: (type: string) => React.CSSProperties;
}) {
  const leftRef = useRef<HTMLDivElement>(null);
  const rightRef = useRef<HTMLDivElement>(null);
  const isScrolling = useRef(false);

  const handleScroll = useCallback((source: 'left' | 'right') => {
    if (isScrolling.current) return;
    isScrolling.current = true;

    const sourceEl = source === 'left' ? leftRef.current : rightRef.current;
    const targetEl = source === 'left' ? rightRef.current : leftRef.current;

    if (sourceEl && targetEl) {
      targetEl.scrollTop = sourceEl.scrollTop;
    }

    requestAnimationFrame(() => {
      isScrolling.current = false;
    });
  }, []);

  return (
    <div className="flex h-full">
      {/* Left side (original) */}
      <div
        ref={leftRef}
        onScroll={() => handleScroll('left')}
        className="w-1/2 overflow-auto border-r"
        style={{ borderColor: 'var(--color-border-dark)' }}
      >
        <div
          className="sticky top-0 px-4 py-2 text-xs font-medium border-b z-10"
          style={{
            backgroundColor: 'var(--color-bg-surface)',
            borderColor: 'var(--color-border-dark)',
            color: 'var(--color-text-muted)',
          }}
        >
          {v1Label}
        </div>
        <div className="font-mono text-sm">
          {sideBySide.map((line, index) => (
            <div
              key={index}
              className="flex"
              style={getSideBySideStyle(line.left_type)}
            >
              <span
                className="min-w-[3rem] px-2 py-0.5 text-right select-none border-r flex-shrink-0"
                style={{
                  backgroundColor: 'rgba(0, 0, 0, 0.1)',
                  borderColor: 'var(--color-border-dark)',
                  color: 'var(--color-text-muted)',
                }}
              >
                {line.left_num ?? ''}
              </span>
              <span
                className="flex-1 px-2 py-0.5 whitespace-pre-wrap break-words"
                style={{
                  color: line.left_type === 'removed' ? '#ef4444' : 'var(--color-text-primary)',
                }}
              >
                {line.left_content ?? ''}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Right side (modified) */}
      <div
        ref={rightRef}
        onScroll={() => handleScroll('right')}
        className="w-1/2 overflow-auto"
      >
        <div
          className="sticky top-0 px-4 py-2 text-xs font-medium border-b z-10"
          style={{
            backgroundColor: 'var(--color-bg-surface)',
            borderColor: 'var(--color-border-dark)',
            color: 'var(--color-text-muted)',
          }}
        >
          {v2Label}
        </div>
        <div className="font-mono text-sm">
          {sideBySide.map((line, index) => (
            <div
              key={index}
              className="flex"
              style={getSideBySideStyle(line.right_type)}
            >
              <span
                className="min-w-[3rem] px-2 py-0.5 text-right select-none border-r flex-shrink-0"
                style={{
                  backgroundColor: 'rgba(0, 0, 0, 0.1)',
                  borderColor: 'var(--color-border-dark)',
                  color: 'var(--color-text-muted)',
                }}
              >
                {line.right_num ?? ''}
              </span>
              <span
                className="flex-1 px-2 py-0.5 whitespace-pre-wrap break-words"
                style={{
                  color: line.right_type === 'added' ? '#22c55e' : 'var(--color-text-primary)',
                }}
              >
                {line.right_content ?? ''}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function DiffViewer({
  filename,
  unifiedDiff,
  sideBySide,
  stats,
  v1Label = 'Version 1',
  v2Label = 'Version 2',
  defaultViewMode = 'unified',
  className = '',
}: DiffViewerProps) {
  const [viewMode, setViewMode] = useState<'unified' | 'split'>(defaultViewMode);

  // Parse unified diff into colored lines
  const unifiedLines = useMemo(() => {
    if (!unifiedDiff) return [];

    return unifiedDiff.split('\n').map((line, index) => {
      let type: 'header' | 'add' | 'remove' | 'context' | 'hunk' = 'context';

      if (line.startsWith('+++') || line.startsWith('---')) {
        type = 'header';
      } else if (line.startsWith('@@')) {
        type = 'hunk';
      } else if (line.startsWith('+')) {
        type = 'add';
      } else if (line.startsWith('-')) {
        type = 'remove';
      }

      return { content: line, type, index };
    });
  }, [unifiedDiff]);

  const getLineStyle = (type: string) => {
    switch (type) {
      case 'add':
        return { backgroundColor: 'rgba(34, 197, 94, 0.15)', color: '#22c55e' };
      case 'remove':
        return { backgroundColor: 'rgba(239, 68, 68, 0.15)', color: '#ef4444' };
      case 'header':
        return { backgroundColor: 'rgba(59, 130, 246, 0.1)', color: '#3b82f6', fontWeight: 'bold' };
      case 'hunk':
        return { backgroundColor: 'rgba(168, 85, 247, 0.1)', color: '#a855f7' };
      default:
        return { color: 'var(--color-text-primary)' };
    }
  };

  const getSideBySideStyle = (type: string) => {
    switch (type) {
      case 'added':
        return { backgroundColor: 'rgba(34, 197, 94, 0.15)' };
      case 'removed':
        return { backgroundColor: 'rgba(239, 68, 68, 0.15)' };
      case 'empty':
        return { backgroundColor: 'rgba(255, 255, 255, 0.02)' };
      default:
        return {};
    }
  };

  return (
    <div className={`flex flex-col h-full ${className}`}>
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-3 border-b"
        style={{ borderColor: 'var(--color-border-dark)' }}
      >
        <div className="flex items-center gap-3">
          <FileText className="w-5 h-5" style={{ color: 'var(--color-text-muted)' }} />
          <span className="font-medium" style={{ color: 'var(--color-text-primary)' }}>
            {filename}
          </span>

          {/* Stats badges */}
          <div className="flex items-center gap-2 ml-4">
            <span
              className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full"
              style={{ backgroundColor: 'rgba(34, 197, 94, 0.2)', color: '#22c55e' }}
            >
              <Plus className="w-3 h-3" />
              {stats.lines_added}
            </span>
            <span
              className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full"
              style={{ backgroundColor: 'rgba(239, 68, 68, 0.2)', color: '#ef4444' }}
            >
              <Minus className="w-3 h-3" />
              {stats.lines_removed}
            </span>
            <span
              className="text-xs px-2 py-0.5 rounded-full"
              style={{ backgroundColor: 'var(--color-border-dark)', color: 'var(--color-text-muted)' }}
            >
              {stats.similarity_ratio}% similar
            </span>
          </div>
        </div>

        {/* View mode toggle */}
        <div
          className="flex rounded-lg overflow-hidden border"
          style={{ borderColor: 'var(--color-border-dark)' }}
        >
          <button
            onClick={() => setViewMode('unified')}
            className={`px-3 py-1.5 flex items-center gap-1.5 text-sm transition-colors ${
              viewMode === 'unified' ? 'bg-primary/20' : 'hover:bg-white/5'
            }`}
            style={{ color: viewMode === 'unified' ? 'var(--color-primary)' : 'var(--color-text-muted)' }}
            title="Unified view"
          >
            <AlignJustify className="w-4 h-4" />
            Unified
          </button>
          <button
            onClick={() => setViewMode('split')}
            className={`px-3 py-1.5 flex items-center gap-1.5 text-sm transition-colors border-l ${
              viewMode === 'split' ? 'bg-primary/20' : 'hover:bg-white/5'
            }`}
            style={{
              color: viewMode === 'split' ? 'var(--color-primary)' : 'var(--color-text-muted)',
              borderColor: 'var(--color-border-dark)',
            }}
            title="Split view"
          >
            <SplitSquareVertical className="w-4 h-4" />
            Split
          </button>
        </div>
      </div>

      {/* Diff Content */}
      <div className="flex-1 overflow-auto">
        {viewMode === 'unified' ? (
          /* Unified View */
          <div className="font-mono text-sm">
            {unifiedLines.length === 0 ? (
              <div className="p-8 text-center" style={{ color: 'var(--color-text-muted)' }}>
                No differences to display
              </div>
            ) : (
              unifiedLines.map((line) => (
                <div
                  key={line.index}
                  className="px-4 py-0.5 whitespace-pre-wrap break-words"
                  style={getLineStyle(line.type)}
                >
                  {line.content || ' '}
                </div>
              ))
            )}
          </div>
        ) : (
          /* Split View with synchronized scrolling */
          <SplitDiffView
            sideBySide={sideBySide}
            v1Label={v1Label}
            v2Label={v2Label}
            getSideBySideStyle={getSideBySideStyle}
          />
        )}
      </div>
    </div>
  );
}
