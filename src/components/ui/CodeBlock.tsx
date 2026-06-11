/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import React, { useState } from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { Copy, Check } from 'lucide-react';

interface CodeBlockProps {
  language?: string;
  children: string;
  showCopy?: boolean;
  /** Render the macOS-dot terminal header with the language label. */
  showHeader?: boolean;
  className?: string;
}

/**
 * Shared syntax-highlighted code block. Uses classed Prism tokens
 * (useInlineStyles={false}) so colors come from the `.code-block .token.*`
 * CSS variables — one definition serves every theme. Terminal surfaces stay
 * dark in both light and dark themes per the design spec.
 */
export function CodeBlock({
  language = 'text',
  children,
  showCopy = true,
  showHeader = true,
  className = '',
}: CodeBlockProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(children);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard unavailable */
    }
  };

  return (
    <div className={`terminal-block my-2 ${className}`}>
      {showHeader && (
        <div className="terminal-block-header">
          <span className="terminal-dots">
            <span />
            <span />
            <span />
          </span>
          <span className="flex-1">{language}</span>
          {showCopy && (
            <button
              onClick={handleCopy}
              className="opacity-60 hover:opacity-100 transition-opacity"
              style={{ color: 'var(--code-text)' }}
              title="Copy code"
            >
              {copied ? <Check size={12} /> : <Copy size={12} />}
            </button>
          )}
        </div>
      )}
      <SyntaxHighlighter
        language={language}
        useInlineStyles={false}
        className="code-block"
        customStyle={{ margin: 0, padding: '0.75rem 1rem', background: 'transparent' }}
        codeTagProps={{ className: 'code-block' }}
      >
        {children}
      </SyntaxHighlighter>
    </div>
  );
}

export default CodeBlock;
