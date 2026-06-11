/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState } from 'react';
import { Activity, Zap, Users, Database, ChevronDown, ChevronRight, DollarSign, FileText, AlertTriangle } from 'lucide-react';
import type { SessionMetrics, ToolCall, SubAgentActivity } from '../types/chat';
import { Surface } from '@/components/ui/Surface';
import { ProgressBar } from '@/components/ui/ProgressBar';

/** Context size (tokens) past which the panel warns about a large context. */
const CONTEXT_WARNING_THRESHOLD = 30000;

interface MetricsPanelProps {
  metrics: SessionMetrics;
  toolCalls: ToolCall[];
  subagentActivity: SubAgentActivity[];
  isLoading: boolean;
  agentName?: string;
  sessionId?: string | null;
}

export default function MetricsPanel({
  metrics,
  toolCalls,
  subagentActivity,
  isLoading,
  agentName,
  sessionId
}: MetricsPanelProps) {
  const [toolCallsExpanded, setToolCallsExpanded] = useState(false);
  const [subagentsExpanded, setSubagentsExpanded] = useState(false);

  const contextTokens = metrics?.context_tokens ?? 0;
  const contextWarning = contextTokens > CONTEXT_WARNING_THRESHOLD;

  return (
    <div
      className="w-80 overflow-y-auto border-l-2"
      style={{
        borderColor: 'var(--border-strong)',
        backgroundColor: 'var(--color-background-light)',
      }}
    >
      {/* Current Agent */}
      {sessionId && agentName && (
        <div
          className="border-b-2 p-6"
          style={{ borderColor: 'var(--border-strong)' }}
        >
          <div
            className="font-mono text-xs uppercase tracking-[0.12em] font-medium mb-2"
            style={{ color: 'var(--color-text-muted)' }}
          >
            Active Agent
          </div>
          <div
            className="text-lg font-semibold"
            style={{ color: 'var(--color-text-primary)', lineHeight: '1.4' }}
          >
            {agentName}
          </div>
        </div>
      )}

      {/* Session Metrics */}
      <div className="p-6">
        <div
          className="font-mono text-xs uppercase tracking-[0.12em] font-medium mb-4"
          style={{ color: 'var(--color-text-muted)' }}
        >
          Session Metrics
        </div>

        {isLoading ? (
          <div
            className="text-sm"
            style={{ color: 'var(--color-text-muted)' }}
          >
            Loading metrics...
          </div>
        ) : (
          <div className="space-y-3">
            <MetricCard
              icon={<Activity className="w-5 h-5" />}
              label="Total Tokens"
              value={(metrics?.total_tokens ?? 0).toLocaleString()}
            />
            <MetricCard
              icon={<DollarSign className="w-5 h-5" />}
              label="Total Cost"
              value={`$${(metrics?.total_cost_usd ?? 0).toFixed(4)}`}
            />
            {metrics?.rag_context_tokens ? (
              <MetricCard
                icon={<FileText className="w-5 h-5" />}
                label="RAG Context"
                value={`${(metrics.rag_context_tokens ?? 0).toLocaleString()} tokens`}
              />
            ) : null}
            {metrics?.context_tokens !== undefined && (
              <MetricCard
                icon={
                  contextWarning ? (
                    <AlertTriangle className="w-5 h-5" />
                  ) : (
                    <Database className="w-5 h-5" />
                  )
                }
                label="Context Size"
                value={`${contextTokens.toLocaleString()} tokens`}
                warning={contextWarning}
              >
                <ProgressBar
                  value={contextTokens}
                  max={CONTEXT_WARNING_THRESHOLD}
                  tone={contextWarning ? 'warning' : 'info'}
                  height={6}
                  className="mt-2"
                />
              </MetricCard>
            )}
            <MetricCard
              icon={<Zap className="w-5 h-5" />}
              label="Tool Calls"
              value={(metrics?.tool_calls ?? 0).toString()}
            />
            <MetricCard
              icon={<Users className="w-5 h-5" />}
              label="Subagent Spawns"
              value={(metrics?.subagent_spawns ?? 0).toString()}
            />
            <MetricCard
              icon={<Database className="w-5 h-5" />}
              label="Context Ops"
              value={(metrics?.context_operations ?? 0).toString()}
            />
          </div>
        )}
      </div>

      {/* Tool Calls */}
      {toolCalls.length > 0 && (
        <div
          className="border-t-2"
          style={{ borderColor: 'var(--border-strong)' }}
        >
          <button
            onClick={() => setToolCallsExpanded(!toolCallsExpanded)}
            className="flex w-full items-center justify-between p-3 font-mono text-xs font-semibold uppercase tracking-[0.12em] transition-colors hover:bg-[var(--surface-2)]"
          >
            <div className="flex items-center gap-2">
              <Zap className="w-3.5 h-3.5" style={{ color: 'var(--color-primary)' }} />
              <h3
                className="text-xs font-semibold uppercase tracking-wide"
                style={{ color: 'var(--color-text-primary)' }}
              >
                Tool Calls ({toolCalls.length})
              </h3>
            </div>
            {toolCallsExpanded ? (
              <ChevronDown className="w-4 h-4" style={{ color: 'var(--color-text-muted)' }} />
            ) : (
              <ChevronRight className="w-4 h-4" style={{ color: 'var(--color-text-muted)' }} />
            )}
          </button>

          {toolCallsExpanded && (
            <div className="px-3 pb-3 space-y-1.5">
              {toolCalls.slice(-10).reverse().map((call, index) => (
                <Surface key={index} variant="inset" className="p-2">
                  <div
                    className="font-mono text-xs font-semibold"
                    style={{ color: 'var(--color-primary)' }}
                  >
                    {call.tool_name}
                  </div>
                  <div
                    className="text-xs mt-0.5"
                    style={{ color: 'var(--color-text-muted)' }}
                  >
                    {new Date(call.timestamp).toLocaleTimeString()}
                  </div>
                </Surface>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Subagent Activity */}
      {subagentActivity.length > 0 && (
        <div
          className="border-t-2"
          style={{ borderColor: 'var(--border-strong)' }}
        >
          <button
            onClick={() => setSubagentsExpanded(!subagentsExpanded)}
            className="flex w-full items-center justify-between p-3 font-mono text-xs font-semibold uppercase tracking-[0.12em] transition-colors hover:bg-[var(--surface-2)]"
          >
            <div className="flex items-center gap-2">
              <Users className="w-3.5 h-3.5" style={{ color: 'var(--color-primary)' }} />
              <h3
                className="text-xs font-semibold uppercase tracking-wide"
                style={{ color: 'var(--color-text-primary)' }}
              >
                Subagent Activity ({subagentActivity.length})
              </h3>
            </div>
            {subagentsExpanded ? (
              <ChevronDown className="w-4 h-4" style={{ color: 'var(--color-text-muted)' }} />
            ) : (
              <ChevronRight className="w-4 h-4" style={{ color: 'var(--color-text-muted)' }} />
            )}
          </button>

          {subagentsExpanded && (
            <div className="px-3 pb-3 space-y-1.5">
              {subagentActivity.slice(-10).reverse().map((activity, index) => (
                <Surface key={index} variant="inset" className="p-2">
                  <div
                    className="font-medium text-xs"
                    style={{ color: 'var(--color-primary)' }}
                  >
                    {activity.subagent_name}
                  </div>
                  <div
                    className="text-xs mt-0.5"
                    style={{ color: 'var(--color-text-primary)' }}
                  >
                    {activity.action}
                  </div>
                  <div
                    className="text-xs mt-0.5"
                    style={{ color: 'var(--color-text-muted)' }}
                  >
                    {new Date(activity.timestamp).toLocaleTimeString()}
                  </div>
                </Surface>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

interface MetricCardProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  warning?: boolean;
  /** Optional extra content (e.g. a usage ProgressBar) rendered under the value. */
  children?: React.ReactNode;
}

function MetricCard({ icon, label, value, warning = false, children }: MetricCardProps) {
  return (
    <Surface variant="card-sm" tone={warning ? 'warning' : undefined} className="p-3">
      <div className="flex items-center gap-3">
        <div style={{ color: warning ? 'var(--color-warning)' : 'var(--color-primary)' }}>
          {icon}
        </div>
        <div className="flex-1 min-w-0">
          <div
            className="text-xs font-medium"
            style={{ color: 'var(--color-text-muted)' }}
          >
            {label}
          </div>
          <div
            className="text-lg font-bold"
            style={{ color: warning ? 'var(--color-warning)' : 'var(--color-text-primary)' }}
          >
            {value}
          </div>
          {children}
          {warning && (
            <div className="text-xs mt-1" style={{ color: 'var(--color-warning)' }}>
              Context is large - consider starting a new session
            </div>
          )}
        </div>
      </div>
    </Surface>
  );
}
