/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useMemo, useState } from 'react';
import type { Workflow } from '@/types/workflow';

interface TemplatesSectionProps {
  templates: Workflow[];
  /** ID of the template currently being forked (disables its button) */
  forkingTemplateId: number | null;
  onUseTemplate: (template: Workflow) => void;
}

/**
 * Seeded workflow templates rail, shown above the project-grouped library.
 * Horizontally scrollable cards with a category chip filter.
 * Renders nothing when no templates exist.
 */
export default function TemplatesSection({
  templates,
  forkingTemplateId,
  onUseTemplate,
}: TemplatesSectionProps) {
  const [activeCategory, setActiveCategory] = useState<string>('all');

  const categories = useMemo(() => {
    const unique = new Set<string>();
    templates.forEach(t => {
      if (t.template_category) unique.add(t.template_category);
    });
    return Array.from(unique).sort();
  }, [templates]);

  const visibleTemplates = useMemo(() => {
    if (activeCategory === 'all') return templates;
    return templates.filter(t => t.template_category === activeCategory);
  }, [templates, activeCategory]);

  if (templates.length === 0) {
    return null;
  }

  return (
    <section className="mb-4" aria-label="Workflow templates">
      <h3
        className="font-mono text-[0.68rem] font-semibold uppercase tracking-[0.14em] mb-2"
        style={{ color: 'var(--color-text-muted)' }}
      >
        Templates
      </h3>

      {/* Category filter chips */}
      {categories.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-3">
          <button
            type="button"
            onClick={() => setActiveCategory('all')}
            className={`badge-mono cursor-pointer ${activeCategory === 'all' ? 'tone-accent' : 'tone-neutral'}`}
          >
            All
          </button>
          {categories.map(category => (
            <button
              key={category}
              type="button"
              onClick={() => setActiveCategory(category)}
              className={`badge-mono cursor-pointer ${activeCategory === category ? 'tone-accent' : 'tone-neutral'}`}
            >
              {category}
            </button>
          ))}
        </div>
      )}

      {/* Horizontally scrollable template cards */}
      <div className="flex gap-3 overflow-x-auto pb-2">
        {visibleTemplates.map(template => (
          <article
            key={template.id}
            className="surface-card surface-card-interactive w-60 shrink-0 p-3 flex flex-col gap-2"
          >
            <div className="flex items-start gap-2">
              <span
                className="material-symbols-outlined text-xl shrink-0"
                style={{ color: 'var(--color-primary)' }}
                aria-hidden="true"
              >
                {template.template_icon || 'account_tree'}
              </span>
              <h4
                className="text-sm font-bold leading-snug"
                style={{ color: 'var(--color-text-primary)' }}
              >
                {template.name}
              </h4>
            </div>

            {template.description && (
              <p
                className="text-xs leading-snug line-clamp-2"
                style={{ color: 'var(--color-text-muted)' }}
              >
                {template.description}
              </p>
            )}

            {template.template_category && (
              <span className="badge-mono tone-accent self-start">
                {template.template_category}
              </span>
            )}

            {template.template_tags && template.template_tags.length > 0 && (
              <p
                className="font-mono text-[0.65rem] truncate"
                style={{ color: 'var(--color-text-muted)' }}
                title={template.template_tags.join(', ')}
              >
                {template.template_tags.join(', ')}
              </p>
            )}

            <div className="mt-auto pt-1">
              <button
                type="button"
                className="btn-brutal btn-brutal-primary w-full"
                disabled={forkingTemplateId === template.id}
                onClick={() => onUseTemplate(template)}
              >
                {forkingTemplateId === template.id ? 'Forking…' : 'Use Template'}
              </button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
