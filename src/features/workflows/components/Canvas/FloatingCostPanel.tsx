/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useEffect, useRef } from 'react';
import { X } from 'lucide-react';

interface CostBreakdown {
  totalCost: number;
  totalTokens: number;
  promptTokens: number;
  completionTokens: number;
  model: string;
  toolCalls: Array<{
    tool: string;
    count: number;
  }>;
  executionHistory: Array<{
    timestamp: string;
    cost: number;
    tokens: number;
  }>;
}

interface FloatingCostPanelProps {
  agentName: string;
  agentId: string;
  costData: CostBreakdown;
  position: { x: number; y: number };
  onClose: () => void;
}

export default function FloatingCostPanel({
  agentName,
  agentId,
  costData,
  position,
  onClose
}: FloatingCostPanelProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [currentPosition, setCurrentPosition] = useState(position);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
  const panelRef = useRef<HTMLDivElement>(null);

  // Handle dragging
  const handleMouseDown = (e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest('button')) return; // Don't drag if clicking buttons

    setIsDragging(true);
    const rect = panelRef.current?.getBoundingClientRect();
    if (rect) {
      setDragOffset({
        x: e.clientX - rect.left,
        y: e.clientY - rect.top
      });
    }
  };

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (isDragging) {
        setCurrentPosition({
          x: e.clientX - dragOffset.x,
          y: e.clientY - dragOffset.y
        });
      }
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, dragOffset]);

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/20 z-40"
        onClick={onClose}
        data-floating-cost-panel
      />

      {/* Floating Panel */}
      <div
        ref={panelRef}
        className="fixed z-50 bg-white dark:bg-panel-dark border-2 rounded-lg shadow-2xl"
        style={{
          left: `${currentPosition.x}px`,
          top: `${currentPosition.y}px`,
          width: '380px',
          borderColor: 'var(--color-primary)',
          cursor: isDragging ? 'grabbing' : 'grab'
        }}
        onMouseDown={handleMouseDown}
        data-floating-cost-panel
      >
        {/* Header - Primary Color */}
        <div
          className="px-4 py-3 flex items-center justify-between rounded-t-md"
          style={{ backgroundColor: 'var(--color-primary)' }}
        >
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-white text-lg">
              payments
            </span>
            <h3 className="text-white font-semibold text-sm">
              {agentName} - Cost Breakdown
            </h3>
          </div>
          <button
            onClick={onClose}
            className="text-white/90 hover:text-white hover:bg-white/15 p-1 rounded transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 space-y-4" style={{ cursor: 'default' }}>
          {/* Total Cost - Big Display */}
          <div className="text-center py-4 rounded-lg border" style={{
            backgroundColor: 'var(--color-background-light)',
            borderColor: 'var(--color-border-dark)'
          }}>
            <div className="text-3xl font-bold" style={{ color: 'var(--color-primary)' }}>
              ${costData.totalCost.toFixed(4)}
            </div>
            <div className="text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
              Total Cost
            </div>
          </div>

          {/* Token Breakdown */}
          <div>
            <h4 className="text-xs font-semibold mb-2 uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>
              Token Usage
            </h4>
            <div className="grid grid-cols-3 gap-2">
              <div className="p-2 rounded text-center" style={{ backgroundColor: 'var(--color-background-light)' }}>
                <div className="text-lg font-bold" style={{ color: 'var(--color-text-primary)' }}>
                  {costData.totalTokens.toLocaleString()}
                </div>
                <div className="text-xxs" style={{ color: 'var(--color-text-muted)' }}>Total</div>
              </div>
              <div className="p-2 rounded text-center" style={{ backgroundColor: 'var(--color-background-light)' }}>
                <div className="text-lg font-bold" style={{ color: 'var(--color-text-primary)' }}>
                  {costData.promptTokens.toLocaleString()}
                </div>
                <div className="text-xxs" style={{ color: 'var(--color-text-muted)' }}>Prompt</div>
              </div>
              <div className="p-2 rounded text-center" style={{ backgroundColor: 'var(--color-background-light)' }}>
                <div className="text-lg font-bold" style={{ color: 'var(--color-text-primary)' }}>
                  {costData.completionTokens.toLocaleString()}
                </div>
                <div className="text-xxs" style={{ color: 'var(--color-text-muted)' }}>Output</div>
              </div>
            </div>
          </div>

          {/* Model Info */}
          <div className="flex items-center justify-between p-2 rounded" style={{ backgroundColor: 'var(--color-background-light)' }}>
            <span className="text-xs font-medium" style={{ color: 'var(--color-text-muted)' }}>Model</span>
            <span className="text-xs font-semibold" style={{ color: 'var(--color-text-primary)' }}>
              {costData.model}
            </span>
          </div>

          {/* Tool Usage */}
          {costData.toolCalls && costData.toolCalls.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold mb-2 uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>
                Tool Usage
              </h4>
              <div className="space-y-1">
                {costData.toolCalls.map((tool, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between p-2 rounded text-xs"
                    style={{ backgroundColor: 'var(--color-background-light)' }}
                  >
                    <span className="flex items-center gap-2">
                      <span className="material-symbols-outlined text-sm" style={{ color: 'var(--color-primary)' }}>
                        build
                      </span>
                      <span style={{ color: 'var(--color-text-primary)' }}>{tool.tool}</span>
                    </span>
                    <span className="font-semibold" style={{ color: 'var(--color-text-muted)' }}>
                      {tool.count}x
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Recent Execution History */}
          {costData.executionHistory && costData.executionHistory.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold mb-2 uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>
                Recent Runs
              </h4>
              <div className="space-y-1 max-h-32 overflow-y-auto">
                {costData.executionHistory.map((run, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between p-2 rounded text-xs"
                    style={{ backgroundColor: 'var(--color-background-light)' }}
                  >
                    <span style={{ color: 'var(--color-text-muted)' }}>
                      {new Date(run.timestamp).toLocaleTimeString()}
                    </span>
                    <span className="flex items-center gap-2">
                      <span style={{ color: 'var(--color-text-muted)' }}>
                        {run.tokens.toLocaleString()} tokens
                      </span>
                      <span className="font-semibold" style={{ color: 'var(--color-primary)' }}>
                        ${run.cost.toFixed(4)}
                      </span>
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* View Full Report Link */}
          <button
            className="w-full py-2 text-xs font-medium rounded transition-colors"
            style={{
              backgroundColor: 'var(--color-background-light)',
              color: 'var(--color-primary)'
            }}
            onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--color-primary-light)'}
            onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'var(--color-background-light)'}
          >
            View Full Report in Library →
          </button>
        </div>
      </div>
    </>
  );
}
