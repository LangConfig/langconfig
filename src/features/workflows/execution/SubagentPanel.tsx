/**
 * SubAgentPanel Component
 *
 * Displays subagent execution in a stacked panel on the right side of RealtimeExecutionPanel.
 * Shows subagent thinking/reasoning and tool calls in real-time.
 * Styled to match RealtimeExecutionPanel for visual consistency.
 */

import React, { useState, useMemo, useRef, useEffect } from 'react';
import { Maximize2, Minimize2, Bot, Loader2, Wrench, CheckCircle, XCircle, X, PenLine } from 'lucide-react';
import { AgentOutputRenderer, sanitizeAgentOutput } from '@/components/ui/AgentOutputRenderer';
import type { WorkflowEvent } from '@/types/events';

interface SubAgentPanelProps {
  subagentId: string;
  subagentLabel: string;
  events: WorkflowEvent[];
  isExpanded: boolean;
  onToggleExpand: () => void;
  onClose?: () => void;
  status: 'running' | 'completed' | 'error';
  inputPreview?: string;  // Task description from subagent_start
  outputPreview?: string;  // Result from subagent_end
}

export const SubAgentPanel: React.FC<SubAgentPanelProps> = ({
  subagentId,
  subagentLabel,
  events,
  isExpanded,
  onToggleExpand,
  onClose,
  status,
  inputPreview = '',
  outputPreview = ''
}) => {
  const contentRef = useRef<HTMLDivElement>(null);
  const [isAutoScroll, setIsAutoScroll] = useState(true);

  // Extract thinking content from streaming events, with fallback to input/output preview
  const thinkingContent = useMemo(() => {
    let content = '';
    for (const event of events) {
      if (event.type === 'on_chat_model_stream') {
        content += (event.data as any)?.token || (event.data as any)?.content || '';
      }
    }

    // Fallback: If no streaming events, show input/output preview
    if (!content && (inputPreview || outputPreview)) {
      if (inputPreview) {
        // Sanitize input preview (may be raw dict string)
        const cleanInput = sanitizeAgentOutput(inputPreview);
        content += `**Task:**\n${cleanInput}\n\n`;
      }
      if (outputPreview) {
        // Sanitize output (may be Command() structure)
        const cleanOutput = sanitizeAgentOutput(outputPreview);
        content += `**Result:**\n${cleanOutput}`;
      }
    }

    return content;
  }, [events, inputPreview, outputPreview]);

  // Extract tool calls
  const toolCalls = useMemo(() => {
    const tools: { name: string; input: string; output?: string; status: 'running' | 'complete' | 'error' }[] = [];
    const startEvents = events.filter(e => e.type === 'on_tool_start');

    for (const startEvent of startEvents) {
      const runId = (startEvent.data as any)?.run_id;
      const endEvent = events.find(e =>
        (e.type === 'on_tool_end' || e.type === 'error') && (e.data as any)?.run_id === runId
      );

      tools.push({
        name: (startEvent.data as any)?.tool_name || 'Tool',
        input: (startEvent.data as any)?.input_preview || '',
        output: (endEvent?.data as any)?.output_preview,
        status: endEvent?.type === 'error' ? 'error' : endEvent ? 'complete' : 'running'
      });
    }
    return tools;
  }, [events]);

  // Auto-scroll to bottom
  useEffect(() => {
    if (contentRef.current && isAutoScroll) {
      contentRef.current.scrollTop = contentRef.current.scrollHeight;
    }
  }, [thinkingContent, toolCalls, isAutoScroll]);

  const statusColor = status === 'error' ? 'var(--color-error)' : status === 'completed' ? 'var(--color-success)' : 'var(--color-primary)';

  return (
    <div
      className={`flex flex-col overflow-hidden transition-all duration-300 ${isExpanded ? 'flex-1' : ''
        } ${status === 'running' ? 'streaming-pulse' : ''}`}
      style={{
        backgroundColor: 'transparent',
        border: `var(--border-w) solid ${statusColor}`,
        borderRadius: 'var(--radius-card)',
        minHeight: isExpanded ? '100%' : '180px',
        maxHeight: isExpanded ? '100%' : '300px',
        boxShadow: status === 'running' ? 'var(--glow-accent)' : 'var(--shadow-card-sm)'
      }}
    >
      {/* Header - styled like RealtimeExecutionPanel */}
      <div
        className="flex items-center gap-3 px-4 py-3 border-b flex-shrink-0"
        style={{
          backgroundColor: statusColor,
          borderBottomColor: 'var(--color-border-dark)'
        }}
      >
        <div className="p-1.5" style={{ backgroundColor: 'color-mix(in srgb, var(--color-on-accent) 20%, transparent)', borderRadius: 'var(--radius-control)' }}>
          {status === 'running' ? (
            <Loader2 className="w-4 h-4 animate-spin" style={{ color: 'var(--color-on-accent)' }} />
          ) : status === 'completed' ? (
            <CheckCircle className="w-4 h-4" style={{ color: 'var(--color-on-accent)' }} />
          ) : (
            <XCircle className="w-4 h-4" style={{ color: 'var(--color-on-accent)' }} />
          )}
        </div>

        <div className="flex-1 min-w-0">
          <div className="font-semibold text-sm font-mono uppercase tracking-wider truncate flex items-center gap-2" style={{ color: 'var(--color-on-accent)' }}>
            <Bot className="w-4 h-4" />
            {subagentLabel}
          </div>
          <div className="text-xs" style={{ color: 'color-mix(in srgb, var(--color-on-accent) 70%, transparent)' }}>
            {status === 'running' ? 'Working...' : status === 'completed' ? 'Complete' : 'Error'}
            {toolCalls.length > 0 && ` • ${toolCalls.length} tool calls`}
          </div>
        </div>

        <div className="flex items-center gap-1">
          <button
            onClick={onToggleExpand}
            className="p-1.5 transition-colors hover:bg-[color-mix(in_srgb,var(--color-on-accent)_20%,transparent)]"
            style={{ color: 'var(--color-on-accent)', borderRadius: 'var(--radius-control)' }}
            title={isExpanded ? 'Minimize' : 'Expand'}
          >
            {isExpanded ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>
          {onClose && (
            <button
              onClick={onClose}
              className="p-1.5 transition-colors hover:bg-[color-mix(in_srgb,var(--color-on-accent)_20%,transparent)]"
              style={{ color: 'var(--color-on-accent)', borderRadius: 'var(--radius-control)' }}
              title="Close"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Content - scrollable area */}
      <div
        ref={contentRef}
        className="flex-1 overflow-auto custom-scrollbar p-4"
        style={{ color: 'var(--color-text-primary)', backgroundColor: 'var(--surface-1)' }}
        onScroll={() => {
          if (contentRef.current) {
            const { scrollTop, scrollHeight, clientHeight } = contentRef.current;
            setIsAutoScroll(scrollHeight - clientHeight - scrollTop < 50);
          }
        }}
      >
        {/* Thinking section */}
        {thinkingContent && (
          <div className="mb-4">
            <div className="flex items-center gap-2 mb-2">
              <PenLine className="w-4 h-4" style={{ color: 'var(--color-primary)' }} />
              <span className="text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>
                Thinking
              </span>
            </div>
            <div className="pl-6">
              <div className="p-2" style={{ backgroundColor: 'var(--surface-1)', borderRadius: 'var(--radius-control)' }}>
                <AgentOutputRenderer content={thinkingContent} compact />
              </div>
            </div>
          </div>
        )}

        {/* Tool calls section */}
        {toolCalls.map((tool, idx) => (
          <div key={idx} className="mb-3 surface-inset overflow-hidden">
            <div className="flex items-center gap-2 px-3 py-2 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
              {tool.status === 'running' ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" style={{ color: 'var(--color-primary)' }} />
              ) : tool.status === 'complete' ? (
                <Wrench className="w-3.5 h-3.5" style={{ color: 'var(--color-success)' }} />
              ) : (
                <XCircle className="w-3.5 h-3.5" style={{ color: 'var(--color-error)' }} />
              )}
              <span className="text-xs font-mono uppercase tracking-wider" style={{ color: 'var(--color-text-primary)' }}>
                TOOL ▸ {tool.name}
              </span>
              <span className={`badge-mono ml-auto ${tool.status === 'running' ? 'tone-info' :
                tool.status === 'complete' ? 'tone-success' :
                  'tone-error'
                }`}>
                {tool.status}
              </span>
            </div>
            {tool.input && (
              <div className="px-3 py-2 text-xs" style={{ color: 'var(--color-text-muted)' }}>
                <div className="font-medium mb-1">Input:</div>
                <pre className="whitespace-pre-wrap font-mono text-xs opacity-80">{tool.input.slice(0, 200)}{tool.input.length > 200 ? '...' : ''}</pre>
              </div>
            )}
            {tool.output && (
              <div className="px-3 py-2 text-xs border-t" style={{ borderColor: 'var(--border-subtle)', color: 'var(--color-text-muted)' }}>
                <div className="font-medium mb-1">Output:</div>
                <pre className="whitespace-pre-wrap font-mono text-xs opacity-80">{tool.output.slice(0, 300)}{tool.output.length > 300 ? '...' : ''}</pre>
              </div>
            )}
          </div>
        ))}

        {/* Empty state */}
        {!thinkingContent && toolCalls.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full py-8" style={{ color: 'var(--color-text-muted)' }}>
            <Loader2 className="w-6 h-6 animate-spin mb-2" style={{ color: 'var(--color-primary)' }} />
            <span className="text-sm">Waiting for subagent response...</span>
          </div>
        )}
      </div>
    </div>
  );
};

