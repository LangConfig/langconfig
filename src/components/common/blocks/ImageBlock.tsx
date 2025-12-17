/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * ImageBlock Component
 *
 * Renders an image content block from MCP tool results.
 * Supports base64-encoded images with click-to-fullscreen and download functionality.
 */

import React from 'react';
import { Download } from 'lucide-react';
import { ImageContentBlock, contentBlockToDataUri } from '@/types/content-blocks';
import { useDownloadContext, sanitizeFilename } from '@/contexts/DownloadContext';

interface ImageBlockProps {
  block: ImageContentBlock;
  onImageClick?: (src: string) => void;
  className?: string;
}

export const ImageBlock: React.FC<ImageBlockProps> = ({ block, onImageClick, className = '' }) => {
  const src = contentBlockToDataUri(block);
  const { workflowName, getNextNumber } = useDownloadContext();

  const handleDownload = (e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent triggering fullscreen
    if (!src) return;

    // Create a link element and trigger download
    const link = document.createElement('a');
    link.href = src;

    // Use workflow name + number for filename
    const mimeType = block.mimeType || 'image/png';
    const extension = mimeType.split('/')[1] || 'png';
    const safeName = sanitizeFilename(workflowName);
    const number = getNextNumber();
    link.download = `${safeName}_${number}.${extension}`;

    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  if (!src) {
    return (
      <div className={`p-4 bg-gray-100 dark:bg-gray-800 rounded-lg text-gray-500 ${className}`}>
        Image data unavailable
      </div>
    );
  }

  return (
    <div className={`my-4 flex justify-center ${className}`}>
      <div className="relative group max-w-2xl w-full">
        <img
          src={src}
          alt={block.alt_text || 'Tool generated image'}
          className="w-full h-auto rounded-lg shadow-lg cursor-pointer transition-transform hover:scale-[1.02] border border-gray-200 dark:border-gray-700"
          style={{ maxHeight: '500px', objectFit: 'contain' }}
          onClick={() => onImageClick?.(src)}
          loading="lazy"
        />
        {block.alt_text && (
          <p className="text-sm text-center mt-2 text-gray-600 dark:text-gray-400 italic">
            {block.alt_text}
          </p>
        )}
        {/* Hover overlay with actions */}
        <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity bg-black/10 rounded-lg pointer-events-none">
          <span className="text-white bg-black/60 px-3 py-1 rounded-md text-sm font-medium">
            Click to view full size
          </span>
        </div>
        {/* Download button */}
        <button
          onClick={handleDownload}
          className="absolute top-2 right-2 p-2 bg-black/50 hover:bg-black/70 rounded-full text-white opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
          title="Download image"
        >
          <Download className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};

export default ImageBlock;
