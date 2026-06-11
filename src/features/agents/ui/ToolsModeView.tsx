/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useEffect } from 'react';
import { Plus } from 'lucide-react';
import apiClient from '../../../lib/api-client';
import type { CustomTool } from './agentLoadoutTypes';

export interface ToolTemplateSummary {
  template_id: string;
  name: string;
  description: string;
  category: string;
  tool_type: string;
  icon: string;
  priority: number;
  is_featured: boolean;
  example_use_cases?: string[];
}

interface Props {
  tools: CustomTool[];
  onCreateCustomTool: () => void;
  onSelectToolPreset: (template: ToolTemplateSummary) => void;
  onSelectExistingTool: (tool: CustomTool) => void;
}

const cardClass =
  'flex items-start gap-3 p-4 rounded-[4px] border-2 border-border-dark bg-white text-left ' +
  'shadow-[3px_3px_0_var(--color-border-dark)] transition-all ' +
  'hover:translate-x-[1px] hover:translate-y-[1px] hover:shadow-[2px_2px_0_var(--color-border-dark)]';

const badgeStyle = {
  backgroundColor: 'color-mix(in srgb, var(--color-primary) 12%, transparent)',
  color: 'var(--color-primary)',
} as const;

export default function ToolsModeView({
  tools,
  onCreateCustomTool,
  onSelectToolPreset,
  onSelectExistingTool,
}: Props) {
  const [templates, setTemplates] = useState<ToolTemplateSummary[]>([]);
  const [loadingTemplates, setLoadingTemplates] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const fetchTemplates = async () => {
      try {
        const response = await apiClient.listToolTemplates();
        const data = (response.data || []) as ToolTemplateSummary[];
        if (!cancelled) setTemplates(data);
      } catch (e) {
        console.error('Failed to load tool templates', e);
      } finally {
        if (!cancelled) setLoadingTemplates(false);
      }
    };
    fetchTemplates();
    return () => {
      cancelled = true;
    };
  }, []);

  const templatesByCategory = templates.reduce<Record<string, ToolTemplateSummary[]>>((acc, t) => {
    const cat = t.category || 'Other';
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(t);
    return acc;
  }, {});

  return (
    <div className="flex-1 overflow-y-auto px-6 py-6">
      {/* Page header */}
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold" style={{ color: 'var(--color-text-primary)' }}>
            Tools
          </h2>
          <p className="text-sm mt-1" style={{ color: 'var(--color-text-muted)' }}>
            Build custom tools or start from a template. Native tools (file read, web search, etc.)
            are always available to agents and don't need to be configured here.
          </p>
        </div>
        <button
          onClick={onCreateCustomTool}
          className="flex-shrink-0 inline-flex items-center gap-2 h-9 px-4 rounded-[4px] border-2 border-border-dark
            bg-primary text-white font-mono text-xs font-semibold uppercase tracking-wide
            shadow-[3px_3px_0_var(--color-border-dark)] transition-all
            hover:translate-x-[1px] hover:translate-y-[1px] hover:shadow-[2px_2px_0_var(--color-border-dark)]"
        >
          <Plus size={14} />
          Create Custom Tool
        </button>
      </div>

      {/* Existing custom tools */}
      <section className="mb-8">
        <div className="flex items-center justify-between mb-3">
          <h3
            className="text-xs font-mono font-semibold uppercase tracking-wider"
            style={{ color: 'var(--color-text-primary)' }}
          >
            Your Tools
          </h3>
          <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
            {tools.length} {tools.length === 1 ? 'tool' : 'tools'}
          </span>
        </div>
        {tools.length === 0 ? (
          <div
            className="p-8 text-center rounded-[4px] border-2 border-border-dark bg-white shadow-[3px_3px_0_var(--color-border-dark)]"
            style={{ color: 'var(--color-text-muted)' }}
          >
            <span className="material-symbols-outlined text-4xl mb-2 block" style={{ color: 'var(--color-text-muted)' }}>
              extension
            </span>
            <p className="text-sm font-semibold">No custom tools yet.</p>
            <p className="text-xs mt-1">Pick a template below or create one from scratch.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {tools.map((tool) => (
              <button
                key={tool.tool_id}
                onClick={() => onSelectExistingTool(tool)}
                className={cardClass}
              >
                <div
                  className="flex-shrink-0 w-10 h-10 rounded-[4px] border-2 border-border-dark flex items-center justify-center"
                  style={badgeStyle}
                >
                  <span className="material-symbols-outlined text-[20px]">extension</span>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-semibold truncate" style={{ color: 'var(--color-text-primary)' }}>
                    {tool.name}
                  </div>
                  {tool.description && (
                    <div className="text-xs mt-0.5 line-clamp-2" style={{ color: 'var(--color-text-muted)' }}>
                      {tool.description}
                    </div>
                  )}
                </div>
              </button>
            ))}
          </div>
        )}
      </section>

      {/* Tool templates */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h3
            className="text-xs font-mono font-semibold uppercase tracking-wider"
            style={{ color: 'var(--color-text-primary)' }}
          >
            Templates
          </h3>
          <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
            {templates.length} available
          </span>
        </div>
        {loadingTemplates ? (
          <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
            Loading...
          </p>
        ) : Object.keys(templatesByCategory).length === 0 ? (
          <div
            className="p-8 text-center rounded-[4px] border-2 border-border-dark bg-white shadow-[3px_3px_0_var(--color-border-dark)]"
            style={{ color: 'var(--color-text-muted)' }}
          >
            <p className="text-sm">No templates available.</p>
          </div>
        ) : (
          Object.entries(templatesByCategory).map(([category, categoryTemplates]) => (
            <div key={category} className="mb-5">
              <div
                className="text-xs uppercase tracking-wider mb-2 font-mono font-medium"
                style={{ color: 'var(--color-text-muted)' }}
              >
                {category}
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {categoryTemplates.map((t) => (
                  <button
                    key={t.template_id}
                    onClick={() => onSelectToolPreset(t)}
                    className={cardClass}
                  >
                    <div
                      className="flex-shrink-0 w-10 h-10 rounded-[4px] border-2 border-border-dark flex items-center justify-center"
                      style={badgeStyle}
                    >
                      <span className="material-symbols-outlined text-[20px]">{t.icon || 'extension'}</span>
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <div className="text-sm font-semibold truncate" style={{ color: 'var(--color-text-primary)' }}>
                          {t.name}
                        </div>
                        {t.is_featured && (
                          <span
                            className="text-[10px] px-1.5 py-0.5 rounded-[4px] border border-border-dark font-mono font-semibold uppercase tracking-wide"
                            style={badgeStyle}
                          >
                            Featured
                          </span>
                        )}
                      </div>
                      {t.description && (
                        <div className="text-xs mt-0.5 line-clamp-2" style={{ color: 'var(--color-text-muted)' }}>
                          {t.description}
                        </div>
                      )}
                    </div>
                  </button>
                ))}
              </div>
            </div>
          ))
        )}
      </section>
    </div>
  );
}
