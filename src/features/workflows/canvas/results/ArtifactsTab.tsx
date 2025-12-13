/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * Artifacts Tab
 *
 * Displays images, generated content, and other artifacts from workflow executions.
 * Shows a gallery view of all multimodal content created by agents.
 */

import { useState, useMemo } from 'react';
import { Image, FileText, Music, File, Download, Maximize2, X, Calendar, Bot } from 'lucide-react';
import { ContentBlockRenderer } from '@/components/common/ContentBlockRenderer';
import type { ContentBlock, ImageContentBlock } from '@/types/content-blocks';
import { isImageBlock } from '@/types/content-blocks';

interface ArtifactEntry {
  id: string;
  taskId: number;
  agentLabel?: string;
  timestamp: string;
  blocks: ContentBlock[];
}

interface ArtifactsTabProps {
  artifacts: ArtifactEntry[];
  loading?: boolean;
}

// Get icon for content block type
const getBlockIcon = (type: string) => {
  switch (type) {
    case 'image':
      return <Image className="w-4 h-4" />;
    case 'audio':
      return <Music className="w-4 h-4" />;
    case 'file':
      return <File className="w-4 h-4" />;
    case 'text':
      return <FileText className="w-4 h-4" />;
    default:
      return <File className="w-4 h-4" />;
  }
};

// Get block type display name
const getBlockTypeName = (type: string) => {
  switch (type) {
    case 'image':
      return 'Image';
    case 'audio':
      return 'Audio';
    case 'file':
      return 'File';
    case 'text':
      return 'Text';
    case 'resource':
      return 'Resource';
    default:
      return 'Content';
  }
};

