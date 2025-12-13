/**
 * Inline File Preview Component
 *
 * Compact preview panel that slides in from the right to display file content
 * with syntax highlighting and markdown rendering.
 */

import { X, Download, ClipboardCopy, Check } from 'lucide-react';
import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { getFileIcon, getLanguage, isCodeFile, isMarkdownFile } from '@/features/workflows/utils/fileHelpers';

export interface TaskFile {
  filename: string;
  path: string;
  full_path?: string;
  size_bytes: number;
  size_human: string;
  modified_at: string;
  extension: string;
  task_id?: number | null;
  project_id?: number | null;
  workflow_id?: number | null;
}

export interface FileContent {
  filename: string;
  content: string | null;
  mime_type: string;
  is_binary: boolean;
  truncated: boolean;
  size_bytes: number;
}

interface InlineFilePreviewProps {
  file: TaskFile;
  content: FileContent | null;
  loading: boolean;
  onClose: () => void;
  onDownload: (filename: string) => void;
}

export default function InlineFilePreview({
  file,
  content,
  loading,
  onClose,
  onDownload,
}: InlineFilePreviewProps) {
  const [pathCopied, setPathCopied] = useState(false);

  const handleCopyPath = async () => {
    await navigator.clipboard.writeText(file.path);
    setPathCopied(true);
    setTimeout(() => setPathCopied(false), 2000);
  };

  return (
    <div className="w-1/2 flex flex-col border-l border-gray-200 dark:border-border-dark bg-white dark:bg-panel-dark animate-in slide-in-from-right duration-200">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-border-dark bg-gray-50 dark:bg-black/20">
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <span className="text-xl flex-shrink-0">{getFileIcon(file.extension)}</span>
          <div className="min-w-0 flex-1">
            <h3 className="font-semibold text-gray-900 dark:text-white truncate text-sm">
              {file.filename}
            </h3>
            <p className="text-xs text-gray-500 dark:text-text-muted">
              {file.size_human} • {new Date(file.modified_at).toLocaleDateString()}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1 flex-shrink-0">
          <button
            onClick={handleCopyPath}
            className="p-1.5 rounded hover:bg-gray-200 dark:hover:bg-white/10 transition-colors"
            title="Copy path"
          >
            {pathCopied ? (
              <Check className="w-4 h-4 text-green-600" />
            ) : (
              <ClipboardCopy className="w-4 h-4 text-gray-600 dark:text-text-muted" />
            )}
          </button>
          <button
            onClick={() => onDownload(file.filename)}
            className="p-1.5 rounded hover:bg-gray-200 dark:hover:bg-white/10 transition-colors"
            title="Download"
          >
            <Download className="w-4 h-4 text-gray-600 dark:text-text-muted" />
          </button>
          <button
            onClick={onClose}
            className="p-1.5 rounded hover:bg-gray-200 dark:hover:bg-white/10 transition-colors ml-1"
            title="Close preview"
          >
            <X className="w-4 h-4 text-gray-600 dark:text-text-muted" />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto">
        {loading ? (
          <div className="flex items-center justify-center h-full">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2" style={{ borderColor: 'var(--color-primary)' }}></div>
          </div>
        ) : content?.is_binary ? (
          <div className="flex flex-col items-center justify-center h-full text-center p-6">
            <span className="text-4xl mb-3">{getFileIcon(file.extension)}</span>
            <p className="text-gray-600 dark:text-text-muted">Binary file - preview not available</p>
            <p className="text-sm text-gray-500 dark:text-text-muted/70 mt-1">
              {file.size_human}
            </p>
            <button
              onClick={() => onDownload(file.filename)}
              className="mt-4 px-4 py-2 rounded-lg bg-primary/10 hover:bg-primary/20 transition-colors text-sm font-medium flex items-center gap-2"
              style={{ color: 'var(--color-primary)' }}
            >
              <Download className="w-4 h-4" />
              Download to view
            </button>
          </div>
        ) : content?.content ? (
          <div className="p-4">
            {isMarkdownFile(file.extension) ? (
              <div className="prose prose-sm dark:prose-invert max-w-none">
                <ReactMarkdown>{content.content}</ReactMarkdown>
              </div>
            ) : isCodeFile(file.extension) ? (
              <SyntaxHighlighter
                language={getLanguage(file.extension)}
                style={oneDark}
                customStyle={{ margin: 0, borderRadius: '0.5rem', fontSize: '0.75rem' }}
                showLineNumbers
              >
                {content.content}
              </SyntaxHighlighter>
            ) : (
              <pre className="text-sm whitespace-pre-wrap break-words font-mono text-gray-800 dark:text-gray-200">
                {content.content}
              </pre>
            )}
            {content.truncated && (
              <div className="mt-4 p-2 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800/30 rounded text-sm text-yellow-800 dark:text-yellow-200">
                File content truncated. Download to see full content.
              </div>
            )}
          </div>
        ) : (
          <div className="flex items-center justify-center h-full text-gray-500 dark:text-text-muted">
            Unable to load file content
          </div>
        )}
      </div>
    </div>
  );
}
