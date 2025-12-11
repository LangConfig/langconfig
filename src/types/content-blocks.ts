/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * MCP Multimodal Content Block Types
 *
 * Defines TypeScript interfaces for MCP (Model Context Protocol) multimodal content blocks.
 * These types correspond to the backend schemas in backend/schemas/mcp_content.py
 *
 * MCP tools can return content in various formats: text, images, audio, and embedded resources.
 * Content blocks are used for LLM context, while artifacts are for UI display only.
 */

/**
 * Text content block
 */
export interface TextContentBlock {
  type: 'text';
  text: string;
}

/**
 * Image content block (e.g., screenshots, generated images)
 */
export interface ImageContentBlock {
  type: 'image';
  /** Base64-encoded image data */
  data: string;
  /** MIME type (image/png, image/jpeg, etc.) */
  mimeType: string;
  /** Alternative text description */
  alt_text?: string;
}

/**
 * Audio content block
 */
export interface AudioContentBlock {
  type: 'audio';
  /** Base64-encoded audio data */
  data: string;
  /** MIME type (audio/wav, audio/mp3, etc.) */
  mimeType: string;
  /** Audio duration in seconds */
  duration_seconds?: number;
}

/**
 * File content block
 */
export interface FileContentBlock {
  type: 'file';
  /** File name */
  name: string;
  /** MIME type */
  mimeType?: string;
  /** Base64-encoded file data */
  data?: string;
  /** Text content if applicable */
  text?: string;
}

/**
 * Embedded resource content block
 */
export interface ResourceContentBlock {
  type: 'resource';
  /** Resource URI */
  uri: string;
  /** MIME type of the resource */
  mimeType?: string;
  /** Base64-encoded binary content */
  blob?: string;
  /** Text content if applicable */
  text?: string;
}

/**
 * Union type for all content block types
 */
export type ContentBlock =
  | TextContentBlock
  | ImageContentBlock
  | AudioContentBlock
  | FileContentBlock
  | ResourceContentBlock;

/**
 * Tool result with multimodal content support
 */
export interface MultimodalToolResult {
  /** Text output for backwards compatibility */
  output_preview?: string;
  full_output?: string;
  /** Parsed content blocks */
  content_blocks: ContentBlock[];
  /** Content blocks for UI display only (not sent to LLM) */
  artifacts: ContentBlock[];
  /** Whether the result contains non-text content */
  has_multimodal: boolean;
}

/**
 * Type guard to check if a content block is an image
 */
export function isImageBlock(block: ContentBlock): block is ImageContentBlock {
  return block.type === 'image';
}

/**
 * Type guard to check if a content block is audio
 */
export function isAudioBlock(block: ContentBlock): block is AudioContentBlock {
  return block.type === 'audio';
}

/**
 * Type guard to check if a content block is text
 */
export function isTextBlock(block: ContentBlock): block is TextContentBlock {
  return block.type === 'text';
}

/**
 * Type guard to check if a content block is a file
 */
export function isFileBlock(block: ContentBlock): block is FileContentBlock {
  return block.type === 'file';
}

/**
 * Type guard to check if a content block is a resource
 */
export function isResourceBlock(block: ContentBlock): block is ResourceContentBlock {
  return block.type === 'resource';
}

/**
 * Convert an image or audio content block to a data URI for display
 */
export function contentBlockToDataUri(block: ContentBlock): string | null {
  if (block.type === 'image' || block.type === 'audio') {
    return `data:${block.mimeType};base64,${block.data}`;
  }
  return null;
}

/**
 * Extract all text content from a list of content blocks
 */
export function getTextFromBlocks(blocks: ContentBlock[]): string {
  return blocks
    .filter(isTextBlock)
    .map((block) => block.text)
    .join('\n');
}

/**
 * Extract all image blocks from a list of content blocks
 */
export function getImagesFromBlocks(blocks: ContentBlock[]): ImageContentBlock[] {
  return blocks.filter(isImageBlock);
}

/**
 * Check if any blocks contain multimodal content (non-text)
 */
export function hasMultimodalContent(blocks: ContentBlock[]): boolean {
  return blocks.some(
    (block) => block.type === 'image' || block.type === 'audio' || block.type === 'file' || block.type === 'resource'
  );
}
