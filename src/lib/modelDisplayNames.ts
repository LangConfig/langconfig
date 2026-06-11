/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

// Maps internal model IDs to user-friendly display names
// Updated June 5, 2026
export const MODEL_DISPLAY_NAMES: Record<string, string> = {
  // OpenAI - selectable current models
  'gpt-5.5': 'GPT-5.5',
  'gpt-5.4': 'GPT-5.4',
  'gpt-5.4-mini': 'GPT-5.4 Mini',
  'gpt-5.4-nano': 'GPT-5.4 Nano',

  // Anthropic - selectable current models
  'claude-opus-4-8': 'Claude Opus 4.8',
  'claude-sonnet-4-6': 'Claude Sonnet 4.6',
  'claude-haiku-4-5': 'Claude Haiku 4.5',

  // Legacy display only. These should not be returned by the selectable model API.
  'gpt-5.2': 'GPT-5.2',
  'gpt-5.1': 'GPT-5.1',
  'gpt-4o': 'GPT-4o',
  'gpt-4o-mini': 'GPT-4o Mini',
  'claude-opus-4-5': 'Claude Opus 4.5',
  'claude-sonnet-4-5': 'Claude Sonnet 4.5',
  'claude-sonnet-4-5-20250929': 'Claude Sonnet 4.5',

  // Google - Gemini 3 (Current)
  'gemini-3-pro-preview': 'Gemini 3 Pro',

  // Google - Gemini 2.5
  'gemini-2.0-flash': 'Gemini 2.0 Flash',
  'gemini-2.5-flash': 'Gemini 2.5 Flash',
  'gemini-2.5-flash-lite': 'Gemini 2.5 Flash-Lite',

  // Default
  'none': 'None'
};

/**
 * Converts an internal model ID to a user-friendly display name
 */
export function getModelDisplayName(modelId: string): string {
  return MODEL_DISPLAY_NAMES[modelId] || modelId;
}

/**
 * Gets the internal model ID from a display name (reverse lookup)
 */
export function getModelIdFromDisplayName(displayName: string): string {
  const entry = Object.entries(MODEL_DISPLAY_NAMES).find(
    ([_, name]) => name === displayName
  );
  return entry ? entry[0] : displayName;
}
