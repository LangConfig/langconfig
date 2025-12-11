/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * AudioBlock Component
 *
 * Renders an audio content block from MCP tool results.
 * Supports base64-encoded audio with native HTML5 audio controls.
 */

import React from 'react';
import { Volume2 } from 'lucide-react';
import { AudioContentBlock, contentBlockToDataUri } from '@/types/content-blocks';

interface AudioBlockProps {
  block: AudioContentBlock;
  className?: string;
}

export const AudioBlock: React.FC<AudioBlockProps> = ({ block, className = '' }) => {
  const src = contentBlockToDataUri(block);

  if (!src) {
    return (
      <div className={`p-4 bg-gray-100 dark:bg-gray-800 rounded-lg text-gray-500 ${className}`}>
        Audio data unavailable
      </div>
    );
  }

  // Format duration for display
  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className={`my-4 p-4 bg-gray-100 dark:bg-gray-800 rounded-lg ${className}`}>
      <div className="flex items-center gap-3 mb-2">
        <Volume2 className="w-5 h-5 text-gray-600 dark:text-gray-400" />
        <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Audio Output</span>
        {block.duration_seconds && (
          <span className="text-xs text-gray-500 dark:text-gray-500">
            {formatDuration(block.duration_seconds)}
          </span>
        )}
      </div>
      <audio controls className="w-full" preload="metadata">
        <source src={src} type={block.mimeType} />
        Your browser does not support audio playback.
      </audio>
    </div>
  );
};

export default AudioBlock;
