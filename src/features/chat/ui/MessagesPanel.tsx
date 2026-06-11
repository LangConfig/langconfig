/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useRef, useEffect, useState } from 'react';
import { Copy, CheckCircle, AlertCircle, X, Trash2, Wrench } from 'lucide-react';
import type { ChatMessage, ChatToolCallRecord, CustomEventPayload } from '../types/chat';
import MessageInput from './MessageInput';
import SessionDocumentsPanel from './SessionDocumentsPanel';
import { ContentBlockRenderer } from '@/components/common/ContentBlockRenderer';
import { ProgressCard, StatusBadge, FileOperationCard } from '@/features/workflows/execution/CustomEventCards';
import type { ProgressEvent, StatusEvent, FileStatusEvent } from '@/hooks/useCustomEvents';
import { Surface } from '@/components/ui/Surface';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Markdown } from '@/components/ui/Markdown';
import { AvatarOrb } from '@/components/ui/AvatarOrb';

interface MessagesPanelProps {
  messages: ChatMessage[];
  isStreaming: boolean;
  error: string | null;
  onSendMessage: (message: string) => void;
  onClearError: () => void;
  onDeleteMessage?: (messageIndex: number) => Promise<void>;
  disabled?: boolean;
  sessionId?: string | null;
  /** @deprecated tool calls now render in-flow via message.tool_calls */
  activeToolCalls?: string[];
  customEvents?: Map<string, CustomEventPayload>;
}

/** Pretty-print tool input/output payloads for the chip detail view. */
function formatToolPayload(payload: any): string {
  if (payload == null) return '';
  if (typeof payload === 'string') return payload;
  try {
    return JSON.stringify(payload, null, 2);
  } catch {
    return String(payload);
  }
}

/** Collapsible status chip for one tool invocation inside a message. */
function ToolCallChip({ call }: { call: ChatToolCallRecord }) {
  const tone = call.status === 'running' ? 'accent' : call.status === 'error' ? 'error' : 'success';
  const input = formatToolPayload(call.input);
  const output = formatToolPayload(call.error ?? call.output);
  const hasDetail = Boolean(input || output);

  return (
    <details className="group">
      <summary
        className={`cursor-pointer list-none inline-flex items-center gap-1.5 ${hasDetail ? '' : 'pointer-events-none'}`}
      >
        <Badge tone={tone} dot pulse={call.status === 'running'}>
          <Wrench className="mr-1 inline h-3 w-3" />
          {call.tool_name}
          {call.status === 'error' ? ' — failed' : ''}
        </Badge>
        {hasDetail && (
          <span
            className="opacity-50 transition-transform group-open:rotate-90 text-[10px]"
            style={{ color: 'var(--color-text-muted)' }}
          >
            ▸
          </span>
        )}
      </summary>
      {hasDetail && (
        <div
          className="surface-inset mt-1 px-3 py-2 font-mono text-xs space-y-2"
          style={{ color: 'var(--color-text-muted)', maxHeight: '12rem', overflowY: 'auto' }}
        >
          {input && (
            <div>
              <div className="uppercase tracking-[0.12em] text-[10px] mb-0.5">Input</div>
              <pre className="whitespace-pre-wrap break-words">{input.slice(0, 2000)}</pre>
            </div>
          )}
          {output && (
            <div>
              <div className="uppercase tracking-[0.12em] text-[10px] mb-0.5">
                {call.status === 'error' ? 'Error' : 'Result'}
              </div>
              <pre className="whitespace-pre-wrap break-words">{output.slice(0, 2000)}</pre>
            </div>
          )}
        </div>
      )}
    </details>
  );
}

