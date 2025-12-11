/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * ResourceBlock Component
 *
 * Renders an embedded resource content block from MCP tool results.
 * Supports displaying URIs, text content, and binary blobs.
 */

import React from 'react';
import { ExternalLink, Link2 } from 'lucide-react';
import { ResourceContentBlock } from '@/types/content-blocks';

interface ResourceBlockProps {
  block: ResourceContentBlock;
  className?: string;
}

export const ResourceBlock: React.FC<ResourceBlockProps> = ({ block, className = '' }) => {
  // Check if URI is a clickable link
  const isLink = block.uri.startsWith('http://') || block.uri.startsWith('https://');

  return (
    <div className={`my-4 p-4 bg-gray-100 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 ${className}`}>
      <div className="flex items-center gap-3">
        <Link2 className="w-5 h-5 text-gray-600 dark:text-gray-400" />
        <div className="flex-1 min-w-0">
          {isLink ? (
            <a
              href={block.uri}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1 truncate"
            >
              {block.uri}
              <ExternalLink className="w-4 h-4 flex-shrink-0" />
            </a>
          ) : (
            <span className="text-gray-700 dark:text-gray-300 font-mono text-sm truncate block">
              {block.uri}
            </span>
          )}
          {block.mimeType && (
            <p className="text-xs text-gray-500 dark:text-gray-500 mt-1">{block.mimeType}</p>
          )}
        </div>
      </div>

      {/* Preview text content if available */}
      {block.text && (
        <div className="mt-3 p-3 bg-white dark:bg-gray-900 rounded border border-gray-200 dark:border-gray-700 max-h-48 overflow-y-auto">
          <pre className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap font-mono">
            {block.text.slice(0, 1000)}
            {block.text.length > 1000 && '...'}
          </pre>
        </div>
      )}
    </div>
  );
};

export default ResourceBlock;
