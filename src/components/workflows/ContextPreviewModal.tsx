/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * Context Preview Modal
 *
 * Shows users what conversation history will be loaded when a workflow
 * with conversation context enabled is executed.
 */

import { useState, useEffect } from 'react';
import { X, MessageSquare, Clock, Hash } from 'lucide-react';
import apiClient from '@/lib/api-client';

interface Message {
  role: string;
  content: string;
  type: string;
}

interface ContextPreview {
  messages: Message[];
  total_count: number;
  token_count: number;
  strategy_used: string;
  breakdown: {
    total: number;
    banked: number;
    recent: number;
    semantic: number;
  };
}

interface ContextPreviewModalProps {
  agentTemplateId: number;
  query: string;
  contextMode: string;
  windowSize: number;
  projectId?: number;
  onClose: () => void;
}

export default function ContextPreviewModal({
  agentTemplateId,
  query,
  contextMode,
  windowSize,
  projectId,
  onClose
}: ContextPreviewModalProps) {
  const [preview, setPreview] = useState<ContextPreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadPreview();
  }, [agentTemplateId, query, contextMode, windowSize, projectId]);

  const loadPreview = async () => {
    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams({
        query,
        context_mode: contextMode,
        window_size: String(windowSize)
      });

      if (projectId) {
        params.append('project_id', String(projectId));
      }

      const response = await apiClient.get(
        `/api/chat/agents/${agentTemplateId}/context-preview?${params.toString()}`
      );

      setPreview(response.data);
    } catch (err: any) {
      console.error('Failed to load context preview:', err);
      setError(err.response?.data?.detail || 'Failed to load preview');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50">
      <div
        className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[80vh] flex flex-col"
        style={{
          backgroundColor: 'var(--color-background-light)',
          borderColor: 'var(--color-border-dark)'
        }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between p-6 border-b"
          style={{ borderColor: 'var(--color-border-dark)' }}
        >
          <div className="flex items-center gap-3">
            <MessageSquare className="w-6 h-6" style={{ color: 'var(--color-primary)' }} />
            <div>
              <h2
                className="text-xl font-bold"
                style={{ color: 'var(--color-text-primary)' }}
              >
                Conversation Context Preview
              </h2>
              <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
                Preview what history will be loaded for this workflow
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
            style={{ color: 'var(--color-text-muted)' }}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {loading && (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
            </div>
          )}

          {error && (
            <div
              className="p-4 rounded-lg border"
              style={{
                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                borderColor: '#ef4444',
                color: '#ef4444'
              }}
            >
              <p className="font-medium">Error loading preview</p>
              <p className="text-sm mt-1">{error}</p>
            </div>
          )}

          {!loading && !error && preview && (
            <div className="space-y-6">
              {/* Stats */}
              <div className="grid grid-cols-3 gap-4">
                <div
                  className="p-4 rounded-lg border"
                  style={{
                    backgroundColor: 'var(--color-panel-dark)',
                    borderColor: 'var(--color-border-dark)'
                  }}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <Hash className="w-4 h-4" style={{ color: 'var(--color-primary)' }} />
                    <span className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
                      Total Messages
                    </span>
                  </div>
                  <p className="text-2xl font-bold" style={{ color: 'var(--color-text-primary)' }}>
                    {preview.total_count}
                  </p>
                </div>

                <div
                  className="p-4 rounded-lg border"
                  style={{
                    backgroundColor: 'var(--color-panel-dark)',
                    borderColor: 'var(--color-border-dark)'
                  }}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <Clock className="w-4 h-4" style={{ color: 'var(--color-primary)' }} />
                    <span className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
                      Estimated Tokens
                    </span>
                  </div>
                  <p className="text-2xl font-bold" style={{ color: 'var(--color-text-primary)' }}>
                    {preview.token_count.toLocaleString()}
                  </p>
                </div>

                <div
                  className="p-4 rounded-lg border"
                  style={{
                    backgroundColor: 'var(--color-panel-dark)',
                    borderColor: 'var(--color-border-dark)'
                  }}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <MessageSquare className="w-4 h-4" style={{ color: 'var(--color-primary)' }} />
                    <span className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
                      Strategy
                    </span>
                  </div>
                  <p className="text-lg font-bold capitalize" style={{ color: 'var(--color-text-primary)' }}>
                    {preview.strategy_used}
                  </p>
                </div>
              </div>

              {/* Breakdown */}
              <div
                className="p-4 rounded-lg border"
                style={{
                  backgroundColor: 'var(--color-panel-dark)',
                  borderColor: 'var(--color-border-dark)'
                }}
              >
                <h3 className="font-semibold mb-3" style={{ color: 'var(--color-text-primary)' }}>
                  Source Breakdown
                </h3>
                <div className="grid grid-cols-3 gap-4 text-sm">
                  <div>
                    <span style={{ color: 'var(--color-text-muted)' }}>Recent:</span>
                    <span className="ml-2 font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                      {preview.breakdown.recent}
                    </span>
                  </div>
                  <div>
                    <span style={{ color: 'var(--color-text-muted)' }}>Banked:</span>
                    <span className="ml-2 font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                      {preview.breakdown.banked}
                    </span>
                  </div>
                  <div>
                    <span style={{ color: 'var(--color-text-muted)' }}>Semantic:</span>
                    <span className="ml-2 font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                      {preview.breakdown.semantic}
                    </span>
                  </div>
                </div>
              </div>

              {/* Messages */}
              <div>
                <h3 className="font-semibold mb-3" style={{ color: 'var(--color-text-primary)' }}>
                  Messages to be Included ({preview.messages.length})
                </h3>
                <div className="space-y-2 max-h-96 overflow-y-auto">
                  {preview.messages.map((msg, idx) => (
                    <div
                      key={idx}
                      className="p-3 rounded-lg border"
                      style={{
                        backgroundColor: msg.role === 'user' ? 'var(--color-background-light)' : 'var(--color-panel-dark)',
                        borderColor: 'var(--color-border-dark)'
                      }}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <span
                          className="text-xs font-semibold uppercase px-2 py-0.5 rounded"
                          style={{
                            backgroundColor: msg.role === 'user' ? 'rgba(59, 130, 246, 0.1)' : 'rgba(16, 185, 129, 0.1)',
                            color: msg.role === 'user' ? '#3b82f6' : '#10b981'
                          }}
                        >
                          {msg.role}
                        </span>
                      </div>
                      <p
                        className="text-sm whitespace-pre-wrap"
                        style={{ color: 'var(--color-text-primary)' }}
                      >
                        {msg.content.length > 200 ? msg.content.substring(0, 200) + '...' : msg.content}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {!loading && !error && preview && preview.total_count === 0 && (
            <div
              className="text-center py-12"
              style={{ color: 'var(--color-text-muted)' }}
            >
              <MessageSquare className="w-12 h-12 mx-auto mb-4 opacity-20" />
              <p>No conversation history found for this agent.</p>
              <p className="text-sm mt-2">Start a chat session to build context.</p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div
          className="flex justify-end gap-3 p-6 border-t"
          style={{ borderColor: 'var(--color-border-dark)' }}
        >
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg font-medium transition-colors"
            style={{
              backgroundColor: 'var(--color-primary)',
              color: '#ffffff'
            }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
