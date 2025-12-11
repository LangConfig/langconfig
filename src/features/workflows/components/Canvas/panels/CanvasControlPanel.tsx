/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { memo } from 'react';
import { Panel } from 'reactflow';
import { List, Brain } from 'lucide-react';

interface CanvasControlPanelProps {
  showLiveExecutionPanel: boolean;
  showThinkingStream: boolean;
  onToggleLiveExecutionPanel: () => void;
  onToggleThinkingStream: () => void;
  onDebugWorkflow: () => void;
}

/**
 * Control panel buttons shown on the canvas (Panel toggle, Thinking toggle, Debug)
 */
const CanvasControlPanel = memo(function CanvasControlPanel({
  showLiveExecutionPanel,
  showThinkingStream,
  onToggleLiveExecutionPanel,
  onToggleThinkingStream,
  onDebugWorkflow,
}: CanvasControlPanelProps) {
  return (
    <Panel position="top-right" className="flex gap-2">
      {/* Live Execution Panel Toggle */}
      <button
        onClick={onToggleLiveExecutionPanel}
        className={`px-2 py-1.5 rounded-md border flex items-center gap-1.5 text-xs font-semibold transition-all ${!showLiveExecutionPanel ? 'hover:scale-105 hover:opacity-90' : ''
          }`}
        style={{
          backgroundColor: showLiveExecutionPanel ? '#0d6832' : 'var(--color-primary)',
          borderColor: showLiveExecutionPanel ? '#0d6832' : 'var(--color-primary)',
          color: 'white',
          boxShadow: showLiveExecutionPanel ? 'inset 0 2px 4px rgba(0,0,0,0.3)' : '0 2px 4px rgba(0,0,0,0.1)',
          transform: showLiveExecutionPanel ? 'translateY(1px)' : 'translateY(-1px)'
        }}
        title="Toggle live execution panel - Shows detailed agent thinking, tool calls, and execution flow"
      >
        <List className="w-3.5 h-3.5" />
        <span>Panel</span>
      </button>

      {/* Thinking Toasts Toggle */}
      <button
        onClick={onToggleThinkingStream}
        className={`px-2 py-1.5 rounded-md border flex items-center gap-1.5 text-xs font-semibold transition-all ${!showThinkingStream ? 'hover:scale-105 hover:opacity-90' : ''
          }`}
        style={{
          backgroundColor: showThinkingStream ? '#0d6832' : 'var(--color-primary)',
          borderColor: showThinkingStream ? '#0d6832' : 'var(--color-primary)',
          color: 'white',
          boxShadow: showThinkingStream ? 'inset 0 2px 4px rgba(0,0,0,0.3)' : '0 2px 4px rgba(0,0,0,0.1)',
          transform: showThinkingStream ? 'translateY(1px)' : 'translateY(-1px)'
        }}
        title={showThinkingStream ? 'Hide thinking toast notifications on canvas' : 'Show thinking toast notifications on canvas'}
      >
        <Brain className="w-3.5 h-3.5" />
        <span>Thinking</span>
      </button>

      {/* Debug Modal */}
      <button
        onClick={onDebugWorkflow}
        className="px-2 py-1.5 rounded-md border flex items-center gap-1.5 text-xs font-semibold transition-all hover:scale-105 hover:opacity-90"
        style={{
          backgroundColor: 'var(--color-primary)',
          borderColor: 'var(--color-primary)',
          color: 'white',
          boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
          transform: 'translateY(-1px)'
        }}
        title="Debug Workflow - View backend configuration and tool assignments"
      >
        <span className="material-symbols-outlined" style={{ fontSize: '16px' }}>bug_report</span>
        <span>Debug</span>
      </button>
    </Panel>
  );
});

export default CanvasControlPanel;
