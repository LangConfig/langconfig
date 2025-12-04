/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * useWorkflowStream Hook
 *
 * Custom React hook for streaming real-time workflow execution events via SSE.
 *
 * Features:
 * - Auto-connects to SSE endpoint when workflow_id provided
 * - Automatic reconnection on connection loss
 * - Typed event handling for all LangGraph events
 * - Event accumulation and state management
 * - Cleanup on unmount
 * - Idempotency key support to prevent duplicate events
 * - Request cancellation support
 * - Enhanced buffering for smoother UI
 *
 * Usage:
 *   const { events, isConnected, error, latestEvent } = useWorkflowStream(workflowId);
 *
 *   // React to specific events
 *   useEffect(() => {
 *     if (latestEvent?.type === 'on_tool_start') {
 *     }
 *   }, [latestEvent]);
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { WorkflowEvent, WorkflowEventType } from '../types/events';
import apiClient from '../lib/api-client';

export interface UseWorkflowStreamOptions {
  /** Auto-connect on mount (default: true) */
  autoConnect?: boolean;
  /** Max events to keep in memory (default: 1000) */
  maxEvents?: number;
  /** Callback for specific event types */
  onEvent?: (event: WorkflowEvent) => void;
  /** Callback for connection status changes */
  onConnectionChange?: (connected: boolean) => void;
  /** Task ID for loading historical events */
  taskId?: number | null;
  /** Auto-load historical events on mount (default: true if taskId provided) */
  loadHistorical?: boolean;
  /** Token buffer duration in ms (default: 16ms for ~60fps) */
  tokenBufferMs?: number;
}

export interface UseWorkflowStreamResult {
  /** All accumulated events (historical + live) */
  events: WorkflowEvent[];
  /** Latest event received */
  latestEvent: WorkflowEvent | null;
  /** Connection status */
  isConnected: boolean;
  /** Connection error */
  error: string | null;
  /** Manually connect to stream */
  connect: () => void;
  /** Manually disconnect from stream */
  disconnect: () => void;
  /** Clear accumulated events */
  clearEvents: () => void;
  /** Get events by type */
  getEventsByType: (type: WorkflowEventType) => WorkflowEvent[];
  /** Load historical events for the task */
  loadHistoricalEvents: () => Promise<void>;
  /** Whether historical events are loading */
  isLoadingHistorical: boolean;
  /** Whether historical events have been loaded */
  historicalLoaded: boolean;
}

