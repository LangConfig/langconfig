/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * TextBlock Component
 *
 * Renders a text content block from MCP tool results.
 * Supports markdown rendering for rich text content.
 */

import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { TextContentBlock } from '@/types/content-blocks';

interface TextBlockProps {
  block: TextContentBlock;
  className?: string;
}

export const TextBlock: React.FC<TextBlockProps> = ({ block, className = '' }) => {
  if (!block.text) {
    return null;
  }

  return (
    <div className={`prose prose-slate dark:prose-invert max-w-none ${className}`}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{block.text}</ReactMarkdown>
    </div>
  );
};

export default TextBlock;
