/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * ThinkingToast Component
 *
 * Elegant toast-style notifications with anime.js powered cascade animations.
 * Displays agent thinking with smooth character-by-character reveal and flow.
 *
 * Features:
 * - Anime.js character cascade with stagger delays
 * - Markdown stripping for clean text display
 * - Sliding vertical motion (stream of consciousness)
 * - Glass-morphism design
 * - Text windowing (shows only recent thoughts)
 *
 * Usage:
 *   <ThinkingToast
 *     text="Agent is analyzing the problem..."
 *     nodePosition={{ x: 100, y: 200 }}
 *     isVisible={true}
 *     agentName="Research Agent"
 *   />
 */

import { useEffect, useState, useRef } from 'react';
import { Brain, Wrench, CheckCircle } from 'lucide-react';

export interface ThinkingToastProps {
  /** Full thinking text to display */
  text: string;

  /** Position of the node (ReactFlow coordinates) */
  nodePosition: { x: number; y: number };

  /** Whether the toast should be visible */
  isVisible: boolean;

  /** Name of the agent (optional) */
  agentName?: string;

  /** Current execution state (optional) */
  executionState?: 'running' | 'thinking' | 'completed' | 'error';

  /** Active tool being used (optional) */
  activeTool?: string;

  /** Recently completed tool (optional) */
  toolCompleted?: string;

  /** Current zoom level from ReactFlow (optional) */
  zoom?: number;

  /** Node width to match (optional) */
  nodeWidth?: number;

  /** Callback when animation completes and toast should be removed */
  onDismiss?: () => void;
}

// Helper: Strip markdown formatting for clean display
function stripMarkdown(text: string): string {
  return text
    .replace(/(\*\*\*|___)(.*?)\1/g, '$2') // Bold italic
    .replace(/(\*\*|__)(.*?)\1/g, '$2')    // Bold
    .replace(/(\*|_)(.*?)\1/g, '$2')       // Italic
    .replace(/`{1,3}[^`\n]+`{1,3}/g, (match) => match.replace(/`/g, '')) // Code
    .replace(/#{1,6}\s?/g, '')             // Headers
    .replace(/>\s?/g, '')                  // Blockquotes
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1') // Links
    .trim();
}