export function useWorkflowStream(
  workflowId: number | null,
  options: UseWorkflowStreamOptions = {}
): UseWorkflowStreamResult {
  const {
    autoConnect = true,
    maxEvents = 1000,
    onEvent,
    onConnectionChange,
    taskId = null,
    loadHistorical = true,
    tokenBufferMs = 16,
  } = options;

  // State
  const [events, setEvents] = useState<WorkflowEvent[]>([]);
  const [latestEvent, setLatestEvent] = useState<WorkflowEvent | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isLoadingHistorical, setIsLoadingHistorical] = useState(false);
  const [historicalLoaded, setHistoricalLoaded] = useState(false);

  // Refs
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const lastSequenceRef = useRef<number>(0);  // Track last received sequence number for gap detection
  const processedEventKeys = useRef(new Set<string>()); // Idempotency key tracking

  // Streaming micro-batching to reduce re-renders (aim ~60fps)
  const streamBufferRef = useRef<WorkflowEvent[]>([]);
  const flushTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const flushStreamBuffer = useCallback(() => {
    if (streamBufferRef.current.length === 0) return;

    const buffered = streamBufferRef.current;
    streamBufferRef.current = [];
    flushTimeoutRef.current = null;

    setEvents((prev) => {
      const merged = prev.concat(buffered);
      return merged.length > maxEvents ? merged.slice(-maxEvents) : merged;
    });

    const last = buffered[buffered.length - 1];
    if (last) setLatestEvent(last);
    // Intentionally do not call onEvent for each token to avoid perf hits
  }, [maxEvents]);

  // Constants
  const MAX_RECONNECT_ATTEMPTS = 5;
  const RECONNECT_DELAY_BASE = 1000; // 1 second

  /**
   * Add event to accumulator
   */
  const addEvent = useCallback((event: WorkflowEvent) => {
    setEvents((prev) => {
      const newEvents = [...prev, event];
      // Limit memory usage
      if (newEvents.length > maxEvents) {
        return newEvents.slice(-maxEvents);
      }
      return newEvents;
    });
    setLatestEvent(event);
    onEvent?.(event);
  }, [maxEvents, onEvent]);

  /**
   * Update connection status
   */
  const updateConnectionStatus = useCallback((connected: boolean) => {
    setIsConnected(connected);
    onConnectionChange?.(connected);
  }, [onConnectionChange]);

  /**
   * Load historical events from the database for completed workflows
   */
  const loadHistoricalEvents = useCallback(async () => {
    if (!taskId) {
      console.warn('[useWorkflowStream] No task ID provided for historical events');
      return;
    }

    if (historicalLoaded) {
      return;
    }

    setIsLoadingHistorical(true);
    setError(null);

    try {
      const url = `${apiClient.baseURL}/api/tasks/${taskId}/events`;
      const response = await fetch(url);

      if (!response.ok) {
        // 404 is expected if task doesn't exist yet or has no events
        if (response.status === 404) {
          setHistoricalLoaded(true);
          return;
        }
        throw new Error(`Failed to load historical events: ${response.statusText}`);
      }

      const data = await response.json();

      // Transform historical events to match WorkflowEvent format
      // Backend returns: { task_id, total_events, events: [...] }
      const eventsArray = data.events || data; // Handle both formats
      const historicalEvents: WorkflowEvent[] = eventsArray.map((event: any) => ({
        type: event.event_type as WorkflowEventType,
        data: event.event_data,
        event_id: event.id,
        timestamp: event.timestamp,
        sequence_number: event.sequence_number || 0,
        idempotency_key: event.idempotency_key || `hist-${event.id}`,
        channel: event.channel || 'historical'
      }));

      // DEBUG: Log event types breakdown
      const eventTypeCounts: Record<string, number> = {};
      const eventsWithoutAgent: any[] = [];
      historicalEvents.forEach(event => {
        eventTypeCounts[event.type] = (eventTypeCounts[event.type] || 0) + 1;
        if (!event.data?.agent_label && !event.data?.node_id) {
          eventsWithoutAgent.push({ type: event.type, data: event.data });
        }
      });
      console.log('[useWorkflowStream] Historical events loaded:', {
        total: historicalEvents.length,
        typeCounts: eventTypeCounts,
        eventsWithoutAgent: eventsWithoutAgent.length,
        sampleEventsWithoutAgent: eventsWithoutAgent.slice(0, 5)
      });

      // Set events to historical events (they will be merged with live events as they arrive)
      setEvents(historicalEvents);
      if (historicalEvents.length > 0) {
        setLatestEvent(historicalEvents[historicalEvents.length - 1]);
      }
      setHistoricalLoaded(true);

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load historical events';
      console.error('[useWorkflowStream]', errorMessage, err);
      setError(errorMessage);
    } finally {
      setIsLoadingHistorical(false);
    }
  }, [taskId, historicalLoaded]);

  /**
   * Connect to SSE stream
   */
  const connect = useCallback(() => {
    if (!workflowId) {
      console.warn('[useWorkflowStream] No workflow ID provided');
      return;
    }

    if (eventSourceRef.current) {
      console.warn('[useWorkflowStream] Already connected');
      return;
    }

    setError(null);

    const url = `${apiClient.baseURL}/api/orchestration/workflows/${workflowId}/stream`;
    console.log('[useWorkflowStream] Connecting to SSE:', url);
    const eventSource = new EventSource(url);

    eventSourceRef.current = eventSource;

    // Handle specific event types
    const eventTypes: WorkflowEventType[] = [
      'connected',
      'on_chain_start',
      'on_chain_end',
      'on_tool_start',
      'on_tool_end',
      'on_chat_model_start',
      'on_chat_model_stream',
      'on_chat_model_end',
      'on_agent_action',
      'on_agent_finish',
      'on_llm_end',
      'checkpoint',
      'status',
      'complete',
      'error',
      'warning',
      'ping',
      'hitl_approved',
      'hitl_rejected',
      'recursion_limit_hit',
      'keepalive'
    ];

    eventTypes.forEach((eventType) => {
      eventSource.addEventListener(eventType, (e: MessageEvent) => {
        try {
          // Skip if no data (shouldn't happen for real SSE events, but browser errors can trigger this)
          if (!e.data || e.data === 'undefined') {
            console.warn(`[useWorkflowStream] Received ${eventType} event with no data, skipping`);
            return;
          }

          const parsedData = JSON.parse(e.data);

          // Extract metadata from data payload (sent by backend via SSE)
          const { sequence_number, timestamp, channel, event_id: dataEventId, idempotency_key, ...cleanData } = parsedData;

          // Idempotency check
          const eventKey = idempotency_key || `${eventType}-${sequence_number}-${timestamp}`;
          if (processedEventKeys.current.has(eventKey)) {
            // console.debug(`[useWorkflowStream] Skipping duplicate event: ${eventKey}`);
            return;
          }
          processedEventKeys.current.add(eventKey);

          // Clear old keys to prevent memory leak (sliding window)
          if (processedEventKeys.current.size > 2000) {
            const keys = Array.from(processedEventKeys.current);
            processedEventKeys.current = new Set(keys.slice(-1000));
          }

          const event: WorkflowEvent = {
            type: eventType,
            data: cleanData,  // Clean data without metadata
            event_id: parseInt(e.lastEventId || '0', 10),
            sequence_number: sequence_number || 0,
            idempotency_key: eventKey,
            timestamp: timestamp || new Date().toISOString(),
            channel: channel || 'default',
          };

          // Gap detection: check for missing sequence numbers
          if (event.sequence_number !== undefined && event.sequence_number > 0) {
            const expected = lastSequenceRef.current + 1;
            if (lastSequenceRef.current > 0 && event.sequence_number > expected) {
              const missing = event.sequence_number - expected;
              console.warn(
                `[useWorkflowStream] Gap detected! Missing ${missing} event(s). ` +
                `Expected sequence ${expected}, received ${event.sequence_number}`
              );
            }
            lastSequenceRef.current = event.sequence_number;
          }

          if (eventType === 'on_chat_model_stream') {
            // Buffer token events and flush on timer
            streamBufferRef.current.push(event);
            if (!flushTimeoutRef.current) {
              flushTimeoutRef.current = setTimeout(flushStreamBuffer, tokenBufferMs);
            }
          } else {
            // Flush any pending tokens before processing non-token event to maintain order
            if (streamBufferRef.current.length > 0) {
              flushStreamBuffer();
              if (flushTimeoutRef.current) {
                clearTimeout(flushTimeoutRef.current);
                flushTimeoutRef.current = null;
              }
            }
            addEvent(event);
          }

        } catch (err) {
          console.error(`[useWorkflowStream] Failed to parse ${eventType} event:`, err, 'Raw data:', e.data);
        }
      });
    });

    // Connection opened
    eventSource.onopen = () => {
      updateConnectionStatus(true);
      reconnectAttemptsRef.current = 0; // Reset reconnect attempts
    };

    // Connection error
    eventSource.onerror = (err) => {
      console.error('[useWorkflowStream] Connection error:', err);
      console.error('[useWorkflowStream] EventSource state:', eventSource.readyState, '(0=CONNECTING, 1=OPEN, 2=CLOSED)');
      updateConnectionStatus(false);

      // EventSource auto-reconnects by default, but we track it
      if (eventSource.readyState === EventSource.CLOSED) {
        setError('Connection closed');

        // Attempt manual reconnect with exponential backoff
        if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
          reconnectAttemptsRef.current += 1;
          const delay = RECONNECT_DELAY_BASE * Math.pow(2, reconnectAttemptsRef.current - 1);

          // Reconnecting...

          reconnectTimeoutRef.current = setTimeout(() => {
            disconnect(); // Clean up old connection
            connect(); // Try reconnecting
          }, delay);
        } else {
          setError('Max reconnection attempts reached');
          disconnect();
        }
      }
    };
  }, [workflowId, addEvent, updateConnectionStatus, tokenBufferMs, flushStreamBuffer]);

  /**
   * Disconnect from SSE stream
   */
  const disconnect = useCallback(async () => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (flushTimeoutRef.current) {
      clearTimeout(flushTimeoutRef.current);
      flushTimeoutRef.current = null;
    }

    // Flush any remaining buffered events
    if (streamBufferRef.current.length > 0) {
      flushStreamBuffer();
    }

    streamBufferRef.current = [];
    lastSequenceRef.current = 0;  // Reset sequence tracking on disconnect
    processedEventKeys.current.clear(); // Clear idempotency keys

    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
      updateConnectionStatus(false);

      // Notify backend of cancellation if workflow is still running
      if (workflowId && isConnected) {
        try {
          await apiClient.apiFetch(`${apiClient.baseURL}/api/workflows/${workflowId}/cancel`, {
            method: 'POST'
          });
        } catch (e) {
          // Ignore errors during cancellation
          console.warn('[useWorkflowStream] Failed to notify backend of cancellation:', e);
        }
      }
    }
  }, [updateConnectionStatus, flushStreamBuffer, workflowId, isConnected]);

  /**
   * Clear accumulated events
   */
  const clearEvents = useCallback(() => {
    setEvents([]);
    setLatestEvent(null);
    processedEventKeys.current.clear();
    lastSequenceRef.current = 0;
  }, []);

  /**
   * Get events by type
   */
  const getEventsByType = useCallback((type: WorkflowEventType): WorkflowEvent[] => {
    return events.filter(event => event.type === type);
  }, [events]);

  // Reset historical loaded state when taskId changes
  useEffect(() => {
    setHistoricalLoaded(false);
    setEvents([]);
    setLatestEvent(null);
    lastSequenceRef.current = 0;
    processedEventKeys.current.clear();
  }, [taskId]);

  // Auto-load historical events on mount if enabled
  useEffect(() => {
    if (loadHistorical && taskId && !historicalLoaded) {
      loadHistoricalEvents();
    }
  }, [taskId, loadHistorical, loadHistoricalEvents, historicalLoaded]);

  // Auto-connect on mount if enabled
  useEffect(() => {
    if (autoConnect && workflowId) {
      connect();
    }

    return () => {
      // Cleanup on unmount
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (flushTimeoutRef.current) {
        clearTimeout(flushTimeoutRef.current);
      }
    };
  }, [workflowId, autoConnect]); // Only reconnect if workflowId changes

  return {
    events,
    latestEvent,
    isConnected,
    error,
    connect,
    disconnect,
    clearEvents,
    getEventsByType,
    loadHistoricalEvents,
    isLoadingHistorical,
    historicalLoaded,
  };
}

/**
 * Helper hook to extract specific event data
 */
export function useWorkflowEventData<T = any>(
  workflowId: number | null,
  eventType: WorkflowEventType,
  options?: UseWorkflowStreamOptions
): T[] {
  const { getEventsByType } = useWorkflowStream(workflowId, options);
  return getEventsByType(eventType).map(event => event.data as T);
}

/**
 * Helper hook to get latest event of specific type
 */
export function useLatestWorkflowEvent(
  workflowId: number | null,
  eventType: WorkflowEventType,
  options?: UseWorkflowStreamOptions
): WorkflowEvent | null {
  const { events } = useWorkflowStream(workflowId, options);

  // Find last event of specified type
  for (let i = events.length - 1; i >= 0; i--) {
    if (events[i].type === eventType) {
      return events[i];
    }
  }

  return null;
}
