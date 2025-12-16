/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

// Maps internal model IDs to user-friendly display names
// Updated December 16, 2025
export const MODEL_DISPLAY_NAMES: Record<string, string> = {
  // OpenAI - GPT-5 Series (Current)
  'gpt-5.2': 'GPT-5.2',
  'gpt-5.1': 'GPT-5.1',
  'gpt-4o': 'GPT-4o',
  'gpt-4o-mini': 'GPT-4o Mini',

  // Anthropic - Claude 4.5 (Current)
  'claude-opus-4-5': 'Claude Opus 4.5',
  'claude-sonnet-4-5': 'Claude Sonnet 4.5',
  'claude-haiku-4-5': 'Claude Haiku 4.5',

  // Google - Gemini 3 (Current)
  'gemini-3-pro-preview': 'Gemini 3 Pro',

  // Google - Gemini 2.5
  'gemini-2.5-flash': 'Gemini 2.5 Flash',

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