export default function ArtifactsTab({ artifacts, loading }: ArtifactsTabProps) {
  const [selectedArtifact, setSelectedArtifact] = useState<ArtifactEntry | null>(null);
  const [fullscreenImage, setFullscreenImage] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'gallery' | 'list'>('gallery');
  const [filterType, setFilterType] = useState<string>('all');

  // Flatten all blocks for filtering/counting
  const allBlocks = useMemo(() => {
    const blocks: { artifact: ArtifactEntry; block: ContentBlock; index: number }[] = [];
    artifacts.forEach(artifact => {
      artifact.blocks.forEach((block, index) => {
        blocks.push({ artifact, block, index });
      });
    });
    return blocks;
  }, [artifacts]);

  // Get unique block types for filter
  const blockTypes = useMemo(() => {
    const types = new Set<string>();
    allBlocks.forEach(({ block }) => types.add(block.type));
    return Array.from(types);
  }, [allBlocks]);

  // Filter blocks
  const filteredBlocks = useMemo(() => {
    if (filterType === 'all') return allBlocks;
    return allBlocks.filter(({ block }) => block.type === filterType);
  }, [allBlocks, filterType]);

  // Count by type
  const countByType = useMemo(() => {
    const counts: Record<string, number> = {};
    allBlocks.forEach(({ block }) => {
      counts[block.type] = (counts[block.type] || 0) + 1;
    });
    return counts;
  }, [allBlocks]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 mx-auto mb-4" style={{ borderColor: 'var(--color-primary)' }}></div>
          <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>Loading artifacts...</p>
        </div>
      </div>
    );
  }

  if (artifacts.length === 0 || allBlocks.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center p-8">
        <Image className="w-16 h-16 mb-4" style={{ color: 'var(--color-text-muted)', opacity: 0.3 }} />
        <p className="text-lg font-medium" style={{ color: 'var(--color-text-muted)' }}>No artifacts yet</p>
        <p className="text-sm mt-2" style={{ color: 'var(--color-text-muted)', opacity: 0.7 }}>
          Images, generated content, and other artifacts from agent executions will appear here.
        </p>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* Toolbar */}
      <div className="flex-shrink-0 flex items-center justify-between gap-4 p-4 border-b" style={{ borderColor: 'var(--color-border-dark)' }}>
        <div className="flex items-center gap-3">
          {/* Type filter */}
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="px-3 py-1.5 text-sm rounded-lg border focus:outline-none focus:ring-2 focus:ring-primary/50"
            style={{
              backgroundColor: 'var(--color-panel-dark)',
              borderColor: 'var(--color-border-dark)',
              color: 'var(--color-text-primary)'
            }}
          >
            <option value="all">All Types ({allBlocks.length})</option>
            {blockTypes.map(type => (
              <option key={type} value={type}>
                {getBlockTypeName(type)} ({countByType[type] || 0})
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2">
          {/* View Toggle */}
          <div className="flex border rounded-lg overflow-hidden" style={{ borderColor: 'var(--color-border-dark)' }}>
            <button
              onClick={() => setViewMode('gallery')}
              className={`px-3 py-1.5 text-sm flex items-center gap-1.5 ${
                viewMode === 'gallery'
                  ? 'bg-primary/10'
                  : 'hover:bg-white/5'
              }`}
              style={{ color: viewMode === 'gallery' ? 'var(--color-primary)' : 'var(--color-text-muted)' }}
              title="Gallery View"
            >
              <Image className="w-4 h-4" />
              Gallery
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={`px-3 py-1.5 text-sm flex items-center gap-1.5 border-l ${
                viewMode === 'list'
                  ? 'bg-primary/10'
                  : 'hover:bg-white/5'
              }`}
              style={{
                color: viewMode === 'list' ? 'var(--color-primary)' : 'var(--color-text-muted)',
                borderColor: 'var(--color-border-dark)'
              }}
              title="List View"
            >
              <FileText className="w-4 h-4" />
              List
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-4">
        {viewMode === 'gallery' ? (
          // Gallery View - Grid of artifacts
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {filteredBlocks.map(({ artifact, block, index }) => (
              <div
                key={`${artifact.id}-${index}`}
                className="group relative rounded-lg border overflow-hidden cursor-pointer transition-all hover:shadow-lg"
                style={{
                  backgroundColor: 'var(--color-panel-dark)',
                  borderColor: 'var(--color-border-dark)'
                }}
                onClick={() => setSelectedArtifact(artifact)}
              >
                {/* Preview */}
                <div className="aspect-square flex items-center justify-center p-2" style={{ backgroundColor: 'var(--color-background-light)' }}>
                  {isImageBlock(block) ? (
                    <img
                      src={`data:${block.mimeType || 'image/png'};base64,${block.data}`}
                      alt={block.alt_text || "Generated image"}
                      className="max-w-full max-h-full object-contain rounded"
                    />
                  ) : (
                    <div className="text-center">
                      <div className="w-12 h-12 mx-auto mb-2 rounded-full flex items-center justify-center" style={{ backgroundColor: 'var(--color-primary)', opacity: 0.1 }}>
                        {getBlockIcon(block.type)}
                      </div>
                      <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>{getBlockTypeName(block.type)}</p>
                    </div>
                  )}
                </div>

                {/* Info footer */}
                <div className="p-2 border-t" style={{ borderColor: 'var(--color-border-dark)' }}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1 text-xs" style={{ color: 'var(--color-text-muted)' }}>
                      {getBlockIcon(block.type)}
                      <span>{getBlockTypeName(block.type)}</span>
                    </div>
                    {artifact.agentLabel && (
                      <div className="flex items-center gap-1 text-xs" style={{ color: 'var(--color-primary)' }}>
                        <Bot className="w-3 h-3" />
                        <span className="truncate max-w-[80px]">{artifact.agentLabel}</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Hover overlay */}
                <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedArtifact(artifact);
                    }}
                    className="p-2 rounded-full bg-white/20 hover:bg-white/30 transition-colors"
                    title="View details"
                  >
                    <Maximize2 className="w-5 h-5 text-white" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          // List View
          <div className="space-y-3">
            {filteredBlocks.map(({ artifact, block, index }) => (
              <div
                key={`${artifact.id}-${index}`}
                className="flex items-center gap-4 p-3 rounded-lg border cursor-pointer transition-colors hover:bg-white/5"
                style={{
                  backgroundColor: 'var(--color-panel-dark)',
                  borderColor: 'var(--color-border-dark)'
                }}
                onClick={() => setSelectedArtifact(artifact)}
              >
                {/* Thumbnail */}
                <div className="w-16 h-16 flex-shrink-0 rounded overflow-hidden flex items-center justify-center" style={{ backgroundColor: 'var(--color-background-light)' }}>
                  {isImageBlock(block) ? (
                    <img
                      src={`data:${block.mimeType || 'image/png'};base64,${block.data}`}
                      alt={block.alt_text || "Generated image"}
                      className="max-w-full max-h-full object-contain"
                    />
                  ) : (
                    getBlockIcon(block.type)
                  )}
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium" style={{ color: 'var(--color-text-primary)' }}>
                      {getBlockTypeName(block.type)}
                    </span>
                    <span className="text-xs px-2 py-0.5 rounded" style={{ backgroundColor: 'var(--color-primary)', color: 'white', opacity: 0.9 }}>
                      Task #{artifact.taskId}
                    </span>
                  </div>
                  {artifact.agentLabel && (
                    <div className="flex items-center gap-1 mt-1 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                      <Bot className="w-3 h-3" />
                      <span>{artifact.agentLabel}</span>
                    </div>
                  )}
                  <div className="flex items-center gap-1 mt-1 text-xs" style={{ color: 'var(--color-text-muted)' }}>
                    <Calendar className="w-3 h-3" />
                    <span>{new Date(artifact.timestamp).toLocaleString()}</span>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedArtifact(artifact);
                    }}
                    className="p-2 rounded hover:bg-white/10 transition-colors"
                    style={{ color: 'var(--color-text-muted)' }}
                    title="View details"
                  >
                    <Maximize2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Detail Modal */}
      {selectedArtifact && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" onClick={() => setSelectedArtifact(null)}>
          <div
            className="relative max-w-4xl w-full max-h-[90vh] rounded-lg overflow-hidden flex flex-col"
            style={{ backgroundColor: 'var(--color-background-light)' }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="flex items-center justify-between p-4 border-b" style={{ borderColor: 'var(--color-border-dark)' }}>
              <div>
                <h3 className="font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                  Artifact from Task #{selectedArtifact.taskId}
                </h3>
                {selectedArtifact.agentLabel && (
                  <p className="text-sm mt-0.5" style={{ color: 'var(--color-text-muted)' }}>
                    Generated by {selectedArtifact.agentLabel}
                  </p>
                )}
              </div>
              <button
                onClick={() => setSelectedArtifact(null)}
                className="p-2 rounded hover:bg-white/10 transition-colors"
                style={{ color: 'var(--color-text-muted)' }}
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Content */}
            <div className="flex-1 overflow-auto p-4">
              <ContentBlockRenderer blocks={selectedArtifact.blocks} enableFullscreen={true} />
            </div>
          </div>
        </div>
      )}

      {/* Fullscreen Image Modal */}
      {fullscreenImage && (
        <div
          className="fixed inset-0 z-[60] flex items-center justify-center bg-black/90 p-4"
          onClick={() => setFullscreenImage(null)}
        >
          <button
            onClick={() => setFullscreenImage(null)}
            className="absolute top-4 right-4 p-2 bg-white/10 hover:bg-white/20 rounded-full text-white transition-colors"
          >
            <X className="w-6 h-6" />
          </button>
          <img
            src={fullscreenImage}
            alt="Fullscreen view"
            className="max-w-full max-h-full object-contain rounded-lg"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </div>
  );
}
