/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { memo } from 'react';

interface NodeTokenCost {
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
  costString: string;
}

interface TotalCostPanelProps {
  nodeTokenCosts: Record<string, NodeTokenCost>;
  isNodeConfigPanelOpen: boolean;
}

/**
 * Floating panel showing total workflow cost and token usage
 */
const TotalCostPanel = memo(function TotalCostPanel({
  nodeTokenCosts,
  isNodeConfigPanelOpen,
}: TotalCostPanelProps) {
  // Calculate total cost from all nodes
  const totalCost = Object.values(nodeTokenCosts).reduce((sum, cost) => {
    // Parse cost string (e.g., "$0.0234" -> 0.0234)
    const costValue = parseFloat(cost.costString.replace('$', '')) || 0;
    return sum + costValue;
  }, 0);

  const totalTokens = Object.values(nodeTokenCosts).reduce(
    (sum, cost) => sum + (cost.totalTokens || 0),
    0
  );

  // Only show if there's any cost data
  if (totalTokens === 0) return null;

  return (
    <div
      className="absolute top-4 z-40 transition-all duration-300 pointer-events-none"
      style={{
        right: isNodeConfigPanelOpen ? '420px' : '20px', // Shift left when node config panel is open
      }}
    >
      <div
        className="rounded-lg shadow-xl border-2 pointer-events-auto"
        style={{
          backgroundColor: 'var(--color-panel-dark)',
          borderColor: 'var(--color-primary)',
        }}
      >
        <div className="px-4 py-2">
          <div className="text-xs font-medium mb-1" style={{ color: 'var(--color-text-muted)' }}>
            Total Workflow Cost
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold font-mono" style={{ color: 'var(--color-primary)' }}>
              ${totalCost.toFixed(4)}
            </span>
            <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
              {totalTokens.toLocaleString()} tokens
            </span>
          </div>
        </div>
      </div>
    </div>
  );
});

export default TotalCostPanel;
