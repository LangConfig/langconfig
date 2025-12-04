/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useEffect } from 'react';
import { Search } from 'lucide-react';
import apiClient from "../../../lib/api-client";

// Map tool types and template icons to Material Symbols icons
const getToolIcon = (toolType: string, iconHint?: string): string => {
  // Check for specific icon hints first (from template.icon)
  if (iconHint) {
    const specificIconMap: Record<string, string> = {
      'social_twitter': 'chat',  // Twitter/X
      'cms_wordpress': 'article',
    };
    if (specificIconMap[iconHint]) {
      return specificIconMap[iconHint];
    }
  }

  // Fall back to tool type mapping
  const iconMap: Record<string, string> = {
    'notification': 'notifications',
    'cms': 'article',
    'api': 'api',
    'image_video': 'image',
    'database': 'storage',
    'data_transform': 'transform',
  };
  return iconMap[toolType] || 'extension';
};

interface ToolTemplate {
  template_id: string;
  name: string;
  description: string;
  category: string;
  tool_type: string;
  icon: string;
  priority: number;
  is_featured: boolean;
  required_user_fields: string[];
  example_use_cases: string[];
  tags: string[];
}

interface ToolTemplateGalleryProps {
  onSelectTemplate: (template: ToolTemplate) => void;
  onStartFromScratch: () => void;
}

const ToolTemplateGallery = ({ onSelectTemplate, onStartFromScratch }: ToolTemplateGalleryProps) => {
  const [templates, setTemplates] = useState<ToolTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');

  useEffect(() => {
    const abortController = new AbortController();

    loadTemplates(abortController.signal);

    return () => {
      abortController.abort();
    };
  }, []);

  const loadTemplates = async (signal?: AbortSignal) => {
    try {
      const response = await apiClient.listToolTemplates();
      setTemplates(response.data);
    } catch (error) {
      // Ignore abort errors
      if (error instanceof Error && error.name === 'AbortError') {
        return;
      }
      console.error('Failed to load tool templates:', error);
    } finally {
      setLoading(false);
    }
  };

  // Filter templates
  const filteredTemplates = templates.filter(template => {
    const matchesSearch = template.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      template.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      template.tags.some(tag => tag.toLowerCase().includes(searchQuery.toLowerCase()));

    const matchesCategory = selectedCategory === 'all' || template.category === selectedCategory;

    return matchesSearch && matchesCategory;
  });

  // Get unique categories
  const categories = ['all', ...new Set(templates.map(t => t.category))];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div style={{ color: 'var(--color-text-muted)' }}>Loading templates...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold" style={{ color: 'var(--color-text-primary)' }}>Choose a Template</h2>
          <p className="text-sm mt-1" style={{ color: 'var(--color-text-muted)' }}>
            Start with a pre-configured template or build from scratch
          </p>
        </div>
      </div>

      {/* Search and Filter Bar */}
      <div className="flex gap-4">
        {/* Search */}
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4" style={{ color: 'var(--color-text-muted)' }} />
          <input
            type="text"
            placeholder="Search templates..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 rounded-lg focus:ring-2"
            style={{
              backgroundColor: 'var(--color-input-background)',
              color: 'var(--color-text-primary)',
              border: '1px solid var(--color-border-dark)',
              outlineColor: 'var(--color-primary)'
            }}
          />
        </div>

        {/* Category Filter */}
        <select
          value={selectedCategory}
          onChange={(e) => setSelectedCategory(e.target.value)}
          className="px-4 py-2 rounded-lg focus:ring-2"
          style={{
            backgroundColor: 'var(--color-input-background)',
            color: 'var(--color-text-primary)',
            border: '1px solid var(--color-border-dark)',
            outlineColor: 'var(--color-primary)'
          }}
        >
          <option value="all">All Categories</option>
          {categories.slice(1).map(cat => (
            <option key={cat} value={cat}>
              {cat.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')}
            </option>
          ))}
        </select>
      </div>

      {/* Start from Scratch Button */}
      <button
        onClick={onStartFromScratch}
        className="w-full p-4 border-2 border-dashed rounded-lg transition-colors text-left group"
        style={{
          borderColor: 'var(--color-border-dark)',
          backgroundColor: 'var(--color-panel-dark)'
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.borderColor = 'var(--color-primary)';
          e.currentTarget.style.backgroundColor = 'var(--color-background-dark)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.borderColor = 'var(--color-border-dark)';
          e.currentTarget.style.backgroundColor = 'var(--color-panel-dark)';
        }}
      >
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-lg flex items-center justify-center transition-colors" style={{ backgroundColor: 'var(--color-input-background)' }}>
            <span className="material-symbols-outlined text-xl" style={{ color: 'var(--color-primary)' }}>add_circle</span>
          </div>
          <div>
            <div className="font-semibold" style={{ color: 'var(--color-text-primary)' }}>Start from Scratch</div>
            <div className="text-sm" style={{ color: 'var(--color-text-muted)' }}>Build a custom tool with advanced mode (full control)</div>
          </div>
        </div>
      </button>

      {/* Template Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredTemplates.map((template) => (
          <button
            key={template.template_id}
            onClick={() => onSelectTemplate(template)}
            className="p-4 border-2 rounded-lg hover:border-primary hover:shadow-lg transition-all duration-200 text-left"
            style={{
              backgroundColor: 'var(--color-panel-dark)',
              borderColor: 'var(--color-border-dark)'
            }}
          >
            {/* Icon and Title */}
            <div className="flex flex-col items-center text-center mb-4">
              <span className="material-symbols-outlined text-3xl mb-2" style={{ color: 'var(--color-primary)' }}>
                {getToolIcon(template.tool_type, template.icon)}
              </span>
              <h3 className="text-base font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                {template.name}
              </h3>
            </div>

            {/* Description */}
            <p className="text-sm leading-relaxed mb-4" style={{ color: 'var(--color-text-muted)' }}>
              {template.description}
            </p>

            {/* Tags */}
            {template.tags.length > 0 && (
              <div className="flex flex-wrap justify-center gap-2 pt-3 border-t" style={{ borderColor: 'var(--color-border-dark)' }}>
                {template.tags.slice(0, 3).map(tag => (
                  <span
                    key={tag}
                    className="px-2 py-1 rounded text-xs font-medium"
                    style={{
                      backgroundColor: 'var(--color-input-background)',
                      color: 'var(--color-text-muted)'
                    }}
                  >
                    {tag}
                  </span>
                ))}
                {template.tags.length > 3 && (
                  <span className="px-2 py-1 rounded text-xs font-medium" style={{
                    backgroundColor: 'var(--color-input-background)',
                    color: 'var(--color-text-muted)'
                  }}>
                    +{template.tags.length - 3}
                  </span>
                )}
              </div>
            )}
          </button>
        ))}
      </div>

      {/* No Results */}
      {filteredTemplates.length === 0 && (
        <div className="text-center py-12">
          <div className="mb-2" style={{ color: 'var(--color-text-muted)' }}>
            <span className="material-symbols-outlined text-4xl">search_off</span>
          </div>
          <p style={{ color: 'var(--color-text-muted)' }}>No templates found matching your search</p>
          <button
            onClick={() => {
              setSearchQuery('');
              setSelectedCategory('all');
            }}
            className="mt-2 text-sm font-medium"
            style={{ color: 'var(--color-primary)' }}
          >
            Clear filters
          </button>
        </div>
      )}
    </div>
  );
};

export default ToolTemplateGallery;
