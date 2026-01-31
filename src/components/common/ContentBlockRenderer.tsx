/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * ContentBlockRenderer Component
 *
 * Renders an array of MCP content blocks (text, images, audio, files, resources).
 * Used for displaying multimodal tool results in chat and workflow outputs.
 *
 * Features:
 * - Renders different content types with appropriate components
 * - Fullscreen modal for images
 * - Download support for files
 * - Markdown rendering for text blocks
 */

import React, { useState } from 'react';
import { X } from 'lucide-react';
import {
  ContentBlock,
  isTextBlock,
  isImageBlock,
  isAudioBlock,
  isFileBlock,
  isResourceBlock,
} from '@/types/content-blocks';
import { ImageBlock } from './blocks/ImageBlock';
import { AudioBlock } from './blocks/AudioBlock';
import { TextBlock } from './blocks/TextBlock';
import { FileBlock } from './blocks/FileBlock';
import { ResourceBlock } from './blocks/ResourceBlock';
import { VideoBlock } from './blocks/VideoBlock';

interface ContentBlockRendererProps {
  /** Array of content blocks to render */
  blocks: ContentBlock[];
  /** Additional class names */
  className?: string;
  /** Whether to show fullscreen modal for images */
  enableFullscreen?: boolean;
  /** Full (untruncated) tool input to display in the fullscreen image modal */
  toolInput?: string;
}

export const ContentBlockRenderer: React.FC<ContentBlockRendererProps> = ({
  blocks,
  className = '',
  enableFullscreen = true,
  toolInput,
}) => {
  const [fullscreenImage, setFullscreenImage] = useState<string | null>(null);
  const [showToolInput, setShowToolInput] = useState(false);

  if (!blocks || blocks.length === 0) {
    return null;
  }

  const handleImageClick = (src: string) => {
    if (enableFullscreen) {
      setFullscreenImage(src);
    }
  };

  return (
    <>
      <div className={`space-y-2 ${className}`}>
        {blocks.map((block, index) => {
          const key = `block-${index}-${block.type}`;

          if (isTextBlock(block)) {
            return <TextBlock key={key} block={block} />;
          }

          if (isImageBlock(block)) {
            return <ImageBlock key={key} block={block} onImageClick={handleImageClick} />;
          }

          if (isAudioBlock(block)) {
            return <AudioBlock key={key} block={block} />;
          }

          if (isFileBlock(block)) {
            return <FileBlock key={key} block={block} />;
          }

          if (isResourceBlock(block)) {
            return <ResourceBlock key={key} block={block} />;
          }

          // Handle video blocks (type: 'video')
          if ((block as any).type === 'video') {
            return <VideoBlock key={key} block={block as any} />;
          }

          // Unknown block type - render as JSON for debugging
          return (
            <div key={key} className="p-3 bg-yellow-50 dark:bg-yellow-900/20 rounded border border-yellow-200 dark:border-yellow-800">
              <p className="text-xs text-yellow-600 dark:text-yellow-400 mb-1">Unknown content type: {(block as any).type}</p>
              <pre className="text-xs overflow-auto">{JSON.stringify(block, null, 2)}</pre>
            </div>
          );
        })}
      </div>

      {/* Fullscreen Image Modal */}
      {fullscreenImage && enableFullscreen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 p-4"
          onClick={() => setFullscreenImage(null)}
        >
          <div className="relative max-w-7xl max-h-[90vh] w-full h-full flex flex-col items-center justify-center">
            <div className="absolute top-4 right-4 flex gap-2 z-10">
              {/* Download button */}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  const link = document.createElement('a');
                  link.href = fullscreenImage;
                  const timestamp = new Date().toISOString().slice(0, 10);
                  link.download = `generated_image_${timestamp}.png`;
                  document.body.appendChild(link);
                  link.click();
                  document.body.removeChild(link);
                }}
                className="p-2 bg-white/10 hover:bg-white/20 rounded-full text-white transition-colors"
                aria-label="Download image"
                title="Download image"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
              </button>
              {/* Close button */}
              <button
                onClick={() => { setFullscreenImage(null); setShowToolInput(false); }}
                className="p-2 bg-white/10 hover:bg-white/20 rounded-full text-white transition-colors"
                aria-label="Close fullscreen"
              >
                <X className="w-6 h-6" />
              </button>
            </div>
            <img
              src={fullscreenImage}
              alt="Fullscreen view"
              className="max-w-full max-h-full object-contain rounded-lg flex-shrink"
              style={{ minHeight: 0 }}
              onClick={(e) => e.stopPropagation()}
            />
            {/* Collapsible Tool Input section */}
            {toolInput && (
              <div className="w-full max-w-3xl mt-3 flex-shrink-0" onClick={(e) => e.stopPropagation()}>
                <button
                  onClick={() => setShowToolInput(!showToolInput)}
                  className="px-3 py-1.5 text-xs font-medium rounded bg-white/10 hover:bg-white/20 text-white/80 hover:text-white transition-colors"
                >
                  {showToolInput ? 'Hide Tool Input' : 'View Tool Input'}
                </button>
                {showToolInput && (
                  <pre className="mt-2 p-3 rounded-lg bg-black/60 text-gray-200 text-xs font-mono overflow-auto max-h-60 whitespace-pre-wrap break-words border border-white/10">
                    {toolInput}
                  </pre>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
};

/**
 * Simplified component for rendering tool results with multimodal content
 */
interface ToolResultRendererProps {
  /** Text output (for backwards compatibility) */
  outputPreview?: string;
  /** Parsed content blocks */
  contentBlocks?: ContentBlock[];
  /** Artifacts for UI display only */
  artifacts?: ContentBlock[];
  /** Whether result has multimodal content */
  hasMultimodal?: boolean;
  /** Additional class names */
  className?: string;
}

export const ToolResultRenderer: React.FC<ToolResultRendererProps> = ({
  outputPreview,
  contentBlocks = [],
  artifacts = [],
  hasMultimodal = false,
  className = '',
}) => {
  // If we have multimodal content, use ContentBlockRenderer
  if (hasMultimodal && (contentBlocks.length > 0 || artifacts.length > 0)) {
    return (
      <div className={className}>
        {contentBlocks.length > 0 && <ContentBlockRenderer blocks={contentBlocks} />}
        {artifacts.length > 0 && (
          <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-2 font-medium">Generated Content:</p>
            <ContentBlockRenderer blocks={artifacts} />
          </div>
        )}
      </div>
    );
  }

  // Fallback to text output
  if (outputPreview) {
    return (
      <div className={`text-sm text-gray-700 dark:text-gray-300 ${className}`}>
        <pre className="whitespace-pre-wrap font-mono text-xs">{outputPreview}</pre>
      </div>
    );
  }

  return null;
};

export default ContentBlockRenderer;
