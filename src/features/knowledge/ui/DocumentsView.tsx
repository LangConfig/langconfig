/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useEffect } from 'react';
import apiClient from '../../../lib/api-client';

interface DocumentsViewProps {
  projectId: number | null;
}

interface Document {
  id: number;
  project_id: number;
  name: string;
  document_type: string;
  content?: string;
  metadata?: any;
  chunk_count?: number;
  size: number;
  indexing_status: string;
  created_at: string;
  indexed_at?: string;
}

export default function DocumentsView({ projectId }: DocumentsViewProps) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    const abortController = new AbortController();

    if (projectId) {
      fetchDocuments(abortController.signal);
    }

    return () => {
      abortController.abort();
    };
  }, [projectId]);

  const fetchDocuments = async (signal?: AbortSignal) => {
    if (!projectId) return;

    setLoading(true);
    try {
      const response = await apiClient.listDocuments({ project_id: projectId, signal });
      setDocuments(response.data || []);
    } catch (error) {
      // Ignore abort errors
      if (error instanceof Error && (error.name === 'AbortError' || error.name === 'CanceledError')) {
        return;
      }
      console.error('Failed to fetch documents:', error);
      alert('Failed to fetch documents. Check console for details.');
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    if (!event.target.files || event.target.files.length === 0 || !projectId) return;

    const file = event.target.files[0];
    setUploading(true);

    try {
      await apiClient.uploadDocument(projectId, file);
      fetchDocuments();
    } catch (error) {
      console.error('Failed to upload document:', error);
      alert('Failed to upload document. Check console for details.');
    } finally {
      setUploading(false);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  const handleDeleteDocument = async (documentId: number) => {
    if (!confirm('Are you sure you want to delete this document?')) return;

    try {
      await apiClient.deleteDocument(documentId);
      fetchDocuments();
    } catch (error) {
      console.error('Failed to delete document:', error);
      alert('Failed to delete document. Check console for details.');
    }
  };

  if (!projectId) {
    return (
      <section className="flex-1 flex flex-col rounded-xl frosted-glass overflow-hidden p-6">
        <div className="flex-1 flex flex-col items-center justify-center gap-4">
          <span className="material-symbols-outlined text-6xl text-[var(--text-light-secondary)] dark:text-[var(--text-dark-secondary)] opacity-50">
            folder_open
          </span>
          <p className="text-[var(--text-light-secondary)] dark:text-[var(--text-dark-secondary)] text-center">
            Select a project to manage its documents
          </p>
        </div>
      </section>
    );
  }

  return (
    <section className="flex-1 flex flex-col rounded-xl frosted-glass overflow-hidden p-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-[var(--text-light-primary)] dark:text-[var(--text-dark-primary)]">
          Documents
        </h2>
        <label className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--primary)] text-white hover:opacity-90 transition-all cursor-pointer button-90s">
          <span className="material-symbols-outlined">upload_file</span>
          Upload Document
          <input
            type="file"
            onChange={handleFileUpload}
            className="hidden"
            accept=".txt,.md,.pdf,.json"
            disabled={uploading}
          />
        </label>
      </div>

      {uploading && (
        <div className="mb-4 p-4 rounded-lg bg-[var(--primary)]/10 text-[var(--primary)] flex items-center gap-3">
          <span className="material-symbols-outlined animate-spin">progress_activity</span>
          Uploading document...
        </div>
      )}

      {loading ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-[var(--text-light-secondary)] dark:text-[var(--text-dark-secondary)]">
            Loading documents...
          </div>
        </div>
      ) : documents.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center gap-4">
          <span className="material-symbols-outlined text-6xl text-[var(--text-light-secondary)] dark:text-[var(--text-dark-secondary)] opacity-50">
            description
          </span>
          <p className="text-[var(--text-light-secondary)] dark:text-[var(--text-dark-secondary)] text-center">
            No documents uploaded yet. Upload documents for RAG context!
          </p>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto space-y-3">
          {documents.map((doc) => (
            <div
              key={doc.id}
              className="p-4 rounded-lg bg-[var(--background-light)] dark:bg-[var(--background-dark)]/50 hover:border-[var(--primary)] border border-transparent transition-all"
            >
              <div className="flex items-start gap-3">
                <span className="material-symbols-outlined text-[var(--primary)] text-2xl">description</span>
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-[var(--text-light-primary)] dark:text-[var(--text-dark-primary)] truncate">
                    {doc.name}
                  </h3>
                  <div className="flex items-center gap-4 mt-2 text-xs text-[var(--text-light-secondary)] dark:text-[var(--text-dark-secondary)]">
                    <span>{formatFileSize(doc.size)}</span>
                    <span className={`px-2 py-1 rounded ${
                      doc.indexing_status === 'indexed'
                        ? 'bg-green-500/20 text-green-700 dark:text-green-300'
                        : doc.indexing_status === 'indexing'
                        ? 'bg-yellow-500/20 text-yellow-700 dark:text-yellow-300'
                        : 'bg-gray-500/20'
                    }`}>
                      {doc.indexing_status}
                    </span>
                    {doc.chunk_count !== undefined && (
                      <span>{doc.chunk_count} chunks</span>
                    )}
                  </div>
                </div>
                <button
                  onClick={() => handleDeleteDocument(doc.id)}
                  className="p-2 rounded-lg hover:bg-red-500/20 text-red-500 transition-all"
                >
                  <span className="material-symbols-outlined text-lg">delete</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
