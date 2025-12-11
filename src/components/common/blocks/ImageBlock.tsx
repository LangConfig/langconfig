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
 * Supports base64-encoded images with click-to-fullscreen functionality.
 */

import React from 'react';
import { ImageContentBlock, contentBlockToDataUri } from '@/types/content-blocks';

interface ImageBlockProps {
  block: ImageContentBlock;
  onImageClick?: (src: string) => void;
  className?: string;
}

export const ImageBlock: React.FC<ImageBlockProps> = ({ block, onImageClick, className = '' }) => {
  const src = contentBlockToDataUri(block);

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
        <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity bg-black/10 rounded-lg pointer-events-none">
          <span className="text-white bg-black/60 px-3 py-1 rounded-md text-sm font-medium">
            Click to view full size
          </span>
        </div>
      </div>
    </div>
  );
};

export default ImageBlock;
