/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useEffect, useCallback } from 'react';
import type { SessionMetrics, ToolCall, SubAgentActivity } from '../types/chat';
import apiClient from '../../../lib/api-client';

interface UseChatMetricsResult {
  metrics: SessionMetrics;
  toolCalls: ToolCall[];
  subagentActivity: SubAgentActivity[];
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

const DEFAULT_METRICS: SessionMetrics = {
  total_tokens: 0,
  tool_calls: 0,
  subagent_spawns: 0,
  context_operations: 0,
};

export function useChatMetrics(sessionId: string | null): UseChatMetricsResult {
  const [metrics, setMetrics] = useState<SessionMetrics>(DEFAULT_METRICS);
  const [toolCalls, setToolCalls] = useState<ToolCall[]>([]);
  const [subagentActivity, setSubagentActivity] = useState<SubAgentActivity[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!sessionId) return;

    setIsLoading(true);
    setError(null);

    try {
      const response = await apiClient.getChatMetrics(sessionId);
      const data = response.data;

      setMetrics(data.metrics || DEFAULT_METRICS);
      setToolCalls(data.tool_calls || []);
      setSubagentActivity(data.subagent_spawns || []);
    } catch (err: any) {
      console.error('Failed to fetch metrics:', err);
      setError('Failed to fetch metrics');
    } finally {
      setIsLoading(false);
    }
  }, [sessionId]);

  // Auto-fetch metrics when sessionId changes
  useEffect(() => {
    if (sessionId) {
      refresh();
    } else {
      // Reset metrics when no session
      setMetrics(DEFAULT_METRICS);
      setToolCalls([]);
      setSubagentActivity([]);
    }
  }, [sessionId, refresh]);

  return {
    metrics,
    toolCalls,
    subagentActivity,
    isLoading,
    error,
    refresh,
  };
}