export default function ThinkingToast({
  text,
  nodePosition,
  isVisible,
  agentName = 'Agent',
  activeTool,
  toolCompleted,
  zoom = 1,
  nodeWidth = 200,
  onDismiss,
}: ThinkingToastProps) {
  const [displayedText, setDisplayedText] = useState('');
  const [visibleChars, setVisibleChars] = useState(0);
  const previousTextLengthRef = useRef(0);
  const textContainerRef = useRef<HTMLDivElement>(null);
  const textContentRef = useRef<HTMLDivElement>(null);
  const typewriterIntervalRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pauseTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Remove hidden/system tags that should never be visible
  const sanitizeHiddenTags = (t: string): string =>
    t
      .replace(/<think>[\s\S]*?<\/think>/g, '')
      .replace(/<function_results>[\s\S]*?<\/function_results>/g, '')
      .replace(/<function_calls>[\s\S]*?<\/function_calls>/g, '')
      .replace(/<tool_response>[\s\S]*?<\/tool_response>/g, '')
      .replace(/<system>[\s\S]*?<\/system>/g, '')
      .replace(/<\/?(result|source|title|content|function_call)[^>]*>/g, '');

  useEffect(() => {
    if (isVisible && text) {
      const cleanText = sanitizeHiddenTags(stripMarkdown(text));
      const previousLength = previousTextLengthRef.current;

      if (cleanText.length < previousLength) {
        // Text got shorter - reset everything
        setVisibleChars(0);
        previousTextLengthRef.current = 0;
      } else if (visibleChars < previousLength) {
        // We haven't finished typing the previous text yet
        // Keep the current visibleChars count
      } else {
        // Text grew - keep what's already visible
        setVisibleChars(previousLength);
      }

      setDisplayedText(cleanText);
      previousTextLengthRef.current = cleanText.length;

      // Clear any existing intervals/timeouts
      if (typewriterIntervalRef.current) {
        clearInterval(typewriterIntervalRef.current);
      }
      if (pauseTimeoutRef.current) {
        clearTimeout(pauseTimeoutRef.current);
      }

      // Show immediately - no typewriter effect
      setVisibleChars(cleanText.length);
    } else if (!isVisible) {
      if (typewriterIntervalRef.current) {
        clearInterval(typewriterIntervalRef.current);
      }
      if (pauseTimeoutRef.current) {
        clearTimeout(pauseTimeoutRef.current);
      }
      setDisplayedText('');
      setVisibleChars(0);
      previousTextLengthRef.current = 0;
      if (onDismiss) {
        onDismiss();
      }
    }

    return () => {
      if (typewriterIntervalRef.current) {
        clearInterval(typewriterIntervalRef.current);
      }
      if (pauseTimeoutRef.current) {
        clearTimeout(pauseTimeoutRef.current);
      }
    };
  }, [text, isVisible, onDismiss]);

  // Auto-scroll to bottom when visible chars increase
  useEffect(() => {
    if (textContentRef.current) {
      textContentRef.current.scrollTop = textContentRef.current.scrollHeight;
    }
  }, [visibleChars]);

  // Don't render if no text AND no tool activity
  if (!text && !displayedText && !activeTool && !toolCompleted) {
    return null;
  }

  // Don't render if node position is invalid (prevents SVG NaN errors)
  if (!nodePosition ||
      typeof nodePosition.x !== 'number' ||
      typeof nodePosition.y !== 'number' ||
      isNaN(nodePosition.x) ||
      isNaN(nodePosition.y)) {
    return null;
  }

  // Calculate centered position directly to avoid transform snapping
  const toastWidth = Math.min(Math.max(nodeWidth * 2, 400), 600); // Same calculation as in style
  const centeredX = nodePosition.x - (toastWidth / 2);

  return (
    <div
      ref={textContainerRef}
      className="pointer-events-none"
      style={{
        position: 'fixed', // Use fixed positioning for screen coordinates
        left: `${centeredX}px`,
        top: `${nodePosition.y}px`,
        transform: `scale(${zoom})`, // Only scale, no translate
        transformOrigin: 'top center', // Scale from top center point
        // No background - just floating text
        zIndex: 1000,
        width: `${Math.max(nodeWidth * 2, 400)}px`, // Much wider - 2x node width or min 400px
        maxWidth: '600px', // Allow wider toasts for more text
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center', // Center all children horizontally
        transition: 'none', // IMPORTANT: Disable position transitions to prevent sliding between nodes
      }}
    >
        {/* Tool Status Header - Centered */}
        {(activeTool || toolCompleted) && (
          <div className="inline-flex items-center gap-1.5 mb-2 px-2 py-1 rounded-full"
               style={{
                 backgroundColor: 'rgba(255, 255, 255, 0.95)',
                 backdropFilter: 'blur(12px)',
                 boxShadow: '0 2px 6px rgba(0, 0, 0, 0.12), 0 1px 2px rgba(0, 0, 0, 0.08)',
                 border: '1px solid rgba(0, 0, 0, 0.06)',
                 fontSize: '13px', // Increased from 11px for better visibility
                 alignSelf: 'center' // Ensure it's centered even if parent isn't flex
               }}>
            {activeTool && (
              <>
                <div className="relative">
                  <Wrench
                    className="w-3 h-3 animate-spin flex-shrink-0"
                    style={{ color: '#f59e0b' }}
                  />
                  <div className="absolute inset-0 w-3 h-3 animate-ping"
                       style={{
                         backgroundColor: '#f59e0b',
                         opacity: 0.3,
                         borderRadius: '50%'
                       }} />
                </div>
                <span className="font-semibold tracking-wide uppercase"
                      style={{
                        color: '#92400e',
                        letterSpacing: '0.03em',
                        fontSize: 'inherit'
                      }}>
                  {activeTool}
                </span>
              </>
            )}
            {!activeTool && toolCompleted && (
              <>
                <CheckCircle
                  className="w-3 h-3 flex-shrink-0"
                  style={{ color: '#10b981' }}
                />
                <span className="font-medium" style={{
                  color: '#047857',
                  fontSize: 'inherit'
                }}>
                  {toolCompleted} completed
                </span>
              </>
            )}
          </div>
        )}

        {/* Thinking text with character-by-character animation - Only show if there's text */}
        {displayedText && (
          <>
            {/* Agent label if no tool status shown - centered */}
            {!activeTool && !toolCompleted && (
              <div className="inline-flex items-center gap-1.5 mb-2 px-2 py-1 rounded-full"
                   style={{
                     backgroundColor: 'rgba(255, 255, 255, 0.95)',
                     backdropFilter: 'blur(12px)',
                     boxShadow: '0 2px 6px rgba(0, 0, 0, 0.12), 0 1px 2px rgba(0, 0, 0, 0.08)',
                     border: '1px solid rgba(0, 0, 0, 0.06)',
                     fontSize: '13px', // Increased from 11px for better visibility
                     alignSelf: 'center' // Ensure it's centered
                   }}>
                <Brain
                  className="w-3 h-3 flex-shrink-0"
                  style={{
                    color: '#6366f1',
                    animation: 'breathe 2s ease-in-out infinite' // Organic breathing animation
                  }}
                />
                <span className="font-medium"
                      style={{
                        color: '#4f46e5',
                        letterSpacing: '0.02em',
                        fontSize: 'inherit'
                      }}>
                  {agentName} is thinking
                </span>
              </div>
            )}

            <div
              ref={textContentRef}
              className="text-sm leading-snug px-1"
              style={{
                fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
                color: '#111827', // Black text
                fontWeight: 600, // Bolder for visibility
                fontSize: '16px', // Increased from 13px for better readability
                lineHeight: '1.6', // Adjusted line height proportionally
                letterSpacing: '0.01em',
                wordBreak: 'keep-all', // Never break words mid-word
                overflowWrap: 'normal', // Don't force-wrap words
                whiteSpace: 'pre-wrap', // Preserve spaces and wrap at natural boundaries
                textAlign: 'left', // Left align for natural reading flow
                width: '100%', // Take full width for text to flow naturally
                maxHeight: '120px', // Compact height to avoid blocking view
                overflowY: 'auto', // Scroll when too much text
                scrollBehavior: 'smooth', // Smooth auto-scroll
                scrollbarWidth: 'none', // Hide scrollbar (Firefox)
                msOverflowStyle: 'none', // Hide scrollbar (IE/Edge)
                display: 'flex',
                flexWrap: 'wrap',
                justifyContent: 'center', // Center the character spans
                textShadow: `
                  0 0 1px rgba(255, 255, 255, 0.8),
                  0 0 2px rgba(255, 255, 255, 0.8),
                  0 0 3px rgba(255, 255, 255, 0.6),
                  0 1px 2px rgba(0, 0, 0, 0.1)
                `, // White glow for contrast against any background
                filter: 'drop-shadow(0 1px 2px rgba(0, 0, 0, 0.15))',
              }}
            >
              {/* Simple typewriter - show only visible characters */}
              {displayedText.substring(0, visibleChars)}

              {/* Hide scrollbar for WebKit browsers */}
              <style>{
                `
                div::-webkit-scrollbar {
                  display: none;
                }
                `
              }</style>
            </div>
          </>
        )}
      </div>
  );
}
