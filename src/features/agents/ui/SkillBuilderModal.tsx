/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState } from 'react';
import { X, Plus, Tag, Zap, BookOpen, Save, ArrowLeft } from 'lucide-react';
import apiClient from '@/lib/api-client';

interface SkillBuilderModalProps {
  onClose: () => void;
  onSave?: (skill: any) => void;
  existingSkill?: {
    skill_id: string;
    name: string;
    description: string;
    tags: string[];
    triggers: string[];
    instructions: string;
  };
}

const SkillBuilderModal = ({ onClose, onSave, existingSkill }: SkillBuilderModalProps) => {
  const isEditing = !!existingSkill;

  // Form state
  const [name, setName] = useState(existingSkill?.name || '');
  const [description, setDescription] = useState(existingSkill?.description || '');
  const [tags, setTags] = useState<string[]>(existingSkill?.tags || ['custom']);
  const [triggers, setTriggers] = useState<string[]>(existingSkill?.triggers || []);
  const [instructions, setInstructions] = useState(existingSkill?.instructions || '');

  // UI state
  const [newTag, setNewTag] = useState('');
  const [newTrigger, setNewTrigger] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    if (!name.trim()) {
      setError('Name is required');
      return;
    }
    if (!description.trim()) {
      setError('Description is required');
      return;
    }
    if (!instructions.trim()) {
      setError('Instructions are required');
      return;
    }

    setSaving(true);
    setError(null);

    try {
      let result;
      if (isEditing && existingSkill) {
        // Update existing skill
        result = await apiClient.put(`/api/skills/${existingSkill.skill_id}`, {
          name: name.trim(),
          description: description.trim(),
          tags,
          triggers,
          instructions: instructions.trim()
        });
      } else {
        // Create new skill
        result = await apiClient.post('/api/skills', {
          name: name.trim(),
          description: description.trim(),
          tags,
          triggers,
          instructions: instructions.trim()
        });
      }

      if (onSave) {
        onSave(result.data);
      }
      onClose();
    } catch (e: any) {
      console.error('Failed to save skill:', e);
      setError(e.response?.data?.detail || 'Failed to save skill');
    } finally {
      setSaving(false);
    }
  };

  const addTag = () => {
    if (newTag.trim() && !tags.includes(newTag.trim())) {
      setTags([...tags, newTag.trim()]);
      setNewTag('');
    }
  };

  const removeTag = (tag: string) => {
    setTags(tags.filter(t => t !== tag));
  };

  const addTrigger = () => {
    if (newTrigger.trim() && !triggers.includes(newTrigger.trim())) {
      setTriggers([...triggers, newTrigger.trim()]);
      setNewTrigger('');
    }
  };

  const removeTrigger = (trigger: string) => {
    setTriggers(triggers.filter(t => t !== trigger));
  };

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50"
      onClick={onClose}
    >
      <div
        className="bg-gray-50 dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-xl w-full max-w-2xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header - Primary Color with White Text (matches DeepAgentBuilder) */}
        <div className="border-b p-6" style={{
          backgroundColor: 'var(--color-primary)',
          borderBottomColor: 'var(--color-border-dark)'
        }}>
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-3 flex-1">
              <button
                onClick={onClose}
                className="p-2 transition-all text-white/90 hover:text-white hover:bg-white/15 rounded-lg"
                style={{ textShadow: '0 1px 2px rgba(0, 0, 0, 0.15)' }}
                title="Back"
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
              <div className="flex-1">
                <h2 className="text-2xl font-semibold text-white" style={{ textShadow: '0 1px 2px rgba(0, 0, 0, 0.25)' }}>
                  {isEditing ? 'Edit Skill' : 'New Skill'}
                </h2>
                <p className="text-sm mt-1 text-white/90" style={{ textShadow: '0 1px 2px rgba(0, 0, 0, 0.15)' }}>
                  Create reusable expertise modules that inject instructions into agent context
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-2 transition-all text-white/90 hover:text-white hover:bg-white/15 rounded-lg"
              style={{ textShadow: '0 1px 2px rgba(0, 0, 0, 0.15)' }}
              title="Close"
            >
              <X className="w-6 h-6" />
            </button>
          </div>
        </div>

        {/* Scrollable Content */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-2xl mx-auto space-y-5">
            {error && (
              <div className="p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800">
                <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
              </div>
            )}

            {/* Name */}
            <div>
              <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-2 uppercase">
                Skill Name <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., Code Review Expert"
                className="w-full px-3 py-2 bg-white dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg text-sm text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
              />
            </div>

            {/* Description */}
            <div>
              <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-2 uppercase">
                Description <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Brief description of what this skill does"
                className="w-full px-3 py-2 bg-white dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg text-sm text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
              />
            </div>

            {/* Tags */}
            <div>
              <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-2 uppercase">
                <Tag size={12} className="inline mr-1" />
                Tags
              </label>
              <div className="flex flex-wrap gap-2 mb-2">
                {tags.map((tag) => (
                  <span
                    key={tag}
                    className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs"
                    style={{ backgroundColor: 'var(--color-primary)', color: 'white' }}
                  >
                    {tag}
                    <button
                      onClick={() => removeTag(tag)}
                      className="hover:opacity-70"
                    >
                      <X size={12} />
                    </button>
                  </span>
                ))}
              </div>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={newTag}
                  onChange={(e) => setNewTag(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addTag())}
                  placeholder="Add tag..."
                  className="flex-1 px-3 py-1.5 bg-white dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg text-sm text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
                />
                <button
                  onClick={addTag}
                  className="px-3 py-1.5 rounded-lg text-sm font-medium bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
                >
                  <Plus size={14} />
                </button>
              </div>
            </div>

            {/* Triggers */}
            <div>
              <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-2 uppercase">
                <Zap size={12} className="inline mr-1" />
                Auto-Triggers
              </label>
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">
                Keywords or phrases that automatically activate this skill
              </p>
              <div className="flex flex-wrap gap-2 mb-2">
                {triggers.map((trigger) => (
                  <span
                    key={trigger}
                    className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300"
                  >
                    {trigger}
                    <button
                      onClick={() => removeTrigger(trigger)}
                      className="hover:opacity-70"
                    >
                      <X size={12} />
                    </button>
                  </span>
                ))}
              </div>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={newTrigger}
                  onChange={(e) => setNewTrigger(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addTrigger())}
                  placeholder="e.g., review my code"
                  className="flex-1 px-3 py-1.5 bg-white dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg text-sm text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
                />
                <button
                  onClick={addTrigger}
                  className="px-3 py-1.5 rounded-lg text-sm font-medium bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
                >
                  <Plus size={14} />
                </button>
              </div>
            </div>

            {/* Instructions */}
            <div>
              <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-2 uppercase">
                Instructions <span className="text-red-500">*</span>
              </label>
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">
                Detailed instructions that will be injected into the agent's system prompt when this skill is active
              </p>
              <textarea
                value={instructions}
                onChange={(e) => setInstructions(e.target.value)}
                placeholder="## Instructions

Describe the expertise and behavior this skill should provide...

## Guidelines
- Be specific about what the agent should do
- Include examples if helpful
- Define output format expectations"
                rows={12}
                className="w-full px-3 py-2 bg-white dark:bg-background-dark border border-gray-200 dark:border-border-dark rounded-lg text-sm text-gray-900 dark:text-white placeholder-gray-400 font-mono resize-none focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
              />
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-200 dark:border-border-dark bg-white dark:bg-panel-dark">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-sm font-medium bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 disabled:opacity-50 transition-colors"
            style={{ backgroundColor: 'var(--color-primary)', color: 'white' }}
          >
            <Save size={14} />
            {saving ? 'Saving...' : isEditing ? 'Save Changes' : 'Create Skill'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default SkillBuilderModal;
