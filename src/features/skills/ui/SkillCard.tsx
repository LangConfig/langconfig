/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { Zap, Tag, Clock, TrendingUp } from 'lucide-react';
import type { Skill } from '../types';

interface SkillCardProps {
  skill: Skill;
  isSelected?: boolean;
  onClick?: () => void;
  compact?: boolean;
}

const SOURCE_STYLES = {
  builtin: { label: 'Built-in', color: 'var(--color-primary)' },
  personal: { label: 'Personal', color: '#10b981' },
  project: { label: 'Project', color: '#8b5cf6' },
};

export default function SkillCard({ skill, isSelected, onClick, compact = false }: SkillCardProps) {
  const sourceStyle = SOURCE_STYLES[skill.source_type] || SOURCE_STYLES.builtin;

  const formatLastUsed = (dateStr: string | null) => {
    if (!dateStr) return 'Never used';
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays} days ago`;
    if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
    return date.toLocaleDateString();
  };

  if (compact) {
    return (
      <div
        onClick={onClick}
        className="p-3 rounded-lg border cursor-pointer transition-all"
        style={{
          backgroundColor: isSelected ? 'var(--color-primary)' : 'var(--color-panel-dark)',
          borderColor: isSelected ? 'var(--color-primary)' : 'var(--color-border-dark)',
          opacity: isSelected ? 0.9 : 1,
        }}
      >
        <div className="flex items-center gap-2">
          <Zap className="w-4 h-4 flex-shrink-0" style={{ color: 'var(--color-primary)' }} />
          <span className="text-sm font-medium truncate" style={{ color: 'var(--color-text-primary)' }}>
            {skill.name}
          </span>
          <span
            className="text-xs px-1.5 py-0.5 rounded"
            style={{ backgroundColor: `${sourceStyle.color}20`, color: sourceStyle.color }}
          >
            {sourceStyle.label}
          </span>
        </div>
        <p className="text-xs mt-1 line-clamp-2" style={{ color: 'var(--color-text-muted)' }}>
          {skill.description}
        </p>
      </div>
    );
  }

  return (
    <div
      onClick={onClick}
      className="p-4 rounded-xl border cursor-pointer transition-all hover:shadow-lg"
      style={{
        backgroundColor: isSelected ? 'var(--color-node-background-light)' : 'var(--color-panel-dark)',
        borderColor: isSelected ? 'var(--color-primary)' : 'var(--color-border-dark)',
      }}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="p-2 rounded-lg" style={{ backgroundColor: `var(--color-primary)20` }}>
            <Zap className="w-5 h-5" style={{ color: 'var(--color-primary)' }} />
          </div>
          <div>
            <h3 className="font-semibold" style={{ color: 'var(--color-text-primary)' }}>{skill.name}</h3>
            <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>v{skill.version}</span>
          </div>
        </div>
        <span
          className="text-xs px-2 py-1 rounded-full border"
          style={{
            backgroundColor: `${sourceStyle.color}15`,
            color: sourceStyle.color,
            borderColor: `${sourceStyle.color}30`,
          }}
        >
          {sourceStyle.label}
        </span>
      </div>

      {/* Description */}
      <p className="text-sm mb-3 line-clamp-2" style={{ color: 'var(--color-text-muted)' }}>
        {skill.description}
      </p>

      {/* Tags */}
      {skill.tags.length > 0 && (
        <div className="flex items-center gap-1 flex-wrap mb-3">
          <Tag className="w-3 h-3" style={{ color: 'var(--color-text-muted)' }} />
          {skill.tags.slice(0, 4).map((tag) => (
            <span
              key={tag}
              className="text-xs px-2 py-0.5 rounded-full"
              style={{
                backgroundColor: 'var(--color-node-background)',
                color: 'var(--color-text-muted)',
              }}
            >
              {tag}
            </span>
          ))}
          {skill.tags.length > 4 && (
            <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
              +{skill.tags.length - 4}
            </span>
          )}
        </div>
      )}

      {/* Stats */}
      <div className="flex items-center gap-4 text-xs" style={{ color: 'var(--color-text-muted)' }}>
        <div className="flex items-center gap-1">
          <TrendingUp className="w-3 h-3" />
          <span>{skill.usage_count} uses</span>
        </div>
        <div className="flex items-center gap-1">
          <Clock className="w-3 h-3" />
          <span>{formatLastUsed(skill.last_used_at)}</span>
        </div>
        <div className="flex items-center gap-1">
          <span style={{ color: skill.avg_success_rate >= 0.8 ? '#10b981' : '#f59e0b' }}>
            {Math.round(skill.avg_success_rate * 100)}% success
          </span>
        </div>
      </div>
    </div>
  );
}
