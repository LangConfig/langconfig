/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useEffect } from 'react';
import apiClient from '../lib/api-client';

interface MetricsPanelProps {
  workflowId: number | null;
}

interface CostData {
  totalCost: number;
  totalTokens: number;
  promptTokens: number;
  completionTokens: number;
  executionCount: number;
  agents: Array<{
    name: string;
    cost: number;
    tokens: number;
  }>;
  tools: Array<{
    name: string;
    count: number;
  }>;
}

export default function MinimizableMetricsPanel({ workflowId }: MetricsPanelProps) {
  const [isMinimized, setIsMinimized] = useState(true);
  const [costData, setCostData] = useState<CostData>({
    totalCost: 0,
    totalTokens: 0,
    promptTokens: 0,
    completionTokens: 0,
    executionCount: 0,
    agents: [],
    tools: []
  });
  const [loading, setLoading] = useState(false);

  // Fetch cost metrics from API
  useEffect(() => {
    if (!workflowId) return;

    const fetchCostMetrics = async () => {
      setLoading(true);
      try {
        const response = await apiClient.getWorkflowCostMetrics(workflowId, 30);
        setCostData(response.data);
      } catch (error) {
        console.error('Failed to fetch cost metrics:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchCostMetrics();
  }, [workflowId]);

  if (isMinimized) {
    return (
      <div
        className="fixed top-4 left-4 z-40 bg-white dark:bg-panel-dark border-2 rounded-lg shadow-xl"
        style={{ borderColor: 'var(--color-primary)' }}
      >
        <button
          onClick={() => setIsMinimized(false)}
          className="flex items-center gap-2 px-3 py-2 hover:opacity-80 transition-opacity"
        >
          <span
            className="material-symbols-outlined"
            style={{ fontSize: '20px', color: 'var(--color-primary)' }}
          >
            payments
          </span>
          <div className="text-left">
            <p className="text-xs font-semibold" style={{ color: 'var(--color-text-primary)' }}>
              ${costData.totalCost.toFixed(4)}
            </p>
            <p className="text-xxs" style={{ color: 'var(--color-text-muted)' }}>
              {costData.totalTokens.toLocaleString()} tokens
            </p>
          </div>
          <span
            className="material-symbols-outlined"
            style={{ fontSize: '16px', color: 'var(--color-text-muted)' }}
          >
            expand_more
          </span>
        </button>
      </div>
    );
  }

  return (
    <div
      className="fixed top-4 left-4 z-40 bg-white dark:bg-panel-dark border-2 rounded-lg shadow-xl"
      style={{ borderColor: 'var(--color-primary)', width: '380px', maxHeight: '600px' }}
    >
      {/* Header */}
      <div
        className="px-4 py-3 flex items-center justify-between rounded-t-lg"
        style={{ backgroundColor: 'var(--color-primary)' }}
      >
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-white text-lg">
            payments
          </span>
          <h3 className="text-white font-semibold text-sm">
            Workflow Cost Metrics
          </h3>
        </div>
        <button
          onClick={() => setIsMinimized(true)}
          className="text-white/90 hover:text-white hover:bg-white/15 p-1 rounded transition-colors"
        >
          <span className="material-symbols-outlined text-base">
            expand_less
          </span>
        </button>
      </div>

      {/* Content */}
      <div className="p-4 space-y-4 overflow-y-auto" style={{ maxHeight: '540px' }}>
        {/* Total Cost Display */}
        <div className="text-center py-4 rounded-lg border" style={{
          backgroundColor: 'var(--color-background-light)',
          borderColor: 'var(--color-border-dark)'
        }}>
          <div className="text-3xl font-bold" style={{ color: 'var(--color-primary)' }}>
            ${costData.totalCost.toFixed(4)}
          </div>
          <div className="text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
            Total Cost (Last 30 Days)
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

        {/* Executions */}
        <div className="flex items-center justify-between p-2 rounded" style={{ backgroundColor: 'var(--color-background-light)' }}>
          <span className="text-xs font-medium" style={{ color: 'var(--color-text-muted)' }}>Executions</span>
          <span className="text-xs font-semibold" style={{ color: 'var(--color-text-primary)' }}>
            {costData.executionCount}
          </span>
        </div>

        {/* Cost by Agent */}
        <div>
          <h4 className="text-xs font-semibold mb-2 uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>
            Cost by Agent
          </h4>
          <div className="space-y-1">
            {costData.agents.length > 0 ? (
              costData.agents.map((agent, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between p-2 rounded text-xs"
                  style={{ backgroundColor: 'var(--color-background-light)' }}
                >
                  <span className="flex items-center gap-2">
                    <span className="material-symbols-outlined text-sm" style={{ color: 'var(--color-primary)' }}>
                      smart_toy
                    </span>
                    <span style={{ color: 'var(--color-text-primary)' }}>{agent.name}</span>
                  </span>
                  <div className="text-right">
                    <div className="font-semibold" style={{ color: 'var(--color-primary)' }}>
                      ${agent.cost.toFixed(4)}
                    </div>
                    <div className="text-xxs" style={{ color: 'var(--color-text-muted)' }}>
                      {agent.tokens.toLocaleString()} tokens
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div className="text-xs text-center py-4" style={{ color: 'var(--color-text-muted)' }}>
                No agent data available
              </div>
            )}
          </div>
        </div>

        {/* Tool Usage */}
        <div>
          <h4 className="text-xs font-semibold mb-2 uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>
            Tool Usage
          </h4>
          <div className="space-y-1">
            {costData.tools.length > 0 ? (
              costData.tools.map((tool, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between p-2 rounded text-xs"
                  style={{ backgroundColor: 'var(--color-background-light)' }}
                >
                  <span className="flex items-center gap-2">
                    <span className="material-symbols-outlined text-sm" style={{ color: 'var(--color-primary)' }}>
                      build
                    </span>
                    <span style={{ color: 'var(--color-text-primary)' }}>{tool.name}</span>
                  </span>
                  <span className="font-semibold" style={{ color: 'var(--color-text-muted)' }}>
                    {tool.count}x
                  </span>
                </div>
              ))
            ) : (
              <div className="text-xs text-center py-4" style={{ color: 'var(--color-text-muted)' }}>
                No tool usage data available
              </div>
            )}
          </div>
        </div>

        {/* View Full Report Button */}
        <button
          className="w-full py-2 text-xs font-medium rounded transition-colors"
          style={{
            backgroundColor: 'var(--color-background-light)',
            color: 'var(--color-primary)'
          }}
          onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--color-primary-light)'}
          onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'var(--color-background-light)'}
          onClick={() => alert('Navigate to Library for full project dashboard')}
        >
          View Full Report in Library →
        </button>
      </div>
    </div>
  );
}
