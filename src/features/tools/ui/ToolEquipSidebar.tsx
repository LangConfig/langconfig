/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useEffect } from 'react';
import { X, Search, Plus } from 'lucide-react';
import apiClient from '../../../lib/api-client';

interface Tool {
  tool_id: string;
  name: string;
  description: string;
  tool_type: string;
  category?: string;
  tags: string[];
  is_template_based: boolean;
}

interface ToolEquipSidebarProps {
  slotType: 'primary' | 'secondary';
  onEquip: (toolId: string) => void;
  onClose: () => void;
}

const ToolEquipSidebar = ({ slotType, onEquip, onClose }: ToolEquipSidebarProps) => {
  const [tools, setTools] = useState<Tool[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');

  // Load available tools
  useEffect(() => {
    const abortController = new AbortController();

    loadTools(abortController.signal);

    return () => {
      abortController.abort();
    };
  }, []);

  const loadTools = async (signal?: AbortSignal) => {
    setLoading(true);
    try {
      const response = await apiClient.listCustomTools({ signal });
      setTools(response.data || []);
    } catch (error) {
      // Ignore abort errors
      if (error instanceof Error && (error.name === 'AbortError' || error.name === 'CanceledError')) {
        return;
      }
      console.error('Failed to load tools:', error);
    } finally {
      setLoading(false);
    }
  };

  // Filter tools based on slot type
  const getToolsForSlot = () => {
    // Define which tool types go in which slots
    const primaryToolTypes = ['web_search', 'rag', 'custom'];
    const secondaryToolTypes = ['middleware', 'api', 'notification', 'image_video', 'database', 'data_transform'];

    const allowedTypes = slotType === 'primary' ? primaryToolTypes : secondaryToolTypes;

    return tools.filter(tool => {
      const matchesType = allowedTypes.includes(tool.tool_type);
      const matchesSearch =
        tool.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        tool.description?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        tool.tags.some(tag => tag.toLowerCase().includes(searchQuery.toLowerCase()));

      return matchesType && matchesSearch;
    });
  };

  const filteredTools = getToolsForSlot();

  // Get icon for tool type
  const getToolIcon = (toolType: string) => {
    const icons: Record<string, string> = {
      web_search: 'search',
      rag: 'database',
      custom: 'extension',
      middleware: 'settings_ethernet',
      api: 'api',
      notification: 'notifications',
      image_video: 'image',
      database: 'storage',
      data_transform: 'transform',
    };
    return icons[toolType] || 'build';
  };

  const slotColor = slotType === 'primary' ? '#3b82f6' : '#10b981';

  return (
    <div className="fixed right-0 top-0 bottom-0 w-[500px] shadow-2xl flex flex-col z-50 animate-slide-in-right" style={{
      backgroundColor: 'var(--color-panel-dark)',
      borderLeft: `1px solid var(--color-border-dark)`
    }}>
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b" style={{ borderBottomColor: 'var(--color-border-dark)' }}>
        <div>
          <h3 className="font-semibold" style={{ color: 'var(--color-text-primary)' }}>
            Equip {slotType === 'primary' ? 'Primary' : 'Secondary'} Tool
          </h3>
          <p className="text-xs mt-0.5" style={{ color: 'var(--color-text-muted)' }}>
            {slotType === 'primary'
              ? 'Main abilities: Web Search, RAG, Custom Tools'
              : 'Support tools: Middleware, APIs, Integrations'}
          </p>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded hover:opacity-70 transition-opacity"
          style={{ color: 'var(--color-text-muted)' }}
        >
          <X size={20} />
        </button>
      </div>

      {/* Search */}
      <div className="p-4 border-b" style={{ borderBottomColor: 'var(--color-border-dark)' }}>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2" size={16} style={{ color: 'var(--color-text-muted)' }} />
          <input
            type="text"
            placeholder="Search tools..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-2 rounded-lg text-sm border focus:outline-none focus:ring-2"
            style={{
              backgroundColor: 'var(--color-input-background)',
              borderColor: 'var(--color-border-dark)',
              color: 'var(--color-text-primary)',
              outlineColor: 'var(--color-primary)'
            }}
          />
        </div>

        {/* Create Tool Button */}
        <button
          className="w-full mt-3 px-4 py-2 text-sm rounded-lg border-2 border-dashed flex items-center justify-center gap-2 transition-colors"
          style={{
            borderColor: 'var(--color-border-dark)',
            color: 'var(--color-text-muted)'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.borderColor = 'var(--color-primary)';
            e.currentTarget.style.backgroundColor = 'var(--color-background-dark)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = 'var(--color-border-dark)';
            e.currentTarget.style.backgroundColor = 'transparent';
          }}
        >
          <Plus size={16} />
          Create New Tool
        </button>
      </div>

      {/* Tool List */}
      <div className="flex-1 overflow-y-auto p-4">
        {loading ? (
          <div className="flex items-center justify-center h-32">
            <div style={{ color: 'var(--color-text-muted)' }}>Loading tools...</div>
          </div>
        ) : filteredTools.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-32 text-center">
            <div className="text-xs mb-2" style={{ color: 'var(--color-text-muted)' }}>
              {searchQuery ? 'No tools found matching your search' : `No ${slotType} tools available`}
            </div>
            <button
              className="text-xs px-3 py-1.5 rounded-lg transition-opacity"
              style={{ backgroundColor: 'var(--color-primary)', color: 'white' }}
              onMouseEnter={(e) => e.currentTarget.style.opacity = '0.9'}
              onMouseLeave={(e) => e.currentTarget.style.opacity = '1'}
            >
              <Plus size={12} className="inline mr-1" />
              Create First Tool
            </button>
          </div>
        ) : (
          <div className="space-y-2">
            {filteredTools.map((tool) => (
              <button
                key={tool.tool_id}
                onClick={() => onEquip(tool.tool_id)}
                className="w-full text-left p-4 rounded-lg border transition-all"
                style={{
                  backgroundColor: 'var(--color-background-dark)',
                  borderColor: 'var(--color-border-dark)',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = slotColor;
                  e.currentTarget.style.backgroundColor = 'var(--color-panel-dark)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = 'var(--color-border-dark)';
                  e.currentTarget.style.backgroundColor = 'var(--color-background-dark)';
                }}
              >
                <div className="flex items-start gap-3">
                  {/* Tool Icon */}
                  <div className="flex-shrink-0">
                    <span className="material-symbols-outlined text-2xl" style={{ color: slotColor }}>
                      {getToolIcon(tool.tool_type)}
                    </span>
                  </div>

                  {/* Tool Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <h4 className="font-medium text-sm" style={{ color: 'var(--color-text-primary)' }}>
                        {tool.name}
                      </h4>
                      {tool.is_template_based && (
                        <span className="text-xs px-1.5 py-0.5 rounded-full bg-purple-500/20 text-purple-500">
                          Template
                        </span>
                      )}
                    </div>
                    <p className="text-xs line-clamp-2 mb-2" style={{ color: 'var(--color-text-muted)' }}>
                      {tool.description}
                    </p>

                    {/* Tags */}
                    {tool.tags.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {tool.tags.slice(0, 3).map((tag, idx) => (
                          <span
                            key={idx}
                            className="text-xs px-2 py-0.5 rounded"
                            style={{
                              backgroundColor: 'var(--color-panel-dark)',
                              color: 'var(--color-text-muted)'
                            }}
                          >
                            {tag}
                          </span>
                        ))}
                        {tool.tags.length > 3 && (
                          <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                            +{tool.tags.length - 3} more
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Footer Info */}
      <div className="p-4 border-t text-xs text-center" style={{ backgroundColor: 'var(--color-background-dark)', borderTopColor: 'var(--color-border-dark)', color: 'var(--color-text-muted)' }}>
        {slotType === 'primary' ? (
          <>
            💡 Primary tools are your main abilities (Web Search, RAG, Custom). No limit on quantity.
          </>
        ) : (
          <>
            🔧 Secondary tools provide support capabilities (APIs, Integrations, Data). No limit on quantity.
          </>
        )}
      </div>
    </div>
  );
};

export default ToolEquipSidebar;
