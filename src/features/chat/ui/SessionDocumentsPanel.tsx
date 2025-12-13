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

interface SessionDocumentsPanelProps {
  sessionId: string | null;
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

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'ready':
        return <CheckCircle className="w-4 h-4" style={{ color: '#10b981' }} />;
      case 'indexing':
        return <Loader2 className="w-4 h-4 animate-spin" style={{ color: 'var(--color-primary)' }} />;
      case 'failed':
        return <AlertCircle className="w-4 h-4" style={{ color: '#ef4444' }} />;
      default:
        return <Clock className="w-4 h-4" style={{ color: 'var(--color-text-muted)' }} />;
    }
  };

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'ready':
        return 'Ready';
      case 'indexing':
        return 'Indexing...';
      case 'failed':
        return 'Failed';
      default:
        return 'Pending';
    }
  };

  if (!sessionId || documents.length === 0) return null;

  return (
    <div
      className="border-t p-4"
      style={{ borderColor: 'var(--color-border-dark)' }}
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
            <div
              key={doc.id}
              className="flex items-center justify-between p-3 rounded-lg border"
              style={{
                backgroundColor: 'white',
                borderColor: 'var(--color-border-dark)'
              }}
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
                    <div className="flex items-center gap-1">
                      {getStatusIcon(doc.indexing_status)}
                      <span
                        className="text-xs"
                        style={{ color: 'var(--color-text-muted)' }}
                      >
                        {getStatusLabel(doc.indexing_status)}
                      </span>
                    </div>
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
              <button
                onClick={() => handleDelete(doc.id)}
                className="p-2 rounded-lg transition-colors hover:bg-red-50 flex-shrink-0"
                title="Delete document"
                style={{ color: '#ef4444' }}
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
