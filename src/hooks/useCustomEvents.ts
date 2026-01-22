/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * useCustomEvents Hook
 *
 * State management for LangGraph-style custom streaming events.
 * Handles event grouping, persistent events (update by event_id), and recent events buffer.
 *
 * Features:
 * - Groups events by type (progress, status, file_status, custom)
 * - Supports persistent events that can be updated in-place via event_id
 * - Maintains a recent events buffer for display
 * - Provides helper methods for accessing specific event types
 *
 * Usage:
 *   const {
 *     progressEvents,
 *     statusEvents,
 *     fileStatusEvents,
 *     recentEvents,
 *     addEvent,
 *     clearEvents
 *   } = useCustomEvents();
 *
 *   // Use with useWorkflowStream
 *   const { events } = useWorkflowStream(workflowId, {
 *     onCustomEvent: addEvent
 *   });
 */

import { useState, useCallback, useMemo } from 'react';
import type {
  CustomEvent,
  ProgressEventData,
  StatusEventData,
  FileStatusEventData,
} from '../types/events';

// Maximum number of recent events to keep in buffer
const MAX_RECENT_EVENTS = 50;

// Progress event with metadata
export interface ProgressEvent {
  id: string;
  data: ProgressEventData;
  toolName?: string;
  agentLabel?: string;
  nodeId?: string;
  timestamp: string;
}

// Status event with metadata
export interface StatusEvent {
  id: string;
  data: StatusEventData;
  toolName?: string;
  agentLabel?: string;
  nodeId?: string;
  timestamp: string;
}

// File status event with metadata
export interface FileStatusEvent {
  id: string;
  data: FileStatusEventData;
  toolName?: string;
  agentLabel?: string;
  nodeId?: string;
  timestamp: string;
}

// Generic custom event for non-standard types
export interface GenericCustomEvent {
  id: string;
  eventType: string;
  data: Record<string, any>;
  toolName?: string;
  agentLabel?: string;
  nodeId?: string;
  timestamp: string;
}

export interface UseCustomEventsResult {
  /** Progress bar events (keyed by event_id for persistent updates) */
  progressEvents: Map<string, ProgressEvent>;
  /** Status badge events (keyed by event_id for persistent updates) */
  statusEvents: Map<string, StatusEvent>;
  /** File operation events */
  fileStatusEvents: FileStatusEvent[];
  /** All other custom events */
  genericEvents: GenericCustomEvent[];
  /** Recent events buffer (all types, most recent first) */
  recentEvents: Array<ProgressEvent | StatusEvent | FileStatusEvent | GenericCustomEvent>;
  /** Add a custom event (handles grouping and persistence) */
  addEvent: (event: CustomEvent) => void;
  /** Clear all events */
  clearEvents: () => void;
  /** Get progress events as array (for rendering) */
  progressEventsArray: ProgressEvent[];
  /** Get status events as array (for rendering) */
  statusEventsArray: StatusEvent[];
  /** Check if there are any active progress events (value < 100) */
  hasActiveProgress: boolean;
  /** Check if there are any error status events */
  hasErrors: boolean;
}

export function useCustomEvents(): UseCustomEventsResult {
  // State for different event types
  const [progressEvents, setProgressEvents] = useState<Map<string, ProgressEvent>>(new Map());
  const [statusEvents, setStatusEvents] = useState<Map<string, StatusEvent>>(new Map());
  const [fileStatusEvents, setFileStatusEvents] = useState<FileStatusEvent[]>([]);
  const [genericEvents, setGenericEvents] = useState<GenericCustomEvent[]>([]);
  const [recentEvents, setRecentEvents] = useState<Array<ProgressEvent | StatusEvent | FileStatusEvent | GenericCustomEvent>>([]);

  /**
   * Add a custom event to the appropriate collection
   */
  const addEvent = useCallback((event: CustomEvent) => {
    const { event_type, event_id, payload, tool_name, agent_label, node_id, timestamp } = event.data;
    const eventId = event_id || `${event_type}-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

    // Create base event metadata
    const baseMetadata = {
      toolName: tool_name,
      agentLabel: agent_label,
      nodeId: node_id,
      timestamp,
    };

    switch (event_type) {
      case 'progress': {
        const progressEvent: ProgressEvent = {
          id: eventId,
          data: payload as ProgressEventData,
          ...baseMetadata,
        };

        // For persistent events, update in-place
        setProgressEvents((prev) => {
          const next = new Map(prev);
          next.set(eventId, progressEvent);
          return next;
        });

        // Add to recent events
        addToRecent(progressEvent);
        break;
      }

      case 'status': {
        const statusEvent: StatusEvent = {
          id: eventId,
          data: payload as StatusEventData,
          ...baseMetadata,
        };

        // For persistent events, update in-place
        setStatusEvents((prev) => {
          const next = new Map(prev);
          next.set(eventId, statusEvent);
          return next;
        });

        // Add to recent events
        addToRecent(statusEvent);
        break;
      }

      case 'file_status': {
        const fileEvent: FileStatusEvent = {
          id: eventId,
          data: payload as FileStatusEventData,
          ...baseMetadata,
        };

        // File events are typically not persistent, just append
        setFileStatusEvents((prev) => [...prev, fileEvent].slice(-MAX_RECENT_EVENTS));

        // Add to recent events
        addToRecent(fileEvent);
        break;
      }

      default: {
        // Generic custom event
        const genericEvent: GenericCustomEvent = {
          id: eventId,
          eventType: event_type,
          data: payload as Record<string, any>,
          ...baseMetadata,
        };

        setGenericEvents((prev) => [...prev, genericEvent].slice(-MAX_RECENT_EVENTS));

        // Add to recent events
        addToRecent(genericEvent);
        break;
      }
    }
  }, []);

  /**
   * Add an event to the recent events buffer
   */
  const addToRecent = useCallback((event: ProgressEvent | StatusEvent | FileStatusEvent | GenericCustomEvent) => {
    setRecentEvents((prev) => {
      // Add to front (most recent first)
      const next = [event, ...prev];
      // Limit buffer size
      return next.slice(0, MAX_RECENT_EVENTS);
    });
  }, []);

  /**
   * Clear all events
   */
  const clearEvents = useCallback(() => {
    setProgressEvents(new Map());
    setStatusEvents(new Map());
    setFileStatusEvents([]);
    setGenericEvents([]);
    setRecentEvents([]);
  }, []);

  // Convert Maps to arrays for rendering
  const progressEventsArray = useMemo(
    () => Array.from(progressEvents.values()),
    [progressEvents]
  );

  const statusEventsArray = useMemo(
    () => Array.from(statusEvents.values()),
    [statusEvents]
  );

  // Check for active progress (not yet at 100%)
  const hasActiveProgress = useMemo(
    () => progressEventsArray.some((e) => e.data.value < (e.data.total || 100)),
    [progressEventsArray]
  );

  // Check for error statuses
  const hasErrors = useMemo(
    () => statusEventsArray.some((e) => e.data.status === 'error'),
    [statusEventsArray]
  );

  return {
    progressEvents,
    statusEvents,
    fileStatusEvents,
    genericEvents,
    recentEvents,
    addEvent,
    clearEvents,
    progressEventsArray,
    statusEventsArray,
    hasActiveProgress,
    hasErrors,
  };
}
