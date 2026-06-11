/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

// Maps internal model IDs to user-friendly display names.
// Single source of truth for the frontend - updated June 10, 2026.
export const MODEL_DISPLAY_NAMES: Record<string, string> = {
  // OpenAI - selectable current models
  'gpt-5.5': 'GPT-5.5',
  'gpt-5.4': 'GPT-5.4',
  'gpt-5.4-mini': 'GPT-5.4 Mini',
  'gpt-5.4-nano': 'GPT-5.4 Nano',

  // Anthropic - selectable current models
  'claude-fable-5': 'Claude Fable 5',
  'claude-opus-4-8': 'Claude Opus 4.8',
  'claude-sonnet-4-6': 'Claude Sonnet 4.6',
  'claude-haiku-4-5': 'Claude Haiku 4.5',

  // Google - selectable current models
  'gemini-3.1-pro-preview': 'Gemini 3.1 Pro',
  'gemini-2.5-flash': 'Gemini 2.5 Flash',
  'gemini-2.5-flash-lite': 'Gemini 2.5 Flash-Lite',

  // Legacy display only - kept so historical executions still render a name.
  // These should not be returned by the selectable model API.
  'gpt-5.2': 'GPT-5.2',
  'gpt-5.1': 'GPT-5.1',
  'gpt-5': 'GPT-5',
  'gpt-5-pro': 'GPT-5 Pro',
  'gpt-4o': 'GPT-4o',
  'gpt-4o-mini': 'GPT-4o Mini',
  'o3': 'o3',
  'o3-mini': 'o3 Mini',
  'o4-mini': 'o4 Mini',
  'claude-opus-4-5': 'Claude Opus 4.5',
  'claude-sonnet-4-5': 'Claude Sonnet 4.5',
  'claude-sonnet-4-5-20250929': 'Claude Sonnet 4.5',
  'claude-3-5-sonnet-20241022': 'Claude 3.5 Sonnet',
  'claude-3-5-haiku-20241022': 'Claude 3.5 Haiku',
  'claude-3-opus-20240229': 'Claude 3 Opus',
  'gemini-3-pro-preview': 'Gemini 3 Pro',
  'gemini-2.5-pro': 'Gemini 2.5 Pro',
  'gemini-2.0-flash': 'Gemini 2.0 Flash',
  'gemini-2.0-flash-exp': 'Gemini 2.0 Flash (Experimental)',

  // Default
  'none': 'None'
};

/**
 * Converts an internal model ID to a user-friendly display name.
 * Tolerates empty/null IDs and strips the `local-` prefix for local models.
 */
export function getModelDisplayName(modelId: string | null | undefined): string {
  if (!modelId) return '';
  if (MODEL_DISPLAY_NAMES[modelId]) return MODEL_DISPLAY_NAMES[modelId];
  if (modelId.startsWith('local-')) return modelId.slice('local-'.length);
  return modelId;
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

/**
 * Infers the provider from a model ID prefix.
 */
export function getModelProvider(
  modelId: string | null | undefined
): 'OpenAI' | 'Anthropic' | 'Google' | 'Local' | 'Unknown' {
  if (!modelId) return 'Unknown';
  if (modelId.startsWith('local-')) return 'Local';
  if (/^(gpt|o\d)/.test(modelId)) return 'OpenAI';
  if (modelId.startsWith('claude')) return 'Anthropic';
  if (modelId.startsWith('gemini')) return 'Google';
  return 'Unknown';
}
