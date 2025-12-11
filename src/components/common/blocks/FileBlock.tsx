/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * FileBlock Component
 *
 * Renders a file content block from MCP tool results.
 * Supports displaying file information and content preview.
 */

import React from 'react';
import { FileText, Download } from 'lucide-react';
import { FileContentBlock } from '@/types/content-blocks';

interface FileBlockProps {
  block: FileContentBlock;
  className?: string;
}

export const FileBlock: React.FC<FileBlockProps> = ({ block, className = '' }) => {
  // Download file handler
  const handleDownload = () => {
    if (!block.data && !block.text) return;

    const content = block.text || atob(block.data || '');
    const mimeType = block.mimeType || 'application/octet-stream';
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href = url;
    a.download = block.name;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className={`my-4 p-4 bg-gray-100 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 ${className}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <FileText className="w-5 h-5 text-gray-600 dark:text-gray-400" />
          <div>
            <p className="font-medium text-gray-900 dark:text-gray-100">{block.name}</p>
            {block.mimeType && (
              <p className="text-xs text-gray-500 dark:text-gray-500">{block.mimeType}</p>
            )}
          </div>
        </div>
        {(block.data || block.text) && (
          <button
            onClick={handleDownload}
            className="p-2 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg text-gray-600 dark:text-gray-400 transition-colors"
            title="Download file"
          >
            <Download className="w-5 h-5" />
          </button>
        )}
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

export default FileBlock;