export default function MessagesPanel({
  messages,
  isStreaming,
  error,
  onSendMessage,
  onClearError,
  onDeleteMessage,
  disabled = false,
  sessionId = null,
  activeToolCalls = [],
  customEvents = new Map()
}: MessagesPanelProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const pinnedToBottomRef = useRef(true);
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  // Track whether the user is reading at the bottom; if they scroll up to
  // re-read something, streaming must not yank the view back down.
  const handleScroll = () => {
    const el = scrollContainerRef.current;
    if (!el) return;
    pinnedToBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 96;
  };

  // Auto-scroll only when pinned to the bottom. 'auto' during streaming:
  // overlapping smooth-scroll animations on every batched flush cause jank.
  useEffect(() => {
    if (!pinnedToBottomRef.current) return;
    messagesEndRef.current?.scrollIntoView({ behavior: isStreaming ? 'auto' : 'smooth' });
  }, [messages, isStreaming]);

  const copyToClipboard = (text: string, index: number) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  return (
    <div className="flex-1 flex flex-col min-w-0" style={{ backgroundColor: 'var(--color-background-light)' }}>
      {/* Messages Area */}
      <div
        ref={scrollContainerRef}
        onScroll={handleScroll}
        className="chat-atmosphere flex-1 overflow-y-auto px-4 py-6"
      >
        {messages.length === 0 && !disabled ? (
          <div
            className="flex items-center justify-center h-full min-h-full"
            style={{ color: 'var(--color-text-muted)' }}
          >
            <div className="text-center max-w-2xl px-6">
              <img
                src="/peony.png"
                alt="Agent"
                className="w-20 h-20 mx-auto mb-6 opacity-25"
                style={{ filter: 'grayscale(100%)' }}
              />
              <p className="text-xl font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                Start a conversation
              </p>
              <div
                className="mx-auto h-1 w-24"
                style={{
                  border: '1px solid var(--border-strong)',
                  background: 'var(--surface-2)',
                }}
              />
            </div>
          </div>
        ) : (
          <div className="relative max-w-4xl mx-auto space-y-6">

          {messages.map((message, index) => {
            const isLastMessage = index === messages.length - 1;
            const isActivelyStreaming = isStreaming && isLastMessage && message.role === 'assistant';

            return (
            <div
              key={index}
              className={`flex gap-4 ${message.role === 'user' ? 'flex-row-reverse' : ''}`}
            >
              {/* Avatar */}
              {message.role !== 'system' && (
                <AvatarOrb
                  kind={message.role === 'user' ? 'user' : 'agent'}
                  state={isActivelyStreaming ? 'streaming' : 'idle'}
                  src={message.role === 'user' ? undefined : '/peony.png'}
                  size={32}
                />
              )}

              {/* Message Content */}
              <div className={`flex-1 ${message.role === 'user' ? 'flex justify-end' : ''}`}>
                <div className={`${message.role === 'system' ? 'text-center w-full' : 'max-w-3xl'}`}>
                  {message.role === 'system' ? (
                    <Badge tone="neutral">{message.content}</Badge>
                  ) : (
                    <>
                      {/* Message Bubble */}
                      {message.role === 'user' ? (
                        <div
                          className="chat-bubble-user px-5 py-3"
                          style={{
                            background: 'var(--color-primary)',
                            color: 'var(--color-on-accent)',
                            borderRadius: 'var(--radius-card)',
                            border: 'var(--border-w) solid var(--border-strong)',
                            boxShadow: 'var(--shadow-card-sm)',
                          }}
                        >
                          <Markdown compact>{message.content}</Markdown>

                          {/* Multimodal Content Blocks (images, audio, files from MCP tools) */}
                          {message.has_multimodal && message.content_blocks && message.content_blocks.length > 0 && (
                            <div className="mt-3 pt-3 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
                              <ContentBlockRenderer blocks={message.content_blocks} />
                            </div>
                          )}
                        </div>
                      ) : (
                        <>
                          {/* Model thinking (adaptive thinking summaries, collapsed by default) */}
                          {message.thinking && (
                            <details className="mb-1.5 group">
                              <summary
                                className="cursor-pointer list-none font-mono text-[10px] uppercase tracking-[0.14em] inline-flex items-center gap-1.5"
                                style={{ color: 'var(--color-text-muted)' }}
                              >
                                <span className={isActivelyStreaming ? 'thinking-shimmer' : ''}>Thinking</span>
                                <span className="opacity-50 group-open:rotate-90 transition-transform">▸</span>
                              </summary>
                              <div
                                className="surface-inset mt-1 px-3 py-2 text-xs whitespace-pre-wrap"
                                style={{ color: 'var(--color-text-muted)', maxHeight: '14rem', overflowY: 'auto' }}
                              >
                                {message.thinking}
                              </div>
                            </details>
                          )}
                        <Surface
                          variant="card-sm"
                          className={`px-5 py-3 ${isActivelyStreaming ? 'streaming-pulse' : ''}`}
                        >
                          {/* Tool calls made while producing this message */}
                          {message.tool_calls && message.tool_calls.length > 0 && (
                            <div className="mb-2 flex flex-col gap-1.5">
                              {message.tool_calls.map((call, callIdx) => (
                                <ToolCallChip key={`${call.tool_name}-${callIdx}`} call={call} />
                              ))}
                            </div>
                          )}

                          <div style={{ color: 'var(--color-text-primary)' }}>
                            <Markdown compact>{message.content}</Markdown>
                          </div>

                          {/* Multimodal Content Blocks (images, audio, files from MCP tools) */}
                          {message.has_multimodal && message.content_blocks && message.content_blocks.length > 0 && (
                            <div className="mt-3 pt-3 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
                              <ContentBlockRenderer blocks={message.content_blocks} />
                            </div>
                          )}

                          {/* Artifacts (UI-only content, not sent to LLM) */}
                          {message.artifacts && message.artifacts.length > 0 && (
                            <div className="mt-3 pt-3 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
                              <p
                                className="font-mono text-[10px] uppercase tracking-[0.12em] mb-2"
                                style={{ color: 'var(--color-text-muted)' }}
                              >
                                Generated Content
                              </p>
                              <ContentBlockRenderer blocks={message.artifacts} />
                            </div>
                          )}
                        </Surface>
                        </>
                      )}

                      {/* Message Footer */}
                      <div className={`flex items-center gap-2 mt-2 px-2 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                        <span
                          className="text-xs"
                          style={{ color: 'var(--color-text-muted)' }}
                        >
                          {new Date(message.timestamp).toLocaleTimeString()}
                        </span>

                        {message.role === 'assistant' && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => copyToClipboard(message.content, index)}
                            title="Copy message"
                          >
                            {copiedIndex === index ? (
                              <CheckCircle className="w-3.5 h-3.5" style={{ color: 'var(--color-success)' }} />
                            ) : (
                              <Copy className="w-3.5 h-3.5" />
                            )}
                          </Button>
                        )}

                        {message.role === 'user' && onDeleteMessage && !isStreaming && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={async () => {
                              const confirmed = window.confirm(
                                'Delete this user message? The live chat runtime will reset so the agent does not keep stale memory.'
                              );
                              if (!confirmed) return;
                              await onDeleteMessage(index);
                            }}
                            title="Delete user message"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </Button>
                        )}
                      </div>
                    </>
                  )}
                </div>
              </div>
            </div>
            );
          })}

          {/* Streaming Indicator - only show before first token */}
          {isStreaming && messages.length > 0 && messages[messages.length - 1].role === 'user' && (
            <div className="flex gap-4">
              <AvatarOrb kind="agent" state="thinking" src="/peony.png" size={32} />
              <div className="flex-1">
                <Surface variant="card-sm" className="inline-block px-5 py-3 streaming-pulse">
                  <span className="thinking-shimmer terminal-caret">Thinking</span>
                </Surface>
              </div>
            </div>
          )}

          {/* Tool calls render in-flow inside each assistant message
              (message.tool_calls -> ToolCallChip); the old floating
              activeToolCalls strip was removed as redundant. */}

          {/* Custom Events (LangGraph-style progress, status, file operations) */}
          {customEvents.size > 0 && (
            <div className="flex gap-4">
              <AvatarOrb kind="agent" state="streaming" size={32} />
              <div className="flex-1">
                <Surface variant="card-sm" className="space-y-2 px-5 py-3">
                  {Array.from(customEvents.values()).map((event, idx) => {
                    const eventId = event.event_id || `custom-${idx}`;

                    // Convert CustomEventPayload to the component-specific event format
                    if (event.event_type === 'progress') {
                      const progressEvent: ProgressEvent = {
                        id: eventId,
                        data: {
                          label: event.payload.label || 'Progress',
                          value: event.payload.value || 0,
                          total: event.payload.total,
                          message: event.payload.message,
                        },
                        toolName: event.tool_name,
                        agentLabel: event.agent_label,
                        nodeId: event.node_id,
                        timestamp: event.timestamp || new Date().toISOString(),
                      };
                      return <ProgressCard key={eventId} event={progressEvent} compact />;
                    }

                    if (event.event_type === 'status') {
                      const statusEvent: StatusEvent = {
                        id: eventId,
                        data: {
                          label: event.payload.label || 'Status',
                          status: event.payload.status || 'running',
                          message: event.payload.message,
                        },
                        toolName: event.tool_name,
                        agentLabel: event.agent_label,
                        nodeId: event.node_id,
                        timestamp: event.timestamp || new Date().toISOString(),
                      };
                      return <StatusBadge key={eventId} event={statusEvent} compact />;
                    }

                    if (event.event_type === 'file_status') {
                      const fileEvent: FileStatusEvent = {
                        id: eventId,
                        data: {
                          filename: event.payload.filename || 'file',
                          operation: event.payload.operation || 'reading',
                          size_bytes: event.payload.size_bytes,
                          message: event.payload.message,
                        },
                        toolName: event.tool_name,
                        agentLabel: event.agent_label,
                        nodeId: event.node_id,
                        timestamp: event.timestamp || new Date().toISOString(),
                      };
                      return <FileOperationCard key={eventId} event={fileEvent} compact />;
                    }

                    // Generic custom event - show as simple badge
                    return (
                      <div
                        key={eventId}
                        className="surface-inset px-2 py-1 font-mono text-xs"
                        style={{ color: 'var(--color-text-primary)' }}
                      >
                        <span className="uppercase tracking-[0.1em]">{event.event_type}</span>: {JSON.stringify(event.payload)}
                      </div>
                    );
                  })}
                </Surface>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Error Display */}
      {error && (
        <Surface variant="card-sm" tone="error" className="mx-4 mb-2 flex items-center gap-2 p-3">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span className="text-sm flex-1">{error}</span>
          <button
            onClick={onClearError}
            className="hover:opacity-70 transition-opacity"
            title="Dismiss error"
          >
            <X className="w-4 h-4" />
          </button>
        </Surface>
      )}

      {/* Session Documents Panel */}
      <SessionDocumentsPanel sessionId={sessionId} />

      {/* Input Area */}
      <div
        className="border-t-2 p-4"
        style={{ borderColor: 'var(--border-strong)' }}
      >
        <MessageInput
          onSendMessage={onSendMessage}
          disabled={disabled}
          isStreaming={isStreaming}
          placeholder={disabled ? "Select an agent first..." : "Type your message..."}
          sessionId={sessionId}
          onFileUploaded={(file) => {
            console.log('File uploaded:', file);
          }}
        />
      </div>
    </div>
  );
}
