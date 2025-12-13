/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useCallback } from 'react';

type ResultsSubTab = 'output' | 'memory' | 'files';

export function useResultsState() {
  // Results sub-tab navigation
  const [resultsSubTab, setResultsSubTab] = useState<ResultsSubTab>('output');

  // Output display options
  const [copiedToClipboard, setCopiedToClipboard] = useState(false);
  const [showRawOutput, setShowRawOutput] = useState(false);
  const [showAnimatedReveal, setShowAnimatedReveal] = useState(true);

  // Expanded tool calls tracking (for detailed view)
  const [expandedToolCalls, setExpandedToolCalls] = useState<Set<number>>(new Set());

  // Copy to clipboard with feedback
  const handleCopyToClipboard = useCallback(async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedToClipboard(true);
      setTimeout(() => setCopiedToClipboard(false), 2000);
      return true;
    } catch (error) {
      console.error('Failed to copy to clipboard:', error);
      return false;
    }
  }, []);

  // Toggle raw output view
  const toggleRawOutput = useCallback(() => {
    setShowRawOutput(prev => !prev);
  }, []);

  // Toggle animated reveal
  const toggleAnimatedReveal = useCallback(() => {
    setShowAnimatedReveal(prev => !prev);
  }, []);

  // Toggle a specific tool call expansion
  const toggleToolCallExpanded = useCallback((index: number) => {
    setExpandedToolCalls(prev => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  }, []);

  // Expand all tool calls
  const expandAllToolCalls = useCallback((indices: number[]) => {
    setExpandedToolCalls(new Set(indices));
  }, []);

  // Collapse all tool calls
  const collapseAllToolCalls = useCallback(() => {
    setExpandedToolCalls(new Set());
  }, []);

  // Reset results state (e.g., when switching workflows)
  const resetResultsState = useCallback(() => {
    setResultsSubTab('output');
    setCopiedToClipboard(false);
    setShowRawOutput(false);
    setExpandedToolCalls(new Set());
  }, []);

  return {
    // Sub-tab navigation
    resultsSubTab,
    setResultsSubTab,

    // Output display
    copiedToClipboard,
    setCopiedToClipboard,
    showRawOutput,
    setShowRawOutput,
    toggleRawOutput,
    showAnimatedReveal,
    setShowAnimatedReveal,
    toggleAnimatedReveal,

    // Tool calls expansion
    expandedToolCalls,
    setExpandedToolCalls,
    toggleToolCallExpanded,
    expandAllToolCalls,
    collapseAllToolCalls,

    // Utilities
    handleCopyToClipboard,
    resetResultsState,
  };
}