/**
 * SubAgentPanelStack Component
 *
 * Container for multiple SubAgentPanels stacked vertically.
 * Styled to match RealtimeExecutionPanel.
 */
interface SubAgentInfo {
  id: string;
  label: string;
  parentRunId: string;
  events: WorkflowEvent[];
  status: 'running' | 'completed' | 'error';
  inputPreview?: string;
  outputPreview?: string;
}

interface SubAgentPanelStackProps {
  subagents: SubAgentInfo[];
  isVisible: boolean;
}

export const SubAgentPanelStack: React.FC<SubAgentPanelStackProps> = ({
  subagents,
  isVisible
}) => {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [dismissedIds, setDismissedIds] = useState<Set<string>>(new Set());

  if (!isVisible || subagents.length === 0) return null;

  const visibleSubagents = subagents.filter(s => !dismissedIds.has(s.id));
  if (visibleSubagents.length === 0) return null;

  return (
    <div className="flex flex-col gap-3 p-4 h-full overflow-auto custom-scrollbar" style={{ backgroundColor: 'var(--surface-1)' }}>


      {visibleSubagents.slice(0, 3).map((subagent) => (
        <SubAgentPanel
          key={subagent.id}
          subagentId={subagent.id}
          subagentLabel={subagent.label}
          events={subagent.events}
          isExpanded={expandedId === subagent.id}
          onToggleExpand={() => setExpandedId(expandedId === subagent.id ? null : subagent.id)}
          onClose={subagent.status !== 'running' ? () => setDismissedIds(new Set([...dismissedIds, subagent.id])) : undefined}
          status={subagent.status}
          inputPreview={subagent.inputPreview}
          outputPreview={subagent.outputPreview}
        />
      ))}

      {visibleSubagents.length > 3 && (
        <div
          className="text-xs text-center py-2 px-4 rounded-lg"
          style={{ backgroundColor: 'var(--color-background-dark)', color: 'var(--color-text-muted)' }}
        >
          +{visibleSubagents.length - 3} more subagents
        </div>
      )}
    </div>
  );
};

export default SubAgentPanel;
