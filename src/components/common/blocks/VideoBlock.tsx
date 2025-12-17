/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * VideoBlock Component
 *
 * Renders a video content block from MCP tool results.
 * Supports base64-encoded videos with native HTML5 video controls and download.
 */

import React from 'react';
import { Video, Download } from 'lucide-react';
import { useDownloadContext, sanitizeFilename } from '@/contexts/DownloadContext';

interface VideoBlockProps {
  block: {
    type: 'video';
    data: string;
    mimeType: string;
    duration_seconds?: number;
  };
  className?: string;
}

export const VideoBlock: React.FC<VideoBlockProps> = ({ block, className = '' }) => {
  const src = `data:${block.mimeType};base64,${block.data}`;
  const { workflowName, getNextNumber } = useDownloadContext();

  const handleDownload = () => {
    const link = document.createElement('a');
    link.href = src;

    // Use workflow name + number for filename
    const mimeType = block.mimeType || 'video/mp4';
    const extension = mimeType.split('/')[1] || 'mp4';
    const safeName = sanitizeFilename(workflowName);
    const number = getNextNumber();
    link.download = `${safeName}_video_${number}.${extension}`;

    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Format duration for display
  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className={`my-4 p-4 bg-gray-100 dark:bg-gray-800 rounded-lg ${className}`}>
      <div className="flex items-center gap-3 mb-3">
        <Video className="w-5 h-5 text-gray-600 dark:text-gray-400" />
        <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Generated Video</span>
        {block.duration_seconds && (
          <span className="text-xs text-gray-500 dark:text-gray-500">
            {formatDuration(block.duration_seconds)}
          </span>
        )}
        <button
          onClick={handleDownload}
          className="ml-auto p-1.5 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-full transition-colors"
          title="Download video"
        >
          <Download className="w-4 h-4 text-gray-600 dark:text-gray-400" />
        </button>
      </div>
      <video
        controls
        className="w-full max-h-[500px] rounded-lg shadow-lg"
        preload="metadata"
      >
        <source src={src} type={block.mimeType} />
        Your browser does not support video playback.
      </video>
    </div>
  );
};

export default VideoBlock;
