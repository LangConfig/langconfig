/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useRef, useCallback } from 'react';
import { X, Upload, Image, FileText, Film, Plus } from 'lucide-react';

/**
 * Attachment types supported by the multimodal input system
 */
export type AttachmentType = 'image' | 'document' | 'video' | 'audio';

/**
 * Attachment data structure matching backend expectations
 */
export interface Attachment {
  id: string;
  type: AttachmentType;
  name: string;
  url?: string;        // URL for remote files
  data?: string;       // Base64 data for local files
  mimeType: string;
  size?: number;       // File size in bytes
  thumbnail?: string;  // Base64 thumbnail for preview
}

interface AttachmentUploaderProps {
  attachments: Attachment[];
  onChange: (attachments: Attachment[]) => void;
  allowedTypes?: AttachmentType[];
  maxAttachments?: number;
  maxFileSizeMB?: number;
  compact?: boolean;
  label?: string;
  description?: string;
}

// MIME type mappings
const MIME_TYPE_MAP: Record<string, AttachmentType> = {
  'image/png': 'image',
  'image/jpeg': 'image',
  'image/gif': 'image',
  'image/webp': 'image',
  'image/svg+xml': 'image',
  'application/pdf': 'document',
  'text/plain': 'document',
  'text/markdown': 'document',
  'application/msword': 'document',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'document',
  'video/mp4': 'video',
  'video/webm': 'video',
  'video/quicktime': 'video',
  'audio/mpeg': 'audio',
  'audio/wav': 'audio',
  'audio/ogg': 'audio',
};

// File extension mappings for accept attribute
const TYPE_ACCEPT_MAP: Record<AttachmentType, string> = {
  image: 'image/*',
  document: '.pdf,.doc,.docx,.txt,.md',
  video: 'video/*',
  audio: 'audio/*',
};

// Icon components for each type
const TypeIcon: Record<AttachmentType, typeof Image> = {
  image: Image,
  document: FileText,
  video: Film,
  audio: Film, // Using Film as placeholder
};

/**
 * Generate unique ID for attachments
 */
