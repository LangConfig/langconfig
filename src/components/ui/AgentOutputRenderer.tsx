/**
 * AgentOutputRenderer Component
 *
 * Reusable component for sanitizing and rendering agent output as markdown.
 * Handles parsing of raw data structures (Command, dicts) and renders clean markdown.
 * Use this throughout the app for consistent agent output display.
 */

import React, { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

interface AgentOutputRendererProps {
  /** Raw output from agent - can be markdown, Command structure, dict string, etc. */
  content: string;
  /** Optional className for the container */
  className?: string;
  /** Maximum height before scrolling (default: none) */
  maxHeight?: string | number;
  /** Whether to show in compact mode (less padding) */
  compact?: boolean;
}

/**
 * Sanitizes raw agent output by:
 * 1. Extracting file content from Command(update={'files': {...}}) structures
 * 2. Extracting description from dict-like strings {'subagent_type': ..., 'description': ...}
 * 3. Cleaning up escape sequences and formatting
 */
function sanitizeAgentOutput(raw: string): string {
  if (!raw || typeof raw !== 'string') return '';

  let output = raw.trim();

  // Process line by line for Task:/Result: sections
  const sections: string[] = [];
  const lines = output.split('\n');
  let currentSection = '';
  let currentContent = '';

  for (const line of lines) {
    if (line.startsWith('**Task:**') || line.startsWith('Task:')) {
      if (currentSection && currentContent) {
        sections.push(`**${currentSection}**\n${sanitizeSingleValue(currentContent.trim())}`);
      }
      currentSection = 'Task';
      currentContent = line.replace(/^\*?\*?Task:\*?\*?\s*/, '');
    } else if (line.startsWith('**Result:**') || line.startsWith('Result:')) {
      if (currentSection && currentContent) {
        sections.push(`**${currentSection}**\n${sanitizeSingleValue(currentContent.trim())}`);
      }
      currentSection = 'Result';
      currentContent = line.replace(/^\*?\*?Result:\*?\*?\s*/, '');
    } else {
      currentContent += '\n' + line;
    }
  }

  // Add last section
  if (currentSection && currentContent) {
    sections.push(`**${currentSection}**\n${sanitizeSingleValue(currentContent.trim())}`);
  }

  // If we found sections, use them; otherwise sanitize the whole thing
  if (sections.length > 0) {
    output = sections.join('\n\n');
  } else {
    output = sanitizeSingleValue(output);
  }

  return output;
}

/**
 * Sanitizes a single value - handles dict strings and Command structures
 */
function sanitizeSingleValue(value: string): string {
  if (!value) return '';

  let output = value.trim();

  // Handle dict-like input strings: {'subagent_type': '...', 'description': '...'}
  if (output.startsWith("{") && output.includes("'description'")) {
    try {
      // Extract the description value - handle multi-line descriptions
      const descMatch = output.match(/'description':\s*['"](.+?)['"]\s*[,}]/s);
      if (descMatch) {
        output = descMatch[1]
          .replace(/\\n/g, '\n')
          .replace(/\\t/g, '\t');
      }
    } catch {
      // Continue with raw output
    }
  }

  // Handle Command(update={'files': {...}}) structure from DeepAgents
  if (output.startsWith("Command(update=")) {
    try {
      // Extract file content from the Command structure
      // Pattern: Command(update={'files': {'/path': {'content': ['line1', 'line2', ...]}}})

      // Find the content array - use a more robust pattern
      const contentMatch = output.match(/'content':\s*\[([\s\S]*?)\]\s*[,}]/);
      if (contentMatch) {
        const contentStr = contentMatch[1];

        // Extract all quoted strings from content array
        const lines: string[] = [];
        // Match quoted strings, handling the Python list format
        const regex = /'([^']*)'/g;
        let match;
        while ((match = regex.exec(contentStr)) !== null) {
          let line = match[1]
            .replace(/\\n/g, '\n')
            .replace(/\\t/g, '\t')
            .replace(/\\'/g, "'")
            .replace(/\\\\/g, '\\');
          lines.push(line);
        }

        if (lines.length > 0) {
          // Join with newlines since content is an array of lines
          output = lines.join('\n');
        }
      }
    } catch {
      // If parsing fails, continue with other sanitization
    }
  }

  // Clean up common escape sequences
  output = output
    .replace(/\\n/g, '\n')
    .replace(/\\t/g, '\t')
    .replace(/\\"/g, '"')
    .replace(/\\'/g, "'");

  return output;
}

/**
 * AgentOutputRenderer - Renders sanitized agent output as markdown
 */
export const AgentOutputRenderer: React.FC<AgentOutputRendererProps> = ({
  content,
  className = '',
  maxHeight,
  compact = false
}) => {
  // Sanitize and clean the content
  const sanitizedContent = useMemo(() => sanitizeAgentOutput(content), [content]);

  if (!sanitizedContent) {
    return null;
  }

  return (
    <div
      className={`agent-output-renderer ${compact ? 'compact' : ''} ${className}`}
      style={{
        maxHeight: maxHeight,
        overflowY: maxHeight ? 'auto' : undefined,
      }}
    >
      <div className="prose prose-sm max-w-none">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            // Code blocks with syntax highlighting
            code({ node, className, children, ...props }) {
              const match = /language-(\w+)/.exec(className || '');
              const isInline = !match && !String(children).includes('\n');

              return !isInline ? (
                <SyntaxHighlighter
                  language={match ? match[1] : 'text'}
                  style={vscDarkPlus}
                  customStyle={{
                    margin: '0.5rem 0',
                    borderRadius: '0.375rem',
                    fontSize: '0.85em',
                    padding: '1rem'
                  }}
                  wrapLongLines
                >
                  {String(children).replace(/\n$/, '')}
                </SyntaxHighlighter>
              ) : (
                <code
                  className="bg-gray-200 px-1.5 py-0.5 rounded text-sm text-gray-800"
                  {...props}
                >
                  {children}
                </code>
              );
            },
            // Style headings - dark text
            h1: ({ children }) => (
              <h1 className="text-xl font-bold mt-4 mb-2 text-gray-900">{children}</h1>
            ),
            h2: ({ children }) => (
              <h2 className="text-lg font-semibold mt-3 mb-2 text-gray-900">{children}</h2>
            ),
            h3: ({ children }) => (
              <h3 className="text-base font-medium mt-2 mb-1 text-gray-900">{children}</h3>
            ),
            // Style paragraphs - dark text
            p: ({ children }) => (
              <p className="my-2 leading-relaxed text-gray-800">{children}</p>
            ),
            // Style lists - dark text
            ul: ({ children }) => (
              <ul className="list-disc list-inside my-2 space-y-1 text-gray-800">{children}</ul>
            ),
            ol: ({ children }) => (
              <ol className="list-decimal list-inside my-2 space-y-1 text-gray-800">{children}</ol>
            ),
            li: ({ children }) => (
              <li className="text-gray-800">{children}</li>
            ),
            // Style links
            a: ({ href, children }) => (
              <a
                href={href}
                className="text-blue-600 hover:text-blue-500 underline"
                target="_blank"
                rel="noopener noreferrer"
              >
                {children}
              </a>
            ),
            // Style blockquotes
            blockquote: ({ children }) => (
              <blockquote className="border-l-4 border-gray-400 pl-4 my-2 italic text-gray-700">
                {children}
              </blockquote>
            ),
            // Style tables
            table: ({ children }) => (
              <div className="overflow-x-auto my-2">
                <table className="min-w-full border-collapse border border-gray-300">
                  {children}
                </table>
              </div>
            ),
            th: ({ children }) => (
              <th className="border border-gray-300 bg-gray-100 px-3 py-2 text-left text-sm font-semibold text-gray-900">
                {children}
              </th>
            ),
            td: ({ children }) => (
              <td className="border border-gray-300 px-3 py-2 text-sm text-gray-800">
                {children}
              </td>
            ),
            // Style horizontal rules
            hr: () => (
              <hr className="my-4 border-gray-300" />
            ),
            // Style strong/bold - dark text
            strong: ({ children }) => (
              <strong className="font-semibold text-gray-900">{children}</strong>
            ),
            // Style emphasis/italic
            em: ({ children }) => (
              <em className="italic text-gray-700">{children}</em>
            ),
          }}
        >
          {sanitizedContent}
        </ReactMarkdown>
      </div>
    </div>
  );
};

// Export the sanitize function for use elsewhere
export { sanitizeAgentOutput };

export default AgentOutputRenderer;
