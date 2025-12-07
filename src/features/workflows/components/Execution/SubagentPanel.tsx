/**
 * SubagentPanel Component
 *
 * Displays subagent execution in a stacked panel on the right side of LiveExecutionPanel.
 * Shows subagent thinking/reasoning and tool calls in real-time.
 */

import React, { useState, useMemo } from 'react';
import { ChevronDown, ChevronUp, Maximize2, Minimize2, Bot, Loader2 } from 'lucide-react';
import type { WorkflowEvent } from '../../../../types/events';

interface SubagentPanelProps {
  subagentId: string;
  subagentLabel: string;
  events: WorkflowEvent[];
  isExpanded: boolean;
  onToggleExpand: () => void;
  status: 'running' | 'completed' | 'error';
}

export const SubagentPanel: React.FC<SubagentPanelProps> = ({
  subagentId,
  subagentLabel,
  events,
  isExpanded,
  onToggleExpand,
  status
}) => {
  const [isCollapsed, setIsCollapsed] = useState(false);

  // Extract thinking content from streaming events
  const thinkingContent = useMemo(() => {
    let content = '';
    for (const event of events) {
      if (event.type === 'on_chat_model_stream') {
        content += event.data?.token || event.data?.content || '';
      }
    }
    return content;
  }, [events]);

  // Count tool calls
  const toolCallCount = useMemo(() => {
    return events.filter(e => e.type === 'on_tool_start').length;
  }, [events]);

  const statusColor = status === 'error' ? '#ef4444' : status === 'completed' ? '#10b981' : '#3b82f6';
  const statusBg = status === 'error' ? 'rgba(239, 68, 68, 0.1)' : status === 'completed' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(59, 130, 246, 0.1)';

  return (
    <div
      className={`rounded-lg border-2 overflow-hidden transition-all duration-300 ${isExpanded ? 'flex-1' : 'h-auto'
        }`}
      style={{
        borderColor: statusColor,
        backgroundColor: 'var(--color-background-dark)',
        boxShadow: status === 'running' ? `0 0 20px ${statusColor}40` : undefined
      }}
    >
      {/* Header */}
      <div
        className="flex items-center gap-2 px-3 py-2 cursor-pointer"
        style={{ backgroundColor: statusBg }}
        onClick={() => setIsCollapsed(!isCollapsed)}
      >
        <div className="flex-shrink-0">
          {status === 'running' ? (
            <Loader2 className="w-4 h-4 animate-spin" style={{ color: statusColor }} />
          ) : (
            <Bot className="w-4 h-4" style={{ color: statusColor }} />
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className="font-medium text-sm truncate" style={{ color: 'var(--color-text-primary)' }}>
            {subagentLabel}
          </div>
          <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
            {toolCallCount > 0 ? `${toolCallCount} tool calls` : 'Thinking...'}
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={(e) => { e.stopPropagation(); onToggleExpand(); }}
            className="p-1 rounded hover:bg-white/10 transition-colors"
            title={isExpanded ? 'Minimize' : 'Expand'}
          >
            {isExpanded ? (
              <Minimize2 className="w-3.5 h-3.5" style={{ color: 'var(--color-text-muted)' }} />
            ) : (
              <Maximize2 className="w-3.5 h-3.5" style={{ color: 'var(--color-text-muted)' }} />
            )}
          </button>
          {isCollapsed ? (
            <ChevronDown className="w-4 h-4" style={{ color: 'var(--color-text-muted)' }} />
          ) : (
            <ChevronUp className="w-4 h-4" style={{ color: 'var(--color-text-muted)' }} />
          )}
        </div>
      </div>

      {/* Content */}
      {!isCollapsed && (
        <div
          className="p-3 overflow-auto custom-scrollbar"
          style={{
            maxHeight: isExpanded ? 'calc(100vh - 200px)' : '200px',
            color: 'var(--color-text-primary)'
          }}
        >
          {thinkingContent ? (
            <pre className="text-xs whitespace-pre-wrap font-mono">
              {thinkingContent}
            </pre>
          ) : (
            <div className="text-xs text-center py-4" style={{ color: 'var(--color-text-muted)' }}>
              Waiting for response...
            </div>
          )}
        </div>
      )}
    </div>
  );
};

/**
 * SubagentPanelStack Component
 *
 * Container for multiple SubagentPanels stacked vertically.
 * Manages expand/collapse state for individual panels.
 */
interface SubagentInfo {
  id: string;
  label: string;
  parentRunId: string;
  events: WorkflowEvent[];
  status: 'running' | 'completed' | 'error';
}

interface SubagentPanelStackProps {
  subagents: SubagentInfo[];
  isVisible: boolean;
}

export const SubagentPanelStack: React.FC<SubagentPanelStackProps> = ({
  subagents,
  isVisible
}) => {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  if (!isVisible || subagents.length === 0) return null;

  return (
    <div
      className="flex flex-col gap-2 h-full overflow-hidden"
      style={{
        width: '33.333%',
        minWidth: '300px',
        maxWidth: '500px'
      }}
    >
      {subagents.slice(0, 3).map((subagent) => (
        <SubagentPanel
          key={subagent.id}
          subagentId={subagent.id}
          subagentLabel={subagent.label}
          events={subagent.events}
          isExpanded={expandedId === subagent.id}
          onToggleExpand={() => setExpandedId(expandedId === subagent.id ? null : subagent.id)}
          status={subagent.status}
        />
      ))}
      {subagents.length > 3 && (
        <div
          className="text-xs text-center py-2 rounded"
          style={{ backgroundColor: 'var(--color-background-dark)', color: 'var(--color-text-muted)' }}
        >
          +{subagents.length - 3} more subagents
        </div>
      )}
    </div>
  );
};

export default SubagentPanel;
