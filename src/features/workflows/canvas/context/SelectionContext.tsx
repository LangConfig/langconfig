/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * Selection Context
 *
 * Provides unified selection state across ArtifactsTab and Files tab
 * for multi-file selection operations like creating presentations.
 */

import { createContext, useContext, useState, useCallback, useMemo, type ReactNode } from 'react';
import type { ContentBlock } from '@/types/content-blocks';

/**
 * Represents a selectable item (either an artifact content block or a workspace file)
 */
export interface SelectionItem {
  /** Item type */
  type: 'artifact' | 'file';
  /** Unique identifier for this item */
  id: string;
  /** Display name for the item */
  displayName: string;
  /** MIME type if known */
  mimeType?: string;

  // Artifact-specific fields
  /** Task ID the artifact belongs to */
  taskId?: number;
  /** Index of the content block within the task */
  blockIndex?: number;
  /** The actual content block data */
  block?: ContentBlock;
  /** Agent label that created this artifact */
  agentLabel?: string;

  // File-specific fields
  /** Full path to the workspace file */
  filePath?: string;
  /** File size in bytes */
  sizeBytes?: number;
  /** File extension */
  extension?: string;
}

/**
 * Selection context type definition
 */
interface SelectionContextType {
  /** Map of selected items by their unique ID */
  selectedItems: Map<string, SelectionItem>;
  /** Whether selection mode is currently active */
  isSelecting: boolean;
  /** Total count of selected items */
  selectedCount: number;

  /** Toggle selection of a single item */
  toggleSelection: (item: SelectionItem) => void;
  /** Select multiple items at once */
  selectAll: (items: SelectionItem[]) => void;
  /** Clear all selections */
  clearSelection: () => void;
  /** Enable or disable selection mode */
  setIsSelecting: (value: boolean) => void;
  /** Check if an item is selected by its ID */
  isSelected: (id: string) => boolean;
  /** Get all selected items as an array */
  getSelectedItems: () => SelectionItem[];
  /** Get selected items filtered by type */
  getSelectedByType: (type: 'artifact' | 'file') => SelectionItem[];
}

const SelectionContext = createContext<SelectionContextType | null>(null);

interface SelectionProviderProps {
  children: ReactNode;
}

/**
 * Provider component for selection context
 */
export function SelectionProvider({ children }: SelectionProviderProps) {
  const [selectedItems, setSelectedItems] = useState<Map<string, SelectionItem>>(new Map());
  const [isSelecting, setIsSelecting] = useState(false);

  const selectedCount = useMemo(() => selectedItems.size, [selectedItems]);

  const toggleSelection = useCallback((item: SelectionItem) => {
    setSelectedItems(prev => {
      const next = new Map(prev);
      if (next.has(item.id)) {
        next.delete(item.id);
      } else {
        next.set(item.id, item);
      }
      return next;
    });
  }, []);

  const selectAll = useCallback((items: SelectionItem[]) => {
    setSelectedItems(prev => {
      const next = new Map(prev);
      // If all items are already selected, deselect them
      const allSelected = items.every(item => next.has(item.id));
      if (allSelected) {
        items.forEach(item => next.delete(item.id));
      } else {
        items.forEach(item => next.set(item.id, item));
      }
      return next;
    });
  }, []);

  const clearSelection = useCallback(() => {
    setSelectedItems(new Map());
    setIsSelecting(false);
  }, []);

  const isSelected = useCallback((id: string) => {
    return selectedItems.has(id);
  }, [selectedItems]);

  const getSelectedItems = useCallback(() => {
    return Array.from(selectedItems.values());
  }, [selectedItems]);

  const getSelectedByType = useCallback((type: 'artifact' | 'file') => {
    return Array.from(selectedItems.values()).filter(item => item.type === type);
  }, [selectedItems]);

  const value = useMemo<SelectionContextType>(() => ({
    selectedItems,
    isSelecting,
    selectedCount,
    toggleSelection,
    selectAll,
    clearSelection,
    setIsSelecting,
    isSelected,
    getSelectedItems,
    getSelectedByType,
  }), [
    selectedItems,
    isSelecting,
    selectedCount,
    toggleSelection,
    selectAll,
    clearSelection,
    isSelected,
    getSelectedItems,
    getSelectedByType,
  ]);

  return (
    <SelectionContext.Provider value={value}>
      {children}
    </SelectionContext.Provider>
  );
}

/**
 * Hook to access selection context
 * @throws Error if used outside of SelectionProvider
 */
export function useSelection(): SelectionContextType {
  const context = useContext(SelectionContext);
  if (!context) {
    throw new Error('useSelection must be used within a SelectionProvider');
  }
  return context;
}

/**
 * Hook to optionally access selection context (returns null if outside provider)
 */
export function useSelectionOptional(): SelectionContextType | null {
  return useContext(SelectionContext);
}

/**
 * Helper to create a selection item from an artifact
 */
export function createArtifactSelectionItem(
  taskId: number,
  blockIndex: number,
  block: ContentBlock,
  agentLabel?: string
): SelectionItem {
  const id = `artifact-${taskId}-${blockIndex}`;
  let displayName = `${block.type} from Task #${taskId}`;
  let mimeType: string | undefined;

  switch (block.type) {
    case 'image':
      displayName = block.alt_text || `Image ${blockIndex + 1}`;
      mimeType = block.mimeType;
      break;
    case 'audio':
      displayName = `Audio ${blockIndex + 1}`;
      mimeType = block.mimeType;
      break;
    case 'file':
      displayName = block.name;
      mimeType = block.mimeType;
      break;
    case 'text':
      displayName = block.text.slice(0, 50) + (block.text.length > 50 ? '...' : '');
      mimeType = 'text/plain';
      break;
    case 'resource':
      displayName = block.uri.split('/').pop() || 'Resource';
      mimeType = block.mimeType;
      break;
  }

  return {
    type: 'artifact',
    id,
    displayName,
    mimeType,
    taskId,
    blockIndex,
    block,
    agentLabel,
  };
}

/**
 * Helper to create a selection item from a workspace file
 */
export function createFileSelectionItem(
  taskId: number,
  filename: string,
  filePath: string,
  sizeBytes?: number,
  extension?: string,
  mimeType?: string
): SelectionItem {
  const id = `file-${taskId}-${filePath}`;

  return {
    type: 'file',
    id,
    displayName: filename,
    mimeType: mimeType || getMimeTypeFromExtension(extension),
    filePath,
    sizeBytes,
    extension,
    taskId,
  };
}

/**
 * Get MIME type from file extension
 */
function getMimeTypeFromExtension(extension?: string): string | undefined {
  if (!extension) return undefined;

  const ext = extension.toLowerCase().replace('.', '');
  const mimeTypes: Record<string, string> = {
    // Text
    txt: 'text/plain',
    md: 'text/markdown',
    json: 'application/json',
    html: 'text/html',
    css: 'text/css',
    js: 'text/javascript',
    ts: 'text/typescript',
    py: 'text/x-python',
    // Images
    png: 'image/png',
    jpg: 'image/jpeg',
    jpeg: 'image/jpeg',
    gif: 'image/gif',
    svg: 'image/svg+xml',
    webp: 'image/webp',
    // Documents
    pdf: 'application/pdf',
    doc: 'application/msword',
    docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    // Audio
    mp3: 'audio/mpeg',
    wav: 'audio/wav',
    // Video
    mp4: 'video/mp4',
    webm: 'video/webm',
  };

  return mimeTypes[ext];
}
