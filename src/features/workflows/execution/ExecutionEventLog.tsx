/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * Workflow Execution Log
 *
 * Beautiful, step-by-step visualization of workflow execution events.
 * Shows agent reasoning, tool calls, and outputs in a readable timeline.
 */

import React from 'react';
import {
  CheckCircle,
  XCircle,
  Clock,
  Wrench,
  MessageSquare,
  Brain,
  Zap,
  ChevronRight,
  ListChecks,
  FileText,
  Users
} from 'lucide-react';
import type { WorkflowEvent } from '@/types/events';
import { calculateAndFormatCost } from '@/utils/modelPricing';
import { sanitizeAgentOutput } from '@/components/ui/AgentOutputRenderer';

interface ExecutionEventLogProps {
  events: WorkflowEvent[];
  className?: string;
}

interface LogEntry {
  timestamp: string;
  icon: React.ReactNode;
  iconColor: string;
  title: string;
  description?: string;
  details?: any;
  type: 'info' | 'success' | 'error' | 'warning';
}

export default function ExecutionEventLog({ events, className = '' }: ExecutionEventLogProps) {
  // Convert events to readable log entries
  const logEntries: LogEntry[] = events.map((event) => {
    const timestamp = event.timestamp || new Date().toISOString();

    switch (event.type as string) {
      case 'on_chain_start':
        return {
          timestamp,
          icon: <Brain className="w-5 h-5" />,
          iconColor: 'var(--color-info)',
          title: `Started: ${event.data?.name || 'Agent Node'}`,
          description: 'Initializing agent execution',
          type: 'info' as const,
        };

      case 'on_chain_end':
        return {
          timestamp,
          icon: <CheckCircle className="w-5 h-5" />,
          iconColor: 'var(--color-success)',
          title: `Completed: ${event.data?.name || 'Agent Node'}`,
          description: 'Node execution finished successfully',
          type: 'success' as const,
        };

      case 'on_tool_start':
        const toolName = event.data?.tool_name || event.data?.name || 'Unknown Tool';
        const toolInput = event.data?.input_str || event.data?.input || '';
        return {
          timestamp,
          icon: <Wrench className="w-5 h-5" />,
          iconColor: 'var(--color-primary)',
          title: `Tool Call: ${toolName}`,
          description: toolInput,
          details: event.data?.arguments,
          type: 'info' as const,
        };

      case 'on_tool_end':
        return {
          timestamp,
          icon: <CheckCircle className="w-5 h-5" />,
          iconColor: 'var(--color-success)',
          title: `Tool Completed: ${event.data?.tool_name || event.data?.name}`,
          description: typeof event.data?.output === 'string'
            ? event.data.output.slice(0, 500) + (event.data.output.length > 500 ? '...' : '')
            : 'Tool executed successfully',
          type: 'success' as const,
        };

      case 'on_agent_action':
        const agentName = event.data?.agent_label || event.data?.node_name || 'Agent';
        const thought = event.data?.thought || event.data?.log || '';
        return {
          timestamp,
          icon: <MessageSquare className="w-5 h-5" />,
          iconColor: 'var(--color-info)',
          title: `${agentName}: Reasoning`,
          description: thought,
          type: 'info' as const,
        };

      case 'on_llm_end':
        const tokens = event.data?.token_usage || event.data?.usage || event.data?.tokens_used;
        let promptTokens = 0;
        let completionTokens = 0;
        let totalTokens = 0;

        if (typeof tokens === 'object' && tokens !== null) {
          promptTokens = Number(tokens.prompt_tokens) || 0;
          completionTokens = Number(tokens.completion_tokens) || 0;
          totalTokens = Number(tokens.total_tokens) || (promptTokens + completionTokens);
        } else if (typeof tokens === 'number') {
          totalTokens = tokens;
          completionTokens = tokens;
        }

        // Fallback to direct event data
        if (totalTokens === 0) {
          promptTokens = Number(event.data?.prompt_tokens) || 0;
          completionTokens = Number(event.data?.completion_tokens) || 0;
          totalTokens = promptTokens + completionTokens;
        }

        const modelName = event.data?.model || event.data?.model_name || 'gpt-5.4';

        let description = undefined;
        if (totalTokens > 0) {
          try {
            const costString = calculateAndFormatCost(promptTokens, completionTokens, modelName);
            description = `${totalTokens} tokens • ${costString} • ${modelName}`;
          } catch (e) {
            description = `${totalTokens} tokens • ${modelName}`;
          }
        }

        return {
          timestamp,
          icon: <Zap className="w-5 h-5" />,
          iconColor: 'var(--color-warning)',
          title: 'LLM Response Generated',
          description,
          type: 'info' as const,
        };

      // DeepAgent-specific events
      case 'DEEPAGENT_TODO_CREATED':
        return {
          timestamp,
          icon: <ListChecks className="w-5 h-5" />,
          iconColor: 'var(--color-info)',
          title: '✅ Created Todo',
          description: event.data?.todo_text,
          type: 'info' as const,
        };

      case 'DEEPAGENT_TODO_COMPLETED':
        return {
          timestamp,
          icon: <CheckCircle className="w-5 h-5" />,
          iconColor: 'var(--color-success)',
          title: '✓ Completed Todo',
          description: event.data?.todo_text,
          type: 'success' as const,
        };

      case 'DEEPAGENT_SUBAGENT_SPAWNED':
        return {
          timestamp,
          icon: <Users className="w-5 h-5" />,
          iconColor: 'var(--color-primary)',
          title: `Spawned Subagent: ${event.data?.subagent_name}`,
          description: event.data?.subagent_task,
          type: 'info' as const,
        };

      case 'DEEPAGENT_FILESYSTEM_OP':
        return {
          timestamp,
          icon: <FileText className="w-5 h-5" />,
          iconColor: 'var(--color-warning)',
          title: `File Operation: ${event.data?.operation}`,
          description: event.data?.file_path,
          type: 'info' as const,
        };

      case 'subagent_start':
        // Sanitize input preview - may be raw dict string
        const startDescription = sanitizeAgentOutput(
          event.data?.input_preview || `Delegated task to ${event.data?.subagent_name}`
        );
        return {
          timestamp,
          icon: <Users className="w-5 h-5" />,
          iconColor: 'var(--color-primary)',
          title: `🤖 Subagent Started: ${event.data?.subagent_name || 'Subagent'}`,
          description: startDescription.slice(0, 500) + (startDescription.length > 500 ? '...' : ''),
          type: 'info' as const,
        };

      case 'subagent_end':
        // Sanitize output - may be Command() structure
        const endOutput = sanitizeAgentOutput(
          event.data?.full_output || event.data?.output_preview || 'Subagent task finished'
        );
        return {
          timestamp,
          icon: event.data?.success ? <CheckCircle className="w-5 h-5" /> : <XCircle className="w-5 h-5" />,
          iconColor: event.data?.success ? 'var(--color-success)' : 'var(--color-error)',
          title: `${event.data?.success ? '✅' : '❌'} Subagent Completed: ${event.data?.subagent_name || 'Subagent'}`,
          description: endOutput.slice(0, 500) + (endOutput.length > 500 ? '...' : ''),
          type: event.data?.success ? 'success' as const : 'error' as const,
        };

      case 'error':
        return {
          timestamp,
          icon: <XCircle className="w-5 h-5" />,
          iconColor: 'var(--color-error)',
          title: 'Error Occurred',
          description: event.data?.error || event.data?.message,
          type: 'error' as const,
        };

      case 'status':
        return {
          timestamp,
          icon: <Clock className="w-5 h-5" />,
          iconColor: 'var(--color-text-muted)',
          title: 'Status Update',
          description: event.data?.message,
          type: 'info' as const,
        };

      default:
        // Skip internal events like ping, connected, etc.
        if (['ping', 'connected', 'complete'].includes(event.type)) {
          return null;
        }

        return {
          timestamp,
          icon: <ChevronRight className="w-5 h-5" />,
          iconColor: 'var(--color-text-muted)',
          title: event.type,
          description: event.data?.message || JSON.stringify(event.data || {}),
          type: 'info' as const,
        };
    }
  }).filter(Boolean) as LogEntry[];

  if (logEntries.length === 0) {
    return (
      <div className={`flex flex-col items-center justify-center py-12 text-center ${className}`}>
        <Clock className="w-16 h-16 mb-4 opacity-30" style={{ color: 'var(--color-text-muted)' }} />
        <p className="text-lg font-medium" style={{ color: 'var(--color-text-muted)' }}>
          No execution events yet
        </p>
        <p className="text-sm mt-2 opacity-70" style={{ color: 'var(--color-text-muted)' }}>
          Events will appear here as the workflow executes
        </p>
      </div>
    );
  }

  return (
    <div className={`space-y-0 ${className}`}>
      {logEntries.map((entry, idx) => (
        <div
          key={idx}
          className="relative flex gap-4 p-4 hover:bg-[var(--color-accent-wash)] transition-colors border-l-2 ml-6"
          style={{ borderColor: 'var(--border-subtle)' }}
        >
          {/* Timeline icon */}
          <div
            className="absolute left-[-25px] top-4 w-10 h-10 rounded-full flex items-center justify-center"
            style={{
              backgroundColor: entry.type === 'success' ? 'var(--color-success-wash)' :
                entry.type === 'error' ? 'var(--color-error-wash)' :
                  entry.type === 'warning' ? 'var(--color-warning-wash)' :
                    'var(--color-info-wash)',
              border: '1px solid var(--border-subtle)'
            }}
          >
            <div style={{ color: entry.iconColor }}>
              {entry.icon}
            </div>
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0 pt-1">
            {/* Timestamp */}
            <div className="text-xs font-mono mb-1 opacity-70" style={{ color: 'var(--color-text-muted)' }}>
              {new Date(entry.timestamp).toLocaleTimeString()}
            </div>

            {/* Title */}
            <div className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
              {entry.title}
            </div>

            {/* Description */}
            {entry.description && (
              <div className="text-sm mt-1.5 whitespace-pre-wrap" style={{ color: 'var(--color-text-muted)' }}>
                {entry.description}
              </div>
            )}

            {/* Details (collapsed by default) */}
            {entry.details && Object.keys(entry.details).length > 0 && (
              <details className="mt-2">
                <summary className="text-xs cursor-pointer opacity-70 hover:opacity-100" style={{ color: 'var(--color-text-muted)' }}>
                  View details
                </summary>
                <pre className="text-xs mt-1 font-mono surface-inset p-2 overflow-x-auto" style={{ color: 'var(--color-text-muted)' }}>
                  {JSON.stringify(entry.details, null, 2)}
                </pre>
              </details>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
