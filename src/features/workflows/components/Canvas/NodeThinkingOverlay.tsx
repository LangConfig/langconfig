/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * NodeThinkingOverlay Component
 *
 * Displays agent thinking/reasoning text in an expandable overlay.
 * Positioned adjacent to the node with smooth animations.
 *
 * Features:
 * - Brief preview (first 50 chars) with expand button
 * - Expandable full text view with syntax highlighting
 * - Auto-scrolls to new content as thinking streams in
 * - Professional minimalist design using theme system
 * - Smooth transitions and animations
 *
 * Usage:
 *   <NodeThinkingOverlay
 *     thinking="Agent is analyzing the problem..."
 *     thinkingPreview="Agent is analyzing..."
 *     isActive={status.state === 'thinking'}
 *     nodePosition={{ x: 100, y: 200 }}
 *   />
 */

import { useState, useEffect, useRef } from 'react';
import { Brain, ChevronDown, ChevronUp, X } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import 'highlight.js/styles/github-dark.css';

export interface NodeThinkingOverlayProps {
  /** Full thinking/reasoning text */
  thinking: string;

  /** Abbreviated preview (first 50 chars) */
  thinkingPreview: string;

  /** Whether agent is actively thinking */
  isActive: boolean;

  /** Node position for overlay positioning */
  nodePosition?: { x: number; y: number };

  /** Optional custom z-index */
  zIndex?: number;

  /** Callback when overlay is closed */
  onClose?: () => void;
}

