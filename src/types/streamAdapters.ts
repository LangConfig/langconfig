import type { WorkflowEvent } from './events';

export type NormalizedStreamPart =
  | { type: 'run_started'; timestamp?: string; nodeId?: string; label?: string }
  | { type: 'run_completed'; timestamp?: string; nodeId?: string; label?: string; status?: 'success' | 'error'; error?: string }
  | { type: 'text_delta'; timestamp?: string; nodeId?: string; label?: string; text: string }
  | { type: 'tool_started'; timestamp?: string; nodeId?: string; label?: string; toolName: string; input?: unknown }
  | { type: 'tool_completed'; timestamp?: string; nodeId?: string; label?: string; toolName?: string; output?: unknown }
  | { type: 'artifact'; timestamp?: string; nodeId?: string; label?: string; artifact: unknown }
  | { type: 'error'; timestamp?: string; nodeId?: string; label?: string; error: string };

export function toNormalizedStreamPart(event: WorkflowEvent): NormalizedStreamPart | null {
  const data: any = event.data || {};
  const nodeId = data.node_id || data.node;
  const label = data.agent_label;

  switch (event.type) {
    case 'node_started':
      return { type: 'run_started', timestamp: event.timestamp, nodeId, label };
    case 'node_completed':
      return {
        type: 'run_completed',
        timestamp: event.timestamp,
        nodeId,
        label,
        status: data.status || 'success',
        error: data.error,
      };
    case 'on_chat_model_stream':
    case 'on_llm_stream':
    case 'token':
      return {
        type: 'text_delta',
        timestamp: event.timestamp,
        nodeId,
        label,
        text: data.content || data.token || '',
      };
    case 'on_tool_start':
    case 'tool_start':
      return {
        type: 'tool_started',
        timestamp: event.timestamp,
        nodeId,
        label,
        toolName: data.tool_name || data.tool || data.name || 'tool',
        input: data.input || data.inputs,
      };
    case 'on_tool_end':
      if (Array.isArray(data.artifacts) && data.artifacts.length > 0) {
        return { type: 'artifact', timestamp: event.timestamp, nodeId, label, artifact: data.artifacts[0] };
      }
      return {
        type: 'tool_completed',
        timestamp: event.timestamp,
        nodeId,
        label,
        toolName: data.tool_name,
        output: data.output,
      };
    case 'error':
      return {
        type: 'error',
        timestamp: event.timestamp,
        nodeId,
        label,
        error: data.error || data.message || 'Unknown error',
      };
    default:
      return null;
  }
}
