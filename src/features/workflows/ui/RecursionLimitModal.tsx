/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * RecursionLimitModal Component
 *
 * HITL (Human-in-the-Loop) modal that appears when workflow hits recursion limit.
 * Allows user to review output so far and decide whether to continue or stop.
 *
 * Usage:
 *   <RecursionLimitModal
 *     isOpen={showRecursionModal}
 *     onClose={() => setShowRecursionModal(false)}
 *     onContinue={(newLimit) => handleContinue(newLimit)}
 *     onStop={handleStop}
 *     currentOutput="..."
 *     iterationCount={100}
 *     currentLimit={100}
 *   />
 */

import { useState } from 'react';
import { X, AlertTriangle, Play, StopCircle } from 'lucide-react';

export interface DiagnosticData {
  detected_issues?: string[];
  loop_pattern?: string | null;
  tool_loop_detected?: boolean;
  question_loop_detected?: boolean;
  graph_cycle_detected?: boolean;
  missing_end_edge?: boolean;
  agent_output_preview?: string;
  recommendations?: string[];
  execution_summary?: {
    total_iterations?: number;
    agent_counts?: Record<string, number>;
    last_10_pattern?: string;
  };
}

export interface RecursionLimitModalProps {
  /** Whether the modal is open */
  isOpen: boolean;

  /** Callback when modal is closed */
  onClose: () => void;

  /** Callback when user chooses to continue (returns new limit) */
  onContinue: (newLimit: number) => void;

  /** Callback when user chooses to stop */
  onStop: () => void;

  /** Current output generated so far */
  currentOutput?: string;

  /** Current iteration count */
  iterationCount?: number;

  /** Current recursion limit */
  currentLimit?: number;

  /** Node/agent that hit the limit */
  agentName?: string;

  /** Comprehensive diagnostic data from backend */
  diagnostics?: DiagnosticData;
}

