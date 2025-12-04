/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { Paperclip, Loader2 } from 'lucide-react';
import { useState, useRef } from 'react';
import type { SessionDocument } from '../types/chat';
import apiClient from '../../../lib/api-client';

interface FileUploadButtonProps {
  sessionId: string | null;
  onFileUploaded: (file: SessionDocument) => void;
  disabled?: boolean;
}

export default function FileUploadButton({ sessionId, onFileUploaded, disabled }: FileUploadButtonProps) {
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !sessionId) return;

    setUploading(true);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await apiClient.client.post(
        `/api/chat/${sessionId}/upload`,
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      );

      onFileUploaded(response.data);
    } catch (error: any) {
      console.error('Failed to upload file:', error);
      alert(error.response?.data?.detail || 'Failed to upload file');
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  return (
    <>
      <input
        ref={fileInputRef}
        type="file"
        onChange={handleFileSelect}
        style={{ display: 'none' }}
        accept=".txt,.md,.pdf,.json,.py,.js,.ts,.tsx,.jsx,.java,.c,.cpp,.h,.hpp,.cs,.rb,.go,.rs,.php,.swift,.kt,.scala,.r,.sql,.sh,.bash,.doc,.docx,.html,.htm,.xml,.csv,.yaml,.yml,.rtf,.odt,.epub,.ppt,.pptx,.xls,.xlsx,.png,.jpg,.jpeg,.gif,.bmp,.tiff,.webp"
        disabled={disabled || uploading || !sessionId}
      />
      <button
        onClick={() => fileInputRef.current?.click()}
        disabled={disabled || uploading || !sessionId}
        className="p-2 rounded-lg transition-colors disabled:opacity-50"
        style={{
          backgroundColor: 'transparent',
          color: 'var(--color-text-muted)'
        }}
        onMouseEnter={(e) => {
          if (!disabled && !uploading && sessionId) {
            e.currentTarget.style.backgroundColor = 'var(--color-panel-dark)';
          }
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.backgroundColor = 'transparent';
        }}
        title={!sessionId ? "Start a chat session first" : "Upload document"}
      >
        {uploading ? (
          <Loader2 className="w-5 h-5 animate-spin" />
        ) : (
          <Paperclip className="w-5 h-5" />
        )}
      </button>
    </>
  );
}
