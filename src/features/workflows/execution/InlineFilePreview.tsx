/**
 * Inline File Preview Component
 *
 * Compact preview panel that slides in from the right to display file content
 * with syntax highlighting and markdown rendering.
 */

import { X, Download, ClipboardCopy, Check, Code, Eye, Maximize2, Minimize2 } from 'lucide-react';
import { useState, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import {
  getFileIcon,
  getLanguage,
  isCodeFile,
  isMarkdownFile,
  isHtmlFile,
  isCsvFile,
  isJsonFile,
  isSvgFile,
  supportsPreviewMode
} from '@/features/workflows/utils/fileHelpers';
import { CsvPreview, JsonPreview, SvgPreview } from '@/features/workflows/components/FilePreviewRenderers';

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
  const [viewMode, setViewMode] = useState<'code' | 'preview'>('preview');
  const [isExpanded, setIsExpanded] = useState(false);

  // Check if this file supports preview mode (HTML, CSV, JSON, SVG)
  const supportsPreview = supportsPreviewMode(file.extension);

  const handleCopyPath = async () => {
    await navigator.clipboard.writeText(file.path);
    setPathCopied(true);
    setTimeout(() => setPathCopied(false), 2000);
  };

  // Custom markdown components for proper document-like rendering
  const markdownComponents = useMemo(() => ({
    h1: ({ children }: any) => (
      <h1 className="text-2xl font-bold mt-6 mb-3 border-b pb-2"
        style={{ color: 'var(--color-text-primary)', borderColor: 'var(--color-border-dark)' }}>
        {children}
      </h1>
    ),
    h2: ({ children }: any) => (
      <h2 className="text-xl font-bold mt-5 mb-2"
        style={{ color: 'var(--color-text-primary)' }}>
        {children}
      </h2>
    ),
    h3: ({ children }: any) => (
      <h3 className="text-lg font-semibold mt-4 mb-2"
        style={{ color: 'var(--color-text-primary)' }}>
        {children}
      </h3>
    ),
    h4: ({ children }: any) => (
      <h4 className="text-base font-semibold mt-3 mb-2"
        style={{ color: 'var(--color-text-primary)' }}>
        {children}
      </h4>
    ),
    p: ({ children }: any) => (
      <p className="mb-3 leading-relaxed"
        style={{ color: 'var(--color-text-primary)' }}>
        {children}
      </p>
    ),
    ul: ({ children }: any) => (
      <ul className="list-disc list-outside ml-5 mb-3 space-y-1"
        style={{ color: 'var(--color-text-primary)' }}>
        {children}
      </ul>
    ),
    ol: ({ children }: any) => (
      <ol className="list-decimal list-outside ml-5 mb-3 space-y-1"
        style={{ color: 'var(--color-text-primary)' }}>
        {children}
      </ol>
    ),
    li: ({ children }: any) => (
      <li style={{ color: 'var(--color-text-primary)' }}>
        {children}
      </li>
    ),
    blockquote: ({ children }: any) => (
      <blockquote className="border-l-4 pl-4 py-2 my-3 italic rounded-r"
        style={{
          borderColor: 'var(--color-primary)',
          backgroundColor: 'var(--color-panel-dark)',
          color: 'var(--color-text-muted)'
        }}>
        {children}
      </blockquote>
    ),
    code: ({ inline, className, children }: any) => {
      const match = /language-(\w+)/.exec(className || '');
      return !inline && match ? (
        <SyntaxHighlighter
          language={match[1]}
          style={oneDark}
          customStyle={{ margin: '1rem 0', borderRadius: '0.375rem', fontSize: '0.875rem' }}
          showLineNumbers
        >
          {String(children).replace(/\n$/, '')}
        </SyntaxHighlighter>
      ) : (
        <code className="px-1.5 py-0.5 rounded text-sm font-mono"
          style={{
            backgroundColor: 'var(--color-panel-dark)',
            color: 'var(--color-primary)'
          }}>
          {children}
        </code>
      );
    },
    strong: ({ children }: any) => (
      <strong className="font-bold" style={{ color: 'var(--color-text-primary)' }}>
        {children}
      </strong>
    ),
    em: ({ children }: any) => (
      <em style={{ color: 'var(--color-text-primary)' }}>
        {children}
      </em>
    ),
    a: ({ href, children }: any) => (
      <a href={href}
        className="underline hover:opacity-80"
        style={{ color: 'var(--color-primary)' }}
        target="_blank"
        rel="noopener noreferrer">
        {children}
      </a>
    ),
    table: ({ children }: any) => (
      <div className="overflow-x-auto my-4">
        <table className="min-w-full border-collapse border"
          style={{ borderColor: 'var(--color-border-dark)' }}>
          {children}
        </table>
      </div>
    ),
    th: ({ children }: any) => (
      <th className="border px-3 py-2 text-left font-semibold text-sm"
        style={{
          borderColor: 'var(--color-border-dark)',
          backgroundColor: 'var(--color-panel-dark)',
          color: 'var(--color-text-primary)'
        }}>
        {children}
      </th>
    ),
    td: ({ children }: any) => (
      <td className="border px-3 py-2 text-sm"
        style={{
          borderColor: 'var(--color-border-dark)',
          color: 'var(--color-text-primary)'
        }}>
        {children}
      </td>
    ),
  }), []);

  // Check if content looks like markdown (has headers, lists, code blocks, etc.)
  const contentLooksLikeMarkdown = useMemo(() => {
    if (!content?.content) return false;
    const text = content.content;
    // Check for common markdown patterns
    return /^#{1,6}\s|^\*\s|^-\s|^\d+\.\s|```|`[^`]+`|\*\*[^*]+\*\*|\[[^\]]+\]\([^)]+\)/m.test(text);
  }, [content?.content]);

  return (
    <div className={`${isExpanded ? 'w-full absolute inset-0 z-50' : 'w-1/2'} flex flex-col border-l border-gray-200 dark:border-border-dark bg-white dark:bg-panel-dark animate-in slide-in-from-right duration-200`}>
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
          {/* Code/Preview Toggle for HTML files */}
          {supportsPreview && (
            <div className="flex items-center bg-gray-200 dark:bg-black/30 rounded-lg p-0.5 mr-2">
              <button
                onClick={() => setViewMode('code')}
                className={`flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors ${
                  viewMode === 'code'
                    ? 'bg-white dark:bg-panel-dark text-gray-900 dark:text-white shadow-sm'
                    : 'text-gray-600 dark:text-text-muted hover:text-gray-900 dark:hover:text-white'
                }`}
                title="View source code"
              >
                <Code className="w-3.5 h-3.5" />
                Code
              </button>
              <button
                onClick={() => setViewMode('preview')}
                className={`flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors ${
                  viewMode === 'preview'
                    ? 'bg-white dark:bg-panel-dark text-gray-900 dark:text-white shadow-sm'
                    : 'text-gray-600 dark:text-text-muted hover:text-gray-900 dark:hover:text-white'
                }`}
                title="Preview rendered HTML"
              >
                <Eye className="w-3.5 h-3.5" />
                Preview
              </button>
            </div>
          )}

          {/* Expand/Collapse button for preview mode */}
          {supportsPreview && viewMode === 'preview' && (
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="p-1.5 rounded hover:bg-gray-200 dark:hover:bg-white/10 transition-colors"
              title={isExpanded ? 'Exit fullscreen' : 'Fullscreen preview'}
            >
              {isExpanded ? (
                <Minimize2 className="w-4 h-4 text-gray-600 dark:text-text-muted" />
              ) : (
                <Maximize2 className="w-4 h-4 text-gray-600 dark:text-text-muted" />
              )}
            </button>
          )}

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
            onClick={() => onDownload(file.path)}
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
              onClick={() => onDownload(file.path)}
              className="mt-4 px-4 py-2 rounded-lg bg-primary/10 hover:bg-primary/20 transition-colors text-sm font-medium flex items-center gap-2"
              style={{ color: 'var(--color-primary)' }}
            >
              <Download className="w-4 h-4" />
              Download to view
            </button>
          </div>
        ) : content?.content ? (
          <div className="h-full relative">
            {/* Preview Mode - always rendered for instant switching, hidden via CSS */}
            {supportsPreview && (
              <div
                className={`absolute inset-0 transition-opacity duration-150 ${
                  viewMode === 'preview' ? 'opacity-100 z-10' : 'opacity-0 z-0 pointer-events-none'
                }`}
              >
                {isHtmlFile(file.extension) ? (
                  <iframe
                    srcDoc={content.content}
                    className="w-full h-full border-0 bg-white"
                    title={`Preview of ${file.filename}`}
                    sandbox="allow-scripts allow-same-origin"
                  />
                ) : isCsvFile(file.extension) ? (
                  <CsvPreview content={content.content} />
                ) : isJsonFile(file.extension) ? (
                  <JsonPreview content={content.content} />
                ) : isSvgFile(file.extension) ? (
                  <SvgPreview content={content.content} />
                ) : null}
              </div>
            )}

            {/* Code/Text View - always rendered for HTML files, hidden via CSS when in preview */}
            <div
              className={`p-4 h-full overflow-auto ${
                supportsPreview
                  ? `transition-opacity duration-150 ${viewMode === 'code' ? 'opacity-100' : 'opacity-0 pointer-events-none absolute inset-0'}`
                  : ''
              }`}
            >
              {isMarkdownFile(file.extension) || contentLooksLikeMarkdown ? (
                // Render as markdown - includes .md files and text files that look like markdown
                <div className="prose prose-lg dark:prose-invert max-w-none">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={markdownComponents}
                  >
                    {content.content}
                  </ReactMarkdown>
                </div>
              ) : isCodeFile(file.extension) ? (
                <SyntaxHighlighter
                  language={getLanguage(file.extension)}
                  style={oneDark}
                  customStyle={{ margin: 0, borderRadius: '0.5rem', fontSize: '0.875rem' }}
                  showLineNumbers
                >
                  {content.content}
                </SyntaxHighlighter>
              ) : (
                // Plain text fallback with proper colors
                <pre className="text-base whitespace-pre-wrap break-words" style={{ color: 'var(--color-text-primary)' }}>
                  {content.content}
                </pre>
              )}
              {content.truncated && (
                <div className="mt-4 p-2 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800/30 rounded text-sm text-yellow-800 dark:text-yellow-200">
                  File content truncated. Download to see full content.
                </div>
              )}
            </div>
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
