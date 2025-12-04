/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * FormattedOutputViewer Component
 *
 * Beautiful, feature-rich viewer for workflow outputs with:
 * - Markdown rendering with GitHub Flavored Markdown support
 * - Syntax-highlighted code blocks
 * - Section navigation for long documents
 * - Copy-to-clipboard for code blocks
 * - Responsive design with Tailwind CSS
 * - Multiple output type support (research, code, documentation, etc.)
 *
 * Based on 2025 best practices for React markdown rendering.
 */

import React, { useState, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import {
  FileCode,
  FileText,
  BookOpen,
  Database,
  CheckSquare,
  Copy,
  Check,
  ChevronRight,
  ChevronDown,
  X,
  Download
} from 'lucide-react';

// Output type definitions (matches backend)
export type OutputType =
  | 'markdown'
  | 'code'
  | 'json'
  | 'research'
  | 'analysis'
  | 'task_plan'
  | 'documentation'
  | 'mixed'
  | 'plain_text';

export interface CodeBlock {
  language: string;
  code: string;
  line_start?: number;
  filename?: string;
  line_count: number;
}

export interface Section {
  level: number;
  title: string;
  id: string;
  content: string;
}

export interface FormattedOutput {
  output_type: OutputType;
  formatted_content: string;
  metadata: {
    workflow_name?: string;
    task_id?: number;
    detected_type: string;
    char_count: number;
    word_count: number;
    line_count: number;
    formatted_at: string;
    has_code: boolean;
    code_block_count: number;
    section_count: number;
  };
  code_blocks: CodeBlock[];
  sections: Section[];
  raw_output?: any;
}

interface FormattedOutputViewerProps {
  output: FormattedOutput;
  className?: string;
  showMetadata?: boolean;
  showNavigation?: boolean;
}

export const FormattedOutputViewer: React.FC<FormattedOutputViewerProps> = ({
  output,
  className = '',
  showMetadata = true,
  showNavigation = true
}) => {
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());
  const [activeSection, setActiveSection] = useState<string | null>(null);
  const [fullscreenImage, setFullscreenImage] = useState<string | null>(null);

  // Get icon for output type
  const getTypeIcon = (type: OutputType) => {
    switch (type) {
      case 'code':
        return <FileCode className="w-5 h-5" />;
      case 'research':
      case 'documentation':
        return <BookOpen className="w-5 h-5" />;
      case 'analysis':
      case 'json':
        return <Database className="w-5 h-5" />;
      case 'task_plan':
        return <CheckSquare className="w-5 h-5" />;
      default:
        return <FileText className="w-5 h-5" />;
    }
  };

  // Get color for output type
  const getTypeColor = (type: OutputType) => {
    switch (type) {
      case 'code':
        return 'text-blue-600 bg-blue-50';
      case 'research':
        return 'text-purple-600 bg-purple-50';
      case 'documentation':
        return 'text-green-600 bg-green-50';
      case 'analysis':
        return 'text-orange-600 bg-orange-50';
      case 'task_plan':
        return 'text-indigo-600 bg-indigo-50';
      default:
        return 'text-gray-600 bg-gray-50';
    }
  };

  // Copy code to clipboard
  const copyCode = async (code: string, index: number) => {
    try {
      await navigator.clipboard.writeText(code);
      setCopiedIndex(index);
      setTimeout(() => setCopiedIndex(null), 2000);
    } catch (err) {
      console.error('Failed to copy code:', err);
    }
  };

  // Download output as file
  const downloadOutput = () => {
    const element = document.createElement("a");
    const file = new Blob([output.formatted_content], { type: 'text/markdown' });
    element.href = URL.createObjectURL(file);
    element.download = `output-${output.output_type}-${new Date().toISOString().slice(0, 10)}.md`;
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
  };

  // Toggle section expansion
  const toggleSection = (sectionId: string) => {
    const newExpanded = new Set(expandedSections);
    if (newExpanded.has(sectionId)) {
      newExpanded.delete(sectionId);
    } else {
      newExpanded.add(sectionId);
    }
    setExpandedSections(newExpanded);
  };

  // Scroll to section
  const scrollToSection = (sectionId: string) => {
    const element = document.getElementById(sectionId);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'start' });
      setActiveSection(sectionId);
    }
  };

  // Custom markdown components
  const markdownComponents = useMemo(() => ({
    code({ node, inline, className, children, ...props }: any) {
      const match = /language-(\w+)/.exec(className || '');
      const language = match ? match[1] : '';

      return !inline && language ? (
        <div className="relative group my-4">
          <div className="absolute right-2 top-2 opacity-0 group-hover:opacity-100 transition-opacity">
            <button
              onClick={() => copyCode(String(children).replace(/\n$/, ''), -1)}
              className="p-2 bg-gray-800 hover:bg-gray-700 rounded-md text-white text-sm flex items-center gap-2"
            >
              {copiedIndex === -1 ? (
                <>
                  <Check className="w-4 h-4" />
                  Copied!
                </>
              ) : (
                <>
                  <Copy className="w-4 h-4" />
                  Copy
                </>
              )}
            </button>
          </div>
          <SyntaxHighlighter
            style={vscDarkPlus}
            language={language}
            PreTag="div"
            className="rounded-lg"
            showLineNumbers
            {...props}
          >
            {String(children).replace(/\n$/, '')}
          </SyntaxHighlighter>
        </div>
      ) : (
        <code className="bg-gray-100 px-1.5 py-0.5 rounded text-sm font-mono text-red-600" {...props}>
          {children}
        </code>
      );
    },
    h1: ({ children }: any) => (
      <h1 className="text-3xl font-bold mt-8 mb-4 border-b-2 pb-2 text-gray-900 dark:text-gray-100 border-gray-200 dark:border-border-dark">
        {children}
      </h1>
    ),
    h2: ({ children }: any) => (
      <h2 className="text-2xl font-bold mt-6 mb-3 text-gray-900 dark:text-gray-100">
        {children}
      </h2>
    ),
    h3: ({ children }: any) => (
      <h3 className="text-xl font-bold mt-4 mb-2 text-gray-900 dark:text-gray-100">
        {children}
      </h3>
    ),
    p: ({ children }: any) => (
      <p className="mb-4 leading-relaxed text-gray-700 dark:text-gray-300">
        {children}
      </p>
    ),
    ul: ({ children }: any) => (
      <ul className="list-disc list-inside mb-4 space-y-2 text-gray-700 dark:text-gray-300">
        {children}
      </ul>
    ),
    ol: ({ children }: any) => (
      <ol className="list-decimal list-inside mb-4 space-y-2 text-gray-700 dark:text-gray-300">
        {children}
      </ol>
    ),
    li: ({ children }: any) => (
      <li className="ml-4 text-gray-700 dark:text-gray-300">
        {children}
      </li>
    ),
    blockquote: ({ children }: any) => (
      <blockquote className="border-l-4 pl-4 py-2 my-4 italic border-primary bg-gray-50 dark:bg-panel-dark text-gray-700 dark:text-gray-300 rounded-r">
        {children}
      </blockquote>
    ),
    table: ({ children }: any) => (
      <div className="overflow-x-auto my-4">
        <table className="min-w-full divide-y divide-gray-200 border border-gray-300">
          {children}
        </table>
      </div>
    ),
    th: ({ children }: any) => (
      <th className="px-4 py-2 text-left text-sm font-semibold border-b bg-gray-50 dark:bg-panel-dark text-gray-900 dark:text-gray-100 border-gray-200 dark:border-border-dark">
        {children}
      </th>
    ),
    td: ({ children }: any) => (
      <td className="px-4 py-2 text-sm border-b text-gray-700 dark:text-gray-300 border-gray-200 dark:border-border-dark">
        {children}
      </td>
    ),
    a: ({ children, href }: any) => (
      <a
        href={href}
        className="text-blue-600 hover:text-blue-800 underline"
        target="_blank"
        rel="noopener noreferrer"
      >
        {children}
      </a>
    ),
    img: ({ src, alt }: any) => (
      <div className="my-6 flex justify-center">
        <div className="relative group max-w-2xl w-full">
          <img
            src={src}
            alt={alt || 'Generated image'}
            className="w-full h-auto rounded-lg shadow-lg cursor-pointer transition-transform hover:scale-[1.02] border border-gray-200 dark:border-gray-700"
            style={{ maxHeight: '500px', objectFit: 'contain' }}
            onClick={() => setFullscreenImage(src)}
            loading="lazy"
          />
          {alt && (
            <p className="text-sm text-center mt-2 text-gray-600 dark:text-gray-400 italic">
              {alt}
            </p>
          )}
          <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity bg-black/10 rounded-lg pointer-events-none">
            <span className="text-white bg-black/60 px-3 py-1 rounded-md text-sm font-medium">
              Click to view full size
            </span>
          </div>
        </div>
      </div>
    ),
  }), [copiedIndex, setFullscreenImage]);

  return (
    <div className={`bg-white dark:bg-panel-dark rounded-lg shadow-sm border border-gray-200 dark:border-border-dark ${className}`}>
      {/* Header with metadata */}
      {showMetadata && (
        <div className="border-b border-gray-200 dark:border-border-dark px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={`p-2 rounded-lg ${getTypeColor(output.output_type)}`}>
                {getTypeIcon(output.output_type)}
              </div>
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 capitalize">
                  {output.output_type.replace('_', ' ')} Output
                </h3>
                {output.metadata.workflow_name && (
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    {output.metadata.workflow_name}
                  </p>
                )}
              </div>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex gap-4 text-sm text-gray-500 dark:text-gray-400">
                <span>{output.metadata.word_count.toLocaleString()} words</span>
                {output.metadata.has_code && (
                  <span>{output.metadata.code_block_count} code blocks</span>
                )}
              </div>
              <button
                onClick={downloadOutput}
                className="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg text-gray-500 dark:text-gray-400 transition-colors"
                title="Download Output"
              >
                <Download className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="flex">
        {/* Navigation sidebar for sections */}
        {showNavigation && output.sections.length > 0 && (
          <div className="w-64 border-r border-gray-200 dark:border-border-dark p-4 max-h-[600px] overflow-y-auto custom-scrollbar">
            <h4 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-3">Contents</h4>
            <nav className="space-y-1">
              {output.sections.map((section) => (
                <button
                  key={section.id}
                  onClick={() => scrollToSection(section.id)}
                  className={`
                    w-full text-left px-3 py-2 rounded-md text-sm transition-colors truncate
                    ${activeSection === section.id
                      ? 'bg-primary/10 text-primary font-medium'
                      : 'text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800'}
                    ${section.level > 1 ? `ml-${(section.level - 1) * 2}` : ''}
                  `}
                  style={{ paddingLeft: `${section.level * 12}px` }}
                >
                  {section.title}
                </button>
              ))}
            </nav>
          </div>
        )}

        {/* Main content */}
        <div className="flex-1 p-6 max-h-[600px] overflow-y-auto">
          <div className="prose prose-slate max-w-none">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeRaw]}
              components={markdownComponents}
            >
              {output.formatted_content}
            </ReactMarkdown>
          </div>

          {/* Standalone code blocks (if any) */}
          {output.code_blocks.length > 0 && output.output_type === 'code' && (
            <div className="mt-8 space-y-4">
              <h3 className="text-lg font-semibold text-gray-900">Code Blocks</h3>
              {output.code_blocks.map((block, index) => (
                <div key={index} className="relative group">
                  <div className="flex items-center justify-between bg-gray-800 px-4 py-2 rounded-t-lg">
                    <span className="text-sm font-mono text-gray-300">
                      {block.filename || block.language}
                    </span>
                    <button
                      onClick={() => copyCode(block.code, index)}
                      className="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-white text-sm flex items-center gap-2"
                    >
                      {copiedIndex === index ? (
                        <>
                          <Check className="w-4 h-4" />
                          Copied!
                        </>
                      ) : (
                        <>
                          <Copy className="w-4 h-4" />
                          Copy
                        </>
                      )}
                    </button>
                  </div>
                  <SyntaxHighlighter
                    style={vscDarkPlus}
                    language={block.language}
                    PreTag="div"
                    showLineNumbers
                    startingLineNumber={block.line_start || 1}
                  >
                    {block.code}
                  </SyntaxHighlighter>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Fullscreen Image Modal */}
      {fullscreenImage && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 p-4"
          onClick={() => setFullscreenImage(null)}
        >
          <div className="relative max-w-7xl max-h-[90vh] w-full h-full flex items-center justify-center">
            <button
              onClick={() => setFullscreenImage(null)}
              className="absolute top-4 right-4 p-2 bg-white/10 hover:bg-white/20 rounded-full text-white transition-colors z-10"
              aria-label="Close fullscreen"
            >
              <X className="w-6 h-6" />
            </button>
            <img
              src={fullscreenImage}
              alt="Fullscreen view"
              className="max-w-full max-h-full object-contain rounded-lg"
              onClick={(e) => e.stopPropagation()}
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default FormattedOutputViewer;
