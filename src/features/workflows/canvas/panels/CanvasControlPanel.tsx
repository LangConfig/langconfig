/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { memo } from 'react';
import { Panel } from 'reactflow';
import { List, Play, StopCircle, Trash2 } from 'lucide-react';

interface ExecutionStatus {
  state: 'idle' | 'running' | 'completed' | 'failed';
  currentNode?: string;
  progress?: number;
  startTime?: string;
  duration?: string;
}

interface CanvasControlPanelProps {
  showLiveExecutionPanel: boolean;
  showThinkingStream: boolean;
  onToggleLiveExecutionPanel: () => void;
  onToggleThinkingStream: () => void;
  onDebugWorkflow: () => void;
  // Execution controls
  executionStatus: ExecutionStatus;
  currentTaskId: number | string | null;
  onRun: () => void;
  onStop: () => void;
  onClear: () => void;
}

/**
 * Control panel buttons shown on the canvas (Run, Stop, Clear, Panel, Thinking, Debug)
 */
const CanvasControlPanel = memo(function CanvasControlPanel({
  showLiveExecutionPanel,
  showThinkingStream,
  onToggleLiveExecutionPanel,
  onToggleThinkingStream,
  onDebugWorkflow,
  executionStatus,
  currentTaskId,
  onRun,
  onStop,
  onClear,
}: CanvasControlPanelProps) {
  const isRunning = executionStatus.state === 'running';

  return (
    <Panel position="top-left" className="flex gap-2 z-50" style={{ left: '70px', pointerEvents: 'auto' }}>
      {/* Run Button */}
      <button
        onClick={onRun}
        className={`px-4 py-2 rounded-md border-2 flex items-center gap-2 text-sm font-bold transition-all cursor-pointer ${
          !isRunning ? 'hover:scale-105 hover:opacity-90' : ''
        }`}
        style={{
          backgroundColor: isRunning ? '#d97706' : '#10b981',
          borderColor: isRunning ? '#b45309' : '#059669',
          color: 'white',
          boxShadow: '0 3px 6px rgba(0,0,0,0.2)',
          pointerEvents: 'auto',
        }}
        title={isRunning ? 'Workflow running - click to cancel and restart' : 'Execute workflow'}
      >
        {isRunning ? (
          <>
            <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            <span>Running</span>
          </>
        ) : (
          <>
            <Play className="w-4 h-4" />
            <span>Run</span>
          </>
        )}
      </button>

      {/* Stop Button */}
      <button
        onClick={onStop}
        disabled={!currentTaskId || !isRunning}
        className="px-4 py-2 rounded-md border-2 flex items-center gap-2 text-sm font-bold transition-all cursor-pointer hover:scale-105 hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
        style={{
          backgroundColor: '#ef4444',
          borderColor: '#dc2626',
          color: 'white',
          boxShadow: '0 3px 6px rgba(0,0,0,0.2)',
          pointerEvents: 'auto',
        }}
        title="Stop running workflow"
      >
        <StopCircle className="w-4 h-4" />
        <span>Stop</span>
      </button>

      {/* Clear Button */}
      <button
        onClick={onClear}
        className="px-4 py-2 rounded-md border flex items-center gap-2 text-sm font-semibold transition-all cursor-pointer hover:scale-105 hover:opacity-90"
        style={{
          backgroundColor: 'transparent',
          borderColor: '#ef4444',
          color: '#ef4444',
          boxShadow: '0 2px 4px rgba(0,0,0,0.05)',
          pointerEvents: 'auto',
        }}
        title="Clear all nodes"
      >
        <Trash2 className="w-4 h-4" />
        <span>Clear</span>
      </button>

      {/* Divider */}
      <div className="w-px h-8 bg-gray-300 dark:bg-gray-600 self-center" />

      {/* Live Execution Panel Toggle */}
      <button
        onClick={onToggleLiveExecutionPanel}
        className={`px-4 py-2 rounded-md border flex items-center gap-2 text-sm font-semibold transition-all cursor-pointer ${!showLiveExecutionPanel ? 'hover:scale-105 hover:opacity-90' : ''
          }`}
        style={{
          backgroundColor: showLiveExecutionPanel ? '#0d6832' : 'var(--color-primary)',
          borderColor: showLiveExecutionPanel ? '#0d6832' : 'var(--color-primary)',
          color: 'white',
          boxShadow: showLiveExecutionPanel ? 'inset 0 2px 4px rgba(0,0,0,0.3)' : '0 2px 4px rgba(0,0,0,0.1)',
          pointerEvents: 'auto',
        }}
        title="Toggle live feed panel - Shows detailed agent thinking, tool calls, and execution flow"
      >
        <List className="w-4 h-4" />
        <span>Live Feed</span>
      </button>

      {/* Canvas Feed Toggle */}
      <button
        onClick={onToggleThinkingStream}
        className={`px-4 py-2 rounded-md border flex items-center gap-2 text-sm font-semibold transition-all cursor-pointer ${!showThinkingStream ? 'hover:scale-105 hover:opacity-90' : ''
          }`}
        style={{
          backgroundColor: showThinkingStream ? '#0d6832' : 'var(--color-primary)',
          borderColor: showThinkingStream ? '#0d6832' : 'var(--color-primary)',
          color: 'white',
          boxShadow: showThinkingStream ? 'inset 0 2px 4px rgba(0,0,0,0.3)' : '0 2px 4px rgba(0,0,0,0.1)',
          pointerEvents: 'auto',
        }}
        title={showThinkingStream ? 'Hide canvas feed notifications' : 'Show canvas feed notifications'}
      >
        <span>Canvas Feed</span>
      </button>

      {/* Debug Modal */}
      <button
        onClick={onDebugWorkflow}
        className="px-4 py-2 rounded-md border flex items-center gap-2 text-sm font-semibold transition-all cursor-pointer hover:scale-105 hover:opacity-90"
        style={{
          backgroundColor: 'var(--color-primary)',
          borderColor: 'var(--color-primary)',
          color: 'white',
          boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
          pointerEvents: 'auto',
        }}
        title="Debug Workflow - View backend configuration and tool assignments"
      >
        <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>bug_report</span>
        <span>Debug</span>
      </button>
    </Panel>
  );
});

export default CanvasControlPanel;
