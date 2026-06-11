/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { CodeBlock } from './CodeBlock';

interface MarkdownProps {
  children: string;
  /** Tighter spacing for inline contexts (chat bubbles). */
  compact?: boolean;
  className?: string;
}

/**
 * Shared markdown renderer. Tables, inline code, blockquotes and links are
 * styled by the `.chat-markdown` CSS (theme-token driven); fenced code routes
 * to the terminal-styled CodeBlock.
 */
export function Markdown({ children, compact = false, className = '' }: MarkdownProps) {
  return (
    <div className={`chat-markdown ${compact ? 'text-sm' : ''} ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code({ className: codeClass, children: codeChildren, ...props }) {
            const match = /language-(\w+)/.exec(codeClass || '');
            const content = String(codeChildren).replace(/\n$/, '');
            if (match || content.includes('\n')) {
              return <CodeBlock language={match?.[1] ?? 'text'}>{content}</CodeBlock>;
            }
            return (
              <code className={codeClass} {...props}>
                {codeChildren}
              </code>
            );
          },
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}

export default Markdown;