export default function RecursionLimitModal({
  isOpen,
  onClose,
  onContinue,
  onStop,
  currentOutput = '',
  iterationCount = 0,
  currentLimit = 100,
  agentName = 'Agent',
  diagnostics,
}: RecursionLimitModalProps) {
  const [newLimit, setNewLimit] = useState(currentLimit + 50); // Default to +50 more iterations
  const [isProcessing, setIsProcessing] = useState(false);

  if (!isOpen) {
    return null;
  }

  const handleContinue = async () => {
    setIsProcessing(true);
    try {
      await onContinue(newLimit);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleStop = async () => {
    setIsProcessing(true);
    try {
      await onStop();
    } finally {
      setIsProcessing(false);
      onClose();
    }
  };

  return (
    <div
      className="fixed inset-0 flex items-center justify-center z-50"
      style={{ backgroundColor: 'rgba(0, 0, 0, 0.7)' }}
      onClick={(e) => {
        if (e.target === e.currentTarget && !isProcessing) {
          onClose();
        }
      }}
    >
      <div
        className="rounded-lg shadow-2xl p-6 max-w-3xl w-full mx-4 max-h-[90vh] overflow-hidden flex flex-col"
        style={{ backgroundColor: 'var(--color-panel-dark)' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between mb-4 pb-4 border-b" style={{ borderColor: 'var(--color-border-dark)' }}>
          <div className="flex items-center gap-3">
            <div
              className="w-12 h-12 rounded-full flex items-center justify-center"
              style={{ backgroundColor: 'rgba(251, 191, 36, 0.2)' }}
            >
              <AlertTriangle className="w-6 h-6" style={{ color: '#f59e0b' }} />
            </div>
            <div>
              <h2 className="text-xl font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                Recursion Limit Reached
              </h2>
              <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
                {agentName} has reached {currentLimit} iterations
              </p>
            </div>
          </div>

          {!isProcessing && (
            <button
              onClick={onClose}
              className="p-2 rounded-lg hover:bg-opacity-10 hover:bg-white transition-colors"
              style={{ color: 'var(--color-text-muted)' }}
            >
              <X className="w-5 h-5" />
            </button>
          )}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto mb-6 space-y-4">
          {/* Explanation */}
          <div
            className="p-4 rounded-lg"
            style={{
              backgroundColor: 'var(--color-background-light)',
              border: '1px solid rgba(251, 191, 36, 0.3)',
            }}
          >
            <p className="text-sm" style={{ color: 'var(--color-text-primary)' }}>
              The workflow has exceeded its maximum iteration limit without reaching a stop condition.
            </p>
          </div>

          {/* Detected Issues */}
          {diagnostics?.detected_issues && diagnostics.detected_issues.length > 0 && (
            <div
              className="p-4 rounded-lg"
              style={{
                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
              }}
            >
              <h3 className="text-sm font-semibold mb-2 flex items-center gap-2" style={{ color: '#ef4444' }}>
                <AlertTriangle className="w-4 h-4" />
                Detected Issues
              </h3>
              <ul className="space-y-1">
                {diagnostics.detected_issues.map((issue, i) => (
                  <li key={i} className="text-sm flex items-start gap-2" style={{ color: 'var(--color-text-primary)' }}>
                    <span style={{ color: '#ef4444', flexShrink: 0 }}>•</span>
                    <span>{issue}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Loop Pattern */}
          {diagnostics?.loop_pattern && (
            <div
              className="p-4 rounded-lg"
              style={{
                backgroundColor: 'var(--color-background-dark)',
                border: '1px solid var(--color-border-dark)',
              }}
            >
              <h3 className="text-sm font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                Execution Pattern
              </h3>
              <div
                className="p-3 rounded font-mono text-xs overflow-x-auto"
                style={{
                  backgroundColor: 'var(--color-background-light)',
                  color: '#f59e0b',
                }}
              >
                {diagnostics.loop_pattern}
              </div>
              {diagnostics.execution_summary?.last_10_pattern && (
                <p className="text-xs mt-2" style={{ color: 'var(--color-text-muted)' }}>
                  Last 10 actions: {diagnostics.execution_summary.last_10_pattern}
                </p>
              )}
            </div>
          )}

          {/* Recommendations */}
          {diagnostics?.recommendations && diagnostics.recommendations.length > 0 && (
            <div
              className="p-4 rounded-lg"
              style={{
                backgroundColor: 'rgba(34, 197, 94, 0.1)',
                border: '1px solid rgba(34, 197, 94, 0.3)',
              }}
            >
              <h3 className="text-sm font-semibold mb-2" style={{ color: '#22c55e' }}>
                💡 How to Fix This
              </h3>
              <ol className="space-y-2">
                {diagnostics.recommendations.map((rec, i) => (
                  <li key={i} className="text-sm flex gap-2" style={{ color: 'var(--color-text-primary)' }}>
                    <span style={{ color: '#22c55e', fontWeight: 'bold', flexShrink: 0 }}>{i + 1}.</span>
                    <span>{rec}</span>
                  </li>
                ))}
              </ol>
            </div>
          )}

          {/* Stats */}
          <div className="grid grid-cols-2 gap-4">
            <div
              className="p-4 rounded-lg"
              style={{ backgroundColor: 'var(--color-background-dark)' }}
            >
              <div className="text-xs font-medium mb-1" style={{ color: 'var(--color-text-muted)' }}>
                Iterations Completed
              </div>
              <div className="text-2xl font-bold" style={{ color: 'var(--color-primary)' }}>
                {iterationCount}
              </div>
            </div>
            <div
              className="p-4 rounded-lg"
              style={{ backgroundColor: 'var(--color-background-dark)' }}
            >
              <div className="text-xs font-medium mb-1" style={{ color: 'var(--color-text-muted)' }}>
                Current Limit
              </div>
              <div className="text-2xl font-bold" style={{ color: 'var(--color-primary)' }}>
                {currentLimit}
              </div>
            </div>
          </div>

          {/* Output Preview */}
          {currentOutput && (
            <div>
              <h3 className="text-sm font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                Output Generated So Far:
              </h3>
              <div
                className="p-4 rounded-lg max-h-64 overflow-y-auto"
                style={{
                  backgroundColor: 'var(--color-background-dark)',
                  border: '1px solid var(--color-border-dark)',
                }}
              >
                <pre
                  className="text-xs whitespace-pre-wrap font-mono"
                  style={{ color: 'var(--color-text-primary)' }}
                >
                  {currentOutput.length > 1000
                    ? currentOutput.substring(0, 1000) + '\n\n... (truncated)'
                    : currentOutput}
                </pre>
              </div>
            </div>
          )}

          {/* Limit Adjustment */}
          <div>
            <label className="block text-sm font-medium mb-2" style={{ color: 'var(--color-text-primary)' }}>
              New Iteration Limit:
            </label>
            <div className="flex items-center gap-4">
              <input
                type="number"
                value={newLimit}
                onChange={(e) => setNewLimit(parseInt(e.target.value) || currentLimit)}
                min={currentLimit + 10}
                max={1000}
                step={10}
                className="flex-1 px-4 py-2 rounded-lg border"
                style={{
                  backgroundColor: 'var(--color-input-background)',
                  borderColor: 'var(--color-border-dark)',
                  color: 'var(--color-text-primary)',
                }}
                disabled={isProcessing}
              />
              <span className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
                (+{newLimit - currentLimit} more)
              </span>
            </div>
            <p className="text-xs mt-2" style={{ color: 'var(--color-text-muted)' }}>
              Recommended: Add 50-100 iterations. Higher limits may indicate a workflow logic issue.
            </p>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-end gap-3 pt-4 border-t" style={{ borderColor: 'var(--color-border-dark)' }}>
          <button
            onClick={handleStop}
            disabled={isProcessing}
            className="inline-flex items-center gap-2 px-6 py-3 rounded-lg font-medium transition-all hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
            style={{
              backgroundColor: 'var(--color-background-dark)',
              color: 'var(--color-text-primary)',
              border: '1px solid var(--color-border-dark)',
            }}
          >
            <StopCircle className="w-4 h-4" />
            <span>Stop & Review</span>
          </button>

          <button
            onClick={handleContinue}
            disabled={isProcessing || newLimit <= currentLimit}
            className="inline-flex items-center gap-2 px-6 py-3 rounded-lg font-medium transition-all hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed text-white"
            style={{
              backgroundColor: 'var(--color-primary)',
            }}
          >
            {isProcessing ? (
              <>
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                <span>Continuing...</span>
              </>
            ) : (
              <>
                <Play className="w-4 h-4" />
                <span>Continue Execution</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