const generateId = () => `att_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

/**
 * Convert file to base64
 */
const fileToBase64 = (file: File): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.readAsDataURL(file);
    reader.onload = () => {
      const result = reader.result as string;
      // Extract just the base64 part (remove data:mime;base64, prefix)
      const base64 = result.split(',')[1];
      resolve(base64);
    };
    reader.onerror = reject;
  });
};

/**
 * Create thumbnail for image files
 */
const createThumbnail = async (file: File, maxSize: number = 100): Promise<string | undefined> => {
  if (!file.type.startsWith('image/')) return undefined;

  return new Promise((resolve) => {
    const img = document.createElement('img');
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');

    img.onload = () => {
      const scale = Math.min(maxSize / img.width, maxSize / img.height);
      canvas.width = img.width * scale;
      canvas.height = img.height * scale;
      ctx?.drawImage(img, 0, 0, canvas.width, canvas.height);
      resolve(canvas.toDataURL('image/jpeg', 0.7));
    };

    img.onerror = () => resolve(undefined);
    img.src = URL.createObjectURL(file);
  });
};

/**
 * AttachmentUploader Component
 *
 * Reusable component for uploading and managing multimodal attachments.
 * Supports images, documents, videos, and audio files.
 */
export default function AttachmentUploader({
  attachments,
  onChange,
  allowedTypes = ['image', 'document', 'video'],
  maxAttachments = 5,
  maxFileSizeMB = 10,
  compact = false,
  label = 'Attachments',
  description = 'Add images, documents, or videos to include in the prompt'
}: AttachmentUploaderProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Build accept string from allowed types
  const acceptString = allowedTypes.map(t => TYPE_ACCEPT_MAP[t]).join(',');

  const processFile = useCallback(async (file: File): Promise<Attachment | null> => {
    // Check file size
    if (file.size > maxFileSizeMB * 1024 * 1024) {
      setUploadError(`File "${file.name}" exceeds ${maxFileSizeMB}MB limit`);
      return null;
    }

    // Determine type
    const attachmentType = MIME_TYPE_MAP[file.type];
    if (!attachmentType || !allowedTypes.includes(attachmentType)) {
      setUploadError(`File type "${file.type}" is not supported`);
      return null;
    }

    try {
      const base64 = await fileToBase64(file);
      const thumbnail = await createThumbnail(file);

      return {
        id: generateId(),
        type: attachmentType,
        name: file.name,
        data: base64,
        mimeType: file.type,
        size: file.size,
        thumbnail
      };
    } catch (error) {
      setUploadError(`Failed to process "${file.name}"`);
      return null;
    }
  }, [allowedTypes, maxFileSizeMB]);

  const handleFiles = useCallback(async (files: FileList | File[]) => {
    setUploadError(null);

    const fileArray = Array.from(files);
    const remainingSlots = maxAttachments - attachments.length;

    if (fileArray.length > remainingSlots) {
      setUploadError(`Can only add ${remainingSlots} more attachments`);
    }

    const filesToProcess = fileArray.slice(0, remainingSlots);
    const newAttachments: Attachment[] = [];

    for (const file of filesToProcess) {
      const attachment = await processFile(file);
      if (attachment) {
        newAttachments.push(attachment);
      }
    }

    if (newAttachments.length > 0) {
      onChange([...attachments, ...newAttachments]);
    }
  }, [attachments, maxAttachments, onChange, processFile]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    handleFiles(e.dataTransfer.files);
  }, [handleFiles]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      handleFiles(e.target.files);
    }
    // Reset input so same file can be selected again
    e.target.value = '';
  }, [handleFiles]);

  const removeAttachment = useCallback((id: string) => {
    onChange(attachments.filter(a => a.id !== id));
  }, [attachments, onChange]);

  const handleUrlAdd = useCallback(() => {
    const url = prompt('Enter image URL:');
    if (url) {
      const attachment: Attachment = {
        id: generateId(),
        type: 'image',
        name: url.split('/').pop() || 'Image',
        url,
        mimeType: 'image/png', // Assume PNG, will be detected server-side
      };
      onChange([...attachments, attachment]);
    }
  }, [attachments, onChange]);

  const canAddMore = attachments.length < maxAttachments;

  if (compact) {
    // Compact inline version for NodeConfigPanel
    return (
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <label className="text-xs font-medium" style={{ color: 'var(--color-text-primary)' }}>
            {label}
          </label>
          {canAddMore && (
            <button
              onClick={() => fileInputRef.current?.click()}
              className="flex items-center gap-1 px-2 py-1 rounded text-xs hover:bg-white/10 transition-colors"
              style={{ color: 'var(--color-primary)' }}
            >
              <Plus size={12} />
              Add
            </button>
          )}
        </div>

        {attachments.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {attachments.map(att => {
              const Icon = TypeIcon[att.type];
              return (
                <div
                  key={att.id}
                  className="flex items-center gap-1.5 px-2 py-1 rounded-lg text-xs border"
                  style={{
                    backgroundColor: 'var(--color-background-dark)',
                    borderColor: 'var(--color-border-dark)'
                  }}
                >
                  {att.thumbnail ? (
                    <img src={att.thumbnail} alt="" className="w-5 h-5 rounded object-cover" />
                  ) : (
                    <Icon size={14} style={{ color: 'var(--color-text-muted)' }} />
                  )}
                  <span className="truncate max-w-20" style={{ color: 'var(--color-text-primary)' }}>
                    {att.name}
                  </span>
                  <button
                    onClick={() => removeAttachment(att.id)}
                    className="p-0.5 rounded hover:bg-red-500/20 text-red-400"
                  >
                    <X size={12} />
                  </button>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
            No attachments
          </p>
        )}

        <input
          ref={fileInputRef}
          type="file"
          accept={acceptString}
          multiple
          onChange={handleFileSelect}
          className="hidden"
        />
      </div>
    );
  }

  // Full version for ExecutionConfigDialog
  return (
    <div className="space-y-3">
      <label className="block text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>
        {label}
      </label>
      <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
        {description}
      </p>

      {/* Drop zone */}
      {canAddMore && (
        <div
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onClick={() => fileInputRef.current?.click()}
          className={`
            border-2 border-dashed rounded-lg p-4 text-center cursor-pointer transition-colors
            ${isDragOver ? 'border-primary bg-primary/10' : 'border-gray-600 hover:border-gray-500'}
          `}
          style={{ backgroundColor: isDragOver ? 'rgba(var(--color-primary-rgb), 0.1)' : 'var(--color-background-dark)' }}
        >
          <Upload size={24} className="mx-auto mb-2" style={{ color: 'var(--color-text-muted)' }} />
          <p className="text-sm" style={{ color: 'var(--color-text-primary)' }}>
            Drop files here or click to browse
          </p>
          <p className="text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
            {allowedTypes.join(', ')} • Max {maxFileSizeMB}MB per file • {maxAttachments - attachments.length} remaining
          </p>
        </div>
      )}

      {/* URL add button */}
      {canAddMore && allowedTypes.includes('image') && (
        <button
          onClick={handleUrlAdd}
          className="text-xs hover:underline"
          style={{ color: 'var(--color-primary)' }}
        >
          + Add image from URL
        </button>
      )}

      {/* Error message */}
      {uploadError && (
        <p className="text-xs text-red-400">{uploadError}</p>
      )}

      {/* Attachment list */}
      {attachments.length > 0 && (
        <div className="space-y-2">
          {attachments.map(att => {
            const Icon = TypeIcon[att.type];
            return (
              <div
                key={att.id}
                className="flex items-center gap-3 p-2 rounded-lg border"
                style={{
                  backgroundColor: 'var(--color-background-dark)',
                  borderColor: 'var(--color-border-dark)'
                }}
              >
                {att.thumbnail ? (
                  <img src={att.thumbnail} alt="" className="w-10 h-10 rounded object-cover" />
                ) : (
                  <div className="w-10 h-10 rounded flex items-center justify-center" style={{ backgroundColor: 'var(--color-panel-dark)' }}>
                    <Icon size={20} style={{ color: 'var(--color-text-muted)' }} />
                  </div>
                )}
                <div className="flex-1 min-w-0">
                  <p className="text-sm truncate" style={{ color: 'var(--color-text-primary)' }}>
                    {att.name}
                  </p>
                  <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                    {att.type} • {att.size ? `${(att.size / 1024).toFixed(1)}KB` : 'URL'}
                  </p>
                </div>
                <button
                  onClick={() => removeAttachment(att.id)}
                  className="p-1.5 rounded hover:bg-red-500/20 text-red-400"
                >
                  <X size={16} />
                </button>
              </div>
            );
          })}
        </div>
      )}

      <input
        ref={fileInputRef}
        type="file"
        accept={acceptString}
        multiple
        onChange={handleFileSelect}
        className="hidden"
      />
    </div>
  );
}