export default function NodeThinkingOverlay({
  thinking,
  thinkingPreview,
  isActive,
  nodePosition,
  zIndex = 1000,
  onClose,
}: NodeThinkingOverlayProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const overlayRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new thinking arrives
  useEffect(() => {
    if (isExpanded && overlayRef.current) {
      overlayRef.current.scrollTo({
        top: overlayRef.current.scrollHeight,
        behavior: 'smooth',
      });
    }
  }, [thinking, isExpanded]);

  // Don't render if no thinking text
  if (!thinking && !thinkingPreview) {
    return null;
  }

  return (
    <div
      className="absolute mt-2 w-full min-w-[300px] max-w-[500px] animate-fadeIn"
      style={{
        top: '100%',
        left: 0,
        zIndex,
      }}
    >
      {/* Pointer triangle (speech bubble effect) */}
      <div
        className="absolute -top-2 left-6 w-0 h-0"
        style={{
          borderLeft: '8px solid transparent',
          borderRight: '8px solid transparent',
          borderBottom: '8px solid var(--color-border-dark)',
        }}
      />
      <div
        className="absolute -top-[7px] left-[25px] w-0 h-0"
        style={{
          borderLeft: '7px solid transparent',
          borderRight: '7px solid transparent',
          borderBottom: '7px solid var(--color-panel-dark)',
        }}
      />

      {/* Overlay container */}
      <div
        className="rounded-lg shadow-2xl border transition-all duration-300"
        style={{
          backgroundColor: 'var(--color-panel-dark)',
          borderColor: 'var(--color-border-dark)',
        }}
      >
        {/* Header with brain icon */}
        <div
          className="flex items-center justify-between px-4 py-2.5 border-b"
          style={{
            borderBottomColor: 'var(--color-border-dark)',
          }}
        >
          <div className="flex items-center gap-2">
            <Brain
              className={`w-4 h-4 transition-all ${isActive ? 'animate-pulse' : ''}`}
              style={{ color: 'var(--color-primary)' }}
            />
            <span
              className="text-sm font-semibold"
              style={{ color: 'var(--color-text-primary)' }}
            >
              {isActive ? 'Thinking...' : 'Agent Reasoning'}
            </span>
          </div>

          <div className="flex items-center gap-1">
            {/* Expand/Collapse button */}
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="p-1 rounded hover:bg-gray-700/50 transition-colors"
              aria-label={isExpanded ? 'Collapse' : 'Expand'}
            >
              {isExpanded ? (
                <ChevronUp className="w-4 h-4" style={{ color: 'var(--color-text-muted)' }} />
              ) : (
                <ChevronDown className="w-4 h-4" style={{ color: 'var(--color-text-muted)' }} />
              )}
            </button>

            {/* Close button */}
            {onClose && (
              <button
                onClick={onClose}
                className="p-1 rounded hover:bg-gray-700/50 transition-colors"
                aria-label="Close"
              >
                <X className="w-4 h-4" style={{ color: 'var(--color-text-muted)' }} />
              </button>
            )}
          </div>
        </div>

        {/* Content area */}
        <div
          ref={overlayRef}
          className="overflow-y-auto transition-all duration-300"
          style={{
            maxHeight: isExpanded ? '400px' : '120px',
            fontSize: '13px',
            fontFamily: 'monospace',
          }}
        >
          {isExpanded ? (
            // Full thinking text with Markdown rendering
            <div className="p-4">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                rehypePlugins={[rehypeHighlight]}
                components={{
                  // Style Markdown elements with theme colors
                  p: ({ children }) => (
                    <p
                      className="mb-2 leading-relaxed"
                      style={{ color: 'var(--color-text-primary)' }}
                    >
                      {children}
                    </p>
                  ),
                  code: ({ inline, children, ...props }: any) =>
                    inline ? (
                      <code
                        className="px-1.5 py-0.5 rounded text-xs"
                        style={{
                          backgroundColor: 'var(--color-background-dark)',
                          color: 'var(--color-primary)',
                        }}
                        {...props}
                      >
                        {children}
                      </code>
                    ) : (
                      <code
                        className="block p-2 rounded text-xs overflow-x-auto"
                        style={{
                          backgroundColor: 'var(--color-background-dark)',
                        }}
                        {...props}
                      >
                        {children}
                      </code>
                    ),
                  ul: ({ children }) => (
                    <ul
                      className="list-disc list-inside mb-2 space-y-1"
                      style={{ color: 'var(--color-text-primary)' }}
                    >
                      {children}
                    </ul>
                  ),
                  ol: ({ children }) => (
                    <ol
                      className="list-decimal list-inside mb-2 space-y-1"
                      style={{ color: 'var(--color-text-primary)' }}
                    >
                      {children}
                    </ol>
                  ),
                  li: ({ children }) => (
                    <li style={{ color: 'var(--color-text-primary)' }}>{children}</li>
                  ),
                }}
              >
                {thinking}
              </ReactMarkdown>

              {/* Blinking cursor if actively thinking */}
              {isActive && (
                <span
                  className="inline-block w-2 h-4 ml-1 align-text-bottom animate-blink"
                  style={{ backgroundColor: 'var(--color-primary)' }}
                />
              )}
            </div>
          ) : (
            // Brief preview
            <div className="p-4">
              <p
                className="leading-relaxed"
                style={{ color: 'var(--color-text-primary)' }}
              >
                {thinkingPreview}
              </p>

              {/* Blinking cursor if actively thinking */}
              {isActive && (
                <span
                  className="inline-block w-2 h-4 ml-1 align-text-bottom animate-blink"
                  style={{ backgroundColor: 'var(--color-primary)' }}
                />
              )}

              {/* "Expand to read more" hint */}
              {thinking.length > thinkingPreview.length && (
                <button
                  onClick={() => setIsExpanded(true)}
                  className="mt-2 text-xs underline hover:no-underline transition-all"
                  style={{ color: 'var(--color-primary)' }}
                >
                  Expand to read more
                </button>
              )}
            </div>
          )}
        </div>

        {/* Footer with character count (optional, for expanded view) */}
        {isExpanded && thinking.length > 100 && (
          <div
            className="px-4 py-2 border-t text-xs"
            style={{
              borderTopColor: 'var(--color-border-dark)',
              color: 'var(--color-text-muted)',
            }}
          >
            {thinking.length} characters
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Compact inline thinking indicator (alternative to overlay)
 * Useful for minimal space usage
 */
export function NodeThinkingBadge({
  thinkingPreview,
  isActive,
  onClick,
}: {
  thinkingPreview: string;
  isActive: boolean;
  onClick?: () => void;
}) {
  if (!thinkingPreview) return null;

  return (
    <div
      className="mt-2 px-2 py-1.5 rounded-lg border-l-2 cursor-pointer hover:bg-opacity-20 transition-all"
      style={{
        backgroundColor: isActive ? 'rgba(19, 91, 236, 0.1)' : 'rgba(146, 164, 201, 0.1)',
        borderLeftColor: isActive ? 'var(--color-primary)' : 'var(--color-text-muted)',
      }}
      onClick={onClick}
    >
      <div className="flex items-center gap-2">
        <Brain
          className={`w-3.5 h-3.5 flex-shrink-0 ${isActive ? 'animate-pulse' : ''}`}
          style={{ color: isActive ? 'var(--color-primary)' : 'var(--color-text-muted)' }}
        />
        <span
          className="text-xs leading-tight truncate"
          style={{ color: 'var(--color-text-primary)' }}
        >
          {thinkingPreview}
        </span>
      </div>
    </div>
  );
}
