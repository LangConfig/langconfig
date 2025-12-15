/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useEffect, useMemo, useCallback } from 'react';
import {
  Search,
  RefreshCw,
  X,
  BookOpen,
  Zap,
  Tag,
  Clock,
  TrendingUp,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';
import apiClient from '../../../lib/api-client';
import type { Skill, SkillDetail, SkillsSummary, SkillSourceFilter } from '../types';

interface SkillLibraryProps {
  onSelectSkill?: (skill: Skill) => void;
  selectedSkillIds?: string[];
  multiSelect?: boolean;
}

const SOURCE_LABELS: Record<string, string> = {
  builtin: 'Built-in',
  personal: 'Personal',
  project: 'Project',
};

export default function SkillLibrary({
  onSelectSkill,
  selectedSkillIds = [],
  multiSelect = false,
}: SkillLibraryProps) {
  // State
  const [skills, setSkills] = useState<Skill[]>([]);
  const [summary, setSummary] = useState<SkillsSummary | null>(null);
  const [selectedSkill, setSelectedSkill] = useState<SkillDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [sourceFilter, setSourceFilter] = useState<SkillSourceFilter>('all');
  const [tagFilter, setTagFilter] = useState<string | null>(null);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['builtin', 'personal', 'project']));

  // Fetch skills
  const fetchSkills = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (sourceFilter !== 'all') params.append('source_type', sourceFilter);
      if (tagFilter) params.append('tag', tagFilter);
      if (searchQuery) params.append('search', searchQuery);

      const queryString = params.toString();
      const url = queryString ? `/api/skills?${queryString}` : '/api/skills';

      const response = await apiClient.get(url);
      setSkills(response.data);
    } catch (err: any) {
      setError(err.message || 'Failed to load skills');
      console.error('Error fetching skills:', err);
    } finally {
      setLoading(false);
    }
  }, [sourceFilter, tagFilter, searchQuery]);

  // Fetch summary
  const fetchSummary = useCallback(async () => {
    try {
      const response = await apiClient.get('/api/skills/summary');
      setSummary(response.data);
    } catch (err) {
      console.error('Error fetching skills summary:', err);
    }
  }, []);

  // Fetch skill details
  const fetchSkillDetail = useCallback(async (skillId: string) => {
    try {
      const response = await apiClient.get(`/api/skills/${skillId}`);
      setSelectedSkill(response.data);
    } catch (err) {
      console.error('Error fetching skill details:', err);
    }
  }, []);

  // Initial load
  useEffect(() => {
    fetchSkills();
    fetchSummary();
  }, []);

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      fetchSkills();
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery, sourceFilter, tagFilter]);

  // Reload skills from filesystem
  const handleReload = async () => {
    setLoading(true);
    try {
      await apiClient.post('/api/skills/reload-all');
      await fetchSkills();
      await fetchSummary();
    } catch (err: any) {
      setError(err.message || 'Failed to reload skills');
    } finally {
      setLoading(false);
    }
  };

  // Handle skill selection
  const handleSkillClick = (skill: Skill) => {
    if (onSelectSkill) {
      onSelectSkill(skill);
    }
    fetchSkillDetail(skill.skill_id);
  };

  // Group skills by source
  const skillsBySource = useMemo(() => {
    const grouped: Record<string, Skill[]> = {
      builtin: [],
      personal: [],
      project: [],
    };
    skills.forEach((skill) => {
      if (grouped[skill.source_type]) {
        grouped[skill.source_type].push(skill);
      }
    });
    return grouped;
  }, [skills]);

  // Get available tags from summary
  const availableTags = useMemo(() => {
    if (!summary?.top_tags) return [];
    return Object.entries(summary.top_tags)
      .sort((a, b) => b[1] - a[1])
      .map(([tag]) => tag);
  }, [summary]);

  const toggleSection = (section: string) => {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      if (next.has(section)) {
        next.delete(section);
      } else {
        next.add(section);
      }
      return next;
    });
  };

  const formatLastUsed = (dateStr: string | null) => {
    if (!dateStr) return 'Never';
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  return (
    <div className="flex-1 overflow-y-auto" style={{ backgroundColor: 'var(--color-background-dark)' }}>
      <div className="p-6">
        <div className="max-w-6xl mx-auto">
          {/* Header */}
          <div className="mb-6 pb-4 border-b" style={{ borderBottomColor: 'var(--color-border-dark)' }}>
            <div className="flex items-start gap-4">
              <div
                className="w-16 h-16 rounded-xl flex items-center justify-center flex-shrink-0 shadow-sm"
                style={{ backgroundColor: 'var(--color-background-light)' }}
              >
                <Zap className="w-8 h-8" style={{ color: 'var(--color-primary)' }} />
              </div>
              <div className="flex-1">
                <h1 className="text-2xl font-bold mb-1" style={{ color: 'var(--color-text-primary)' }}>
                  Skills Library
                </h1>
                <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
                  Modular capabilities that agents can automatically invoke based on context
                </p>
                {summary && (
                  <div className="flex items-center gap-4 mt-2">
                    <span className="text-xs px-2.5 py-1 rounded-md font-medium" style={{
                      backgroundColor: 'var(--color-primary)',
                      color: 'white'
                    }}>
                      {summary.total_skills} Skills
                    </span>
                    {Object.entries(summary.by_source).map(([source, count]) => (
                      <span key={source} className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                        {SOURCE_LABELS[source]}: {count}
                      </span>
                    ))}
                  </div>
                )}
              </div>
              <button
                onClick={handleReload}
                disabled={loading}
                className="px-4 py-2 rounded-lg text-sm font-medium border flex items-center gap-2 transition-colors"
                style={{
                  backgroundColor: 'var(--color-panel-dark)',
                  borderColor: 'var(--color-border-dark)',
                  color: 'var(--color-text-primary)',
                }}
              >
                <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                Reload
              </button>
            </div>
          </div>

          {/* Search and Filters */}
          <div className="mb-6 space-y-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4" style={{ color: 'var(--color-text-muted)' }} />
              <input
                type="text"
                placeholder="Search skills..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-10 py-2.5 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                style={{
                  backgroundColor: 'var(--color-input-background)',
                  borderColor: 'var(--color-border-dark)',
                  color: 'var(--color-text-primary)',
                }}
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  className="absolute right-3 top-1/2 transform -translate-y-1/2"
                  style={{ color: 'var(--color-text-muted)' }}
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>

            {/* Tag Filters */}
            {availableTags.length > 0 && (
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs font-medium" style={{ color: 'var(--color-text-muted)' }}>Tags:</span>
                {availableTags.slice(0, 12).map((tag) => (
                  <button
                    key={tag}
                    onClick={() => setTagFilter(tagFilter === tag ? null : tag)}
                    className="px-2.5 py-1 rounded-md text-xs font-medium border transition-colors"
                    style={{
                      backgroundColor: tagFilter === tag ? 'var(--color-primary)' : 'var(--color-panel-dark)',
                      borderColor: tagFilter === tag ? 'var(--color-primary)' : 'var(--color-border-dark)',
                      color: tagFilter === tag ? 'white' : 'var(--color-text-muted)',
                    }}
                  >
                    {tag}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Error */}
          {error && (
            <div className="p-4 rounded-lg mb-6 border" style={{
              backgroundColor: 'rgba(239, 68, 68, 0.1)',
              borderColor: 'rgba(239, 68, 68, 0.3)',
              color: '#ef4444'
            }}>
              {error}
            </div>
          )}

          {/* Skills by Source */}
          <div className="space-y-4">
            {(['builtin', 'personal', 'project'] as const).map((sourceType) => {
              const sourceSkills = skillsBySource[sourceType];
              if (sourceSkills.length === 0 && sourceFilter !== 'all' && sourceFilter !== sourceType) return null;

              const isExpanded = expandedSections.has(sourceType);

              return (
                <div key={sourceType}>
                  {/* Section Header */}
                  <button
                    onClick={() => toggleSection(sourceType)}
                    className="w-full px-3 py-2 rounded-lg flex items-center justify-between mb-2"
                    style={{ backgroundColor: 'var(--color-primary)' }}
                  >
                    <div className="flex items-center gap-2">
                      {isExpanded ? (
                        <ChevronDown className="w-4 h-4 text-white" />
                      ) : (
                        <ChevronRight className="w-4 h-4 text-white" />
                      )}
                      <span className="text-sm font-semibold text-white">
                        {SOURCE_LABELS[sourceType]} Skills
                      </span>
                      <span className="text-xs text-white/70">({sourceSkills.length})</span>
                    </div>
                  </button>

                  {/* Skills Grid */}
                  {isExpanded && (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                      {sourceSkills.length === 0 ? (
                        <div className="col-span-full text-center py-8" style={{ color: 'var(--color-text-muted)' }}>
                          <p className="text-sm">No {SOURCE_LABELS[sourceType].toLowerCase()} skills found</p>
                        </div>
                      ) : (
                        sourceSkills.map((skill) => (
                          <div
                            key={skill.skill_id}
                            onClick={() => handleSkillClick(skill)}
                            className="p-4 rounded-xl border cursor-pointer transition-all hover:shadow-md"
                            style={{
                              backgroundColor: selectedSkill?.skill_id === skill.skill_id
                                ? 'var(--color-node-background-light)'
                                : 'var(--color-panel-dark)',
                              borderColor: selectedSkill?.skill_id === skill.skill_id
                                ? 'var(--color-primary)'
                                : 'var(--color-border-dark)',
                            }}
                          >
                            {/* Card Header */}
                            <div className="flex items-start gap-3 mb-2">
                              <div
                                className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                                style={{ backgroundColor: 'var(--color-background-light)' }}
                              >
                                <Zap className="w-5 h-5" style={{ color: 'var(--color-primary)' }} />
                              </div>
                              <div className="flex-1 min-w-0">
                                <h3 className="text-sm font-semibold truncate" style={{ color: 'var(--color-text-primary)' }}>
                                  {skill.name}
                                </h3>
                                <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                                  v{skill.version}
                                </span>
                              </div>
                            </div>

                            {/* Description */}
                            <p className="text-xs mb-3 line-clamp-2" style={{ color: 'var(--color-text-muted)' }}>
                              {skill.description}
                            </p>

                            {/* Tags */}
                            {skill.tags.length > 0 && (
                              <div className="flex items-center gap-1 flex-wrap mb-3">
                                {skill.tags.slice(0, 3).map((tag) => (
                                  <span
                                    key={tag}
                                    className="text-xs px-2 py-0.5 rounded-full"
                                    style={{
                                      backgroundColor: 'var(--color-background-dark)',
                                      color: 'var(--color-text-muted)',
                                    }}
                                  >
                                    {tag}
                                  </span>
                                ))}
                                {skill.tags.length > 3 && (
                                  <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                                    +{skill.tags.length - 3}
                                  </span>
                                )}
                              </div>
                            )}

                            {/* Stats */}
                            <div className="flex items-center gap-3 text-xs" style={{ color: 'var(--color-text-muted)' }}>
                              <div className="flex items-center gap-1">
                                <TrendingUp className="w-3 h-3" />
                                <span>{skill.usage_count}</span>
                              </div>
                              <div className="flex items-center gap-1">
                                <Clock className="w-3 h-3" />
                                <span>{formatLastUsed(skill.last_used_at)}</span>
                              </div>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Loading */}
          {loading && skills.length === 0 && (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="w-6 h-6 animate-spin" style={{ color: 'var(--color-text-muted)' }} />
              <span className="ml-2" style={{ color: 'var(--color-text-muted)' }}>Loading skills...</span>
            </div>
          )}
        </div>
      </div>

      {/* Skill Detail Panel */}
      {selectedSkill && (
        <div
          className="fixed bottom-0 left-0 right-0 border-t shadow-lg max-h-80 overflow-y-auto"
          style={{
            backgroundColor: 'var(--color-panel-dark)',
            borderTopColor: 'var(--color-border-dark)',
          }}
        >
          <div className="max-w-6xl mx-auto p-4">
            <div className="flex items-start justify-between mb-3">
              <div>
                <h3 className="text-lg font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                  {selectedSkill.name}
                </h3>
                <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
                  {SOURCE_LABELS[selectedSkill.source_type]} • v{selectedSkill.version}
                  {selectedSkill.author && ` • by ${selectedSkill.author}`}
                </p>
              </div>
              <button
                onClick={() => setSelectedSkill(null)}
                className="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-700"
                style={{ color: 'var(--color-text-muted)' }}
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="text-sm mb-4" style={{ color: 'var(--color-text-muted)' }}>
              {selectedSkill.description}
            </p>

            {/* Triggers */}
            {selectedSkill.triggers.length > 0 && (
              <div className="mb-4">
                <h4 className="text-xs font-semibold uppercase mb-2" style={{ color: 'var(--color-text-muted)' }}>
                  Auto-triggers
                </h4>
                <ul className="space-y-1">
                  {selectedSkill.triggers.map((trigger, i) => (
                    <li key={i} className="flex items-center gap-2 text-sm" style={{ color: 'var(--color-text-primary)' }}>
                      <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: 'var(--color-primary)' }} />
                      {trigger}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Instructions Preview */}
            <div>
              <h4 className="text-xs font-semibold uppercase mb-2 flex items-center gap-1" style={{ color: 'var(--color-text-muted)' }}>
                <BookOpen className="w-3 h-3" />
                Instructions
              </h4>
              <div
                className="p-3 rounded-lg max-h-32 overflow-y-auto"
                style={{ backgroundColor: 'var(--color-background-dark)' }}
              >
                <pre className="whitespace-pre-wrap font-mono text-xs" style={{ color: 'var(--color-text-primary)' }}>
                  {selectedSkill.instructions.slice(0, 800)}
                  {selectedSkill.instructions.length > 800 && '...'}
                </pre>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
