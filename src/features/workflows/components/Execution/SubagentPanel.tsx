/**
 * SubAgentPanel Component
 *
 * Displays subagent execution in a stacked panel on the right side of RealtimeExecutionPanel.
 * Shows subagent thinking/reasoning and tool calls in real-time.
 * Styled to match RealtimeExecutionPanel for visual consistency.
 */

import React, { useState, useMemo, useRef, useEffect } from 'react';
import { Maximize2, Minimize2, Bot, Loader2, Wrench, CheckCircle, XCircle, X, PenLine } from 'lucide-react';
import { AgentOutputRenderer, sanitizeAgentOutput } from '../../../../components/ui/AgentOutputRenderer';
import type { WorkflowEvent } from '../../../../types/events';

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

  const statusColor = status === 'error' ? '#ef4444' : status === 'completed' ? '#6ee7b7' : 'var(--color-primary)';

  return (
    <div
      className={`flex flex-col rounded-lg overflow-hidden transition-all duration-300 ${isExpanded ? 'flex-1' : ''
        }`}
      style={{
        backgroundColor: 'transparent',
        border: `3px solid ${statusColor}`,
        minHeight: isExpanded ? '100%' : '180px',
        maxHeight: isExpanded ? '100%' : '300px',
        boxShadow: status === 'running' ? `0 0 12px ${statusColor}40` : 'none'
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
        <div className="p-1.5 rounded-md" style={{ backgroundColor: 'rgba(255, 255, 255, 0.2)' }}>
          {status === 'running' ? (
            <Loader2 className="w-4 h-4 text-white animate-spin" />
          ) : status === 'completed' ? (
            <CheckCircle className="w-4 h-4 text-white" />
          ) : (
            <XCircle className="w-4 h-4 text-white" />
          )}
        </div>

        <div className="flex-1 min-w-0">
          <div className="font-semibold text-sm text-white truncate flex items-center gap-2">
            <Bot className="w-4 h-4" />
            {subagentLabel}
          </div>
          <div className="text-xs text-white/70">
            {status === 'running' ? 'Working...' : status === 'completed' ? 'Complete' : 'Error'}
            {toolCalls.length > 0 && ` • ${toolCalls.length} tool calls`}
          </div>
        </div>

        <div className="flex items-center gap-1">
          <button
            onClick={onToggleExpand}
            className="p-1.5 rounded-md hover:bg-white/20 transition-colors text-white"
            title={isExpanded ? 'Minimize' : 'Expand'}
          >
            {isExpanded ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>
          {onClose && (
            <button
              onClick={onClose}
              className="p-1.5 rounded-md hover:bg-white/20 transition-colors text-white"
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
        style={{ color: 'var(--color-text-primary)', backgroundColor: 'white' }}
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
              <div className="bg-white rounded-md p-2">
                <AgentOutputRenderer content={thinkingContent} compact />
              </div>
            </div>
          </div>
        )}

        {/* Tool calls section */}
        {toolCalls.map((tool, idx) => (
          <div key={idx} className="mb-3 rounded-lg overflow-hidden" style={{ backgroundColor: 'white' }}>
            <div className="flex items-center gap-2 px-3 py-2 border-b" style={{ borderColor: 'var(--color-border-dark)' }}>
              {tool.status === 'running' ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" style={{ color: 'var(--color-primary)' }} />
              ) : tool.status === 'complete' ? (
                <Wrench className="w-3.5 h-3.5" style={{ color: '#10b981' }} />
              ) : (
                <XCircle className="w-3.5 h-3.5 text-red-500" />
              )}
              <span className="text-xs font-medium" style={{ color: 'var(--color-text-primary)' }}>
                {tool.name}
              </span>
              <span className={`text-xs ml-auto px-1.5 py-0.5 rounded ${tool.status === 'running' ? 'bg-blue-500/20 text-blue-400' :
                tool.status === 'complete' ? 'bg-green-500/20 text-green-400' :
                  'bg-red-500/20 text-red-400'
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
              <div className="px-3 py-2 text-xs border-t" style={{ borderColor: 'var(--color-border-dark)', color: 'var(--color-text-secondary)' }}>
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
    <div className="flex flex-col gap-3 p-4 h-full overflow-auto custom-scrollbar" style={{ backgroundColor: 'white' }}>


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
