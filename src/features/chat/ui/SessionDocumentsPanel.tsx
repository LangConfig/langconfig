/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useEffect } from 'react';
import { File, Trash2, Loader2, CheckCircle, AlertCircle, Clock } from 'lucide-react';
import type { SessionDocument } from '../types/chat';
import apiClient from '../../../lib/api-client';
import { Surface } from '@/components/ui/Surface';
import { Badge } from '@/components/ui/Badge';
import type { BadgeTone } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';

interface SessionDocumentsPanelProps {
  sessionId: string | null;
}

const STATUS_TONE: Record<string, BadgeTone> = {
  ready: 'success',
  indexing: 'info',
  failed: 'error',
};

const STATUS_LABEL: Record<string, string> = {
  ready: 'Ready',
  indexing: 'Indexing...',
  failed: 'Failed',
};

function statusIcon(status: string) {
  switch (status) {
    case 'ready':
      return <CheckCircle className="w-3 h-3" />;
    case 'indexing':
      return <Loader2 className="w-3 h-3 animate-spin" />;
    case 'failed':
      return <AlertCircle className="w-3 h-3" />;
    default:
      return <Clock className="w-3 h-3" />;
  }
}

export default function SessionDocumentsPanel({ sessionId }: SessionDocumentsPanelProps) {
  const [documents, setDocuments] = useState<SessionDocument[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (sessionId) {
      loadDocuments();
    } else {
      setDocuments([]);
    }
  }, [sessionId]);

  const loadDocuments = async () => {
    if (!sessionId) return;

    setLoading(true);
    try {
      const response = await apiClient.get(`/api/chat/${sessionId}/documents`);
      setDocuments(response.data || []);
    } catch (error) {
      console.error('Failed to load documents:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (docId: number) => {
    if (!window.confirm('Delete this document?')) return;

    try {
      await apiClient.delete(`/api/chat/${sessionId}/documents/${docId}`);
      setDocuments(docs => docs.filter(d => d.id !== docId));
    } catch (error) {
      console.error('Failed to delete document:', error);
      alert('Failed to delete document');
    }
  };

  if (!sessionId || documents.length === 0) return null;

  return (
    <div
      className="border-t-2 p-4"
      style={{ borderColor: 'var(--border-strong)' }}
    >
      <h3
        className="text-sm font-semibold mb-3"
        style={{ color: 'var(--color-text-primary)' }}
      >
        Session Documents ({documents.length})
      </h3>

      {loading ? (
        <div className="flex items-center justify-center py-4">
          <Loader2 className="w-5 h-5 animate-spin" style={{ color: 'var(--color-primary)' }} />
        </div>
      ) : (
        <div className="space-y-2 max-h-48 overflow-y-auto">
          {documents.map(doc => (
            <Surface
              key={doc.id}
              variant="inset"
              className="flex items-center justify-between p-3"
            >
              <div className="flex items-center gap-3 flex-1 min-w-0">
                <File className="w-4 h-4 flex-shrink-0" style={{ color: 'var(--color-primary)' }} />
                <div className="flex-1 min-w-0">
                  <div
                    className="text-sm font-medium truncate"
                    style={{ color: 'var(--color-text-primary)' }}
                    title={doc.filename}
                  >
                    {doc.filename}
                  </div>
                  <div className="flex items-center gap-2 mt-1">
                    <span
                      className="text-xs"
                      style={{ color: 'var(--color-text-muted)' }}
                    >
                      {(doc.file_size / 1024).toFixed(1)} KB
                    </span>
                    <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>•</span>
                    <Badge tone={STATUS_TONE[doc.indexing_status] ?? 'neutral'}>
                      {statusIcon(doc.indexing_status)}
                      {STATUS_LABEL[doc.indexing_status] ?? 'Pending'}
                    </Badge>
                    {doc.indexed_chunks_count && (
                      <>
                        <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>•</span>
                        <span
                          className="text-xs"
                          style={{ color: 'var(--color-text-muted)' }}
                        >
                          {doc.indexed_chunks_count} chunks
                        </span>
                      </>
                    )}
                  </div>
                </div>
              </div>
              <Button
                variant="danger"
                size="sm"
                onClick={() => handleDelete(doc.id)}
                title="Delete document"
                className="flex-shrink-0"
              >
                <Trash2 className="w-4 h-4" />
              </Button>
            </Surface>
          ))}
        </div>
      )}
    </div>
  );
}
